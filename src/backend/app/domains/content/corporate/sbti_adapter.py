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
        count = 0
        errors = []
        try:
            resp = await self.client.get(SBTI_CSV_URL)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    name = (row.get("Company Name") or row.get("Organization") or "").strip()
                    if not name:
                        continue
                    cid = upsert_company(
                        db, name,
                        country_code=(row.get("Country") or row.get("HQ Country") or "")[:2] or None,
                    )
                    year = int(row.get("Target Year") or row.get("Year") or 2024)
                    upsert_disclosure(db, DisclosureRecord(
                        company_id=cid, source=SOURCE_NAME, reporting_year=year,
                        sbti_validated=(
                            row.get("Target Status", "").lower() in (
                                "targets set", "committed", "1.5°c", "well-below 2°c",
                            )
                        ),
                        target_year=_int(row.get("Target Year")),
                        baseline_year=_int(row.get("Base Year")),
                        target_pct_reduction=_float(row.get("Percent Reduction")),
                        net_zero_target_year=_int(row.get("Net Zero Target Year")),
                        methodology_version="sbti_corporate_net_zero_v1.2",
                        raw_record=dict(row),
                    ))
                    count += 1
                except Exception as exc:
                    errors.append(str(exc))
        except Exception as exc:
            _logger.error(f"SBTi sync failed: {exc}")
            errors.append(str(exc))
        return {"source": SOURCE_NAME, "upserted": count, "errors": errors}


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
