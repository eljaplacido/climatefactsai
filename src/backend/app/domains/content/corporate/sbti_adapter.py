"""SBTi commitments adapter — ingests public Science Based Targets data.

SBTi publishes a public CSV of company commitments (target year, baseline
year, scope coverage, validation status). This adapter downloads and upserts.

Source: https://sciencebasedtargets.org/companies-taking-action
Data URL: https://sciencebasedtargets.org/target-dashboard
"""

from __future__ import annotations

import csv
import io
import logging
from uuid import uuid4

import httpx

_logger = logging.getLogger("sbti_adapter")

SBTI_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRUls6LEAlOAGCEXuLdOZ"
    "DNYiFmf_VJHh5Gz1cdKKoaLQQx832pyr9ynbFJDgJM3KorP5u97ODewQmx/pub?output=csv"
)

SOURCE_NAME = "sbti"


# Aliases the SBTi CSV uses that don't appear verbatim in COUNTRY_NAMES
# (formal name vs common name, abbreviations, historical names).
_COUNTRY_ALIASES: dict[str, str] = {
    "USA": "US", "U.S.A.": "US", "U.S.": "US", "United States of America": "US",
    "UK": "GB", "U.K.": "GB", "Great Britain": "GB", "England": "GB",
    "Scotland": "GB", "Wales": "GB", "Northern Ireland": "GB",
    "South Korea": "KR", "Republic of Korea": "KR", "Korea, South": "KR",
    "Korea": "KR",  # ambiguous — defaults to South per SBTi data convention
    "North Korea": "KP", "Korea, North": "KP",
    "Czech Republic": "CZ",
    "Slovak Republic": "SK",
    "Russian Federation": "RU",
    "Vietnam": "VN", "Viet Nam": "VN",
    "Iran": "IR", "Iran, Islamic Republic of": "IR",
    "Syria": "SY", "Syrian Arab Republic": "SY",
    "Venezuela": "VE", "Venezuela, Bolivarian Republic of": "VE",
    "Bolivia": "BO", "Bolivia, Plurinational State of": "BO",
    "Tanzania": "TZ", "Tanzania, United Republic of": "TZ",
    "Moldova": "MD", "Moldova, Republic of": "MD",
    "Macedonia": "MK", "Republic of North Macedonia": "MK",
    "Macedonia, The Former Yugoslav Republic of": "MK",
    "Taiwan, Province of China": "TW",
    "Hong Kong SAR": "HK", "Hong Kong, China": "HK",
    "Macao": "MO", "Macau": "MO", "Macao SAR": "MO",
    "Côte d'Ivoire": "CI", "Cote d'Ivoire": "CI", "Ivory Coast": "CI",
    "Cape Verde": "CV", "Cabo Verde": "CV",
    "Brunei Darussalam": "BN",
    "Lao People's Democratic Republic": "LA", "Laos": "LA",
    "Myanmar (Burma)": "MM", "Burma": "MM",
    "Palestine, State of": "PS",
    "Congo, Democratic Republic of the": "CD", "DRC": "CD",
    "Republic of the Congo": "CG", "Congo-Brazzaville": "CG",
    "Holy See (Vatican City State)": "VA", "Holy See": "VA",
}


def _build_country_map() -> dict[str, str]:
    """Reverse the COUNTRY_NAMES dict (ISO→name) into name→ISO, plus aliases.

    Returns a case-insensitive lookup keyed by lower-stripped country name.
    Covers ~190 countries from forecast_service.COUNTRY_NAMES plus the
    common alternative spellings the SBTi CSV actually uses.
    """
    # Imported lazily so a missing forecast_service at test-time doesn't
    # crash the import path.
    from app.domains.content.forecast_service import COUNTRY_NAMES

    out: dict[str, str] = {}
    for code, name in COUNTRY_NAMES.items():
        out[name.lower().strip()] = code
    for alias, code in _COUNTRY_ALIASES.items():
        out[alias.lower().strip()] = code
    return out


class SBTIAdapter:
    source_name = SOURCE_NAME

    def __init__(self) -> None:
        # follow_redirects=True for the sciencebasedtargets.org → Google Sheets
        # hop that happens 2024 onwards.
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    async def sync(self, db) -> dict:
        """Sync SBTi target dashboard CSV — BATCHED (2026-06-04, seq-7 batch).

        Schema (Google Sheets export): row_entry_id, sbti_id, company_name,
        isin, lei, location, region, sector, organization_type,
        validation_route, action, commitment_type, commitment_deadline, status,
        ..., target, ..., target_value, type, ..., base_year, target_year,
        ..., date_published.

        Throughput: the old per-row path did ~3 DB round-trips × 38k rows
        (~114k sequential round-trips), so a full sync took hours/never. This
        aggregates the CSV per (name, country) and per (name, country, year) in
        Python, bulk-resolves company_ids in ONE query, batch-inserts only the
        missing companies, and batch-upserts disclosures in chunks of 500 —
        ~100 round-trips total, completing in ~1-2 minutes.
        """
        errors: list[str] = []
        country_map = _build_country_map()
        try:
            resp = await self.client.get(SBTI_CSV_URL)
            resp.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(resp.text)))
        except Exception as exc:
            _logger.error(f"SBTi fetch failed: {exc}")
            return {"source": SOURCE_NAME, "upserted": 0,
                    "errors": [str(exc)[:300]], "error_count": 1}

        companies, disclosures = _aggregate_sbti_rows(rows, country_map)

        upserted = 0
        try:
            cmap = _resolve_company_ids(db, companies)
            missing = [c for k, c in companies.items() if k not in cmap]
            _batch_insert_companies(db, [c for c in missing if c["cc"] is not None], with_country=True)
            _batch_insert_companies(db, [c for c in missing if c["cc"] is None], with_country=False)
            cmap = _resolve_company_ids(db, companies)  # re-resolve incl. new rows
            upserted = _batch_upsert_disclosures(db, disclosures, cmap)
        except Exception as exc:
            _logger.error(f"SBTi batch sync failed: {exc}")
            errors.append(str(exc)[:300])

        return {
            "source": SOURCE_NAME,
            "upserted": upserted,
            "companies_seen": len(companies),
            "disclosures": len(disclosures),
            "errors": errors[:50],
            "error_count": len(errors),
        }


def _float(v: any) -> float | None:
    try:
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def _int(v: any) -> int | None:
    try:
        return int(float(v)) if v else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Batched sync helpers (seq-7 batch, 2026-06-04)
# ---------------------------------------------------------------------------

def _aggregate_sbti_rows(rows: list, country_map: dict):
    """Pure (DB-free, testable): collapse the 38k CSV rows into dedup'd
    companies + disclosures.

    A company is SBTi-VALIDATED when it has any row with status "Target set"
    (SBTi approved a science-based target). The dashboard splits a company
    across rows: action="Commitment" rows carry the lifecycle `status`, while
    action="Target" rows carry the target DETAILS with status="NA" — so the
    legacy `status=="active"` test could never match. Dedup key is
    (lower(name), country_code) to match the DB's partial unique index;
    disclosures key adds reporting_year. Returns (companies, disclosures) where
    companies[(nk,cc)] = {name, cc, sector, isin, lei} and
    disclosures[(nk,cc,year)] = {ckey, reporting_year, sbti_validated, ...}.
    """
    validated = {
        (r.get("company_name") or "").strip().strip('"').lower()
        for r in rows
        if (r.get("status") or "").strip().lower() == "target set"
        and (r.get("company_name") or "").strip()
    }
    companies: dict = {}
    disclosures: dict = {}
    for row in rows:
        name = (row.get("company_name") or "").strip().strip('"')
        if not name:
            continue
        location = (row.get("location") or "").strip()
        # 'XX' sentinel for present-but-unmapped locations (so the partial
        # unique index covers them); None only when location is blank.
        cc = country_map.get(location.lower().strip()) or ("XX" if location else None)
        nk = name.lower()
        ckey = (nk, cc)
        c = companies.get(ckey)
        isin = (row.get("isin") or "").strip()[:12] or None
        lei = (row.get("lei") or "").strip()[:20] or None
        sector = (row.get("sector") or "")[:8] or None
        if c is None:
            companies[ckey] = {"name": name, "cc": cc, "sector": sector, "isin": isin, "lei": lei}
        else:
            c["isin"] = c["isin"] or isin
            c["lei"] = c["lei"] or lei
            c["sector"] = c["sector"] or sector

        target_year = _int(row.get("target_year"))
        base_year = _int(row.get("base_year"))
        reporting_year = (
            target_year or base_year
            or _int((row.get("date_published") or "")[:4]) or 2024
        )
        is_validated = nk in validated
        is_net_zero = any(
            "net-zero" in (row.get(col) or "").lower() or "net zero" in (row.get(col) or "").lower()
            for col in ("target", "commitment_type", "type")
        )
        tpr = _float(row.get("target_value"))
        nz = target_year if is_net_zero else None
        dkey = (nk, cc, reporting_year)
        d = disclosures.get(dkey)
        if d is None:
            disclosures[dkey] = {
                "ckey": ckey, "reporting_year": reporting_year,
                "sbti_validated": is_validated, "target_year": target_year,
                "baseline_year": base_year, "target_pct_reduction": tpr,
                "net_zero_target_year": nz,
            }
        else:
            d["sbti_validated"] = d["sbti_validated"] or is_validated
            d["target_year"] = d["target_year"] or target_year
            d["baseline_year"] = d["baseline_year"] or base_year
            if d["target_pct_reduction"] is None:
                d["target_pct_reduction"] = tpr
            d["net_zero_target_year"] = d["net_zero_target_year"] or nz
    return companies, disclosures


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _resolve_company_ids(db, companies: dict) -> dict:
    """One bulk SELECT mapping (lower(name), country_code) -> company_id, then
    filtered to the keys we care about. country_code may be None."""
    rows = db.execute_query(
        "SELECT company_id, LOWER(TRIM(name)) AS nk, country_code AS cc FROM companies"
    ) or []
    full = {(r["nk"], r["cc"]): str(r["company_id"]) for r in rows}
    return {k: full[k] for k in companies if k in full}


def _batch_insert_companies(db, items: list, with_country: bool) -> None:
    """Batch-insert NEW companies, dedup'd on the (name, country) partial unique
    index. isin/lei are intentionally omitted — they carry their own UNIQUE
    constraints which a single ON CONFLICT can't cover, so including them would
    break the batch on a stray duplicate identifier. Existing companies already
    carry their identifiers; new SBTi rows rarely have a reliable isin/lei."""
    if not items:
        return
    conflict = (
        "(LOWER(TRIM(name)), country_code) WHERE country_code IS NOT NULL"
        if with_country else "(LOWER(TRIM(name))) WHERE country_code IS NULL"
    )
    for chunk in _chunks(items, 500):
        vals, params = [], {}
        for i, c in enumerate(chunk):
            params[f"id{i}"] = str(uuid4())
            params[f"n{i}"] = c["name"]
            params[f"cc{i}"] = c["cc"]
            params[f"s{i}"] = c["sector"]
            vals.append(f"(:id{i}, :n{i}, :cc{i}, :s{i})")
        db.execute_update(
            "INSERT INTO companies (company_id, name, country_code, sector_nace) "
            f"VALUES {','.join(vals)} ON CONFLICT {conflict} DO NOTHING",
            params,
        )


def _batch_upsert_disclosures(db, disclosures: dict, cmap: dict) -> int:
    """Batch-upsert disclosures (chunks of 500). Merges on conflict: keeps the
    validated flag if either side has it, prefers non-null target details."""
    items = [(cmap[d["ckey"]], d) for d in disclosures.values() if d["ckey"] in cmap]
    upserted = 0
    for chunk in _chunks(items, 500):
        vals, params = [], {}
        for i, (cid, d) in enumerate(chunk):
            params[f"cid{i}"] = cid
            params[f"yr{i}"] = d["reporting_year"]
            params[f"v{i}"] = bool(d["sbti_validated"])
            params[f"ty{i}"] = d["target_year"]
            params[f"by{i}"] = d["baseline_year"]
            params[f"tp{i}"] = d["target_pct_reduction"]
            params[f"nz{i}"] = d["net_zero_target_year"]
            vals.append(
                f"(:cid{i}, 'sbti', :yr{i}, :v{i}, :ty{i}, :by{i}, :tp{i}, :nz{i}, "
                "'sbti_corporate_net_zero_v1.2')"
            )
        db.execute_update(
            "INSERT INTO company_climate_disclosures (company_id, source, "
            "reporting_year, sbti_validated, target_year, baseline_year, "
            "target_pct_reduction, net_zero_target_year, methodology_version) "
            f"VALUES {','.join(vals)} "
            "ON CONFLICT (company_id, source, reporting_year) DO UPDATE SET "
            "sbti_validated = EXCLUDED.sbti_validated OR company_climate_disclosures.sbti_validated, "
            "target_year = COALESCE(EXCLUDED.target_year, company_climate_disclosures.target_year), "
            "baseline_year = COALESCE(EXCLUDED.baseline_year, company_climate_disclosures.baseline_year), "
            "target_pct_reduction = COALESCE(EXCLUDED.target_pct_reduction, company_climate_disclosures.target_pct_reduction), "
            "net_zero_target_year = COALESCE(EXCLUDED.net_zero_target_year, company_climate_disclosures.net_zero_target_year), "
            "fetched_at = NOW()",
            params,
        )
        upserted += len(chunk)
    return upserted
