"""Drift-detection tests (Phase 6 wave 1).

Pins the KL math + the integration with the source-mix endpoint:
- normalise_distribution with smoothing
- kl_divergence symmetric-zero on identical inputs
- kl_divergence > 0 on different inputs
- top_shifts ordered by |delta| descending
- verdict bucketing thresholds
- detect_source_mix_drift returns DriftReport with the expected shape
- /api/drift/source-mix endpoint surfaces the report
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.domains.intelligence.drift_detection import (
    DriftReport,
    detect_prompt_fingerprint_drift,
    detect_source_mix_drift,
    fetch_prompt_fingerprint_counts,
    fetch_source_counts,
    kl_divergence,
    normalise_distribution,
    top_shifts_between,
    verdict_for,
    SMOOTHING_EPSILON,
)


# ---------------------------------------------------------------------------
# normalise_distribution
# ---------------------------------------------------------------------------

class TestNormaliseDistribution:
    def test_sums_to_one(self):
        out = normalise_distribution({"a": 3, "b": 7})
        assert sum(out.values()) == pytest.approx(1.0)

    def test_smoothing_keeps_zeros_nonzero(self):
        out = normalise_distribution({"a": 0, "b": 1})
        # Both keys present with positive probability after smoothing.
        assert out["a"] > 0
        assert out["b"] > out["a"]

    def test_keys_param_creates_union_support(self):
        out = normalise_distribution({"a": 5}, keys=["a", "b", "c"])
        # b and c are added with smoothing only.
        assert sum(out.values()) == pytest.approx(1.0)
        assert out["b"] == pytest.approx(out["c"])
        assert out["a"] > out["b"]

    def test_empty_counts_returns_zero_distribution(self):
        # No keys + no counts = all-zero distribution (graceful, doesn't crash).
        out = normalise_distribution({})
        assert out == {}


# ---------------------------------------------------------------------------
# kl_divergence math
# ---------------------------------------------------------------------------

class TestKLDivergence:
    def test_identical_distributions_yield_zero(self):
        p = {"a": 0.5, "b": 0.5}
        assert kl_divergence(p, p) == pytest.approx(0.0)

    def test_known_value_two_outcomes(self):
        """KL((0.7,0.3) || (0.5,0.5)) = 0.7*log(0.7/0.5) + 0.3*log(0.3/0.5)
        ≈ 0.7*0.3365 + 0.3*(-0.5108) ≈ 0.0823 nats."""
        p = {"a": 0.7, "b": 0.3}
        q = {"a": 0.5, "b": 0.5}
        kl = kl_divergence(p, q)
        expected = 0.7 * math.log(0.7 / 0.5) + 0.3 * math.log(0.3 / 0.5)
        assert kl == pytest.approx(expected, abs=1e-6)

    def test_kl_is_nonnegative(self):
        # KL is always >= 0 (Gibbs' inequality); test a few random shapes.
        cases = [
            ({"a": 0.9, "b": 0.1}, {"a": 0.5, "b": 0.5}),
            ({"a": 0.1, "b": 0.9}, {"a": 0.5, "b": 0.5}),
            ({"a": 0.5, "b": 0.5}, {"a": 0.9, "b": 0.1}),
        ]
        for p, q in cases:
            assert kl_divergence(p, q) >= 0.0

    def test_zero_in_p_contributes_zero(self):
        """0 * log(0/q) is defined as 0 in KL — no NaN."""
        p = {"a": 0.0, "b": 1.0}
        q = {"a": 0.5, "b": 0.5}
        kl = kl_divergence(p, q)
        assert kl == pytest.approx(math.log(1.0 / 0.5))

    def test_zero_in_q_uses_smoothing_floor(self):
        """When q has a zero for a key where p is positive, fall back to ε."""
        p = {"a": 1.0}
        q = {"a": 0.0}
        kl = kl_divergence(p, q)
        # Should be a large but finite penalty.
        assert kl > 5.0
        assert math.isfinite(kl)


# ---------------------------------------------------------------------------
# verdict bucketing
# ---------------------------------------------------------------------------

class TestVerdictFor:
    @pytest.mark.parametrize("kl,expected", [
        (0.0, "stable"),
        (0.09, "stable"),
        (0.10, "minor"),
        (0.24, "minor"),
        (0.25, "notable"),
        (0.49, "notable"),
        (0.50, "significant"),
        (5.0, "significant"),
    ])
    def test_thresholds(self, kl, expected):
        assert verdict_for(kl) == expected


# ---------------------------------------------------------------------------
# top_shifts
# ---------------------------------------------------------------------------

class TestTopShifts:
    def test_ordered_by_abs_delta_descending(self):
        recent = {"a": 0.6, "b": 0.3, "c": 0.05, "d": 0.05}
        baseline = {"a": 0.3, "b": 0.4, "c": 0.2, "d": 0.1}
        shifts = top_shifts_between(recent, baseline, limit=10)
        deltas = [abs(s["delta"]) for s in shifts]
        # Sorted descending.
        assert deltas == sorted(deltas, reverse=True)
        # Top shift is "a" (+0.3 absolute change).
        assert shifts[0]["source_name"] == "a"

    def test_handles_keys_unique_to_one_side(self):
        recent = {"a": 1.0}
        baseline = {"b": 1.0}
        shifts = top_shifts_between(recent, baseline)
        names = {s["source_name"] for s in shifts}
        assert names == {"a", "b"}


# ---------------------------------------------------------------------------
# detect_source_mix_drift (DB integration)
# ---------------------------------------------------------------------------

class _FakeDB:
    """Returns canned source counts based on the SQL pattern."""
    def __init__(self, recent: Dict[str, int], baseline: Dict[str, int]):
        self.recent = recent
        self.baseline = baseline

    def execute_query(self, query, params=None):
        params = params or {}
        start = params.get("start", "")
        end = params.get("end", "")
        # Recent window has end='0 days'.
        if end.startswith("0"):
            return [{"source_name": k, "n": v} for k, v in self.recent.items()]
        return [{"source_name": k, "n": v} for k, v in self.baseline.items()]


class TestDetectSourceMixDrift:
    def test_identical_distributions_yield_stable_verdict(self):
        recent = {"reuters": 100, "bbc": 100}
        baseline = {"reuters": 1000, "bbc": 1000}  # same proportions
        report = detect_source_mix_drift(_FakeDB(recent, baseline), recent_days=7, baseline_days=30)
        assert report.verdict == "stable"
        assert report.kl_divergence < 0.05

    def test_dead_feed_produces_notable_drift(self):
        """If 'bbc' was 50% of baseline but is 0% recent, KL should be notable."""
        recent = {"reuters": 100, "bbc": 0}
        baseline = {"reuters": 100, "bbc": 100}
        report = detect_source_mix_drift(_FakeDB(recent, baseline))
        assert report.verdict in {"notable", "significant"}
        # The top shift should point at 'bbc' (large negative delta) or 'reuters'.
        top_sources = {s["source_name"] for s in report.top_shifts[:2]}
        assert {"bbc", "reuters"} <= top_sources

    def test_empty_windows_return_insufficient_data(self):
        # The honesty gate: 0/0 articles must NOT read as a confident 'stable'.
        report = detect_source_mix_drift(_FakeDB({}, {}))
        assert report.verdict == "insufficient_data"
        assert report.kl_divergence == 0.0
        assert report.recent_count == 0
        assert report.baseline_count == 0
        assert report.notes is not None
        assert "insufficient" in report.notes.lower()

    def test_sparse_window_is_insufficient_not_stable(self):
        # Identical small windows would have given KL=0 -> 'stable'. With too few
        # samples we refuse to claim a verdict instead of painting it green.
        recent = {"a": 3, "b": 2}     # 5 < MIN_WINDOW_SAMPLES
        baseline = {"a": 3, "b": 2}
        report = detect_source_mix_drift(_FakeDB(recent, baseline))
        assert report.verdict == "insufficient_data"
        assert report.recent_count == 5

    def test_sufficient_windows_still_yield_a_real_verdict(self):
        recent = {"reuters": 60, "bbc": 40}    # 100 >= MIN_WINDOW_SAMPLES
        baseline = {"reuters": 600, "bbc": 400}
        report = detect_source_mix_drift(_FakeDB(recent, baseline))
        assert report.verdict in {"stable", "minor", "notable", "significant"}

    def test_report_shape(self):
        recent = {"a": 50, "b": 50}
        baseline = {"a": 50, "b": 50}
        report = detect_source_mix_drift(_FakeDB(recent, baseline), recent_days=7, baseline_days=30)
        out = report.as_dict()
        for key in (
            "metric", "kl_divergence", "verdict", "recent_window_days",
            "baseline_window_days", "recent_count", "baseline_count",
            "top_shifts", "recent_end", "baseline_end",
        ):
            assert key in out
        assert out["metric"] == "source_mix"
        assert out["recent_window_days"] == 7
        assert out["baseline_window_days"] == 30


# ---------------------------------------------------------------------------
# /api/drift/source-mix endpoint
# ---------------------------------------------------------------------------

class TestSourceMixEndpoint:
    def test_endpoint_returns_report(self, monkeypatch):
        import shared.database as _shared_db
        from api.main import app

        recent = {"reuters": 50, "bbc": 30}
        baseline = {"reuters": 200, "bbc": 200, "ap": 100}
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _FakeDB(recent, baseline)
        try:
            client = TestClient(app)
            r = client.get("/api/drift/source-mix?recent_days=7&baseline_days=30")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["metric"] == "source_mix"
            assert body["verdict"] in {"stable", "minor", "notable", "significant"}
            assert body["recent_window_days"] == 7
            assert "top_shifts" in body
        finally:
            _shared_db._postgres_client = prior


# ---------------------------------------------------------------------------
# top_shifts_between key_label parameter (Phase 6 wave 5 prerequisite)
# ---------------------------------------------------------------------------

class TestTopShiftsKeyLabel:
    def test_default_label_unchanged(self):
        shifts = top_shifts_between({"a": 1.0}, {"b": 1.0})
        # Existing callers must continue to see 'source_name'.
        for s in shifts:
            assert "source_name" in s
            assert "prompt_fingerprint" not in s

    def test_custom_label_replaces_source_name(self):
        shifts = top_shifts_between(
            {"a1b2": 0.7, "c3d4": 0.3},
            {"a1b2": 0.5, "c3d4": 0.5},
            key_label="prompt_fingerprint",
        )
        for s in shifts:
            assert "prompt_fingerprint" in s
            assert "source_name" not in s
            # Same numeric fields still present.
            assert "recent_share" in s
            assert "baseline_share" in s
            assert "delta" in s


# ---------------------------------------------------------------------------
# detect_prompt_fingerprint_drift (Phase 6 wave 5)
# ---------------------------------------------------------------------------

class _FakeDBPrompts:
    """Mimics claim_provenance query: returns rows with
    {prompt_fingerprint, prompt_name, prompt_version, n}.

    Like _FakeDB, dispatches by the params['end'] value: '0 days' → recent."""

    def __init__(
        self,
        recent: List[Dict[str, Any]],
        baseline: List[Dict[str, Any]],
    ):
        self.recent = recent
        self.baseline = baseline

    def execute_query(self, query, params=None):
        params = params or {}
        end = params.get("end", "")
        return self.recent if end.startswith("0") else self.baseline


def _row(fp: str, name: str, version: str, n: int) -> Dict[str, Any]:
    return {
        "prompt_fingerprint": fp,
        "prompt_name": name,
        "prompt_version": version,
        "n": n,
    }


class TestFetchPromptFingerprintCounts:
    def test_returns_counts_and_display_map(self):
        db = _FakeDBPrompts(
            recent=[_row("abcd1234", "synth", "v1.0", 50)],
            baseline=[],
        )
        counts, display = fetch_prompt_fingerprint_counts(db, 7, 0)
        assert counts == {"abcd1234": 50}
        assert display == {"abcd1234": "synth@v1.0"}

    def test_skips_rows_without_fingerprint(self):
        db = _FakeDBPrompts(
            recent=[
                _row("abcd", "p", "v1", 5),
                {"prompt_fingerprint": None, "prompt_name": "p", "prompt_version": "v1", "n": 99},
            ],
            baseline=[],
        )
        counts, _ = fetch_prompt_fingerprint_counts(db, 7, 0)
        assert counts == {"abcd": 5}

    def test_falls_back_to_question_mark_for_missing_metadata(self):
        db = _FakeDBPrompts(
            recent=[{"prompt_fingerprint": "deadbeef", "prompt_name": None, "prompt_version": None, "n": 3}],
            baseline=[],
        )
        _, display = fetch_prompt_fingerprint_counts(db, 7, 0)
        assert display["deadbeef"] == "?@?"

    def test_db_error_returns_empty(self):
        class _Broken:
            def execute_query(self, query, params=None):
                raise RuntimeError("table doesn't exist yet")
        counts, display = fetch_prompt_fingerprint_counts(_Broken(), 7, 0)
        assert counts == {}
        assert display == {}


class TestDetectPromptFingerprintDrift:
    def test_identical_distributions_yield_stable_verdict(self):
        recent = [_row("aa", "p1", "v1", 50), _row("bb", "p2", "v1", 50)]
        baseline = [_row("aa", "p1", "v1", 500), _row("bb", "p2", "v1", 500)]
        report = detect_prompt_fingerprint_drift(_FakeDBPrompts(recent, baseline))
        assert report.metric == "prompt_fingerprint"
        assert report.verdict == "stable"
        assert report.kl_divergence < 0.05

    def test_silent_prompt_edit_produces_drift(self):
        """A new fingerprint appears in `recent` that wasn't in `baseline` — the
        signature of a silent prompt edit. Drift should be notable or worse."""
        recent = [_row("NEW_FP", "synth", "v1.0", 100)]
        baseline = [_row("OLD_FP", "synth", "v1.0", 100)]
        report = detect_prompt_fingerprint_drift(_FakeDBPrompts(recent, baseline))
        # Completely disjoint distributions push KL high.
        assert report.verdict in {"notable", "significant"}
        # top_shifts should call out both fingerprints.
        fps = {s.get("prompt_fingerprint") for s in report.top_shifts}
        assert {"NEW_FP", "OLD_FP"} <= fps

    def test_top_shifts_include_display_label(self):
        recent = [_row("aa11", "synth", "v1.0", 80), _row("bb22", "classifier", "v0.9", 20)]
        baseline = [_row("aa11", "synth", "v0.9", 50), _row("bb22", "classifier", "v0.9", 50)]
        report = detect_prompt_fingerprint_drift(_FakeDBPrompts(recent, baseline))
        # Recent labels should win (so the synth fingerprint shows v1.0).
        for s in report.top_shifts:
            assert "display" in s
            if s["prompt_fingerprint"] == "aa11":
                assert s["display"] == "synth@v1.0"
            elif s["prompt_fingerprint"] == "bb22":
                assert s["display"] == "classifier@v0.9"

    def test_empty_windows_return_insufficient_data(self):
        report = detect_prompt_fingerprint_drift(_FakeDBPrompts([], []))
        assert report.verdict == "insufficient_data"
        assert report.kl_divergence == 0.0
        assert report.recent_count == 0
        assert report.baseline_count == 0
        assert report.notes is not None
        assert "prompt" in report.notes.lower()
        assert "insufficient" in report.notes.lower()

    def test_report_shape_matches_source_mix(self):
        """The endpoint surface must look the same across drift metrics so a
        single dashboard can render any metric type."""
        recent = [_row("aa", "p", "v1", 50)]
        baseline = [_row("aa", "p", "v1", 50)]
        report = detect_prompt_fingerprint_drift(_FakeDBPrompts(recent, baseline))
        out = report.as_dict()
        for key in (
            "metric", "kl_divergence", "verdict",
            "recent_window_days", "baseline_window_days",
            "recent_count", "baseline_count",
            "top_shifts", "recent_end", "baseline_end",
        ):
            assert key in out
        assert out["metric"] == "prompt_fingerprint"


# ---------------------------------------------------------------------------
# /api/drift/prompt-fingerprints endpoint (Phase 6 wave 5)
# ---------------------------------------------------------------------------

class TestPromptFingerprintEndpoint:
    def test_endpoint_returns_report(self, monkeypatch):
        import shared.database as _shared_db
        from api.main import app

        recent = [_row("ff00", "synth", "v1.0", 50), _row("ee11", "classifier", "v0.9", 30)]
        baseline = [_row("ff00", "synth", "v1.0", 500), _row("ee11", "classifier", "v0.9", 500)]
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = _FakeDBPrompts(recent, baseline)
        try:
            client = TestClient(app)
            r = client.get("/api/drift/prompt-fingerprints?recent_days=7&baseline_days=30")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["metric"] == "prompt_fingerprint"
            assert body["verdict"] in {"stable", "minor", "notable", "significant"}
            assert body["recent_window_days"] == 7
            assert body["baseline_window_days"] == 30
            assert "top_shifts" in body
            # Display labels should propagate to the wire format.
            displays = {s.get("display") for s in body["top_shifts"]}
            assert any(d and "@" in d for d in displays)
        finally:
            _shared_db._postgres_client = prior
