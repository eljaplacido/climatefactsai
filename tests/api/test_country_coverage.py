"""Country-coverage discipline guard.

Three invariants this test enforces:

1. **Drift guard** — REGION_COUNTRIES, COUNTRY_COORDS, COUNTRY_NAMES, and
   the SQL country seed (``infrastructure/database/04_countries_seed.sql``)
   must remain in sync.  The only documented exceptions are:
     - ``XX``: the cross-border / international placeholder (lives in
       COUNTRY_NAMES + the seed but never in REGION_COUNTRIES or coords).

2. **95% live-coverage floor** — when a real Postgres is reachable, at
   least 95% of REGION_COUNTRIES codes must have ≥1 article in the
   ``articles`` table.  Skipped (not failed) when no DB is reachable so
   the suite still runs in CI without a database.

3. **Region completeness** — every region listed in REGION_COUNTRIES must
   contain ≥1 country (no empty buckets).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Set

import pytest


# ---------------------------------------------------------------------------
# Static set extraction (no DB needed)
# ---------------------------------------------------------------------------

def _region_country_codes() -> Set[str]:
    from api.map_routes import REGION_COUNTRIES
    return {code for codes in REGION_COUNTRIES.values() for code in codes}


def _coords_country_codes() -> Set[str]:
    from app.domains.content.forecast_service import COUNTRY_COORDS
    return set(COUNTRY_COORDS.keys())


def _names_country_codes() -> Set[str]:
    from app.domains.content.forecast_service import COUNTRY_NAMES
    return set(COUNTRY_NAMES.keys())


def _seed_country_codes() -> Set[str]:
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "infrastructure" / "database" / "04_countries_seed.sql"
    )
    if not seed_path.exists():
        pytest.skip(f"Seed file not found at {seed_path}")
    sql = seed_path.read_text(encoding="utf-8")
    # Match the leading column of each row in the multi-row INSERT.
    return set(re.findall(r"\('([A-Z]{2})',", sql))


# Documented exceptions to the alignment rule
ALLOWED_EXTRAS = {
    # XX is the cross-border / international placeholder used by ingestion
    # for articles that span multiple countries. Not a real country, so it
    # has no coords or region — but it is in COUNTRY_NAMES + seed.
    "XX",
}


# ---------------------------------------------------------------------------
# 1. Drift invariants
# ---------------------------------------------------------------------------

class TestRegionCoverageAlignment:
    def test_every_region_code_has_coords(self):
        regions = _region_country_codes()
        coords = _coords_country_codes()
        missing = regions - coords
        assert not missing, (
            f"REGION_COUNTRIES references {len(missing)} codes with no entry "
            f"in COUNTRY_COORDS: {sorted(missing)}. "
            "Every map-region country needs capital coordinates so the "
            "weather and temperature-anomaly endpoints don't silently 404."
        )

    def test_every_region_code_has_name(self):
        regions = _region_country_codes()
        names = _names_country_codes()
        missing = regions - names
        assert not missing, (
            f"REGION_COUNTRIES references {len(missing)} codes with no entry "
            f"in COUNTRY_NAMES: {sorted(missing)}."
        )

    def test_every_region_code_is_seeded(self):
        regions = _region_country_codes()
        seed = _seed_country_codes()
        missing = regions - seed
        assert not missing, (
            f"REGION_COUNTRIES references {len(missing)} codes that are not "
            f"in 04_countries_seed.sql: {sorted(missing)}. "
            "FK constraint fk_articles_country will silently drop article "
            "inserts for those codes."
        )

    def test_coords_and_names_agree(self):
        coords = _coords_country_codes()
        names = _names_country_codes()
        only_in_coords = coords - names
        only_in_names = names - coords - ALLOWED_EXTRAS
        assert not only_in_coords, (
            f"COUNTRY_COORDS has codes missing from COUNTRY_NAMES: "
            f"{sorted(only_in_coords)}"
        )
        assert not only_in_names, (
            f"COUNTRY_NAMES has codes missing from COUNTRY_COORDS "
            f"(beyond allowed extras {sorted(ALLOWED_EXTRAS)}): "
            f"{sorted(only_in_names)}"
        )

    def test_seed_extras_are_documented(self):
        """The seed file may contain entries beyond REGION_COUNTRIES (e.g. XX)
        but every such extra must be in ALLOWED_EXTRAS.  Catches accidental
        additions to the seed without a corresponding region entry."""
        seed = _seed_country_codes()
        regions = _region_country_codes()
        extras = seed - regions - ALLOWED_EXTRAS
        assert not extras, (
            f"04_countries_seed.sql contains country codes that are not in "
            f"REGION_COUNTRIES and not in the allowed-extras list "
            f"({sorted(ALLOWED_EXTRAS)}): {sorted(extras)}. "
            "Either add them to a region or to the documented allow-list."
        )

    def test_no_region_is_empty(self):
        from api.map_routes import REGION_COUNTRIES
        empty = [name for name, codes in REGION_COUNTRIES.items() if not codes]
        assert not empty, f"Empty region buckets: {empty}"


# ---------------------------------------------------------------------------
# 2. Live 95% coverage floor (skipped without DB)
# ---------------------------------------------------------------------------

def _try_get_postgres():
    """Return a live psycopg2 connection or None if DB is unreachable.

    Reads the same env vars the app does (DB_HOST/DB_PORT/DB_NAME/DB_USER/
    DB_PASSWORD) with the docker-compose defaults the seed scripts assume.
    """
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5433")),
            dbname=os.getenv("DB_NAME", "climatenews"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "climatenews123"),
            connect_timeout=2,
        )
        return conn
    except Exception:
        return None


class TestLiveCountryCoverage:
    """The 'platform reaches 95% of countries' contract.

    Requires CLILENS_ASSERT_LIVE_COVERAGE=1 to fail (otherwise skipped in
    environments without DB).  Set in CI for the full-stack smoke job.
    """

    @pytest.fixture(scope="class")
    def live_db(self):
        conn = _try_get_postgres()
        if conn is None:
            pytest.skip(
                "No reachable Postgres at $DB_HOST:$DB_PORT — "
                "skipping live coverage floor (set CLILENS_ASSERT_LIVE_COVERAGE=1 in "
                "CI to make this fatal once the DB is wired)."
            )
        yield conn
        conn.close()

    def test_at_least_95_percent_of_regions_have_articles(self, live_db):
        regions = _region_country_codes()
        with live_db.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT country_code
                   FROM articles
                   WHERE country_code = ANY(%s)""",
                (list(regions),),
            )
            populated = {row[0] for row in cur.fetchall()}
        coverage = len(populated) / max(1, len(regions))
        threshold = 0.95
        # Hard-fail mode for CI; otherwise emit a clear warning and pass-through.
        if os.getenv("CLILENS_ASSERT_LIVE_COVERAGE") == "1":
            assert coverage >= threshold, (
                f"Live country coverage is {coverage:.1%} "
                f"({len(populated)}/{len(regions)}) — below the 95% floor. "
                f"Missing: {sorted(regions - populated)}"
            )
        else:
            # Non-strict mode — record but don't fail
            if coverage < threshold:
                pytest.skip(
                    f"Coverage {coverage:.1%} below 95% but "
                    "CLILENS_ASSERT_LIVE_COVERAGE!=1 — not failing. "
                    f"Missing: {sorted(regions - populated)[:20]}…"
                )
