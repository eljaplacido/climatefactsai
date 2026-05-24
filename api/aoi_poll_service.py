"""AOI poll service — Phase 3C (2026-05-23).

The runtime half of MH5: takes the subscriptions persisted by
`aoi_service.AOIService.create` and actually fires email alerts when
the underlying indicator values cross their thresholds.

Architecture:
  1. `poll_all_active()` is the orchestrator — usually invoked hourly
     by Celery beat. Returns a `PollSummary` so the scheduler can log
     totals and so endpoint-triggered runs (admin "fire now") can
     report back what fired.
  2. Subscriptions are batched by `variable` so the indicator lookup
     is done once per variable (not once per subscription). For 5,000
     subscriptions across 5 variables that's 5 DB queries instead of
     5,000 — meaningful when scaled to the Basic tier ceiling.
  3. `check_threshold_crossed()` from aoi_service is the pure decision
     primitive — see test_aoi_service.py for the 24-case rule matrix.
  4. After dispatch the subscription row is updated with
     `last_fired_at`, `last_observed_value`, `fire_count`. The crossing
     debounce in `check_threshold_crossed` reads `last_observed_value`
     so the next poll won't re-fire on the same crossing.
  5. Indicator lookup is read from `country_indicators` (migration 020).
     The `temperature_anomaly_c` variable is intentionally NOT polled in
     v1 — it's a live Open-Meteo derived value that needs a different
     fetch path; deferred to Phase 4.

Failure semantics: ANY subscription's poll/dispatch failure is logged
but never crashes the whole loop. One bad row doesn't stop other alerts
from firing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from shared.database import get_postgres
from shared.logger import setup_logging

from api.aoi_service import check_threshold_crossed
from api.email_service import send_email


logger = setup_logging("aoi_poll_service")


# Variables we know how to poll in v1. Maps the AOI subscription `variable`
# slug → the `country_indicators.indicator_id` slug. Extending v1 = add a
# row here AND extend the indicator adapter coverage. Variables NOT in
# this map silently skip (logged) — the subscription stays active.
SUPPORTED_VARIABLES: dict[str, str] = {
    "renewable_share_pct": "renewable_share_pct",
    "co2_emissions_per_capita": "co2_emissions_per_capita",
    "climate_risk_score": "climate_risk_score",
    # "temperature_anomaly_c" — deferred to Phase 4 (needs live Open-Meteo fetch)
}


@dataclass
class FireEvent:
    """One alert dispatch — what fired, when, with what value."""
    subscription_id: str
    user_id: str
    country_code: str
    variable: str
    comparison: str
    threshold: float
    observed_value: float
    last_observed_value: Optional[float]
    label: Optional[str]
    delivery_target: str
    fired_at: datetime
    email_sent: bool
    email_error: Optional[str] = None


@dataclass
class PollSummary:
    """Aggregate result of a single poll-loop run."""
    total_subscriptions_checked: int = 0
    variables_polled: int = 0
    subscriptions_skipped_unknown_variable: int = 0
    indicator_lookup_failures: int = 0
    fires: list[FireEvent] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "total_subscriptions_checked": self.total_subscriptions_checked,
            "variables_polled": self.variables_polled,
            "subscriptions_skipped_unknown_variable": self.subscriptions_skipped_unknown_variable,
            "indicator_lookup_failures": self.indicator_lookup_failures,
            "fire_count": len(self.fires),
            "fires": [
                {
                    "subscription_id": f.subscription_id,
                    "country_code": f.country_code,
                    "variable": f.variable,
                    "observed_value": f.observed_value,
                    "threshold": f.threshold,
                    "email_sent": f.email_sent,
                    "email_error": f.email_error,
                }
                for f in self.fires
            ],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def _load_active_subscriptions(db) -> list[dict]:
    """Pull every active subscription with the user's email joined in
    (so we don't need a per-subscription user lookup downstream)."""
    try:
        rows = db.execute_query(
            """
            SELECT s.subscription_id, s.user_id, s.country_code, s.variable,
                   s.comparison, s.threshold, s.delivery_channel,
                   s.delivery_target, s.last_observed_value, s.last_fired_at,
                   s.fire_count, s.label,
                   u.email AS user_email
            FROM aoi_subscriptions s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.active = TRUE
            ORDER BY s.variable, s.country_code
            """,
            {},
        )
        return [dict(r) for r in (rows or [])]
    except Exception as exc:
        logger.error(f"Failed to load active AOI subscriptions: {exc}")
        return []


def _fetch_latest_indicator_values(
    db,
    indicator_id: str,
    country_codes: list[str],
) -> dict[str, float]:
    """For one variable + a list of countries, batch-fetch the latest
    observed value per country. Returns a {country_code: value} dict.

    The country_indicators table is append-only with one row per
    (country_code, indicator_id, year). We take the most recent year per
    country.
    """
    if not country_codes:
        return {}
    try:
        rows = db.execute_query(
            """
            SELECT DISTINCT ON (country_code) country_code, value
            FROM country_indicators
            WHERE indicator_id = :indicator_id
              AND country_code = ANY(:codes)
            ORDER BY country_code, year DESC
            """,
            {"indicator_id": indicator_id, "codes": country_codes},
        )
        return {
            str(r["country_code"]).upper(): float(r["value"])
            for r in (rows or [])
            if r.get("value") is not None
        }
    except Exception as exc:
        logger.warning(
            f"Indicator lookup failed for {indicator_id}: {exc}"
        )
        return {}


def _format_alert_email_subject(
    sub: dict, observed: float
) -> str:
    label = sub.get("label") or f"{sub['country_code']} {sub['variable']}"
    return f"[Climatefacts.ai alert] {label} (observed: {observed})"


def _format_alert_email_html(sub: dict, observed: float) -> str:
    """Plain HTML for the alert body. Includes:
      - what crossed
      - what the threshold was
      - the observed value
      - a link to the country passport for context
      - an unsubscribe / manage-alerts link
    """
    frontend = "https://climatefacts.ai"  # TODO: read from FRONTEND_URL env at call site
    label = sub.get("label") or f"{sub['country_code']} {sub['variable']}"
    comparison_word = {
        "gt": "exceeded",
        "gte": "reached or exceeded",
        "lt": "fell below",
        "lte": "fell to or below",
        "eq": "equalled",
    }.get(sub["comparison"], "crossed")
    return f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 580px; margin: 0 auto; padding: 20px; color: #1f2937;">
  <h2 style="color: #b45309;">Climatefacts.ai alert: {label}</h2>
  <p>The threshold you set for <strong>{sub['country_code']}</strong> has been crossed.</p>
  <table style="border-collapse: collapse; margin: 16px 0;">
    <tr><td style="padding: 4px 12px; color: #6b7280;">Variable</td><td><strong>{sub['variable']}</strong></td></tr>
    <tr><td style="padding: 4px 12px; color: #6b7280;">Rule</td><td>{comparison_word} {sub['threshold']}</td></tr>
    <tr><td style="padding: 4px 12px; color: #6b7280;">Observed value</td><td><strong style="color: #b45309;">{observed}</strong></td></tr>
    <tr><td style="padding: 4px 12px; color: #6b7280;">Previous value</td><td>{sub.get('last_observed_value', '—')}</td></tr>
  </table>
  <p>
    <a href="{frontend}/country/{sub['country_code']}" style="background: #0d9488; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px;">
      Open {sub['country_code']} on Climatefacts.ai
    </a>
  </p>
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
  <p style="font-size: 12px; color: #6b7280;">
    You're receiving this because you subscribed to alerts on Climatefacts.ai.
    <a href="{frontend}/dashboard/aoi" style="color: #0d9488;">Manage your alerts</a>.
  </p>
</body>
</html>
"""


def _update_subscription_after_fire(
    db,
    subscription_id: str,
    observed: float,
) -> None:
    """Update last_fired_at + last_observed_value + bump fire_count."""
    try:
        db.execute_update(
            """
            UPDATE aoi_subscriptions
            SET last_fired_at = NOW(),
                last_observed_value = :observed,
                fire_count = fire_count + 1,
                updated_at = NOW()
            WHERE subscription_id = :sid
            """,
            {"sid": subscription_id, "observed": observed},
        )
    except Exception as exc:
        logger.error(f"Failed to update fired-state for {subscription_id}: {exc}")


def _update_subscription_observation(
    db,
    subscription_id: str,
    observed: float,
) -> None:
    """Update only last_observed_value (not last_fired_at) — call on
    every poll for subscriptions that DIDN'T fire, so the next crossing
    can be detected via debounce."""
    try:
        db.execute_update(
            """
            UPDATE aoi_subscriptions
            SET last_observed_value = :observed,
                updated_at = NOW()
            WHERE subscription_id = :sid
            """,
            {"sid": subscription_id, "observed": observed},
        )
    except Exception as exc:
        logger.warning(
            f"Failed to update observation for {subscription_id}: {exc}"
        )


def poll_all_active(db=None) -> PollSummary:
    """Main orchestrator. Polls every active subscription, fires alerts
    when thresholds cross, returns a `PollSummary` for the caller to log
    or surface to the scheduler-trigger endpoint.

    Args:
        db: optional pre-resolved DB client (for tests). Production
            callers pass None and we resolve via `get_postgres()`.
    """
    summary = PollSummary(started_at=datetime.now(timezone.utc))
    db = db or get_postgres()
    subscriptions = _load_active_subscriptions(db)
    summary.total_subscriptions_checked = len(subscriptions)
    if not subscriptions:
        summary.finished_at = datetime.now(timezone.utc)
        return summary

    # Group by variable so we fetch indicator values in batches
    by_variable: dict[str, list[dict]] = {}
    for sub in subscriptions:
        var = sub["variable"]
        if var not in SUPPORTED_VARIABLES:
            summary.subscriptions_skipped_unknown_variable += 1
            logger.debug(
                f"Skipping subscription {sub['subscription_id']}: "
                f"unsupported variable {var!r}"
            )
            continue
        by_variable.setdefault(var, []).append(sub)

    summary.variables_polled = len(by_variable)

    for var, subs in by_variable.items():
        indicator_id = SUPPORTED_VARIABLES[var]
        country_codes = sorted({s["country_code"].upper() for s in subs})
        observations = _fetch_latest_indicator_values(db, indicator_id, country_codes)
        if not observations:
            summary.indicator_lookup_failures += 1
            logger.warning(
                f"No indicator values returned for {var} across {len(country_codes)} countries"
            )
            continue

        for sub in subs:
            cc = sub["country_code"].upper()
            observed = observations.get(cc)
            if observed is None:
                continue  # no data for this country this poll; skip

            crossed = check_threshold_crossed(
                observed=observed,
                comparison=sub["comparison"],
                threshold=float(sub["threshold"]),
                last_observed=sub.get("last_observed_value"),
            )

            if crossed:
                target = sub.get("delivery_target") or sub.get("user_email")
                fire = FireEvent(
                    subscription_id=str(sub["subscription_id"]),
                    user_id=str(sub["user_id"]),
                    country_code=cc,
                    variable=var,
                    comparison=sub["comparison"],
                    threshold=float(sub["threshold"]),
                    observed_value=observed,
                    last_observed_value=sub.get("last_observed_value"),
                    label=sub.get("label"),
                    delivery_target=target or "",
                    fired_at=datetime.now(timezone.utc),
                    email_sent=False,
                )
                if not target:
                    fire.email_error = "no_delivery_target"
                    logger.warning(
                        f"AOI subscription {sub['subscription_id']} crossed but "
                        "has no delivery_target and no user.email — skipping send."
                    )
                else:
                    try:
                        send_email(
                            to_email=target,
                            subject=_format_alert_email_subject(sub, observed),
                            html_body=_format_alert_email_html(sub, observed),
                        )
                        fire.email_sent = True
                    except Exception as exc:
                        fire.email_error = str(exc)[:200]
                        logger.error(
                            f"AOI alert email failed for {sub['subscription_id']}: {exc}"
                        )
                summary.fires.append(fire)
                # Persist the fire — even when email failed, we record the
                # crossing so the next poll's debounce works correctly.
                # Otherwise we'd email-bomb on the next poll when email
                # service recovers.
                _update_subscription_after_fire(db, str(sub["subscription_id"]), observed)
            else:
                # No fire — still record the observation so the debounce
                # primitive sees an up-to-date `last_observed_value` next
                # round. Without this update, a value that crosses, settles,
                # then re-crosses wouldn't fire the second time.
                _update_subscription_observation(db, str(sub["subscription_id"]), observed)

    summary.finished_at = datetime.now(timezone.utc)
    logger.info(
        "AOI poll loop finished",
        total=summary.total_subscriptions_checked,
        fired=len(summary.fires),
        variables=summary.variables_polled,
    )
    return summary
