"""UNFCCC NDC adapter — Phase 3 wave 6 (rewritten 2026-07-02, ML-14).

Source: UNFCCC NDC Registry — https://unfccc.int/NDCREG
Methodology: NDC summary tables published by the UNFCCC; structured into a
queryable JSON API by Climate Watch (WRI).

Records two indicators per country:
  * `ndc_target_year` — the (latest) year by which the pledge is to be met.
  * `ndc_target_reduction_percent` — pledged emissions reduction.

WHY THIS WAS REWRITTEN (ML-14): the previous version fetched
``/ndc_content?per_page=500`` with NO pagination. Climate Watch sorts the
result by ``iso_code3`` ASC and every country has ~1,900 content rows, so all
500 rows were Afghanistan — and it then mapped ISO3→ISO2 through an 80-entry
map that omitted ``AFG``, so every row was skipped. Net result: the "NDC
Targets" map layer advertised ~190 countries but held ZERO NDC data.

THE FIX (verified live 2026-07-02):
  * The ``value`` field is NOT free NDC prose keyed one-row-per-country; the
    endpoint returns rows keyed by ``indicator_id``. The target data lives in
    two specific indicators, which we isolate SERVER-SIDE by their numeric ids:
        ghg_target        -> 627369   (e.g. "13.6% reduction ... by 2030 ...")
        time_target_year  -> 627372   (e.g. "2030")
    Filtering to just these collapses the dataset to ~1,400 rows over ~3 pages
    covering ~198 countries (169 with a parseable year, 156 with a percent).
  * We PAGINATE (``&page=N``) until a short/empty page. Climate Watch's ``meta``
    carries no pagination counters, so the short-page rule + a safety cap are
    how we stop.
  * We map ISO3→ISO2 through the FULL ``ISO3_TO_ISO2`` shared from the ND-GAIN
    adapter (every UN country), not the 80-entry emitter map.
  * Target year and reduction percent are parsed INDEPENDENTLY: the year from
    the ``time_target_year`` field (latest in-range year, so a "2021 to 2030"
    commitment period yields 2030, not the start year), the percent from the
    ``ghg_target`` text.

When the upstream API is unreachable the adapter fails fast (no records) — it
never silently emits stale data; the application layer surfaces "data
unavailable" instead of a wrong number.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from .base import IndicatorAdapter, IndicatorRecord
# ML-14: reuse the FULL ISO 3166-1 alpha-3 -> alpha-2 map (every UN country)
# the ND-GAIN adapter assembled, not the ~80-entry emitter subset that dropped
# AFG (and ~110 others).
from .nd_gain import ISO3_TO_ISO2

_logger = logging.getLogger("indicators.unfccc_ndc")


# ---------------------------------------------------------------------------
# Climate Watch indicator ids (verified live 2026-07-02 via
# /api/v1/data/ndc_content/indicators). These filter the endpoint server-side.
# ---------------------------------------------------------------------------
INDICATOR_GHG_TARGET = 627369        # slug: ghg_target
INDICATOR_TIME_TARGET_YEAR = 627372  # slug: time_target_year
_GHG_TARGET_SLUG = "ghg_target"
_TIME_TARGET_YEAR_SLUG = "time_target_year"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_BY_YEAR_RE = re.compile(r"by\s+(20\d{2})", re.IGNORECASE)

_NET_ZERO_RE = re.compile(
    r"net[\s-]?zero\s+(?:by\s+)?(?P<year>20\d{2})",
    re.IGNORECASE,
)

# Legacy combined pattern kept for `parse_target` (pure text parsing helper,
# still unit-tested and used as a fallback).
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


def _years_in(text: Any) -> List[int]:
    """All 4-digit target-horizon years (2020–2100) mentioned in `text`."""
    out: List[int] = []
    for m in _YEAR_RE.finditer(str(text or "")):
        y = int(m.group(1))
        if 2020 <= y <= 2100:
            out.append(y)
    return out


def parse_target_year(
    time_target_values: List[str],
    ghg_target_values: Optional[List[str]] = None,
) -> Optional[int]:
    """Latest in-range target year across the ``time_target_year`` values.

    Climate Watch stores several submissions per country and messy formats
    ("2021 to 2030", "1 January 2021- 31 December 2030", a bare "2030", "2035").
    We take the MAX in-range year so a commitment PERIOD collapses to its end
    (target) year and the most recent NDC horizon wins. When the timing field
    holds no clean year we fall back to a "by YYYY" clause inside the ghg target
    text (which avoids picking a base year like "below 2005 levels").
    """
    years: List[int] = []
    for v in time_target_values or []:
        years.extend(_years_in(v))
    if not years and ghg_target_values:
        for v in ghg_target_values:
            for m in _BY_YEAR_RE.finditer(str(v or "")):
                y = int(m.group(1))
                if 2020 <= y <= 2100:
                    years.append(y)
    return max(years) if years else None


def parse_reduction_pct(ghg_target_values: List[str]) -> Optional[float]:
    """First parseable reduction percentage across the ``ghg_target`` values.

    A net-zero pledge maps to 100.0 and takes precedence. Otherwise the first
    value carrying a ``0 < pct <= 100`` token wins ("26% to 28%" -> 26, the
    lower/conservative bound). Values with no percentage yield None.
    """
    values = ghg_target_values or []
    # Net-zero anywhere wins.
    for v in values:
        if _NET_ZERO_RE.search(str(v or "")):
            return 100.0
    for v in values:
        m = _PCT_RE.search(str(v or ""))
        if m:
            try:
                pct = float(m.group(1))
            except ValueError:
                continue
            if 0 < pct <= 100:
                return pct
    return None


def parse_target(text: str) -> Tuple[Optional[float], Optional[int]]:
    """Best-effort extraction of (reduction_percent, target_year) from a single
    NDC commitment string.

    Retained as a pure text-parsing helper (unit-tested) and used by the adapter
    only as a per-string fallback. See `parse_reduction_pct` / `parse_target_year`
    for the field-keyed extraction the adapter now relies on.
    """
    if not text:
        return None, None

    blob = text.strip()
    pct: Optional[float] = None
    year: Optional[int] = None

    nz = _NET_ZERO_RE.search(blob)
    if nz:
        try:
            return 100.0, int(nz.group("year"))
        except ValueError:
            pass

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
            continue

    return pct, year


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class UNFCCCNdcAdapter(IndicatorAdapter):
    """Pulls NDC target year + reduction percentage per country."""

    source_name = "unfccc_ndc"
    methodology_url = "https://unfccc.int/NDCREG"

    # Server-side filtered to the two target indicators (ghg_target +
    # time_target_year). ~1,400 rows over ~3 pages, ~198 countries.
    DEFAULT_API_URL = (
        "https://www.climatewatchdata.org/api/v1/data/ndc_content"
        f"?indicator_ids[]={INDICATOR_GHG_TARGET}"
        f"&indicator_ids[]={INDICATOR_TIME_TARGET_YEAR}"
        "&per_page=500"
    )

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        api_url: Optional[str] = None,
        request_timeout: float = 60.0,
        max_retries: int = 3,
        max_pages: int = 40,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._api_url = api_url or self.DEFAULT_API_URL
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._max_pages = max(1, int(max_pages))
        m = re.search(r"per_page=(\d+)", self._api_url)
        self._per_page = int(m.group(1)) if m else 500

    def _page_url(self, page: int) -> str:
        """Return the API URL with `page=N` set (raw `indicator_ids[]` brackets
        preserved — Climate Watch expects the unencoded form)."""
        base = re.sub(r"([?&])page=\d+", r"\1", self._api_url).rstrip("?&")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}page={page}"

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

            # Accumulate the target-indicator values per country across pages.
            by_country: Dict[str, Dict[str, List[str]]] = {}

            for page in range(1, self._max_pages + 1):
                payload = await self._get_json(client, self._page_url(page))
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list) or not rows:
                    break

                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    slug = str(row.get("indicator_id") or "").strip()
                    if slug not in (_GHG_TARGET_SLUG, _TIME_TARGET_YEAR_SLUG):
                        continue
                    alpha3 = (row.get("iso_code3") or row.get("iso") or "").strip().upper()
                    value = row.get("value")
                    if not alpha3 or value in (None, ""):
                        continue
                    by_country.setdefault(alpha3, {}).setdefault(slug, []).append(str(value))

                # No pagination counters in `meta`; a short page is the last one.
                if len(rows) < self._per_page:
                    break

            year_stamp = datetime.utcnow().year

            for alpha3, fields in by_country.items():
                alpha2 = ISO3_TO_ISO2.get(alpha3)
                if not alpha2:
                    _logger.debug("UNFCCC NDC: no ISO2 for %s; skipping", alpha3)
                    continue

                ghg_values = fields.get(_GHG_TARGET_SLUG) or []
                year_values = fields.get(_TIME_TARGET_YEAR_SLUG) or []

                pct = parse_reduction_pct(ghg_values)
                target_year = parse_target_year(year_values, ghg_values)
                if target_year is None and pct is None:
                    continue

                source_url = f"https://www.climatewatchdata.org/ndcs/country/{alpha3}"
                snippet = (ghg_values[0] if ghg_values else (year_values[0] if year_values else ""))[:512]

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
                            "parsed_year": target_year,
                            "time_target_year_raw": (year_values[0] if year_values else None),
                            "snippet": snippet,
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
                            "parsed_pct": pct,
                            "snippet": snippet,
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
