"""Corporate data access layer — company/disclosure/claim CRUD."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .schemas import CompanyClaim, CompanyProfile, DisclosureRecord

_logger = logging.getLogger("corporate_repo")


def upsert_company(db, name: str, **kwargs) -> str:
    """Insert or update a company, return company_id.

    Dedup strategy (in order — first match wins):
      1. Strong: ticker / isin / lei (DB-level UNIQUE constraints from mig 029)
      2. Weak fallback: case-insensitive name + country_code, guarded by
         partial unique indexes `uq_companies_name_country` (non-null cc)
         and `uq_companies_name_nocountry` (null cc; added in mig 043).

    Race protection (Slice 2, 2026-05-25): the weak-fallback INSERT uses
    `ON CONFLICT ... DO NOTHING RETURNING company_id`. If the RETURNING
    clause returns no rows, a concurrent caller won the race and we
    re-SELECT to fetch the canonical id. Pre-Slice-2 this was a
    read-then-INSERT race that re-populated dups every SBTi sync.
    """
    ticker = kwargs.get("ticker")
    isin = kwargs.get("isin")
    lei = kwargs.get("lei")
    cc = kwargs.get("country_code")
    sector = kwargs.get("sector_nace")

    # Strong dedup by identifier — DB-level UNIQUE constraints make these
    # race-safe; if a concurrent insert wins, the SELECT below catches it.
    existing = db.execute_query(
        "SELECT company_id FROM companies WHERE "
        "(ticker = :ticker AND :ticker IS NOT NULL) OR "
        "(isin = :isin AND :isin IS NOT NULL) OR "
        "(lei = :lei AND :lei IS NOT NULL) LIMIT 1",
        {"ticker": ticker, "isin": isin, "lei": lei},
    )
    if existing:
        company_id = str(existing[0]["company_id"])
        db.execute_update(
            """UPDATE companies SET name = :name, country_code = :country_code,
               sector_nace = :sector, updated_at = NOW() WHERE company_id = :id""",
            {"name": name, "country_code": cc, "sector": sector, "id": company_id},
        )
        return company_id

    # Weak-fallback INSERT with race-proof ON CONFLICT. The conflict target
    # must exactly match the partial unique index predicate, so we branch on
    # whether cc is NULL — each branch targets its dedicated partial index.
    new_id = str(uuid4())
    params = {
        "id": new_id, "name": name, "ticker": ticker, "cc": cc,
        "sector": sector, "isin": isin, "lei": lei,
    }
    if cc is not None:
        insert_sql = """
            INSERT INTO companies (company_id, name, ticker, country_code, sector_nace, isin, lei)
            VALUES (:id, :name, :ticker, :cc, :sector, :isin, :lei)
            ON CONFLICT (LOWER(TRIM(name)), country_code) WHERE country_code IS NOT NULL
            DO NOTHING
            RETURNING company_id
        """
    else:
        insert_sql = """
            INSERT INTO companies (company_id, name, ticker, country_code, sector_nace, isin, lei)
            VALUES (:id, :name, :ticker, :cc, :sector, :isin, :lei)
            ON CONFLICT (LOWER(TRIM(name))) WHERE country_code IS NULL
            DO NOTHING
            RETURNING company_id
        """
    rows = db.execute_query(insert_sql, params)
    if rows:
        return str(rows[0]["company_id"])

    # Conflict happened — a concurrent caller inserted the canonical row.
    canonical = db.execute_query(
        "SELECT company_id FROM companies WHERE "
        "LOWER(TRIM(name)) = LOWER(TRIM(:name)) "
        "AND (country_code = :cc OR (country_code IS NULL AND :cc IS NULL)) "
        "LIMIT 1",
        {"name": name, "cc": cc},
    )
    if canonical:
        return str(canonical[0]["company_id"])

    # Truly unreachable under normal conditions (either the INSERT returned
    # rows or the conflict resolution SELECT did). Surface loudly if hit.
    raise RuntimeError(
        f"upsert_company: could not insert or resolve canonical row for "
        f"name={name!r} country_code={cc!r}"
    )


def upsert_disclosure(db, record: DisclosureRecord) -> None:
    """Idempotent upsert on (company_id, source, reporting_year)."""
    db.execute_update(
        """INSERT INTO company_climate_disclosures (
               company_id, source, reporting_year, scope1_tco2e,
               scope2_tco2e_market, scope2_tco2e_location, scope3_tco2e,
               scope1_2_verified, sbti_validated, target_year, baseline_year,
               target_pct_reduction, net_zero_target_year, offset_based_claims,
               assurance_level, assurance_provider, methodology_version, raw_record
           ) VALUES (
               :cid, :source, :year, :s1, :s2m, :s2l, :s3,
               :verified, :sbti, :target_yr, :base_yr,
               :target_pct, :nz_yr, :offset, :assur_level, :assur_provider,
               :mv, CAST(:raw AS jsonb)
           )
           ON CONFLICT (company_id, source, reporting_year)
           DO UPDATE SET
               scope1_tco2e = EXCLUDED.scope1_tco2e,
               scope2_tco2e_market = EXCLUDED.scope2_tco2e_market,
               scope2_tco2e_location = EXCLUDED.scope2_tco2e_location,
               scope3_tco2e = EXCLUDED.scope3_tco2e,
               scope1_2_verified = EXCLUDED.scope1_2_verified,
               sbti_validated = EXCLUDED.sbti_validated,
               target_year = EXCLUDED.target_year,
               baseline_year = EXCLUDED.baseline_year,
               target_pct_reduction = EXCLUDED.target_pct_reduction,
               net_zero_target_year = EXCLUDED.net_zero_target_year,
               offset_based_claims = EXCLUDED.offset_based_claims,
               assurance_level = EXCLUDED.assurance_level,
               assurance_provider = EXCLUDED.assurance_provider,
               methodology_version = EXCLUDED.methodology_version,
               raw_record = EXCLUDED.raw_record,
               fetched_at = NOW()
           """,
        {
            "cid": record.company_id,
            "source": record.source,
            "year": record.reporting_year,
            "s1": record.scope1_tco2e,
            "s2m": record.scope2_tco2e_market,
            "s2l": record.scope2_tco2e_location,
            "s3": record.scope3_tco2e,
            "verified": record.scope1_2_verified,
            "sbti": record.sbti_validated,
            "target_yr": record.target_year,
            "base_yr": record.baseline_year,
            "target_pct": record.target_pct_reduction,
            "nz_yr": record.net_zero_target_year,
            "offset": record.offset_based_claims,
            "assur_level": record.assurance_level,
            "assur_provider": record.assurance_provider,
            "mv": record.methodology_version,
            "raw": json.dumps(record.raw_record) if record.raw_record else None,
        },
    )


def get_company(db, ticker_or_id: str) -> Optional[CompanyProfile]:
    # Phase 8 fix (2026-05-24): Postgres errors with InvalidTextRepresentation
    # when casting non-UUID strings (e.g. "MSFT") against the UUID column.
    # Detect UUIDs and use the right WHERE clause.
    import uuid as _uuid
    try:
        _uuid.UUID(str(ticker_or_id))
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    # CAST(:q AS uuid) instead of :q::uuid — the `::` PostgreSQL cast
    # collides with SQLAlchemy text() param-name parsing on some
    # versions, surfacing as a 500 on /api/companies/{uuid} even when
    # the same row resolves fine via the ticker path.
    where_clause = (
        "c.company_id = CAST(:q AS uuid)"
        if is_uuid
        else "c.ticker = :q"
    )
    rows = db.execute_query(
        f"""SELECT c.*,
                  COUNT(cd.disclosure_id) AS disclosure_count,
                  MAX(cd.reporting_year) AS latest_disclosure_year,
                  BOOL_OR(cd.sbti_validated) AS sbti_validated,
                  MAX(cd.net_zero_target_year) AS net_zero_target_year
           FROM companies c
           LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
           WHERE {where_clause}
           GROUP BY c.company_id LIMIT 1""",
        {"q": ticker_or_id},
    )
    if not rows:
        return None
    r = rows[0]
    return CompanyProfile(
        company_id=str(r["company_id"]),
        name=r["name"],
        ticker=r.get("ticker"),
        country_code=r.get("country_code"),
        sector_nace=r.get("sector_nace"),
        disclosure_count=int(r.get("disclosure_count") or 0),
        latest_disclosure_year=r.get("latest_disclosure_year"),
        sbti_validated=bool(r.get("sbti_validated", False)),
        net_zero_target_year=r.get("net_zero_target_year"),
    )


def list_companies(
    db,
    limit: int = 50,
    offset: int = 0,
    sort: str = "richness",
    has_climate_data: bool = False,
    sbti_only: bool = False,
) -> List[dict]:
    """List companies with climate-disclosure summary.

    Golden Example fix (2026-05-27): the user saw "No company data
    ingested yet" because the default sort was alphabetical and the
    first 200 rows were obscure SBTi-listed shell companies with no
    ticker/sector/scope data. Switched default to rank-by-richness so
    the well-known companies with comprehensive disclosures surface
    first.

    Args:
        sort: "richness" (sbti_validated + disclosure_count + ticker
              first, default) | "name" (alphabetical) | "recent"
              (latest disclosure year).
        has_climate_data: filter to companies with at least one
              disclosure carrying scope1 OR sbti_validated OR
              net_zero_target_year.
        sbti_only: filter to companies with at least one
              sbti_validated=TRUE disclosure.
    """
    where_clauses = []
    if has_climate_data:
        # Match the `with_disclosures` stat definition: any substance
        # field non-null (scope1/2/3 OR sbti OR net-zero OR target%).
        # Previously the filter only checked scope1/sbti/net-zero, so a
        # company with only scope3 disclosed got hidden — diverging from
        # what the headline badge counted.
        # NOTE: scope2 in the schema is split into market vs location
        # variants (mig 029) — match either.
        where_clauses.append(
            "(MAX(CASE WHEN cd.scope1_tco2e IS NOT NULL THEN 1 ELSE 0 END) = 1 "
            "OR MAX(CASE WHEN cd.scope2_tco2e_market IS NOT NULL THEN 1 ELSE 0 END) = 1 "
            "OR MAX(CASE WHEN cd.scope2_tco2e_location IS NOT NULL THEN 1 ELSE 0 END) = 1 "
            "OR MAX(CASE WHEN cd.scope3_tco2e IS NOT NULL THEN 1 ELSE 0 END) = 1 "
            "OR BOOL_OR(cd.sbti_validated) = TRUE "
            "OR MAX(cd.net_zero_target_year) IS NOT NULL "
            "OR MAX(cd.target_pct_reduction) IS NOT NULL)"
        )
    if sbti_only:
        where_clauses.append("BOOL_OR(cd.sbti_validated) = TRUE")
    having_sql = ("HAVING " + " AND ".join(where_clauses)) if where_clauses else ""

    order_sql = {
        "richness": (
            # Composite richness rank: sbti+scope+net_zero coverage,
            # then disclosure count, then ticker first (well-known
            # publicly-traded companies usually have one), then name.
            "ORDER BY "
            "(MAX(CASE WHEN cd.sbti_validated THEN 1 ELSE 0 END) "
            " + MAX(CASE WHEN cd.scope1_tco2e IS NOT NULL THEN 1 ELSE 0 END) "
            " + MAX(CASE WHEN cd.net_zero_target_year IS NOT NULL THEN 1 ELSE 0 END)) DESC, "
            "COUNT(cd.disclosure_id) DESC, "
            "(c.ticker IS NOT NULL) DESC, "
            "c.name"
        ),
        "name": "ORDER BY c.name",
        "recent": "ORDER BY MAX(cd.reporting_year) DESC NULLS LAST, c.name",
    }.get(sort, "ORDER BY c.name")

    rows = db.execute_query(
        f"""SELECT c.*,
                   COUNT(cd.disclosure_id) AS disclosure_count,
                   MAX(cd.reporting_year) AS latest_year,
                   BOOL_OR(cd.sbti_validated) AS sbti_validated,
                   MAX(cd.net_zero_target_year) AS net_zero_target_year,
                   MAX(cd.scope1_tco2e) AS scope1_tco2e,
                   MAX(cd.scope3_tco2e) AS scope3_tco2e,
                   MAX(cd.target_pct_reduction) AS target_pct_reduction
            FROM companies c
            LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
            GROUP BY c.company_id
            {having_sql}
            {order_sql}
            LIMIT :limit OFFSET :offset""",
        {"limit": limit, "offset": offset},
    )
    return [
        {
            "company_id": str(r["company_id"]),
            "name": r["name"],
            "ticker": r.get("ticker"),
            "country_code": r.get("country_code"),
            "sector_nace": r.get("sector_nace"),
            "disclosure_count": int(r.get("disclosure_count") or 0),
            "latest_disclosure_year": r.get("latest_year"),
            # Polish (2026-05-27): include climate signals directly in the
            # list response so the FE card can preview scope/SBTi/net-zero
            # without a per-row /companies/{ticker} round trip.
            "sbti_validated": bool(r.get("sbti_validated", False)),
            "net_zero_target_year": r.get("net_zero_target_year"),
            "scope1_tco2e": r.get("scope1_tco2e"),
            "scope3_tco2e": r.get("scope3_tco2e"),
            "target_pct_reduction": r.get("target_pct_reduction"),
        }
        for r in (rows or [])
    ]


def companies_stats(db) -> dict:
    """Top-line stats for the /companies index banner.

    `with_disclosures` previously counted any joined row in
    company_climate_disclosures, but every imported company gets a
    placeholder row at import time — so the stat was always equal to
    total_companies and the badge read "14,797 / 14,797" misleadingly.
    Honest definition: a company "has climate disclosures" only when
    at least one substance field (scope1/2/3, sbti, net-zero, target%)
    is non-null. This makes the headline match the `has_climate_data`
    filter the user toggles in the UI.
    """
    rows = db.execute_query(
        """SELECT COUNT(DISTINCT c.company_id) AS total_companies,
                  COUNT(DISTINCT CASE
                      WHEN cd.scope1_tco2e IS NOT NULL
                        OR cd.scope2_tco2e_market IS NOT NULL
                        OR cd.scope2_tco2e_location IS NOT NULL
                        OR cd.scope3_tco2e IS NOT NULL
                        OR cd.sbti_validated = TRUE
                        OR cd.net_zero_target_year IS NOT NULL
                        OR cd.target_pct_reduction IS NOT NULL
                      THEN cd.company_id END) AS with_disclosures,
                  COUNT(DISTINCT CASE WHEN cd.sbti_validated THEN cd.company_id END) AS sbti_validated,
                  COUNT(DISTINCT CASE WHEN cd.net_zero_target_year IS NOT NULL
                                       AND cd.scope1_tco2e IS NOT NULL
                                       AND cd.sbti_validated THEN cd.company_id END) AS fully_disclosed
           FROM companies c
           LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id""",
        {},
    )
    r = rows[0] if rows else {}
    return {
        "total_companies": int(r.get("total_companies") or 0),
        "with_disclosures": int(r.get("with_disclosures") or 0),
        "sbti_validated": int(r.get("sbti_validated") or 0),
        "fully_disclosed": int(r.get("fully_disclosed") or 0),
    }


def get_company_disclosures(db, company_id: str, source: Optional[str] = None) -> List[dict]:
    where = "WHERE cd.company_id = :cid"
    params: dict = {"cid": company_id}
    if source:
        where += " AND cd.source = :src"
        params["src"] = source
    rows = db.execute_query(
        f"""SELECT cd.*, c.name AS company_name, c.ticker
            FROM company_climate_disclosures cd
            JOIN companies c ON c.company_id = cd.company_id
            {where}
            ORDER BY cd.reporting_year DESC""",
        params,
    )
    return [_disclosure_row(r) for r in (rows or [])]


def get_company_claims(db, company_id: str) -> List[dict]:
    rows = db.execute_query(
        """SELECT * FROM company_claims
           WHERE company_id = :cid
           ORDER BY created_at DESC LIMIT 50""",
        {"cid": company_id},
    )
    return [
        {
            "claim_id": str(r["claim_id"]),
            "claim_text": r["claim_text"],
            "claim_type": r.get("claim_type"),
            "verdict": r.get("verdict"),
            "evidence_url": r.get("evidence_url"),
            "flag_reason": r.get("flag_reason"),
            "created_at": str(r["created_at"]) if r.get("created_at") else None,
        }
        for r in (rows or [])
    ]


def upsert_company_claim(db, claim: CompanyClaim) -> str:
    claim_id = str(uuid4())
    db.execute_update(
        """INSERT INTO company_claims (claim_id, company_id, claim_text, claim_type,
           verdict, evidence_url, flag_reason, methodology_version)
           VALUES (:id, :cid, :text, :type, :verdict, :url, :flag, :mv)""",
        {
            "id": claim_id, "cid": claim.company_id, "text": claim.claim_text,
            "type": claim.claim_type, "verdict": claim.verdict,
            "url": claim.evidence_url, "flag": claim.flag_reason,
            "mv": claim.methodology_version,
        },
    )
    return claim_id


def _disclosure_row(r: dict) -> dict:
    return {
        "disclosure_id": str(r["disclosure_id"]),
        "company_id": str(r["company_id"]),
        "company_name": r.get("company_name"),
        "ticker": r.get("ticker"),
        "source": r.get("source"),
        "reporting_year": r.get("reporting_year"),
        "scope1_tco2e": r.get("scope1_tco2e"),
        "scope2_tco2e_market": r.get("scope2_tco2e_market"),
        "scope2_tco2e_location": r.get("scope2_tco2e_location"),
        "scope3_tco2e": r.get("scope3_tco2e"),
        "scope1_2_verified": bool(r.get("scope1_2_verified", False)),
        "sbti_validated": bool(r.get("sbti_validated", False)),
        "target_year": r.get("target_year"),
        "baseline_year": r.get("baseline_year"),
        "target_pct_reduction": r.get("target_pct_reduction"),
        "net_zero_target_year": r.get("net_zero_target_year"),
        "offset_based_claims": r.get("offset_based_claims"),
        "assurance_level": r.get("assurance_level"),
        "assurance_provider": r.get("assurance_provider"),
    }
