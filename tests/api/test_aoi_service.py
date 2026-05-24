"""AOI alert service unit tests — Phase 3 (2026-05-23).

Pins the threshold-check primitive (pure function, no I/O) and the
tier-gating logic (semi-pure, just one DB count call).

The threshold-check is the platform's most behavioural primitive — a
regression here means alerts fire when they shouldn't OR don't fire
when they should. Both are silent failure modes the user can't see
until they miss a heatwave alert. We test 24 distinct cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.aoi_service import (
    AOI_TIER_LIMITS,
    AOIService,
    VALID_COMPARISONS,
    check_threshold_crossed,
)


# ---------------------------------------------------------------------------
# check_threshold_crossed — pure function, exhaustive coverage
# ---------------------------------------------------------------------------


class TestThresholdCrossed:
    @pytest.mark.parametrize("comparison,observed,threshold,expected", [
        # gt
        ("gt", 11.0, 10.0, True),
        ("gt", 10.0, 10.0, False),  # equal — NOT greater than
        ("gt", 9.0, 10.0, False),
        # gte
        ("gte", 10.0, 10.0, True),
        ("gte", 10.01, 10.0, True),
        ("gte", 9.99, 10.0, False),
        # lt
        ("lt", 9.0, 10.0, True),
        ("lt", 10.0, 10.0, False),
        ("lt", 11.0, 10.0, False),
        # lte
        ("lte", 10.0, 10.0, True),
        ("lte", 9.99, 10.0, True),
        ("lte", 10.01, 10.0, False),
        # eq
        ("eq", 10.0, 10.0, True),
        ("eq", 10.000001, 10.0, False),  # strict
    ])
    def test_rule_evaluation_no_prior(self, comparison, observed, threshold, expected):
        """Without a prior observation, any rule satisfaction fires."""
        assert (
            check_threshold_crossed(observed, comparison, threshold, last_observed=None)
            is expected
        )

    def test_missing_observed_never_fires(self):
        """observed=None means 'no data this poll' — alerting on absence is
        a different concern; we silently skip."""
        for cmp in VALID_COMPARISONS:
            assert check_threshold_crossed(None, cmp, 10.0) is False

    def test_unknown_comparison_never_fires(self):
        """Defensive: garbage comparison string never fires."""
        assert check_threshold_crossed(15.0, "approximately", 10.0) is False
        assert check_threshold_crossed(15.0, "", 10.0) is False
        assert check_threshold_crossed(15.0, "GT", 10.0) is False  # case-sensitive

    def test_debounce_no_fire_when_rule_was_already_satisfied(self):
        """Steady-state suppression: if last_observed also satisfied the
        rule, don't fire again on the same crossing."""
        # 12 > 10 last time AND 13 > 10 this time → no fire (already crossed)
        assert check_threshold_crossed(13.0, "gt", 10.0, last_observed=12.0) is False
        # 11 >= 10 last time AND 10 >= 10 this time → no fire
        assert check_threshold_crossed(10.0, "gte", 10.0, last_observed=11.0) is False

    def test_debounce_fires_when_prior_did_not_satisfy(self):
        """Genuine crossing: prior was below threshold, current is above."""
        # 9 NOT > 10 last time AND 11 > 10 this time → fire
        assert check_threshold_crossed(11.0, "gt", 10.0, last_observed=9.0) is True
        # 11 NOT < 10 last time AND 9 < 10 this time → fire (downward crossing)
        assert check_threshold_crossed(9.0, "lt", 10.0, last_observed=11.0) is True

    def test_debounce_fires_on_first_observation(self):
        """No prior observation = first poll = fire if rule satisfied."""
        assert check_threshold_crossed(15.0, "gt", 10.0, last_observed=None) is True

    def test_no_fire_when_rule_not_satisfied_regardless_of_prior(self):
        """Current observation below threshold = no fire, prior doesn't matter."""
        assert check_threshold_crossed(5.0, "gt", 10.0, last_observed=None) is False
        assert check_threshold_crossed(5.0, "gt", 10.0, last_observed=15.0) is False
        assert check_threshold_crossed(5.0, "gt", 10.0, last_observed=4.0) is False


# ---------------------------------------------------------------------------
# Tier ladder — pin the Basic+ gate
# ---------------------------------------------------------------------------


class TestTierLadder:
    def test_freemium_and_anonymous_have_zero_quota(self):
        assert AOI_TIER_LIMITS["freemium"] == 0
        assert AOI_TIER_LIMITS["anonymous"] == 0
        assert AOI_TIER_LIMITS["free"] == 0

    def test_basic_is_5(self):
        assert AOI_TIER_LIMITS["basic"] == 5
        assert AOI_TIER_LIMITS["standard"] == 5  # alias

    def test_professional_is_50(self):
        assert AOI_TIER_LIMITS["professional"] == 50

    def test_enterprise_is_unlimited(self):
        assert AOI_TIER_LIMITS["enterprise"] == -1

    def test_tier_limit_resolves_unknown_to_anonymous(self):
        assert AOIService.tier_limit("enterprise-platinum") == 0
        assert AOIService.tier_limit(None) == 0
        assert AOIService.tier_limit("") == 0


# ---------------------------------------------------------------------------
# can_create — gates Basic+ + counts existing
# ---------------------------------------------------------------------------


class TestCanCreate:
    def _patched(self, count: int):
        db = MagicMock()
        db.execute_query.return_value = [{"n": count}]
        return patch("api.aoi_service.get_postgres", return_value=db)

    def test_freemium_is_blocked_immediately(self):
        with self._patched(0):
            allowed, used, limit = AOIService.can_create("u-1", "freemium")
        assert allowed is False
        assert limit == 0

    def test_basic_with_room_is_allowed(self):
        with self._patched(2):
            allowed, used, limit = AOIService.can_create("u-1", "basic")
        assert allowed is True
        assert used == 2
        assert limit == 5

    def test_basic_at_quota_is_blocked(self):
        with self._patched(5):
            allowed, used, limit = AOIService.can_create("u-1", "basic")
        assert allowed is False
        assert used == 5

    def test_enterprise_is_always_allowed(self):
        with self._patched(10_000):
            allowed, used, limit = AOIService.can_create("u-1", "enterprise")
        assert allowed is True
        assert limit == -1


# ---------------------------------------------------------------------------
# create() — validation + tier gate + insert
# ---------------------------------------------------------------------------


class TestCreate:
    def _patched_db(self, existing_count: int = 0):
        db = MagicMock()
        db.execute_query.return_value = [{"n": existing_count}]
        db.execute_update.return_value = None
        return db

    def test_rejects_unknown_comparison(self):
        db = self._patched_db()
        with patch("api.aoi_service.get_postgres", return_value=db):
            with pytest.raises(HTTPException) as exc:
                AOIService.create(
                    user_id="u-1", tier="basic", country_code="DE",
                    variable="temperature_anomaly_c", comparison="approximately",
                    threshold=2.0,
                )
        assert exc.value.status_code == 400
        assert "Invalid comparison" in str(exc.value.detail)

    def test_rejects_bad_country_code(self):
        db = self._patched_db()
        with patch("api.aoi_service.get_postgres", return_value=db):
            with pytest.raises(HTTPException) as exc:
                AOIService.create(
                    user_id="u-1", tier="basic", country_code="DEU",
                    variable="x", comparison="gt", threshold=1.0,
                )
        assert exc.value.status_code == 400

    def test_rejects_empty_variable(self):
        db = self._patched_db()
        with patch("api.aoi_service.get_postgres", return_value=db):
            with pytest.raises(HTTPException) as exc:
                AOIService.create(
                    user_id="u-1", tier="basic", country_code="DE",
                    variable="   ", comparison="gt", threshold=1.0,
                )
        assert exc.value.status_code == 400

    def test_freemium_user_blocked_with_structured_429(self):
        db = self._patched_db(existing_count=0)
        with patch("api.aoi_service.get_postgres", return_value=db):
            with pytest.raises(HTTPException) as exc:
                AOIService.create(
                    user_id="u-1", tier="freemium", country_code="DE",
                    variable="temperature_anomaly_c", comparison="gt",
                    threshold=2.0,
                )
        assert exc.value.status_code == 429
        body = exc.value.detail
        assert body["error"] == "aoi_tier_limit"
        assert body["tier"] == "freemium"
        assert body["limit"] == 0
        assert body["upgrade_url"] == "/dashboard/subscription"
        assert "Basic+" in body["message"]

    def test_basic_at_limit_blocked_with_structured_429(self):
        db = self._patched_db(existing_count=5)
        with patch("api.aoi_service.get_postgres", return_value=db):
            with pytest.raises(HTTPException) as exc:
                AOIService.create(
                    user_id="u-1", tier="basic", country_code="DE",
                    variable="renewable_share_pct", comparison="gte",
                    threshold=50.0,
                )
        assert exc.value.status_code == 429
        body = exc.value.detail
        assert body["used"] == 5
        assert body["limit"] == 5
        assert "Upgrade" in body["message"]

    def test_basic_with_room_creates_subscription(self):
        db = self._patched_db(existing_count=2)
        with patch("api.aoi_service.get_postgres", return_value=db):
            sub = AOIService.create(
                user_id="u-1", tier="basic", country_code="de",
                variable="temperature_anomaly_c", comparison="gt",
                threshold=2.0, label="Germany hot summer",
            )
        assert sub.user_id == "u-1"
        # country_code is uppercased
        assert sub.country_code == "DE"
        assert sub.variable == "temperature_anomaly_c"
        assert sub.comparison == "gt"
        assert sub.threshold == 2.0
        assert sub.label == "Germany hot summer"
        assert sub.active is True
        # DB insert was called
        db.execute_update.assert_called_once()


# ---------------------------------------------------------------------------
# deactivate() — soft delete
# ---------------------------------------------------------------------------


class TestDeactivate:
    def test_returns_true_when_row_updated(self):
        db = MagicMock()
        db.execute_update.return_value = 1
        with patch("api.aoi_service.get_postgres", return_value=db):
            assert AOIService.deactivate("u-1", "sub-1") is True

    def test_returns_false_when_no_row_affected(self):
        db = MagicMock()
        db.execute_update.return_value = 0
        with patch("api.aoi_service.get_postgres", return_value=db):
            assert AOIService.deactivate("u-1", "sub-1") is False

    def test_returns_false_on_db_error(self):
        db = MagicMock()
        db.execute_update.side_effect = RuntimeError("boom")
        with patch("api.aoi_service.get_postgres", return_value=db):
            assert AOIService.deactivate("u-1", "sub-1") is False
