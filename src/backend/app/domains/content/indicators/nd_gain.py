"""ND-GAIN climate-vulnerability adapter — Phase 3 wave 6.

Source: Notre Dame Global Adaptation Index (ND-GAIN).
Methodology: https://gain.nd.edu/our-work/country-index/

ND-GAIN summarises a country's vulnerability to climate change AND its
readiness to leverage private and public sector investment for adaptive
actions. The Country Index combines:

  * Vulnerability (food, water, health, ecosystem services, human
    habitat, infrastructure)
  * Readiness (economic, governance, social)

The output is a 0–100 index — higher = better-positioned to adapt.
This fills the "adaptation/exposure" slot in the indicator catalogue
(migration 020) and gives the platform a vulnerability signal alongside
the emissions/energy/policy axes already covered by Climate TRACE / OWID
/ Climate Action Tracker.

Data distribution: ND-GAIN publishes its country index as a CSV
download from the public site, refreshed annually. The schema is
stable (country / iso3 / year / score columns) so the adapter is a
straight CSV stream. The `csv_url` constructor parameter lets the
operator swap to a pinned snapshot for reproducibility.

When the upstream CSV is unreachable, the adapter fails fast — the
application layer detects empty SyncResult and surfaces "data
unavailable" rather than displaying a stale figure.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import IndicatorAdapter, IndicatorRecord
from .climate_trace import ALPHA3_TO_ALPHA2

_logger = logging.getLogger("indicators.nd_gain")


class NDGainAdapter(IndicatorAdapter):
    """Pulls ND-GAIN Country Index per country per year."""

    source_name = "nd_gain"
    methodology_url = "https://gain.nd.edu/our-work/country-index/"

    DEFAULT_CSV_URL = (
        "https://gain.nd.edu/assets/522870/nd_gain_countryindex.csv"
    )

    # Acceptable header variants — ND-GAIN has used `ISO3`, `ISO_alpha3`,
    # `iso_alpha3_code`, and `country_code` across publication years. We
    # check each in order.
    _ISO3_HEADER_CANDIDATES = ("ISO3", "ISO_alpha3", "iso_alpha3_code", "country_code", "Code")
    _YEAR_HEADER_CANDIDATES = ("Year", "year")
    _SCORE_HEADER_CANDIDATES = ("Index", "ND-GAIN", "nd_gain_index", "Score", "score", "country_index")

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        csv_url: Optional[str] = None,
        request_timeout: float = 60.0,
        min_year: int = 2000,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._csv_url = csv_url or self.DEFAULT_CSV_URL
        self._request_timeout = request_timeout
        self._min_year = min_year
        self._max_retries = max_retries

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

            text = await self._fetch_csv_text(client, self._csv_url)
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                return

            iso_col = self._pick_header(reader.fieldnames, self._ISO3_HEADER_CANDIDATES)
            year_col = self._pick_header(reader.fieldnames, self._YEAR_HEADER_CANDIDATES)
            score_col = self._pick_header(reader.fieldnames, self._SCORE_HEADER_CANDIDATES)

            if not iso_col or not year_col or not score_col:
                _logger.warning(
                    "ND-GAIN: cannot resolve headers (iso=%s year=%s score=%s); fieldnames=%s",
                    iso_col, year_col, score_col, reader.fieldnames,
                )
                return

            for row in reader:
                alpha3 = (row.get(iso_col) or "").strip().upper()
                alpha2 = ALPHA3_TO_ALPHA2.get(alpha3)
                if not alpha2:
                    continue
                try:
                    year = int(row.get(year_col) or "")
                except ValueError:
                    continue
                if year < self._min_year:
                    continue
                raw_value = row.get(score_col)
                if raw_value is None or raw_value == "":
                    continue
                try:
                    score = float(raw_value)
                except (TypeError, ValueError):
                    continue
                # ND-GAIN publishes on a 0–100 scale; defensive clamp.
                if score < 0 or score > 100:
                    continue

                yield IndicatorRecord(
                    country_code=alpha2,
                    indicator_id="nd_gain_index",
                    year=year,
                    value=score,
                    source_url=self._csv_url,
                    methodology_version="nd_gain_v1",
                    raw_record={
                        "iso3": alpha3,
                        "year": year,
                        "score": score,
                    },
                )
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    @staticmethod
    def _pick_header(fieldnames: List[str], candidates: tuple) -> Optional[str]:
        """First case-insensitive match between candidate names and the CSV's headers."""
        lc_field = {f.strip().lower(): f for f in fieldnames if f}
        for c in candidates:
            actual = lc_field.get(c.lower())
            if actual:
                return actual
        return None

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
