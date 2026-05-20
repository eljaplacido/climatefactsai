"""CDP open data adapter — ingests public CDP corporate disclosures.

CDP publishes an annual public dataset subset (company-level emissions,
scope coverage, and target data). This adapter downloads the latest CSV,
parses it, and upserts into company_climate_disclosures.

API: No auth required for the public CSV export.
Source: https://www.cdp.net/en/data
"""

from __future__ import annotations

import csv
import io
import logging
from typing import AsyncIterator

import httpx

from app.domains.content.corporate.repository import upsert_company, upsert_disclosure
from app.domains.content.corporate.schemas import DisclosureRecord

_logger = logging.getLogger("cdp_adapter")

CDP_PUBLIC_CSV_URL = "https://cdn.cdp.net/cdp-production/comfy_datasets/public-2024/2024_public_full_export.csv"

SOURCE_NAME = "cdp"


class CDPAdapter:
    source_name = SOURCE_NAME

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=60.0)

    async def sync(self, db) -> dict:
        count = 0
        errors = []
        try:
            resp = await self.client.get(CDP_PUBLIC_CSV_URL)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    name = (row.get("organization") or row.get("account_name") or "").strip()
                    if not name:
                        continue
                    ticker = (row.get("ticker") or row.get("isin") or "").strip()[:16] or None
                    cid = upsert_company(
                        db, name,
                        ticker=ticker,
                        country_code=(row.get("country") or "")[:2] or None,
                    )
                    year = int(row.get("reporting_year") or row.get("year") or 0)
                    if year < 2010:
                        continue
                    upsert_disclosure(db, DisclosureRecord(
                        company_id=cid, source=SOURCE_NAME, reporting_year=year,
                        scope1_tco2e=_float(row.get("scope1_tco2e")),
                        scope2_tco2e_market=_float(row.get("scope2_tco2e_market")),
                        scope2_tco2e_location=_float(row.get("scope2_tco2e_location")),
                        scope3_tco2e=_float(row.get("scope3_tco2e")),
                        scope1_2_verified=row.get("verification_status", "").lower() in (
                            "verified", "third party verified", "limited assurance",
                            "reasonable assurance",
                        ),
                        assurance_level=row.get("verification_status"),
                        methodology_version="cdp_2024",
                        raw_record=dict(row),
                    ))
                    count += 1
                except Exception as exc:
                    errors.append(str(exc))
        except Exception as exc:
            _logger.error(f"CDP sync failed: {exc}")
            errors.append(str(exc))
        return {"source": SOURCE_NAME, "upserted": count, "errors": errors}


def _float(v: any) -> float | None:
    try:
        return float(v) if v else None
    except (ValueError, TypeError):
        return None
