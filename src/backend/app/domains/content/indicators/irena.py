"""IRENA renewable-capacity adapter — Phase 3 wave 6.

Source: International Renewable Energy Agency (IRENA) statistics.
Methodology: https://www.irena.org/Statistics

Records `renewable_capacity_mw` (installed renewable electricity capacity in MW)
per country per year. Cross-validates the `renewable_share_electricity_percent`
already pulled from OWID with an independent authoritative source from
the energy/policy domain.

IRENA's primary public-data interface is the Statistics download portal,
which is XLSX-heavy and not friendly to parse. OWID re-publishes the
canonical IRENA "Renewable Capacity Statistics" series as a stable CSV
that we can stream:

    https://ourworldindata.org/grapher/installed-solar-capacity.csv
    https://ourworldindata.org/grapher/installed-wind-capacity.csv
    https://ourworldindata.org/grapher/hydropower-installed-capacity.csv

We aggregate solar + wind + hydro into a single
`renewable_capacity_mw` value per country-year. Geothermal/bioenergy
are smaller contributors and can be added later via the same pattern —
the adapter's `capacity_csv_urls` constructor param exposes the list
so the operator can extend without modifying code.

When a country appears in some but not all source CSVs, the partial
sum is recorded (with the contributing technologies enumerated in
raw_record). The application layer's uncertainty propagation can
account for partial coverage.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from .base import IndicatorAdapter, IndicatorRecord
from .climate_trace import ALPHA3_TO_ALPHA2

_logger = logging.getLogger("indicators.irena")


# OWID grapher CSVs default URLs. Each contains columns:
#   Entity (country name), Code (ISO3), Year, <single-tech capacity column>
DEFAULT_CAPACITY_CSV_URLS: List[Tuple[str, str]] = [
    ("solar",  "https://ourworldindata.org/grapher/installed-solar-capacity.csv?v=1"),
    ("wind",   "https://ourworldindata.org/grapher/installed-wind-capacity.csv?v=1"),
    ("hydro",  "https://ourworldindata.org/grapher/hydropower-installed-capacity.csv?v=1"),
]


def _capacity_column_for_csv(headers: List[str]) -> Optional[str]:
    """Find the technology-capacity column in an OWID grapher CSV.

    The CSV always has Entity / Code / Year, then one trailing column
    whose name carries the technology + unit (e.g. "Solar Capacity").
    We pick the first column not in the fixed set.
    """
    fixed = {"entity", "code", "year"}
    for header in headers:
        if header.strip().lower() not in fixed:
            return header
    return None


class IRENAAdapter(IndicatorAdapter):
    """Aggregates renewable capacity (solar + wind + hydro) per country-year."""

    source_name = "irena"
    methodology_url = "https://www.irena.org/Statistics"

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        capacity_csv_urls: Optional[List[Tuple[str, str]]] = None,
        request_timeout: float = 60.0,
        min_year: int = 2010,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._capacity_csv_urls = (
            list(capacity_csv_urls)
            if capacity_csv_urls is not None
            else list(DEFAULT_CAPACITY_CSV_URLS)
        )
        self._request_timeout = request_timeout
        self._min_year = min_year
        self._max_retries = max_retries

    async def fetch_records(self) -> AsyncIterator[IndicatorRecord]:
        # Aggregate by (alpha2, year) → {tech: mw}.
        aggregate: Dict[Tuple[str, int], Dict[str, float]] = defaultdict(dict)

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

            for tech, url in self._capacity_csv_urls:
                try:
                    text = await self._fetch_csv_text(client, url)
                except Exception as exc:
                    # One bad source CSV shouldn't abort the whole sync.
                    _logger.warning(
                        "IRENA: skipping %s (fetch failed): %s", tech, exc,
                    )
                    continue

                reader = csv.DictReader(io.StringIO(text))
                if not reader.fieldnames:
                    continue
                capacity_col = _capacity_column_for_csv(list(reader.fieldnames))
                if not capacity_col:
                    _logger.warning(
                        "IRENA: cannot locate capacity column in %s; skipping", url,
                    )
                    continue

                for row in reader:
                    alpha3 = (row.get("Code") or "").strip().upper()
                    alpha2 = ALPHA3_TO_ALPHA2.get(alpha3)
                    if not alpha2:
                        continue
                    try:
                        year = int(row.get("Year") or "")
                    except ValueError:
                        continue
                    if year < self._min_year:
                        continue
                    raw_value = row.get(capacity_col)
                    if raw_value is None or raw_value == "":
                        continue
                    try:
                        mw = float(raw_value)
                    except (TypeError, ValueError):
                        continue
                    if mw < 0:
                        continue
                    aggregate[(alpha2, year)][tech] = mw

            for (alpha2, year), tech_map in aggregate.items():
                total_mw = sum(tech_map.values())
                if total_mw <= 0:
                    continue
                yield IndicatorRecord(
                    country_code=alpha2,
                    indicator_id="renewable_capacity_mw",
                    year=year,
                    value=total_mw,
                    source_url="https://ourworldindata.org/renewable-energy",
                    methodology_version="irena_owid_v1",
                    raw_record={
                        "year": year,
                        "by_technology": tech_map,
                        "covered_techs": sorted(tech_map.keys()),
                    },
                )
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    async def _fetch_csv_text(self, client: httpx.AsyncClient, url: str) -> str:
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
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
                if attempt + 1 < self._max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        assert last_exc is not None
        raise last_exc
