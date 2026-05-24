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
        # Map a non-ISO country name → 2-char ISO. Tiny built-in subset;
        # unrecognised names just store NULL country_code.
        country_map = {
            "United States": "US", "United Kingdom": "GB", "Germany": "DE",
            "France": "FR", "Japan": "JP", "China": "CN", "India": "IN",
            "Canada": "CA", "Australia": "AU", "Brazil": "BR", "Italy": "IT",
            "Spain": "ES", "Netherlands": "NL", "Sweden": "SE", "Norway": "NO",
            "Finland": "FI", "Denmark": "DK", "Belgium": "BE", "Switzerland": "CH",
            "Austria": "AT", "Ireland": "IE", "Mexico": "MX", "South Korea": "KR",
            "South Africa": "ZA", "Singapore": "SG", "New Zealand": "NZ",
            "Saudi Arabia": "SA", "United Arab Emirates": "AE", "Indonesia": "ID",
            "Turkey": "TR", "Poland": "PL", "Portugal": "PT", "Greece": "GR",
        }
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
                    cid = upsert_company(
                        db, name,
                        isin=(row.get("isin") or "").strip()[:12] or None,
                        lei=(row.get("lei") or "").strip()[:20] or None,
                        country_code=country_map.get(location),
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
