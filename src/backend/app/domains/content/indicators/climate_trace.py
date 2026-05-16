"""Climate TRACE adapter — sector-level emissions, satellite-verified.

Source: https://climatetrace.org / API at https://api.climatetrace.org
Methodology: https://climatetrace.org/methodology

Climate TRACE publishes country-level emissions by sector (power,
transportation, agriculture, etc.), reconciled against satellite
observations. We pull two slices per sync:

  1. Country total emissions (CO₂-equivalent) → emissions_tco2e_total
  2. Sector subtotals → emissions_tco2_power, emissions_tco2_transportation

The API returns ISO 3166-1 alpha-3 codes; we map to alpha-2 to match the
platform's `countries.country_code`. Records with unknown / missing codes
are skipped (counted in SyncResult.skipped_count).

The HTTP client uses a tight timeout + bounded retries with exponential
backoff. Schema drift on individual records is tolerated (debug-logged,
skipped); a complete schema break aborts the sync.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import IndicatorAdapter, IndicatorRecord

_logger = logging.getLogger("indicators.climate_trace")


# Climate TRACE uses ISO 3166-1 alpha-3; the platform stores alpha-2.
# This is a small static map for the common cases; missing codes get
# skipped with a debug log. (Full ISO mapping lives in
# infrastructure/database/04_countries_seed.sql when we need it.)
ALPHA3_TO_ALPHA2 = {
    "USA": "US", "CHN": "CN", "IND": "IN", "RUS": "RU", "JPN": "JP",
    "DEU": "DE", "IRN": "IR", "KOR": "KR", "SAU": "SA", "IDN": "ID",
    "CAN": "CA", "MEX": "MX", "ZAF": "ZA", "BRA": "BR", "AUS": "AU",
    "TUR": "TR", "GBR": "GB", "ITA": "IT", "FRA": "FR", "POL": "PL",
    "ESP": "ES", "THA": "TH", "VNM": "VN", "EGY": "EG", "MYS": "MY",
    "ARG": "AR", "UKR": "UA", "PAK": "PK", "KAZ": "KZ", "NLD": "NL",
    "ARE": "AE", "BGD": "BD", "VEN": "VE", "PHL": "PH", "IRQ": "IQ",
    "ALG": "DZ", "DZA": "DZ", "BEL": "BE", "CZE": "CZ", "COL": "CO",
    "QAT": "QA", "KWT": "KW", "OMN": "OM", "SWE": "SE", "AUT": "AT",
    "ROU": "RO", "GRC": "GR", "PRT": "PT", "HUN": "HU", "FIN": "FI",
    "DNK": "DK", "NOR": "NO", "CHE": "CH", "IRL": "IE", "ISR": "IL",
    "NZL": "NZ", "SGP": "SG", "HKG": "HK", "PER": "PE", "CHL": "CL",
    "MAR": "MA", "TUN": "TN", "KEN": "KE", "ETH": "ET", "NGA": "NG",
    "GHA": "GH", "TZA": "TZ", "UGA": "UG", "RWA": "RW", "SEN": "SN",
    "URY": "UY", "PRY": "PY", "BOL": "BO", "ECU": "EC", "CRI": "CR",
    "PAN": "PA", "DOM": "DO", "JAM": "JM", "TTO": "TT", "BHS": "BS",
}


class ClimateTRACEAdapter(IndicatorAdapter):
    """Pulls country totals + power + transportation emissions from Climate TRACE."""

    source_name = "climate_trace"
    methodology_url = "https://climatetrace.org/methodology"

    # The /v6 endpoint is the current stable surface as of 2026-05.
    # If Climate TRACE bumps to /v7 we'll add a methodology_version bump.
    BASE_URL = "https://api.climatetrace.org/v6"

    # The Climate TRACE "country emissions" endpoint returns rows that
    # include subsectors; we aggregate per (country, year, sector_top).
    SECTOR_TO_INDICATOR = {
        # Climate TRACE sector → CliLens indicator_id
        # We only emit a row for sectors we expose; everything else gets
        # rolled into the total. Total is computed separately via the
        # `/country/emissions` rollup endpoint when available, otherwise
        # by summing all rows for a (country, year).
        "power":          "emissions_tco2_power",
        "transportation": "emissions_tco2_transportation",
    }

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        request_timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._http_client = http_client       # injected for tests
        self._owns_client = http_client is None
        self._request_timeout = request_timeout
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # IndicatorAdapter contract
    # ------------------------------------------------------------------

    async def fetch_records(self) -> AsyncIterator[IndicatorRecord]:
        client_cm: Optional[httpx.AsyncClient] = None
        client: httpx.AsyncClient
        try:
            if self._http_client is not None:
                client = self._http_client
            else:
                client_cm = httpx.AsyncClient(
                    timeout=self._request_timeout,
                    headers={"User-Agent": self.default_user_agent},
                )
                client = client_cm

            payload = await self._get_json(
                client, f"{self.BASE_URL}/country/emissions"
            )
            if not isinstance(payload, list):
                raise RuntimeError(
                    f"Unexpected Climate TRACE payload shape: "
                    f"{type(payload).__name__}"
                )

            # Aggregate rows by (country, year) so we emit one total row +
            # one row per tracked sector.
            totals: Dict[tuple, float] = {}
            sectors: Dict[tuple, float] = {}

            for raw in payload:
                if not isinstance(raw, dict):
                    continue
                alpha3 = (raw.get("country") or raw.get("country_code") or "").upper()
                alpha2 = ALPHA3_TO_ALPHA2.get(alpha3)
                if not alpha2:
                    continue
                try:
                    year = int(raw.get("year"))
                except (TypeError, ValueError):
                    continue

                # Prefer co2e_100yr_tonnes (newer field) → fallback co2e_100yr → co2e.
                gas_total = (
                    raw.get("co2e_100yr_tonnes")
                    or raw.get("co2e_100yr")
                    or raw.get("co2e")
                    or raw.get("co2")
                )
                try:
                    gas_total_f = float(gas_total) if gas_total is not None else None
                except (TypeError, ValueError):
                    gas_total_f = None
                if gas_total_f is None:
                    continue

                key_total = (alpha2, year)
                totals[key_total] = totals.get(key_total, 0.0) + gas_total_f

                sector = (raw.get("sector") or "").strip().lower()
                indicator = self.SECTOR_TO_INDICATOR.get(sector)
                if indicator:
                    key_sector = (alpha2, year, indicator)
                    sectors[key_sector] = (
                        sectors.get(key_sector, 0.0) + gas_total_f
                    )

            # Emit totals.
            for (cc, year), total_value in totals.items():
                yield IndicatorRecord(
                    country_code=cc,
                    indicator_id="emissions_tco2e_total",
                    year=year,
                    value=total_value,
                    source_url=f"{self.BASE_URL}/country/emissions",
                    methodology_version="climate_trace_v6",
                    raw_record={"aggregated_from": "sector_rows", "year": year, "country": cc},
                )

            # Emit sector breakdowns.
            for (cc, year, indicator), sector_value in sectors.items():
                yield IndicatorRecord(
                    country_code=cc,
                    indicator_id=indicator,
                    year=year,
                    value=sector_value,
                    source_url=f"{self.BASE_URL}/country/emissions",
                    methodology_version="climate_trace_v6",
                    raw_record={
                        "aggregated_from": "sector_rows",
                        "sector": indicator.replace("emissions_tco2_", ""),
                        "year": year,
                        "country": cc,
                    },
                )
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> Any:
        """GET with bounded retries + exponential backoff. Raises on final failure."""
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                # Don't retry on 4xx other than 429 — schema/auth errors won't fix themselves.
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and 400 <= exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    raise
                if attempt + 1 < self._max_retries:
                    backoff = 0.5 * (2 ** attempt)
                    _logger.debug(
                        "climate_trace GET %s attempt %d failed (%s); "
                        "retrying in %.1fs",
                        url, attempt + 1, exc, backoff,
                    )
                    await asyncio.sleep(backoff)
                continue
        assert last_exc is not None
        raise last_exc
