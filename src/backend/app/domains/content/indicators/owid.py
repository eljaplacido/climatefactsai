"""Our World in Data adapter — canonical climate CSVs.

OWID maintains the de-facto reference datasets for climate journalism:
emissions, energy, and policy series, all open-licensed (CC-BY) and
versioned on GitHub. We pull two slices per sync:

  1. CO2 dataset (per-country, per-year emissions + energy)
     → emissions_tco2e_total (scaled from million-tonne CO2 column)
     → emissions_tco2e_per_capita
     → renewable_share_electricity_percent

OWID's CSVs are stable, public, and don't require auth, so the adapter is
a pure GET + csv.DictReader stream. ISO 3166-1 alpha-3 codes map to
alpha-2 the same way as Climate TRACE.

Note on data freshness: OWID typically lags by 1–2 years on emissions
(2024 numbers land mid-2026). The application layer should display the
year alongside the value so users aren't surprised.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import IndicatorAdapter, IndicatorRecord
from .climate_trace import ALPHA3_TO_ALPHA2  # share the alpha3→alpha2 mapping

_logger = logging.getLogger("indicators.owid")


class OWIDAdapter(IndicatorAdapter):
    """Pulls CO2 + renewable share data from OWID's public CSV.

    Source CSV: https://github.com/owid/co2-data
    Methodology: https://github.com/owid/co2-data/blob/master/README.md
    Licence: CC-BY 4.0 — attribution required, included via
    `indicator_definitions.methodology_url`.
    """

    source_name = "owid"
    methodology_url = "https://github.com/owid/co2-data/blob/master/README.md"

    CSV_URL = (
        "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
    )

    # OWID column → (indicator_id, transform)
    # `transform` converts the raw column value to the indicator's storage unit.
    # For emissions_tco2e_total: OWID reports `co2` in MILLION tonnes CO₂; we
    # store TONNES, so multiply by 1e6.
    COLUMN_MAP = {
        "co2": ("emissions_tco2e_total", lambda v: v * 1_000_000.0),
        "co2_per_capita": ("emissions_tco2e_per_capita", lambda v: v),
        "renewables_share_elec": (
            "renewable_share_electricity_percent",
            lambda v: v,
        ),
    }

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        request_timeout: float = 60.0,  # CSV is ~50 MB
        min_year: int = 2010,           # ignore older rows to keep table tight
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._request_timeout = request_timeout
        self._min_year = min_year

    async def fetch_records(self) -> AsyncIterator[IndicatorRecord]:
        client_cm: Optional[httpx.AsyncClient] = None
        try:
            if self._http_client is not None:
                client = self._http_client
            else:
                client_cm = httpx.AsyncClient(
                    timeout=self._request_timeout,
                    headers={"User-Agent": self.default_user_agent},
                )
                client = client_cm

            text = await self._fetch_csv_text(client, self.CSV_URL)

            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                alpha3 = (row.get("iso_code") or "").strip().upper()
                alpha2 = ALPHA3_TO_ALPHA2.get(alpha3)
                if not alpha2:
                    continue

                try:
                    year = int(row.get("year") or "")
                except ValueError:
                    continue
                if year < self._min_year:
                    continue

                for col, (indicator_id, transform) in self.COLUMN_MAP.items():
                    raw_value = row.get(col)
                    if raw_value is None or raw_value == "":
                        continue
                    try:
                        numeric = float(raw_value)
                    except (TypeError, ValueError):
                        continue

                    try:
                        stored_value = transform(numeric)
                    except Exception:  # transform raised — skip but log
                        _logger.debug(
                            "OWID transform raised for (%s, %s, %s, %s); skipping",
                            alpha2, indicator_id, year, raw_value,
                        )
                        continue

                    yield IndicatorRecord(
                        country_code=alpha2,
                        indicator_id=indicator_id,
                        year=year,
                        value=stored_value,
                        source_url=self.CSV_URL,
                        methodology_version="owid_co2_data_master",
                        raw_record={
                            "iso_code": alpha3,
                            "year": year,
                            "column": col,
                            "raw_value": raw_value,
                        },
                    )
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    # ------------------------------------------------------------------
    # Internal: fetch CSV with retry
    # ------------------------------------------------------------------

    async def _fetch_csv_text(self, client: httpx.AsyncClient, url: str) -> str:
        max_retries = 3
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and 400 <= exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    raise
                if attempt + 1 < max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        assert last_exc is not None
        raise last_exc
