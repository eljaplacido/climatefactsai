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

import httpx

from app.domains.content.corporate.repository import upsert_company, upsert_disclosure
from app.domains.content.corporate.schemas import DisclosureRecord

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
        """Sync SBTi target dashboard CSV.

        Schema as of 2026 (Google Sheets export):
          row_entry_id, sbti_id, company_name, isin, lei, location, region,
          sector, organization_type, validation_route, action, commitment_type,
          commitment_deadline, status, reason_for_commitment_extension_or_removal,
          full_target_language, company_temperature_alignment, target,
          target_wording, scope, target_value, type, sub_type,
          target_classification_short, base_year, target_year, year_type,
          date_published
        """
        count = 0
        errors = []
        country_map = _build_country_map()
        try:
            resp = await self.client.get(SBTI_CSV_URL)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    name = (row.get("company_name") or "").strip().strip('"')
                    if not name:
                        continue
                    location = (row.get("location") or "").strip()
                    # Slice 2 (2026-05-25) — fall back to 'XX' sentinel
                    # ("International") for unmapped locations so the
                    # partial unique index on (name, country_code) WHERE
                    # country_code IS NOT NULL covers every row. Without
                    # the sentinel, unmapped locations stored NULL and
                    # were free to duplicate (root cause of the dup
                    # re-pollution observed 2026-05-25).
                    resolved_cc = country_map.get(location.lower().strip())
                    if not resolved_cc and location:
                        resolved_cc = "XX"
                    cid = upsert_company(
                        db, name,
                        isin=(row.get("isin") or "").strip()[:12] or None,
                        lei=(row.get("lei") or "").strip()[:20] or None,
                        country_code=resolved_cc,
                        sector_nace=(row.get("sector") or "")[:8] or None,
                    )
                    target_year = _int(row.get("target_year"))
                    base_year = _int(row.get("base_year"))
                    # reporting_year: target_year if present, else base_year,
                    # else the year of the date_published cell, else 2024.
                    reporting_year = (
                        target_year or base_year
                        or _int((row.get("date_published") or "")[:4]) or 2024
                    )
                    status = (row.get("status") or "").lower()
                    action = (row.get("action") or "").lower()
                    upsert_disclosure(db, DisclosureRecord(
                        company_id=cid, source=SOURCE_NAME,
                        reporting_year=reporting_year,
                        sbti_validated=(
                            # SBTi-validated = the row IS a target (not just a
                            # commitment), and status is active. Commitments
                            # without targets aren't validation.
                            action == "target" and status == "active"
                        ),
                        target_year=target_year,
                        baseline_year=base_year,
                        target_pct_reduction=_float(row.get("target_value")),
                        # target_value of 1.0 = 100% reduction = "net zero"
                        # signal, but the explicit net-zero target lives
                        # elsewhere; only set it when commitment_type marks it.
                        net_zero_target_year=(
                            target_year
                            if "net zero" in (row.get("type") or "").lower()
                            else None
                        ),
                        methodology_version="sbti_corporate_net_zero_v1.2",
                        raw_record=dict(row),
                    ))
                    count += 1
                except Exception as exc:
                    errors.append(str(exc)[:200])
        except Exception as exc:
            _logger.error(f"SBTi sync failed: {exc}")
            errors.append(str(exc))
        # Cap errors list so a fully-broken sync doesn't return 100KB of text
        return {
            "source": SOURCE_NAME, "upserted": count,
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
