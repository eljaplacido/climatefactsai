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

# NZT public exports are JSON via their interactive map; no clean CSV
# endpoint as of 2026. Attempt the documented endpoints in order; if all
# fail, return a clean 200 with a documented warning rather than crashing.
NZT_CSV_URLS = [
    "https://zerotracker.net/data/companies.csv",
    "https://zerotracker.net/api/v1/export/companies.csv",
]

SOURCE_NAME = "net_zero_tracker"


class NetZeroTrackerAdapter:
    source_name = SOURCE_NAME

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    async def sync(self, db) -> dict:
        """Attempt NZT public CSV pull. Returns clean response either way.

        Known limitation (2026): NZT's CSV export was deprecated in favour
        of their interactive map's GraphQL endpoint. If both URLs 404,
        returns a documented warning so the operator UI sees "no live
        data" cleanly. Seed data (migration 034) covers the surface.
        """
        count = 0
        errors = []
        resp = None
        last_status: int | None = None
        for url in NZT_CSV_URLS:
            try:
                resp = await self.client.get(url)
                last_status = resp.status_code
                if resp.status_code == 200:
                    break
            except Exception as exc:
                errors.append(f"{url}: {str(exc)[:120]}")
        if resp is None or resp.status_code != 200:
            return {
                "source": SOURCE_NAME,
                "upserted": 0,
                "errors": errors[:50],
                "warning": (
                    f"NZT public CSV unavailable (last status: {last_status}). "
                    "Net Zero Tracker deprecated their CSV export in 2024 — "
                    "their data is now behind a GraphQL endpoint. Seed data "
                    "(migration 034) covers the surface; live integration "
                    "requires the GraphQL adapter."
                ),
            }
        try:
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
                    errors.append(str(exc)[:200])
        except Exception as exc:
            _logger.error(f"NZT sync failed: {exc}")
            errors.append(str(exc))
        return {
            "source": SOURCE_NAME, "upserted": count,
            "errors": errors[:50], "error_count": len(errors),
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


def _bool(v: any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "yes", "1", "y")
