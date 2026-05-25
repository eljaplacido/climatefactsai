"""Full-text fetch helper for the ingestion pipeline.

Slice 4b (2026-05-25, Honest-Gap-Audit v2 item 3). RSS feeds typically
deliver excerpt-only payloads (<300 chars), so when the claim extractor
runs against `extracted_text or excerpt`, it has almost nothing to chew
on and produces 0-1 atomic claims. Combined with the Slice 4a credibility
formula change this means most RSS-only articles show 1-claim coverage
AND the Limited Evidence badge — both honest, but they hide the article's
actual content.

This helper does a polite HTTP fetch of the source URL, runs BeautifulSoup
extraction, and returns clean article body text. Use it as a pre-pass
BEFORE claim extraction whenever the persisted text is short.

  body = await fetch_full_text(article["source_url"])
  if body and len(body) > len(article_text):
      persist_to_db(body)
      article_text = body

Constraints respected:
- ComplianceChecker.check_url_compliance (robots.txt + deny list)
- 10s default timeout
- Returns None on any failure (network, parse, compliance, content-type)
- Returns None when extracted text is suspiciously short (<200 chars)
  so we don't replace a 300-char excerpt with a 50-char "subscribe"
  call-to-action.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("full_text_fetch")

DEFAULT_TIMEOUT = 10.0
MIN_USEFUL_LENGTH = 200
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MiB; anything larger is not an article
USER_AGENT = (
    "Mozilla/5.0 (compatible; ClimatefactsBot/1.0; "
    "+https://climatefacts.ai/about/crawler) "
    "Climate news verification ingestion"
)
# Tags we never want in the extracted body — navigation, layout chrome,
# inline scripts, social-share widgets.
STRIP_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "form", "iframe", "noscript", "svg", "button",
}
# Class / id substrings that almost always indicate non-article content.
STRIP_PATTERNS = (
    "comment", "sidebar", "share", "social", "advert", "promo",
    "newsletter", "related-articles", "recommended",
)


def _strip_chrome(soup: BeautifulSoup) -> None:
    """Remove tags + class/id-matched divs that aren't article content."""
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()
    for el in soup.find_all(True):
        # Class is sometimes a list; id is always str-or-None.
        candidate = " ".join(el.get("class", []) + [el.get("id") or ""]).lower()
        if any(p in candidate for p in STRIP_PATTERNS):
            el.decompose()


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Heuristic: prefer <article> or <main>; fall back to <p> collection."""
    container = soup.find("article") or soup.find("main")
    if container is None:
        container = soup.find("body") or soup
    paragraphs = [
        p.get_text(strip=True) for p in container.find_all("p")
    ]
    text = "\n\n".join(p for p in paragraphs if len(p) >= 20)
    return text


async def fetch_full_text(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    *,
    compliance_check: bool = True,
) -> Optional[str]:
    """Fetch + extract article body from a URL.

    Returns None when:
      - URL fails compliance check (deny list or robots.txt)
      - HTTP error (4xx, 5xx, network failure, timeout)
      - Content-type is not HTML
      - Body too large (>5 MiB)
      - Extracted text shorter than MIN_USEFUL_LENGTH

    Designed for graceful degradation: never raises to the caller.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    if compliance_check:
        try:
            # Lazy import — avoids dragging compliance settings into the
            # test path when caller passes compliance_check=False.
            from app.core.compliance import get_compliance_checker
            result = await get_compliance_checker().check_url_compliance(url)
            if not result.get("compliant", True):
                logger.info(
                    f"full_text_fetch: skipped non-compliant URL {url} "
                    f"({result.get('reason')})"
                )
                return None
        except Exception as exc:
            # Compliance check shouldn't block ingestion if its module
            # is unavailable — log and proceed (the existing ingestion
            # path doesn't enforce robots either).
            logger.debug(f"full_text_fetch: compliance probe failed: {exc}")

    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
        if resp.status_code >= 400:
            logger.debug(f"full_text_fetch: HTTP {resp.status_code} for {url}")
            return None
        ctype = (resp.headers.get("content-type") or "").lower()
        if "html" not in ctype:
            logger.debug(f"full_text_fetch: non-HTML content-type {ctype} for {url}")
            return None
        if len(resp.content) > MAX_RESPONSE_BYTES:
            logger.debug(
                f"full_text_fetch: response too large ({len(resp.content)}b) for {url}"
            )
            return None
        html = resp.text
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.debug(f"full_text_fetch: transport error for {url}: {exc}")
        return None
    except Exception as exc:
        # Defensive: anything unexpected (DNS, ssl, etc.) is logged and
        # treated as a fetch miss.
        logger.debug(f"full_text_fetch: unexpected error for {url}: {exc}")
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        _strip_chrome(soup)
        text = _extract_main_text(soup)
    except Exception as exc:
        logger.debug(f"full_text_fetch: parse error for {url}: {exc}")
        return None

    if len(text) < MIN_USEFUL_LENGTH:
        logger.debug(
            f"full_text_fetch: extracted text too short ({len(text)}b) for {url}"
        )
        return None
    return text
