"""Premium-feature matrix vs enforcement audit (Slice S7, gap §4-9).

The rate-limiter declares 15 features as paid-tier-only in
api/rate_limiter.py:premium_features. The truth contract of the
platform is: every declared premium feature MUST have at least one
check_premium_feature(...) call site so users get a 403 with a
useful upgrade message instead of silently getting the paid surface.

The master-prompt audit caught the gap: 8 of 15 features had no
enforcement at all. This test catalogs the current state so:
  - CI fails loudly the moment a new premium feature is declared
    without enforcement.
  - Existing gaps are explicitly listed with EXPECTED_UNENFORCED so
    we can't pretend they don't exist.
  - A subsequent slice that closes a gap will trip the assertion
    and force the test update — i.e. you can't quietly fix a gap
    without acknowledging it in this audit.

Each EXPECTED_UNENFORCED entry should be paired with either:
  - A planned route that will land the check, OR
  - A justification for why the feature is enforced via a different
    mechanism (middleware, route-level Depends, etc.), OR
  - A decision to remove the feature from the premium matrix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RATE_LIMITER = REPO_ROOT / "api" / "rate_limiter.py"
API_DIR = REPO_ROOT / "api"
SRC_BACKEND = REPO_ROOT / "src" / "backend"


# Features currently declared but unenforced. Each requires either an
# enforcement-add slice or removal from the premium matrix. Tracked so a
# regression that adds another unenforced feature trips the assertion.
EXPECTED_UNENFORCED: dict[str, str] = {
    # feature_name: justification / planned-slice
    # NOTE: "url_analysis" was removed from this list — it now has an explicit
    # check_premium_feature(..., "url_analysis") call site (api/research_routes.py),
    # so it is enforced and must NOT be listed as an unenforced gap.
    "notifications": (
        "No /api/notifications/* surface in the API directory yet. "
        "Remove from the matrix until the feature ships, or stub the "
        "endpoint that will enforce it."
    ),
    "advanced_analytics": (
        "/api/analytics/* exists but doesn't tier-check. Could either "
        "depend on require_premium('advanced_analytics') decorator or "
        "drop the entry from the matrix."
    ),
    "infographics": (
        "/api/articles/{id}/infographic is currently public. Add a "
        "freemium quota OR enforce as premium per the matrix."
    ),
    "feed_customization": (
        "User feed preferences (mig 010) are currently free. Decide: "
        "premium-gate or drop from matrix."
    ),
    "advanced_insights": (
        "/api/insights/* surface — verify if it actually requires tier "
        "or remove."
    ),
    "source_registration": (
        "POST /api/companies/suggestions does enforce via Depends("
        "get_current_user) — but doesn't call check_premium_feature. "
        "Currently any authenticated user can suggest. Decide tier."
    ),
    "comparative_analysis": (
        "/api/map/compare doesn't gate. Either restrict per matrix or "
        "remove."
    ),
}


def _read_premium_features() -> set[str]:
    """Parse the premium_features dict from api/rate_limiter.py."""
    text = RATE_LIMITER.read_text(encoding="utf-8")
    # Match `'feature_name': [...]` lines inside the premium_features block.
    block_match = re.search(
        r"premium_features\s*=\s*\{(.+?)\}",
        text,
        re.DOTALL,
    )
    assert block_match, "Couldn't locate premium_features dict in rate_limiter.py"
    block = block_match.group(1)
    return set(re.findall(r'["\']([a-z_]+)["\']\s*:', block))


def _find_enforced() -> set[str]:
    """Scan every .py under api/ and src/backend/ for check_premium_feature
    callsites and extract the feature-name string literal."""
    pattern = re.compile(
        r"check_premium_feature\([^,]+,\s*['\"]([a-z_]+)['\"]"
    )
    enforced: set[str] = set()
    for root in (API_DIR, SRC_BACKEND):
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "rate_limiter.py":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in pattern.finditer(text):
                enforced.add(m.group(1))
    return enforced


class TestPremiumFeatureMatrix:
    def test_no_undeclared_features_in_use(self):
        """check_premium_feature() is called with a feature name that's
        NOT in the matrix → callsite will silently return False → user
        gets locked out of something we never declared as paid. Catch it."""
        declared = _read_premium_features()
        enforced = _find_enforced()
        undeclared = enforced - declared
        assert not undeclared, (
            f"check_premium_feature() called with features not in the "
            f"premium_features matrix: {sorted(undeclared)}. Add them to "
            f"api/rate_limiter.py:premium_features or fix the typo."
        )

    def test_known_unenforced_gaps_are_explicitly_tracked(self):
        """Every feature in EXPECTED_UNENFORCED must really lack a callsite.
        If an enforcement slice closed a gap, this test trips so the
        EXPECTED_UNENFORCED dict gets updated — no quiet fixes."""
        enforced = _find_enforced()
        falsely_listed = set(EXPECTED_UNENFORCED) & enforced
        assert not falsely_listed, (
            f"EXPECTED_UNENFORCED lists features that ARE now enforced: "
            f"{sorted(falsely_listed)}. Remove them from EXPECTED_UNENFORCED "
            f"so the gap-list reflects truth."
        )

    def test_no_silent_unenforced_features(self):
        """Every declared premium feature must EITHER have a callsite OR
        be explicitly listed in EXPECTED_UNENFORCED with a justification.
        A silent unenforced feature is the §4-9 gap that motivated this
        audit — never let one slip in unannounced."""
        declared = _read_premium_features()
        enforced = _find_enforced()
        unenforced = declared - enforced
        silent_gaps = unenforced - set(EXPECTED_UNENFORCED)
        assert not silent_gaps, (
            f"Premium features declared with no check_premium_feature() "
            f"callsite AND not in EXPECTED_UNENFORCED: {sorted(silent_gaps)}. "
            f"Either add enforcement, remove from the matrix, or add to "
            f"EXPECTED_UNENFORCED with a justification."
        )
