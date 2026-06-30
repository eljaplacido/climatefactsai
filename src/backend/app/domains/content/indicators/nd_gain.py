"""ND-GAIN climate-vulnerability adapter — Phase 3 wave 6 (rev. 2026-06-30).

Source: Notre Dame Global Adaptation Index (ND-GAIN).
Methodology: https://gain.nd.edu/our-work/country-index/

ND-GAIN summarises a country's vulnerability to climate change AND its
readiness to leverage private and public sector investment for adaptive
actions. The Country Index combines:

  * Vulnerability (food, water, health, ecosystem services, human
    habitat, infrastructure)
  * Readiness (economic, governance, social)

The composite index is a 0-100 score — higher = better-positioned to adapt.
Vulnerability and Readiness are published on a 0-1 scale.

Data distribution (2026-06-30 rework): ND-GAIN no longer serves a single
flat CSV. The legacy URL

    https://gain.nd.edu/assets/522870/nd_gain_countryindex.csv

now returns HTTP 403 / a PDF. The live download is a single ZIP archive of
per-metric CSVs, linked from
https://gain.nd.edu/our-work/country-index/download-data/ :

    https://gain.nd.edu/assets/647440/ndgain_countryindex_2026.zip   (HTTP 200, ~4.4 MB)

Inside the archive the three metrics we surface live at:

    resources/gain/gain.csv                     -> nd_gain_index          (0-100)
    resources/vulnerability/vulnerability.csv   -> nd_gain_vulnerability  (0-1)
    resources/readiness/readiness.csv           -> nd_gain_readiness      (0-1)

Each CSV is WIDE: columns are `ISO3, Name, 1995, 1996, ... 2023`, one row per
country, with the metric value in each year cell.

The `csv_url` / `zip_url` constructor parameter lets the operator pin a
snapshot for reproducibility (ND-GAIN refreshes the asset id annually).

When the upstream archive is unreachable, the adapter fails fast — the
application layer detects an empty/failed SyncResult and surfaces "data
unavailable" rather than displaying a stale figure.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import zipfile
from typing import AsyncIterator, Iterator, List, Optional, Tuple

import httpx

from .base import IndicatorAdapter, IndicatorRecord
from .climate_trace import ALPHA3_TO_ALPHA2

_logger = logging.getLogger("indicators.nd_gain")


# The shared ALPHA3_TO_ALPHA2 in climate_trace.py is intentionally a small
# "common cases" map (~80 of the world's emitters). ND-GAIN publishes ~192 UN
# countries, so reusing that map alone would silently skip ~114 countries and
# leave the adaptation map layer mostly grey. We extend it here with the full
# ISO 3166-1 alpha-3 -> alpha-2 set for every country ND-GAIN reports, so the
# adaptation-finance-gap layer can reach genuine global coverage.
_ND_GAIN_EXTRA_ISO3: dict = {
    "AFG": "AF", "ALB": "AL", "AND": "AD", "AGO": "AO", "ATG": "AG",
    "ARM": "AM", "AZE": "AZ", "BHR": "BH", "BRB": "BB", "BLR": "BY",
    "BLZ": "BZ", "BEN": "BJ", "BTN": "BT", "BIH": "BA", "BWA": "BW",
    "BRN": "BN", "BGR": "BG", "BFA": "BF", "BDI": "BI", "KHM": "KH",
    "CMR": "CM", "CPV": "CV", "CAF": "CF", "TCD": "TD", "COM": "KM",
    "COG": "CG", "COD": "CD", "CIV": "CI", "HRV": "HR", "CUB": "CU",
    "CYP": "CY", "DJI": "DJ", "DMA": "DM", "SLV": "SV", "GNQ": "GQ",
    "ERI": "ER", "EST": "EE", "FJI": "FJ", "GAB": "GA", "GMB": "GM",
    "GEO": "GE", "GRD": "GD", "GTM": "GT", "GIN": "GN", "GNB": "GW",
    "GUY": "GY", "HTI": "HT", "HND": "HN", "ISL": "IS", "JOR": "JO",
    "KIR": "KI", "PRK": "KP", "KGZ": "KG", "LAO": "LA", "LVA": "LV",
    "LBN": "LB", "LSO": "LS", "LBR": "LR", "LBY": "LY", "LIE": "LI",
    "LTU": "LT", "LUX": "LU", "MKD": "MK", "MDG": "MG", "MWI": "MW",
    "MDV": "MV", "MLI": "ML", "MLT": "MT", "MHL": "MH", "MRT": "MR",
    "MUS": "MU", "FSM": "FM", "MDA": "MD", "MCO": "MC", "MNG": "MN",
    "MNE": "ME", "MOZ": "MZ", "MMR": "MM", "NAM": "NA", "NRU": "NR",
    "NPL": "NP", "NIC": "NI", "NER": "NE", "PLW": "PW", "PNG": "PG",
    "KNA": "KN", "LCA": "LC", "VCT": "VC", "WSM": "WS", "SMR": "SM",
    "STP": "ST", "SRB": "RS", "SYC": "SC", "SLE": "SL", "SVK": "SK",
    "SVN": "SI", "SLB": "SB", "SOM": "SO", "LKA": "LK", "SDN": "SD",
    "SUR": "SR", "SWZ": "SZ", "SYR": "SY", "TJK": "TJ", "TLS": "TL",
    "TGO": "TG", "TON": "TO", "TKM": "TM", "TUV": "TV", "UZB": "UZ",
    "VUT": "VU", "YEM": "YE", "ZMB": "ZM", "ZWE": "ZW",
}

# Existing shared entries win on conflict (they are authoritative for the
# overlapping ~80 codes); extra entries fill the long tail.
ISO3_TO_ISO2 = {**_ND_GAIN_EXTRA_ISO3, **ALPHA3_TO_ALPHA2}


class NDGainAdapter(IndicatorAdapter):
    """Pulls ND-GAIN Country Index + vulnerability + readiness per country/year."""

    source_name = "nd_gain"
    methodology_url = "https://gain.nd.edu/our-work/country-index/"

    # Verified HTTP 200 (application/zip, ~4.4 MB) on 2026-06-30. Refreshed
    # annually — the asset id changes, so pin via the constructor for repro.
    DEFAULT_ZIP_URL = (
        "https://gain.nd.edu/assets/647440/ndgain_countryindex_2026.zip"
    )

    # Member CSV (matched by path suffix, case-insensitive) -> (indicator_id,
    # value_scale_max). The composite index is 0-100; the two sub-scores are
    # published on a native 0-1 scale (preserved verbatim — honest provenance).
    _MEMBERS: Tuple[Tuple[str, str, float], ...] = (
        ("gain/gain.csv", "nd_gain_index", 100.0),
        ("vulnerability/vulnerability.csv", "nd_gain_vulnerability", 1.0),
        ("readiness/readiness.csv", "nd_gain_readiness", 1.0),
    )

    # Acceptable ISO3 header variants — ND-GAIN has used `ISO3`, `ISO_alpha3`,
    # `iso_alpha3_code`, `country_code`, `Code` across publication years.
    _ISO3_HEADER_CANDIDATES = ("ISO3", "ISO_alpha3", "iso_alpha3_code", "country_code", "Code")

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        zip_url: Optional[str] = None,
        csv_url: Optional[str] = None,  # legacy alias for the download URL
        request_timeout: float = 60.0,
        min_year: int = 2000,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        # `csv_url` is kept as a backwards-compatible alias for the download
        # URL override; the source is now a ZIP, so `zip_url` is the canonical
        # name. Either pins a snapshot.
        self._zip_url = zip_url or csv_url or self.DEFAULT_ZIP_URL
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

            raw = await self._fetch_zip_bytes(client, self._zip_url)
            for record in self._parse_zip(raw):
                yield record
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_zip(self, raw: bytes) -> Iterator[IndicatorRecord]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            _logger.warning("ND-GAIN: downloaded payload is not a valid zip: %s", exc)
            return

        with archive as zf:
            names = zf.namelist()
            for suffix, indicator_id, scale_max in self._MEMBERS:
                member = self._resolve_member(names, suffix)
                if not member:
                    _logger.warning(
                        "ND-GAIN: member ending in %r not found in archive (have %d entries)",
                        suffix, len(names),
                    )
                    continue
                try:
                    text = zf.read(member).decode("utf-8-sig")
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.warning("ND-GAIN: could not read %s: %s", member, exc)
                    continue
                yield from self._parse_wide_csv(text, indicator_id, scale_max)

    @staticmethod
    def _resolve_member(names: List[str], suffix: str) -> Optional[str]:
        """First archive entry whose normalised path ends with `suffix`.

        Suffixes are parent-qualified (e.g. `gain/gain.csv`) so the per-metric
        CSV is picked and the `trends/` variants (`trends/gain.csv`, ...) are
        excluded.
        """
        suffix_l = suffix.lower()
        for n in names:
            if n.replace("\\", "/").lower().endswith(suffix_l):
                return n
        return None

    def _parse_wide_csv(
        self, text: str, indicator_id: str, scale_max: float
    ) -> Iterator[IndicatorRecord]:
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return

        iso_idx = self._find_iso_column(header)
        if iso_idx is None:
            _logger.warning(
                "ND-GAIN: %s missing an ISO3 column; header=%s", indicator_id, header
            )
            return

        # Year columns: any header cell that is a 4-digit year.
        year_cols: List[Tuple[int, int]] = []
        for i, h in enumerate(header):
            hs = (h or "").strip()
            if len(hs) == 4 and hs.isdigit():
                year_cols.append((i, int(hs)))
        if not year_cols:
            _logger.warning("ND-GAIN: %s has no year columns; header=%s", indicator_id, header)
            return

        for row in reader:
            if iso_idx >= len(row):
                continue
            alpha3 = (row[iso_idx] or "").strip().upper()
            alpha2 = ISO3_TO_ISO2.get(alpha3)
            if not alpha2:
                continue
            for col_idx, year in year_cols:
                if year < self._min_year or col_idx >= len(row):
                    continue
                raw_value = row[col_idx]
                if raw_value is None or raw_value.strip() == "":
                    continue
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                # Defensive clamp against the metric's published scale.
                if value < 0 or value > scale_max:
                    continue

                yield IndicatorRecord(
                    country_code=alpha2,
                    indicator_id=indicator_id,
                    year=year,
                    value=value,
                    source_url=self._zip_url,
                    methodology_version="nd_gain_v2_2026",
                    raw_record={
                        "iso3": alpha3,
                        "year": year,
                        "value": value,
                        "indicator": indicator_id,
                    },
                )

    @classmethod
    def _find_iso_column(cls, header: List[str]) -> Optional[int]:
        lc = {(h or "").strip().lower(): i for i, h in enumerate(header)}
        for candidate in cls._ISO3_HEADER_CANDIDATES:
            idx = lc.get(candidate.lower())
            if idx is not None:
                return idx
        return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _fetch_zip_bytes(self, client: httpx.AsyncClient, url: str) -> bytes:
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
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
