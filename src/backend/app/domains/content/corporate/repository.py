"""Corporate data access layer — company/disclosure/claim CRUD."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .schemas import CompanyClaim, CompanyProfile, DisclosureRecord

_logger = logging.getLogger("corporate_repo")


def upsert_company(db, name: str, **kwargs) -> str:
    """Insert or update a company, return company_id."""
    existing = db.execute_query(
        "SELECT company_id FROM companies WHERE "
        "(ticker = :ticker AND :ticker IS NOT NULL) OR "
        "(isin = :isin AND :isin IS NOT NULL) OR "
        "(lei = :lei AND :lei IS NOT NULL) LIMIT 1",
        {
            "ticker": kwargs.get("ticker"),
            "isin": kwargs.get("isin"),
            "lei": kwargs.get("lei"),
        },
    )
    if existing:
        company_id = str(existing[0]["company_id"])
        db.execute_update(
            """UPDATE companies SET name = :name, country_code = :country_code,
               sector_nace = :sector, updated_at = NOW() WHERE company_id = :id""",
            {
                "name": name,
                "country_code": kwargs.get("country_code"),
                "sector": kwargs.get("sector_nace"),
                "id": company_id,
            },
        )
        return company_id

    company_id = str(uuid4())
    db.execute_update(
        """INSERT INTO companies (company_id, name, ticker, country_code, sector_nace, isin, lei)
           VALUES (:id, :name, :ticker, :cc, :sector, :isin, :lei)""",
        {
            "id": company_id,
            "name": name,
            "ticker": kwargs.get("ticker"),
            "cc": kwargs.get("country_code"),
            "sector": kwargs.get("sector_nace"),
            "isin": kwargs.get("isin"),
            "lei": kwargs.get("lei"),
        },
    )
    return company_id


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
    rows = db.execute_query(
        """SELECT c.*,
                  COUNT(cd.disclosure_id) AS disclosure_count,
                  MAX(cd.reporting_year) AS latest_disclosure_year,
                  BOOL_OR(cd.sbti_validated) AS sbti_validated,
                  MAX(cd.net_zero_target_year) AS net_zero_target_year
           FROM companies c
           LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
           WHERE c.ticker = :q OR c.company_id = :q
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


def list_companies(db, limit: int = 50, offset: int = 0) -> List[dict]:
    rows = db.execute_query(
        """SELECT c.*, COUNT(cd.disclosure_id) AS disclosure_count,
                  MAX(cd.reporting_year) AS latest_year
           FROM companies c
           LEFT JOIN company_climate_disclosures cd ON cd.company_id = c.company_id
           GROUP BY c.company_id
           ORDER BY c.name LIMIT :limit OFFSET :offset""",
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
        }
        for r in (rows or [])
    ]


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
