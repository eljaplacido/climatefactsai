"""Net Zero Tracker adapter — ingests public NZT dataset.

Net Zero Tracker publishes a public CSV of corporate and national net-zero
pledges with quality assessments. Ingests company-level target data.

Source: https://zerotracker.net/insights
Data URL: https://zerotracker.net/api/v1/export/companies.csv
"""

from __future__ import annotations

import csv
import io
import logging

import httpx

from app.domains.content.corporate.repository import upsert_company, upsert_disclosure
from app.domains.content.corporate.schemas import DisclosureRecord

_logger = logging.getLogger("nzt_adapter")

NZT_CSV_URL = "https://zerotracker.net/api/v1/export/companies.csv"

SOURCE_NAME = "net_zero_tracker"


class NetZeroTrackerAdapter:
    source_name = SOURCE_NAME

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=60.0)

    async def sync(self, db) -> dict:
        count = 0
        errors = []
        try:
            resp = await self.client.get(NZT_CSV_URL)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    name = (row.get("name") or row.get("company_name") or "").strip()
                    if not name:
                        continue
                    cid = upsert_company(
                        db, name,
                        country_code=(row.get("country") or row.get("headquarters_country") or "")[:2] or None,
                    )
                    reporting_year = 2024
                    nz_target_year = _int(row.get("end_target") or row.get("target_year"))
                    upsert_disclosure(db, DisclosureRecord(
                        company_id=cid, source=SOURCE_NAME,
                        reporting_year=reporting_year,
                        sbti_validated=False,
                        net_zero_target_year=nz_target_year,
                        offset_based_claims="offset" if _bool(row.get("offset_usage")) else None,
                        assurance_level=row.get("integrity_assessment"),
                        methodology_version="nzt_2024",
                        raw_record=dict(row),
                    ))
                    count += 1
                except Exception as exc:
                    errors.append(str(exc))
        except Exception as exc:
            _logger.error(f"NZT sync failed: {exc}")
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


def _bool(v: any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "yes", "1", "y")
