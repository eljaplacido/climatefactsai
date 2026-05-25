"""SBTi adapter country-map coverage + upsert_company ON CONFLICT contract.

Slice 2 (2026-05-25) — companies dedup hardening. The dup re-pollution
incident traced back to two failure modes:

  1. SBTi adapter's tiny 33-entry country dict left most rows with
     country_code=NULL, dodging the partial unique index.
  2. upsert_company was read-then-INSERT, so concurrent adapter rows
     could both pass the SELECT and both INSERT.

This test file pins both fixes:

  - `_build_country_map` covers every country common in the SBTi CSV
    plus the aliases the CSV actually uses (USA, UK, etc.).
  - `upsert_company` emits an SQL string containing ON CONFLICT for
    both the non-null and null-country branches.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# _build_country_map — coverage of SBTi-common locations
# ---------------------------------------------------------------------------


class TestBuildCountryMap:
    """The SBTi public CSV uses ~80 distinct country/region strings. The
    reverse-map MUST resolve every common one — otherwise unmapped rows
    fall through to the 'XX' sentinel and the audit trail tells us we
    silently lost provenance for an entire jurisdiction.
    """

    @pytest.fixture(scope="class")
    def country_map(self):
        from app.domains.content.corporate.sbti_adapter import _build_country_map
        return _build_country_map()

    @pytest.mark.parametrize("name,expected", [
        # Core economies (canonical names from COUNTRY_NAMES)
        ("United States", "US"), ("United Kingdom", "GB"),
        ("Germany", "DE"), ("France", "FR"), ("Japan", "JP"),
        ("China", "CN"), ("India", "IN"), ("Brazil", "BR"),
        ("Canada", "CA"), ("Australia", "AU"), ("Sweden", "SE"),
        ("South Korea", "KR"), ("Switzerland", "CH"),
        # Aliases the SBTi CSV uses verbatim
        ("USA", "US"), ("UK", "GB"), ("Vietnam", "VN"),
        ("Czech Republic", "CZ"), ("Russian Federation", "RU"),
        ("Iran", "IR"), ("Venezuela", "VE"), ("Bolivia", "BO"),
        ("Tanzania", "TZ"), ("Cape Verde", "CV"),
        ("Côte d'Ivoire", "CI"), ("Ivory Coast", "CI"),
        ("Hong Kong SAR", "HK"), ("Macao", "MO"),
        # Case + whitespace normalisation
        ("  germany  ", "DE"), ("UNITED KINGDOM", "GB"),
    ])
    def test_resolves_common_sbti_location(self, country_map, name, expected):
        assert country_map.get(name.lower().strip()) == expected, (
            f"SBTi location {name!r} did not resolve to {expected} — would "
            f"fall through to 'XX' sentinel and lose country provenance"
        )

    def test_covers_at_least_150_countries(self, country_map):
        """Sanity: the reverse-map should pull from a ~190-entry source.
        If this regresses below 150, COUNTRY_NAMES probably got truncated."""
        unique_codes = set(country_map.values())
        assert len(unique_codes) >= 150, (
            f"Only {len(unique_codes)} unique ISO codes; expected ≥150 "
            f"from COUNTRY_NAMES + aliases"
        )


# ---------------------------------------------------------------------------
# upsert_company — ON CONFLICT contract
# ---------------------------------------------------------------------------


class TestUpsertCompanyOnConflict:
    """Race protection requires INSERT ... ON CONFLICT DO NOTHING RETURNING.
    A regression that drops the ON CONFLICT clause would silently re-open
    the dup window observed 2026-05-25. We assert the SQL string contains
    the right race-proof shape per code path.
    """

    def _make_db_returning_id(self, returned_id: str):
        """Mock db where execute_query returns one row with company_id."""
        db = MagicMock()
        db.execute_query.return_value = [{"company_id": returned_id}]
        db.execute_update.return_value = 1
        return db

    def test_insert_with_country_uses_non_null_partial_index(self):
        from app.domains.content.corporate.repository import upsert_company

        db = self._make_db_returning_id("00000000-0000-0000-0000-000000000001")
        # First execute_query is the strong-identifier SELECT — return empty
        # so the code falls through to the weak-fallback INSERT.
        db.execute_query.side_effect = [
            [],  # strong identifier SELECT — no match
            [{"company_id": "00000000-0000-0000-0000-000000000001"}],  # INSERT RETURNING
        ]

        upsert_company(db, "Acme Corp", country_code="DE")

        # Second execute_query call is the INSERT — assert the SQL shape.
        insert_call = db.execute_query.call_args_list[1]
        sql = insert_call[0][0]
        assert "INSERT INTO companies" in sql
        assert "ON CONFLICT" in sql
        assert "country_code IS NOT NULL" in sql
        assert "DO NOTHING" in sql
        assert "RETURNING company_id" in sql

    def test_insert_with_null_country_uses_null_partial_index(self):
        from app.domains.content.corporate.repository import upsert_company

        db = MagicMock()
        db.execute_query.side_effect = [
            [],  # strong identifier SELECT — no match
            [{"company_id": "00000000-0000-0000-0000-000000000002"}],  # INSERT RETURNING
        ]
        db.execute_update.return_value = 1

        upsert_company(db, "Unmapped Co", country_code=None)

        insert_call = db.execute_query.call_args_list[1]
        sql = insert_call[0][0]
        assert "INSERT INTO companies" in sql
        assert "ON CONFLICT" in sql
        assert "country_code IS NULL" in sql
        assert "DO NOTHING" in sql
        assert "RETURNING company_id" in sql

    def test_conflict_falls_back_to_select_canonical(self):
        """If INSERT...RETURNING returns no rows, a concurrent caller won;
        upsert_company MUST SELECT the canonical row rather than raise."""
        from app.domains.content.corporate.repository import upsert_company

        db = MagicMock()
        db.execute_query.side_effect = [
            [],  # strong identifier SELECT — no match
            [],  # INSERT...RETURNING — conflict, no rows returned
            [{"company_id": "canonical-uuid"}],  # canonical-resolution SELECT
        ]
        db.execute_update.return_value = 1

        result = upsert_company(db, "Race Co", country_code="DE")
        assert result == "canonical-uuid"
        # 3 execute_query calls: strong SELECT, INSERT, canonical-resolution SELECT.
        assert db.execute_query.call_count == 3
