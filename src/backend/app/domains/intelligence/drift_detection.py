"""KL-divergence drift detection — Phase 6 wave 1.

Detects when the platform's source mix has drifted significantly from its
baseline, e.g.:

  * A high-credibility feed has gone down (its share of recent articles
    collapses to ~0 while it was meaningful in the baseline window).
  * One publisher's share has spiked unexpectedly (potential bias creep).
  * The whole ingest pipeline has stalled and only one or two sources
    keep producing.

KL divergence is the right tool: it measures information loss when
approximating one distribution by another, weighted toward changes in
the high-probability tail (so a dead major source registers louder than
a missing minor one). We compute KL(recent || baseline) so:

  * A source that disappeared from `recent` but was active in `baseline`
    contributes a 0 * log(0/q) = 0 term (KL is finite by convention here).
  * A source that appeared in `recent` but wasn't in `baseline` is more
    interesting — we add a small ε to `baseline` to avoid divide-by-zero
    and the term becomes p * log(p/ε) which is large.

Threshold guide (from preliminary calibration on the 2026-04 → 2026-05
production seed):

  * KL < 0.10  — stable mix; no action needed.
  * 0.10 ≤ KL < 0.25 — minor drift; log for trend analysis.
  * 0.25 ≤ KL < 0.50 — notable drift; flag in ops dashboard.
  * KL ≥ 0.50 — significant drift; page on-call to investigate
    (likely a feed outage or bias spike).

These thresholds are tuned per-deployment as the source mix matures.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

_logger = logging.getLogger("drift_detection")

# Smoothing constant — added to every count before normalising so a
# previously-zero source doesn't blow up KL when it appears in `recent`,
# and so a `recent` zero doesn't crash the log. Same constant applied to
# both distributions keeps the comparison fair.
SMOOTHING_EPSILON = 1e-6


@dataclass
class DriftReport:
    """Result of a single drift check."""
    metric: str                                 # e.g. 'source_mix'
    kl_divergence: float                        # KL(recent || baseline), nats
    verdict: str                                # 'stable' | 'minor' | 'notable' | 'significant'
    recent_window_days: int
    baseline_window_days: int
    recent_count: int                           # total articles in the recent window
    baseline_count: int                         # total articles in the baseline window
    top_shifts: List[Dict[str, float]] = field(default_factory=list)
    # Window endpoints so the report is reproducible.
    recent_end: Optional[str] = None
    baseline_end: Optional[str] = None
    notes: Optional[str] = None

    def as_dict(self) -> Dict[str, float]:
        return {
            "metric": self.metric,
            "kl_divergence": round(self.kl_divergence, 4),
            "verdict": self.verdict,
            "recent_window_days": self.recent_window_days,
            "baseline_window_days": self.baseline_window_days,
            "recent_count": self.recent_count,
            "baseline_count": self.baseline_count,
            "top_shifts": self.top_shifts,
            "recent_end": self.recent_end,
            "baseline_end": self.baseline_end,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------

def normalise_distribution(
    counts: Dict[str, float],
    epsilon: float = SMOOTHING_EPSILON,
    keys: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Convert raw counts to a probability distribution with Laplace smoothing.

    Args:
        counts: source-name → count.
        epsilon: smoothing constant added to every key in `keys`.
        keys: union of keys across both distributions; defaults to counts.keys().
              When provided, ensures both distributions have the same support.

    Returns:
        Dict mapping every key in `keys` (or counts.keys() if None) to a
        probability that sums to 1.0 after smoothing.
    """
    support = keys if keys is not None else list(counts.keys())
    smoothed = {k: float(counts.get(k, 0.0)) + epsilon for k in support}
    total = sum(smoothed.values())
    if total <= 0:
        return {k: 0.0 for k in support}
    return {k: v / total for k, v in smoothed.items()}


def kl_divergence(p: Dict[str, float], q: Dict[str, float]) -> float:
    """KL(p || q) — non-negative; 0 iff p == q.

    Computed in nats. Assumes both distributions share the same key set
    (use `normalise_distribution(..., keys=...)` with the union of supports
    before calling).
    """
    total = 0.0
    for key, p_val in p.items():
        if p_val <= 0:
            continue
        q_val = q.get(key, 0.0)
        if q_val <= 0:
            # With smoothing this shouldn't happen; defensive: log a huge
            # but finite penalty so a totally novel source registers loudly
            # without producing inf.
            q_val = SMOOTHING_EPSILON
        total += p_val * math.log(p_val / q_val)
    return max(0.0, total)


def verdict_for(kl: float) -> str:
    """Bucket the KL value per the thresholds documented in the module docstring."""
    if kl < 0.10:
        return "stable"
    if kl < 0.25:
        return "minor"
    if kl < 0.50:
        return "notable"
    return "significant"


def top_shifts_between(
    recent: Dict[str, float],
    baseline: Dict[str, float],
    limit: int = 10,
    key_label: str = "source_name",
) -> List[Dict[str, float]]:
    """Return the biggest absolute share changes per key.

    Used by the API surface to explain WHY the KL flagged. The list is
    ordered by |Δshare| descending and truncated to `limit`.

    `key_label` controls the label on the returned dict (default "source_name"
    so existing callers stay backwards-compatible). Pass e.g. "prompt_fingerprint"
    for fingerprint-drift output.
    """
    union = set(recent.keys()) | set(baseline.keys())
    diffs: List[Tuple[str, float, float, float]] = []
    for src in union:
        r = recent.get(src, 0.0)
        b = baseline.get(src, 0.0)
        diffs.append((src, r, b, r - b))
    diffs.sort(key=lambda t: abs(t[3]), reverse=True)
    return [
        {
            key_label: src,
            "recent_share": round(r, 4),
            "baseline_share": round(b, 4),
            "delta": round(d, 4),
        }
        for src, r, b, d in diffs[:limit]
    ]


# ---------------------------------------------------------------------------
# DB integration
# ---------------------------------------------------------------------------

def fetch_source_counts(db, days_back_start: int, days_back_end: int) -> Dict[str, int]:
    """Counts of articles per source for a window.

    Window definition: ingested between `now - days_back_start` (exclusive)
    and `now - days_back_end` (inclusive). e.g. days_back_start=7, end=0
    gives "last 7 days".
    """
    try:
        rows = db.execute_query(
            """
            SELECT
                COALESCE(source_name, 'unknown') AS source_name,
                COUNT(*)                          AS n
            FROM articles
            WHERE created_at > NOW() - :start::interval
              AND created_at <= NOW() - :end::interval
            GROUP BY source_name
            """,
            {
                "start": f"{int(days_back_start)} days",
                "end": f"{int(days_back_end)} days",
            },
        )
    except Exception as exc:
        _logger.warning(f"fetch_source_counts failed: {exc}")
        return {}
    return {r["source_name"]: int(r["n"]) for r in (rows or [])}


def detect_source_mix_drift(
    db,
    recent_days: int = 7,
    baseline_days: int = 30,
) -> DriftReport:
    """Compare the last `recent_days` window to the prior `baseline_days` window.

    Baseline excludes the recent window: it covers
        (now - recent_days - baseline_days) ... (now - recent_days)
    so a stable mix gives KL ≈ 0 and the two distributions never overlap
    in time.
    """
    recent_counts = fetch_source_counts(db, days_back_start=recent_days, days_back_end=0)
    baseline_counts = fetch_source_counts(
        db,
        days_back_start=recent_days + baseline_days,
        days_back_end=recent_days,
    )

    support = sorted(set(recent_counts.keys()) | set(baseline_counts.keys()))
    if not support:
        return DriftReport(
            metric="source_mix",
            kl_divergence=0.0,
            verdict="stable",
            recent_window_days=recent_days,
            baseline_window_days=baseline_days,
            recent_count=0,
            baseline_count=0,
            top_shifts=[],
            notes="No articles in either window.",
        )

    p_recent = normalise_distribution(recent_counts, keys=support)
    q_baseline = normalise_distribution(baseline_counts, keys=support)
    kl = kl_divergence(p_recent, q_baseline)

    now_iso = datetime.utcnow().isoformat()
    baseline_end_iso = (datetime.utcnow() - timedelta(days=recent_days)).isoformat()

    return DriftReport(
        metric="source_mix",
        kl_divergence=kl,
        verdict=verdict_for(kl),
        recent_window_days=recent_days,
        baseline_window_days=baseline_days,
        recent_count=sum(recent_counts.values()),
        baseline_count=sum(baseline_counts.values()),
        top_shifts=top_shifts_between(p_recent, q_baseline, limit=10),
        recent_end=now_iso,
        baseline_end=baseline_end_iso,
    )


# ---------------------------------------------------------------------------
# Prompt-fingerprint drift (Phase 6 wave 5)
# ---------------------------------------------------------------------------
#
# Why this matters: every prompt the platform ships with is fingerprinted
# (SHA-256 prefix of template + system, stored in claim_provenance.prompt_fingerprint).
# If a prompt's text changes without a version bump, the fingerprint shifts —
# this drift detector is the canary. It also catches:
#   * Phase-out of an old prompt version (fingerprint's share collapses).
#   * Adoption of a new prompt version (a fingerprint appears in `recent`
#     that wasn't in `baseline`).
#   * Mis-routing where one prompt unexpectedly dominates calls that used
#     to go through several.
#
# Verdict thresholds match the source-mix detector — a `notable` or
# `significant` KL is the on-call signal to inspect the prompt registry.

def fetch_prompt_fingerprint_counts(
    db,
    days_back_start: int,
    days_back_end: int,
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """Counts of claim_provenance rows per prompt_fingerprint in a window.

    Returns:
        counts: fingerprint → count
        display: fingerprint → "name@version" (best-effort, for top_shifts UX)

    Same window semantics as `fetch_source_counts`.
    """
    try:
        rows = db.execute_query(
            """
            SELECT
                prompt_fingerprint,
                MAX(prompt_name)    AS prompt_name,
                MAX(prompt_version) AS prompt_version,
                COUNT(*)             AS n
            FROM claim_provenance
            WHERE created_at > NOW() - :start::interval
              AND created_at <= NOW() - :end::interval
              AND prompt_fingerprint IS NOT NULL
            GROUP BY prompt_fingerprint
            """,
            {
                "start": f"{int(days_back_start)} days",
                "end": f"{int(days_back_end)} days",
            },
        )
    except Exception as exc:
        _logger.warning(f"fetch_prompt_fingerprint_counts failed: {exc}")
        return {}, {}

    counts: Dict[str, int] = {}
    display: Dict[str, str] = {}
    for r in rows or []:
        fp = r.get("prompt_fingerprint")
        if not fp:
            continue
        counts[fp] = int(r.get("n", 0) or 0)
        name = r.get("prompt_name") or "?"
        version = r.get("prompt_version") or "?"
        display[fp] = f"{name}@{version}"
    return counts, display


def detect_prompt_fingerprint_drift(
    db,
    recent_days: int = 7,
    baseline_days: int = 30,
) -> DriftReport:
    """Compare prompt-fingerprint usage between two non-overlapping windows.

    Identical math to `detect_source_mix_drift` but pulling counts from
    `claim_provenance.prompt_fingerprint`. Top-shifts entries carry an
    extra `display` field with the resolved "name@version" so operators
    can quickly identify the affected prompt.
    """
    recent_counts, recent_display = fetch_prompt_fingerprint_counts(
        db, days_back_start=recent_days, days_back_end=0,
    )
    baseline_counts, baseline_display = fetch_prompt_fingerprint_counts(
        db, days_back_start=recent_days + baseline_days, days_back_end=recent_days,
    )

    # Prefer recent display labels (more current) but fall back to baseline
    # when a fingerprint disappeared from `recent`.
    display_map: Dict[str, str] = {**baseline_display, **recent_display}

    support = sorted(set(recent_counts.keys()) | set(baseline_counts.keys()))
    if not support:
        return DriftReport(
            metric="prompt_fingerprint",
            kl_divergence=0.0,
            verdict="stable",
            recent_window_days=recent_days,
            baseline_window_days=baseline_days,
            recent_count=0,
            baseline_count=0,
            top_shifts=[],
            notes="No claim_provenance rows with prompt_fingerprint in either window.",
        )

    p_recent = normalise_distribution(recent_counts, keys=support)
    q_baseline = normalise_distribution(baseline_counts, keys=support)
    kl = kl_divergence(p_recent, q_baseline)

    shifts = top_shifts_between(
        p_recent, q_baseline, limit=10, key_label="prompt_fingerprint",
    )
    for s in shifts:
        fp = s.get("prompt_fingerprint")
        if isinstance(fp, str):
            s["display"] = display_map.get(fp, "?")

    now_iso = datetime.utcnow().isoformat()
    baseline_end_iso = (datetime.utcnow() - timedelta(days=recent_days)).isoformat()

    return DriftReport(
        metric="prompt_fingerprint",
        kl_divergence=kl,
        verdict=verdict_for(kl),
        recent_window_days=recent_days,
        baseline_window_days=baseline_days,
        recent_count=sum(recent_counts.values()),
        baseline_count=sum(baseline_counts.values()),
        top_shifts=shifts,
        recent_end=now_iso,
        baseline_end=baseline_end_iso,
    )
