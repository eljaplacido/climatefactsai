"""Climate Action Tracker adapter — Phase 3 wave 4.

Source: https://climateactiontracker.org/
Methodology: https://climateactiontracker.org/methodology/

Climate Action Tracker rates ~40 of the world's largest emitters on the
ambition of their climate policy + action. Each country's page carries a
qualitative "Overall rating" in one of five bands:

  Critically insufficient | Highly insufficient | Insufficient |
  Almost sufficient       | 1.5°C compatible

We map these to a 0-100 numeric score via the band midpoints so the
score can feed `sustainability_score`'s 3rd component
(`cat_overall_rating`), unlocking the max-confidence (3-indicator)
composite for the ~40 countries CAT covers.

CAT has no public API; this adapter HTML-scrapes the country pages. The
parsing is deliberately tolerant — per-country failures (CSS selector
drift, missing rating, page 404) skip that one country without aborting
the run. CAT updates its ratings ~monthly, so a nightly Celery sync is
overkill; weekly is plenty.

The COUNTRIES_TO_SCRAPE list is hardcoded rather than auto-discovered
to keep the adapter resilient: a sudden change in CAT's country index
page won't pull the rug out.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import AsyncIterator, Dict, Optional, Tuple

import httpx

from .base import IndicatorAdapter, IndicatorRecord

_logger = logging.getLogger("indicators.climate_action_tracker")


# ---------------------------------------------------------------------------
# Rating bands → 0-100 score
# ---------------------------------------------------------------------------
# Each band maps to its midpoint. These are documented as the
# `cat_overall_rating` indicator's seed scale in migration 020.

RATING_BAND_SCORE: Dict[str, float] = {
    "critically insufficient": 10.0,
    "highly insufficient":     30.0,
    "insufficient":            50.0,
    "almost sufficient":       70.0,
    "1.5°c compatible":        90.0,
    "1.5c compatible":         90.0,    # encoding-tolerant alias
    "1.5 c compatible":        90.0,    # spacing-tolerant alias
    "1.5°c paris agreement compatible": 90.0,
}


def _normalize_rating_text(s: str) -> str:
    """Lowercase, collapse whitespace, strip trailing punctuation."""
    if not s:
        return ""
    out = s.lower().strip()
    out = re.sub(r"\s+", " ", out)
    out = out.rstrip(".,;:!")
    return out


def rating_to_score(rating_text: str) -> Optional[float]:
    """Map a CAT rating string to a 0-100 score. Returns None on unknown band.

    Looks up by normalized text; tolerant of `°` vs `c`, whitespace
    variants, trailing punctuation. Unknown ratings return None so the
    caller skips the country rather than recording garbage.
    """
    norm = _normalize_rating_text(rating_text)
    if not norm:
        return None
    if norm in RATING_BAND_SCORE:
        return RATING_BAND_SCORE[norm]
    # Substring fallback — CAT sometimes embellishes the label ("Insufficient (Fair share)").
    for band, score in RATING_BAND_SCORE.items():
        if band in norm:
            return score
    return None


# ---------------------------------------------------------------------------
# Country index — alpha-2 → CAT URL slug
# ---------------------------------------------------------------------------
# Hardcoded snapshot of CAT's covered countries (as of 2026-05). Adding a
# new country here is the only adapter-side change needed when CAT expands
# coverage. The keys are ISO 3166-1 alpha-2 (matching the platform's
# `countries.country_code`); the values are the URL slug CAT uses in
# /countries/{slug}/.

COUNTRIES_TO_SCRAPE: Dict[str, str] = {
    "AR": "argentina",
    "AU": "australia",
    "BR": "brazil",
    "CA": "canada",
    "CL": "chile",
    "CN": "china",
    "CO": "colombia",
    "DE": "germany",
    "EG": "egypt",
    "ES": "spain",
    "ET": "ethiopia",
    "FR": "france",
    "GB": "the-uk",
    "ID": "indonesia",
    "IN": "india",
    "IR": "iran",
    "JP": "japan",
    "KR": "south-korea",
    "KZ": "kazakhstan",
    "MA": "morocco",
    "MX": "mexico",
    "NG": "nigeria",
    "NO": "norway",
    "NP": "nepal",
    "NZ": "new-zealand",
    "PE": "peru",
    "PH": "philippines",
    "PK": "pakistan",
    "RU": "russian-federation",
    "SA": "saudi-arabia",
    "TH": "thailand",
    "TR": "turkey",
    "UA": "ukraine",
    "US": "the-usa",
    "VN": "viet-nam",
    "ZA": "south-africa",
}


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

# CSS / class hints we try in order. The FIRST — CAT's specific "overall"
# ratings-matrix tile — is the authoritative overall-rating element; the rest
# are legacy/robustness hints for older page structures. We match on class
# SUBSTRING (CAT uses `ratings-matrix__overall ratings-matrix__overall--insufficient`).
RATING_CSS_HINTS: Tuple[str, ...] = (
    "ratings-matrix__overall",
    "rating-headline",
    "overall-rating",
    "country-rating",
    "rating-summary",
    "rating-label",
)

# The specific selector whose match we trust as high-confidence.
_HIGH_CONFIDENCE_HINT = "ratings-matrix__overall"

# CAT renders the tile as the label "Overall rating" followed by the band text
# ("Overall rating Insufficient"); strip the label so the band text remains.
_OVERALL_LABEL_RE = re.compile(r"(?i)overall\s+rating")


def _clean_overall_text(text: str) -> str:
    """Remove the 'Overall rating' label + collapse whitespace, leaving the
    band text (e.g. 'Overall rating  Insufficient' -> 'Insufficient')."""
    if not text:
        return ""
    out = _OVERALL_LABEL_RE.sub(" ", text)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def extract_overall_rating(html: str) -> Optional[Tuple[str, str]]:
    """Extract ``(rating_text, scrape_confidence)`` from a CAT country page.

    ``scrape_confidence``:
      * ``'high'``   — matched CAT's specific ``ratings-matrix__overall`` tile.
      * ``'medium'`` — matched a legacy rating CSS hint.

    Returns ``None`` when no rating tile is found — an HONEST no_data.

    ML-13: we deliberately do NOT scan the whole page for a band name. The old
    page-wide, longest-match-first fallback grabbed a band mentioned in prose or
    in a neighbouring tile and mis-reported the country's rating (e.g. Australia
    read as 'critically insufficient' when CAT rates it 'Insufficient'). A
    missed tile MUST yield None, not a wrong band.
    """
    if not html:
        return None

    # A DOM parser is required to isolate the overall-rating tile. Without one,
    # the only option is a page-wide band scan — exactly the guess ML-13 bans —
    # so we return None instead. bs4 ships in requirements (url_analysis).
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return None

    soup = None
    for parser in ("lxml", "html.parser"):
        try:
            soup = BeautifulSoup(html, parser)
            break
        except Exception:
            continue
    if soup is None:
        return None

    for css_hint in RATING_CSS_HINTS:
        # Class-substring match — CAT class names carry a band modifier suffix.
        for el in soup.find_all(attrs={"class": re.compile(css_hint, re.I)}):
            cleaned = _clean_overall_text(el.get_text(separator=" ", strip=True))
            if cleaned and rating_to_score(cleaned) is not None:
                confidence = "high" if css_hint == _HIGH_CONFIDENCE_HINT else "medium"
                return cleaned, confidence

    return None


def extract_rating_from_html(html: str) -> Optional[str]:
    """Back-compat wrapper returning just the overall-rating band text (or None).

    See ``extract_overall_rating`` for the confidence-aware variant used by the
    adapter to persist a scrape-confidence flag.
    """
    result = extract_overall_rating(html)
    return result[0] if result else None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class ClimateActionTrackerAdapter(IndicatorAdapter):
    """Pulls overall ratings for the ~40 CAT-covered countries."""

    source_name = "cat"
    methodology_url = "https://climateactiontracker.org/methodology/"

    BASE_URL = "https://climateactiontracker.org/countries"

    def __init__(
        self,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        request_timeout: float = 30.0,
        max_retries: int = 3,
        countries: Optional[Dict[str, str]] = None,
        # How long to wait between successive country fetches — be a
        # polite scraper.
        inter_country_delay_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self._http_client = http_client
        self._owns_client = http_client is None
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._countries = dict(countries) if countries is not None else dict(COUNTRIES_TO_SCRAPE)
        self._inter_country_delay = max(0.0, float(inter_country_delay_seconds))

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
                    headers={
                        "User-Agent": self.default_user_agent,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                client = client_cm

            # CAT updates ratings ~monthly; the year stamp on the record is
            # the current year (the rating reflects the latest assessment).
            year = datetime.utcnow().year

            for alpha2, slug in self._countries.items():
                url = f"{self.BASE_URL}/{slug}/"
                try:
                    html = await self._get_text(client, url)
                except Exception as exc:
                    _logger.debug(
                        "Skipping %s (%s): fetch failed: %s",
                        alpha2, slug, exc,
                    )
                    continue

                extracted = extract_overall_rating(html)
                if not extracted:
                    _logger.debug(
                        "Skipping %s (%s): no overall-rating tile found in page",
                        alpha2, slug,
                    )
                    continue

                rating_text, scrape_confidence = extracted
                score = rating_to_score(rating_text)
                if score is None:
                    _logger.debug(
                        "Skipping %s (%s): rating '%s' didn't map to a band",
                        alpha2, slug, rating_text,
                    )
                    continue

                yield IndicatorRecord(
                    country_code=alpha2,
                    indicator_id="cat_overall_rating",
                    year=year,
                    value=score,
                    source_url=url,
                    methodology_version="cat_2026",
                    raw_record={
                        # Persist the raw band text + how confident the scrape is
                        # so a 'medium' (legacy-selector) read is auditable and a
                        # future CSS drift is visible in the data (ML-13).
                        "raw_rating": rating_text,
                        "scrape_confidence": scrape_confidence,
                        "slug": slug,
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                )

                # Be a polite scraper between successive fetches.
                if self._inter_country_delay > 0:
                    await asyncio.sleep(self._inter_country_delay)
        finally:
            if client_cm is not None and self._owns_client:
                await client_cm.aclose()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        """GET with bounded retries + exponential backoff. Raises on final failure."""
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
                    backoff = 0.5 * (2 ** attempt)
                    _logger.debug(
                        "CAT GET %s attempt %d failed (%s); retrying in %.1fs",
                        url, attempt + 1, exc, backoff,
                    )
                    await asyncio.sleep(backoff)
                continue
        assert last_exc is not None
        raise last_exc
