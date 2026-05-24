"""Unit tests for the AOI poll loop — Phase 3C (2026-05-23).

Pins the orchestration: that subscriptions get checked, crossings fire
emails, observations get persisted, and ANY single failure (bad email,
missing indicator) doesn't crash the whole loop.

Strategy: mock the DB + the email service, hand-feed subscription rows
and indicator values, then assert on:
  - PollSummary aggregates (totals, fire count, skipped counts)
  - Email dispatch invocations
  - DB update calls (fire vs observation-only path)
  - Failure isolation (one bad row, others still fire)

The pure threshold-decision primitive is exhaustively covered in
test_aoi_service.py; this file tests the orchestration layer above it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.aoi_poll_service import (
    SUPPORTED_VARIABLES,
    PollSummary,
    poll_all_active,
)


def _sub_row(
    *,
    subscription_id: str = "sub-1",
    user_id: str = "u-1",
    country_code: str = "DE",
    variable: str = "renewable_share_pct",
    comparison: str = "gte",
    threshold: float = 50.0,
    delivery_target: str | None = None,
    user_email: str | None = "user@example.com",
    last_observed_value: float | None = None,
    last_fired_at=None,
    fire_count: int = 0,
    label: str | None = None,
) -> dict:
    return {
        "subscription_id": subscription_id,
        "user_id": user_id,
        "country_code": country_code,
        "variable": variable,
        "comparison": comparison,
        "threshold": threshold,
        "delivery_channel": "email",
        "delivery_target": delivery_target,
        "last_observed_value": last_observed_value,
        "last_fired_at": last_fired_at,
        "fire_count": fire_count,
        "label": label,
        "user_email": user_email,
    }


def _fake_db(
    *,
    subscriptions: list[dict] | None = None,
    indicator_values: dict[tuple[str, str], float] | None = None,
):
    """Build a MagicMock DB that responds to the two query patterns
    the poll loop uses."""
    subscriptions = subscriptions or []
    indicator_values = indicator_values or {}
    db = MagicMock()

    def execute_query(query, params=None):
        params = params or {}
        q = " ".join(query.split()).lower()
        if "from aoi_subscriptions" in q and "active = true" in q:
            return subscriptions
        if "from country_indicators" in q:
            indicator_id = params.get("indicator_id")
            codes = params.get("codes", []) or []
            rows = []
            for cc in codes:
                key = (str(indicator_id), str(cc).upper())
                if key in indicator_values:
                    rows.append({
                        "country_code": cc.upper(),
                        "value": float(indicator_values[key]),
                    })
            return rows
        return []

    db.execute_query.side_effect = execute_query
    db.execute_update.return_value = None
    return db


# ---------------------------------------------------------------------------
# Empty + happy-path orchestration
# ---------------------------------------------------------------------------


class TestPollOrchestration:
    def test_empty_subscriptions_returns_zero_summary(self):
        db = _fake_db(subscriptions=[])
        summary = poll_all_active(db=db)
        assert summary.total_subscriptions_checked == 0
        assert summary.fires == []
        assert summary.started_at is not None
        assert summary.finished_at is not None

    def test_single_subscription_that_crosses_fires_email(self):
        sub = _sub_row(
            variable="renewable_share_pct",
            comparison="gte",
            threshold=50.0,
            last_observed_value=45.0,  # was below
        )
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={("renewable_share_pct", "DE"): 52.0},  # now above
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert summary.total_subscriptions_checked == 1
        assert summary.variables_polled == 1
        assert len(summary.fires) == 1
        fire = summary.fires[0]
        assert fire.country_code == "DE"
        assert fire.observed_value == 52.0
        assert fire.email_sent is True
        # Email actually dispatched once with the right target
        mock_send.assert_called_once()
        kw = mock_send.call_args.kwargs
        assert kw["to_email"] == "user@example.com"
        assert "DE" in kw["subject"] or "renewable" in kw["subject"]

    def test_subscription_that_does_not_cross_only_updates_observation(self):
        """Below-threshold observation: no fire, but last_observed_value
        MUST still be updated so debounce works next round."""
        sub = _sub_row(
            variable="renewable_share_pct",
            comparison="gte",
            threshold=50.0,
            last_observed_value=45.0,
        )
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={("renewable_share_pct", "DE"): 48.0},
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert len(summary.fires) == 0
        mock_send.assert_not_called()
        # The observation update SQL ran (lookup `last_observed_value =`)
        update_calls = [
            c for c in db.execute_update.call_args_list
            if "last_observed_value = :observed" in str(c.args[0])
            and "last_fired_at" not in str(c.args[0])
        ]
        assert len(update_calls) == 1

    def test_steady_state_above_threshold_debounces_no_fire(self):
        """Already-crossed last poll AND still-crossed this poll = no email."""
        sub = _sub_row(
            variable="renewable_share_pct",
            comparison="gte",
            threshold=50.0,
            last_observed_value=52.0,  # already above last time
        )
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={("renewable_share_pct", "DE"): 53.0},  # still above
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert summary.fires == []
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Batching + variable grouping
# ---------------------------------------------------------------------------


class TestBatching:
    def test_two_subscriptions_same_variable_share_indicator_query(self):
        """Two countries same variable → ONE country_indicators query
        with ARRAY(ANY) — not two queries."""
        subs = [
            _sub_row(subscription_id="s1", country_code="DE", last_observed_value=45),
            _sub_row(subscription_id="s2", country_code="FR", last_observed_value=40),
        ]
        db = _fake_db(
            subscriptions=subs,
            indicator_values={
                ("renewable_share_pct", "DE"): 52,
                ("renewable_share_pct", "FR"): 51,
            },
        )
        with patch("api.aoi_poll_service.send_email"):
            summary = poll_all_active(db=db)
        assert summary.variables_polled == 1
        # Both fired
        assert len(summary.fires) == 2
        # Indicator query was called ONCE (the batched lookup)
        indicator_queries = [
            c for c in db.execute_query.call_args_list
            if "from country_indicators" in str(c.args[0]).lower()
        ]
        assert len(indicator_queries) == 1

    def test_mixed_variables_each_get_their_own_indicator_query(self):
        subs = [
            _sub_row(subscription_id="s1", variable="renewable_share_pct",
                     comparison="gte", threshold=50, last_observed_value=45),
            _sub_row(subscription_id="s2", variable="co2_emissions_per_capita",
                     comparison="gt", threshold=8.0, last_observed_value=7.0),
        ]
        db = _fake_db(
            subscriptions=subs,
            indicator_values={
                ("renewable_share_pct", "DE"): 52,
                ("co2_emissions_per_capita", "DE"): 9.0,
            },
        )
        with patch("api.aoi_poll_service.send_email"):
            summary = poll_all_active(db=db)
        assert summary.variables_polled == 2
        assert len(summary.fires) == 2


# ---------------------------------------------------------------------------
# Unsupported variables + missing data + failure isolation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_unsupported_variable_is_skipped_and_counted(self):
        """temperature_anomaly_c is intentionally unsupported in v1.
        The subscription stays active but counts as skipped."""
        sub = _sub_row(variable="temperature_anomaly_c", comparison="gt", threshold=2.0)
        assert "temperature_anomaly_c" not in SUPPORTED_VARIABLES
        db = _fake_db(subscriptions=[sub])
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert summary.subscriptions_skipped_unknown_variable == 1
        assert summary.fires == []
        mock_send.assert_not_called()

    def test_country_with_no_indicator_data_is_skipped_silently(self):
        sub = _sub_row(country_code="TV")  # Tuvalu — likely no indicator data
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={},  # empty
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        # Empty indicator response → indicator_lookup_failures incremented
        assert summary.indicator_lookup_failures == 1
        assert summary.fires == []
        mock_send.assert_not_called()

    def test_email_dispatch_failure_still_persists_fire_state(self):
        """If email throws, we still update last_fired_at + last_observed_value.
        Without this, the next poll would re-fire on the same crossing
        and email-bomb when the email service recovers."""
        sub = _sub_row(
            comparison="gte", threshold=50.0, last_observed_value=45.0,
        )
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={("renewable_share_pct", "DE"): 52.0},
        )
        with patch(
            "api.aoi_poll_service.send_email",
            side_effect=RuntimeError("smtp down"),
        ):
            summary = poll_all_active(db=db)
        assert len(summary.fires) == 1
        assert summary.fires[0].email_sent is False
        assert summary.fires[0].email_error == "smtp down"
        # last_fired_at update WAS called (we record the crossing even on email failure)
        fire_state_updates = [
            c for c in db.execute_update.call_args_list
            if "last_fired_at = now()" in str(c.args[0]).lower()
        ]
        assert len(fire_state_updates) == 1

    def test_subscription_with_no_delivery_target_or_user_email_records_error(self):
        sub = _sub_row(delivery_target=None, user_email=None,
                       comparison="gte", threshold=50.0, last_observed_value=45.0)
        db = _fake_db(
            subscriptions=[sub],
            indicator_values={("renewable_share_pct", "DE"): 52.0},
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert len(summary.fires) == 1
        assert summary.fires[0].email_sent is False
        assert summary.fires[0].email_error == "no_delivery_target"
        mock_send.assert_not_called()

    def test_one_bad_subscription_does_not_block_others(self):
        """Failure isolation: a subscription that fails (e.g. no email)
        MUST NOT prevent others from firing."""
        subs = [
            # Bad: no email at all
            _sub_row(subscription_id="bad", user_email=None, delivery_target=None,
                     comparison="gte", threshold=50, last_observed_value=45),
            # Good: should fire
            _sub_row(subscription_id="good", country_code="FR",
                     comparison="gte", threshold=50, last_observed_value=45),
        ]
        db = _fake_db(
            subscriptions=subs,
            indicator_values={
                ("renewable_share_pct", "DE"): 52,
                ("renewable_share_pct", "FR"): 52,
            },
        )
        with patch("api.aoi_poll_service.send_email") as mock_send:
            summary = poll_all_active(db=db)
        assert len(summary.fires) == 2
        # The good one sent
        good_fire = next(f for f in summary.fires if f.subscription_id == "good")
        assert good_fire.email_sent is True
        # The bad one didn't send but is recorded
        bad_fire = next(f for f in summary.fires if f.subscription_id == "bad")
        assert bad_fire.email_sent is False
        # send_email was called once (only for the good one)
        assert mock_send.call_count == 1

    def test_db_load_failure_returns_empty_summary(self):
        """Total DB outage on subscription load: poll returns a zero
        summary cleanly. The Celery beat task logs + retries on the
        next tick."""
        db = MagicMock()
        db.execute_query.side_effect = RuntimeError("postgres down")
        summary = poll_all_active(db=db)
        assert summary.total_subscriptions_checked == 0
        assert summary.fires == []


# ---------------------------------------------------------------------------
# Summary shape (for the scheduler endpoint that returns it as JSON)
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_to_dict_has_expected_keys(self):
        summary = PollSummary()
        d = summary.to_dict()
        assert "total_subscriptions_checked" in d
        assert "variables_polled" in d
        assert "subscriptions_skipped_unknown_variable" in d
        assert "indicator_lookup_failures" in d
        assert "fire_count" in d
        assert "fires" in d
        assert d["fire_count"] == 0
