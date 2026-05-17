"""UNFCCC NDC adapter — Phase 3 wave 6.

Source: UNFCCC NDC Registry — https://unfccc.int/NDCREG
Methodology: NDC summary tables published by the UNFCCC; cross-referenced
against Climate Watch (WRI) which structures the registry into queryable
JSON.

Records two indicators per country:
  * `ndc_target_year` — the year by which the pledge is to be met.
  * `ndc_target_reduction_percent` — pledged emissions reduction (vs base year).

The UNFCCC registry itself publishes XLSX/PDF summaries that are not
machine-friendly to parse. Climate Watch (WRI) wraps the same source
data in a stable public JSON API:

    https://www.climatewatchdata.org/api/v1/data/ndc_content
        ?categories[]=11&categories[]=12
        &start_year=2020
        &per_page=200

For deployment reproducibility, we accept the `api_url` as a constructor
parameter so an operator can swap to a different mirror (or a pinned
cached copy) without code changes. The default targets Climate Watch's
public endpoint.

When the upstream API is unreachable, the adapter fails fast (no records
emitted) — never silently falls back to stale data. The application
layer can detect this via the empty SyncResult and surface "data
unavailable" in the UI rather than displaying a wrong number.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from .base import IndicatorAdapter, IndicatorRecord
from .climate_trace import ALPHA3_TO_ALPHA2

_logger = logging.getLogger("indicators.unfccc_ndc")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Common patterns in NDC commitment text:
#   "30% reduction by 2030"
#   "reduce emissions by 45% by 2030"
#   "55% below 1990 levels by 2030"
#   "net-zero by 2050"
_PCT_YEAR_RE = re.compile(
    r"""
    (?:
        (?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s*
        (?:reduction|below|below\s+\d{4}\s+levels?|cut)?\s*
    )?
    (?:by\s+)?
    (?P<year>20\d{2})
    """,
    re.IGNORECASE | re.VERBOSE,
)

_NET_ZERO_RE = re.compile(
    r"net[\s-]?zero\s+(?:by\s+)?(?P<year>20\d{2})",
    re.IGNORECASE,
)


def parse_target(text: str) -> Tuple[Optional[float], Optional[int]]:
    """Best-effort extraction of (reduction_percent, target_year) from NDC text.

    Returns:
        (reduction_pct, target_year)
            * reduction_pct: 0–100, or None when the pledge is qualitative.
              A "net-zero" pledge maps to 100.0 (full elimination).
            * target_year: 4-digit year >=2020, or None.

    The function is intentionally lenient — NDC text is heterogeneous and
    we'd rather skip a malformed row than emit a garbage value. Caller
    treats `(None, None)` as "no machine-readable target found".
    """
    if not text:
        return None, None

    blob = text.strip()
    pct: Optional[float] = None
    year: Optional[int] = None

    # Net-zero pledge → 100% reduction by the stated year.
    nz = _NET_ZERO_RE.search(blob)
    if nz:
        try:
            return 100.0, int(nz.group("year"))
        except ValueError:
            pass

    # Search for first explicit pct + year combo.
    for m in _PCT_YEAR_RE.finditer(blob):
        candidate_year = m.group("year")
        candidate_pct = m.group("pct")
        if not candidate_year:
            continue
        try:
            yi = int(candidate_year)
            if yi < 2020 or yi > 2100:
                continue
        except ValueError:
            continue
        year = yi
        if candidate_pct:
            try:
                pi = float(candidate_pct)
                if 0 < pi <= 100:
                    pct = pi
                    break
            except ValueError:
                continue
        else:
            # Got a year but no pct on this match; keep scanning for a
            # better match before settling.
            continue

    return pct, year


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class UNFCCCNdcAdapter(IndicatorAdapter):
    """Pulls NDC target year + reduction percentage per country."""

    source_name = "unfccc_ndc"
    methodology_url = "https://unfccc.int/NDCREG"

    DEFAULT_API_URL = (
        "https://www.climatewatchdata.org/api/v1/data/ndc_content"
        "?start_year=2020&per_page=500"
    )

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        api_url: Optional[str] = None,
        request_timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._api_url = api_url or self.DEFAULT_API_URL
        self._request_timeout = request_timeout
        self._max_retries = max_retries

    async def fetch_records(self) -> AsyncIterator[IndicatorRecord]:
        client_cm: Optional[httpx.AsyncClient] = None
        try:
            if self._http_client is not None:
                client = self._http_client
            else:
                client_cm = httpx.AsyncClient(
                    timeout=self._request_timeout,
                    headers={
                        "User-Agent": self.default_user_agent,
                        "Accept": "application/json",
                    },
                )
                client = client_cm

            payload = await self._get_json(client, self._api_url)

            # Climate Watch returns {"data": [...], "meta": {...}} — be
            # defensive about variants.
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                _logger.warning(
                    "UNFCCC NDC adapter: unexpected payload shape; no rows extracted"
                )
                return

            year_stamp = datetime.utcnow().year

            for row in rows:
                if not isinstance(row, dict):
                    continue

                # `iso_code3` is Climate Watch's per-country key; fall back
                # to `country` if a payload variant uses the long name.
                alpha3 = (row.get("iso_code3") or row.get("iso") or "").strip().upper()
                if not alpha3:
                    continue
                alpha2 = ALPHA3_TO_ALPHA2.get(alpha3)
                if not alpha2:
                    continue

                text_blob = (
                    row.get("value")
                    or row.get("commitment")
                    or row.get("ndc_commitment")
                    or ""
                )
                if not text_blob:
                    continue

                pct, target_year = parse_target(text_blob)
                if target_year is None and pct is None:
                    # Qualitative pledge — skip.
                    continue

                source_url = (
                    f"https://www.climatewatchdata.org/ndcs/country/{alpha3}"
                )

                if target_year is not None:
                    yield IndicatorRecord(
                        country_code=alpha2,
                        indicator_id="ndc_target_year",
                        year=year_stamp,
                        value=float(target_year),
                        source_url=source_url,
                        methodology_version="cw_ndc_v1",
                        raw_record={
                            "iso_code3": alpha3,
                            "snippet": text_blob[:512],
                            "parsed_year": target_year,
                        },
                    )

                if pct is not None:
                    yield IndicatorRecord(
                        country_code=alpha2,
                        indicator_id="ndc_target_reduction_percent",
                        year=year_stamp,
                        value=pct,
                        source_url=source_url,
                        methodology_version="cw_ndc_v1",
                        raw_record={
                            "iso_code3": alpha3,
                            "snippet": text_blob[:512],
                            "parsed_pct": pct,
                        },
                    )
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
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
