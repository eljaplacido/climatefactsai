"""
RSS Adapter — Global climate news RSS feed integration.

Parses Carbon Brief, EEA, and global climate RSS feeds as discovery sources.
Supports dynamic feed registry from the database with hardcoded fallback.
Deduplicates against existing articles by URL.

Each RSS entry's article body is fetched from the canonical URL and parsed
via BeautifulSoup so downstream consumers (claim extraction, embeddings,
hallucination check, enrichment) operate on real article text rather than
RSS <summary> stubs. Fetches are bounded by RSS_FETCH_TIMEOUT seconds and
fail-soft to the RSS summary when extraction errors out.
"""

import os
import re
from typing import Any, Dict, List, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

# End2End audit follow-up (2026-05-27, Task D): the RSS-summary fallback
# below used to write raw HTML markup (img / p / a tags + WordPress
# "The post X appeared first on Y" footers) directly into
# articles.extracted_text, which then surfaced verbatim in the Full
# Article panel. Route fallback content through the shared cleaner.
from shared.html_cleaner import clean_article_text

logger = get_logger(__name__)

# Full-text fetch settings (env-overridable for ops tuning)
RSS_FETCH_TIMEOUT_S = float(os.getenv("RSS_FETCH_TIMEOUT_S", "10"))
RSS_FETCH_MAX_BYTES = int(os.getenv("RSS_FETCH_MAX_BYTES", str(2 * 1024 * 1024)))  # 2 MB
RSS_USER_AGENT = os.getenv(
    "RSS_USER_AGENT",
    "Mozilla/5.0 (compatible; ClimatefactsBot/1.0; +https://climatefacts.ai/about)",
)
RSS_FETCH_FULL_TEXT = os.getenv("RSS_FETCH_FULL_TEXT", "1").strip() != "0"


def _extract_article_body_html(html: str, url: str) -> Optional[str]:
    """Pull readable body text from an article HTML page.

    Strategy: prefer semantic containers (`<article>`, `<main>`,
    `[role=main]`), fall back to the largest `<div>` by paragraph count.
    Strip nav/aside/footer/script/style. Returns plain text joined by
    double-newlines, or None when no candidate has substantive paragraphs.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        # lxml not available or malformed — fall through to html.parser
        soup = BeautifulSoup(html, "html.parser")

    # Drop noise
    for tag in soup(["script", "style", "noscript", "iframe", "form",
                     "nav", "aside", "footer", "header"]):
        tag.decompose()

    candidates: List = []
    for sel in ["article", "main", "[role=main]", "div.article-body",
                "div.entry-content", "div.post-content", "div.story-body"]:
        candidates.extend(soup.select(sel))

    # Pick the candidate with the most <p> tags, fall back to the body
    best = None
    best_p_count = 0
    for c in candidates:
        n = len(c.find_all("p"))
        if n > best_p_count:
            best = c
            best_p_count = n
    if best is None:
        best = soup.body or soup

    paragraphs = [
        p.get_text(strip=True, separator=" ")
        for p in best.find_all("p")
    ]
    paragraphs = [p for p in paragraphs if p and len(p) >= 40]

    if not paragraphs:
        return None

    text = "\n\n".join(paragraphs)
    # Collapse excessive whitespace
    text = re.sub(r"\s{3,}", "  ", text)
    return text.strip() or None


def _fetch_and_extract_article_body(url: str) -> Optional[str]:
    """Fetch the article URL and return extracted body text.

    Returns None on any failure (timeout, non-HTML, parse failure, no
    candidate body). Caller falls back to the RSS summary.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        with httpx.Client(
            timeout=RSS_FETCH_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": RSS_USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        ) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return None
        ctype = (resp.headers.get("content-type") or "").lower()
        if "html" not in ctype and "xml" not in ctype:
            return None
        # Truncate oversized responses (some publisher pages embed huge JSON-LD)
        html = resp.text
        if len(html) > RSS_FETCH_MAX_BYTES:
            html = html[:RSS_FETCH_MAX_BYTES]
        return _extract_article_body_html(html, url)
    except httpx.TimeoutException:
        logger.debug(f"RSS body fetch timeout: {url}")
    except Exception as exc:
        logger.debug(f"RSS body fetch failed for {url}: {exc}")
    return None

# Default RSS feed URLs
CARBON_BRIEF_RSS = "https://www.carbonbrief.org/feed/"
EEA_RSS = "https://www.eea.europa.eu/api/rss"

# Global climate news feeds — international sources used as a fallback when the
# rss_feed_registry table is empty or unreachable.
GLOBAL_CLIMATE_FEEDS = {
    "Grist": {
        "url": "https://grist.org/feed/",
        "country_code": "US",
        "reliability_tier": "public",
        "source_domain": "grist.org",
    },
    "The Daily Climate": {
        "url": "https://www.dailyclimate.org/rss.xml",
        "country_code": "US",
        "reliability_tier": "public",
        "source_domain": "dailyclimate.org",
    },
    "IPCC": {
        "url": "https://www.ipcc.ch/feed/",
        "country_code": "XX",
        "reliability_tier": "scientific",
        "source_domain": "ipcc.ch",
    },
    "Inside Climate News": {
        "url": "https://insideclimatenews.org/feed/",
        "country_code": "US",
        "reliability_tier": "research",
        "source_domain": "insideclimatenews.org",
    },
    "Climate Change News": {
        "url": "https://www.climatechangenews.com/feed/",
        "country_code": "GB",
        "reliability_tier": "public",
        "source_domain": "climatechangenews.com",
    },
    "Reuters Environment": {
        "url": "https://www.reuters.com/arc/outboundfeeds/v3/all/section/environment/?outputType=xml",
        "country_code": "XX",
        "reliability_tier": "public",
        "source_domain": "reuters.com",
    },
    "Climate Central": {
        "url": "https://www.climatecentral.org/feed",
        "country_code": "US",
        "reliability_tier": "research",
        "source_domain": "climatecentral.org",
    },
    "NYT Climate": {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",
        "country_code": "US",
        "reliability_tier": "public",
        "source_domain": "nytimes.com",
    },
    "UN Climate News": {
        "url": "https://news.un.org/feed/subscribe/en/topic/climate-change/feed/rss.xml",
        "country_code": "XX",
        "reliability_tier": "scientific",
        "source_domain": "news.un.org",
    },
    "Earth.org": {
        "url": "https://earth.org/feed/",
        "country_code": "XX",
        "reliability_tier": "research",
        "source_domain": "earth.org",
    },
    "Nature Climate Change": {
        "url": "https://www.nature.com/nclimate.rss",
        "country_code": "XX",
        "reliability_tier": "scientific",
        "source_domain": "nature.com",
    },
    "Carbon Brief": {
        "url": "https://www.carbonbrief.org/feed/",
        "country_code": "GB",
        "reliability_tier": "research",
        "source_domain": "carbonbrief.org",
    },
    "The Guardian Climate": {
        "url": "https://www.theguardian.com/environment/climate-crisis/rss",
        "country_code": "GB",
        "reliability_tier": "public",
        "source_domain": "theguardian.com",
    },
}


def _parse_feed(url: str, max_items: int = 20) -> List[Dict[str, Any]]:
    """Parse an RSS feed and return normalized article entries.

    For each entry, fetches the canonical article URL and extracts the body
    text via BeautifulSoup. The extracted body is preferred over the RSS
    summary so downstream consumers (claim extraction, embeddings,
    hallucination check, article enrichment) work on real article text.
    Falls back to the RSS summary when extraction fails. Disable globally
    by setting RSS_FETCH_FULL_TEXT=0.
    """
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse issue for {url}: {feed.bozo_exception}")
            return []

        articles = []
        bodies_fetched = 0
        bodies_failed = 0
        for entry in feed.entries[:max_items]:
            entry_url = entry.get("link", "").strip()
            # End2End audit (2026-05-27, Task D) — strip HTML from the
            # RSS summary before storing. Publishers like Premium Times
            # Nigeria embed `<img>` + `<p>` + "The post ... appeared first
            # on ..." footer markup directly in the feed; the cleaner
            # normalises this to readable plain text so the Full Article
            # panel doesn't render raw tags.
            rss_summary_raw = entry.get("summary", "")[:2000]
            rss_summary = clean_article_text(rss_summary_raw)[:500]

            # Fetch the article body from the canonical URL. Fail-soft to
            # the RSS summary so a publisher that blocks scrapers still
            # surfaces something to the user.
            body_text = None
            if RSS_FETCH_FULL_TEXT and entry_url:
                body_text = _fetch_and_extract_article_body(entry_url)
                if body_text:
                    body_text = clean_article_text(body_text)
                    bodies_fetched += 1
                else:
                    bodies_failed += 1

            article = {
                "title": entry.get("title", "").strip(),
                "url": entry_url,
                "published_date": entry.get("published", entry.get("updated", "")),
                "summary": rss_summary,
                # `extracted_text` is what ingestion writes to articles.extracted_text.
                # Prefer the fetched body; fall back to the cleaned RSS
                # summary so we never write an empty extraction for
                # non-extractable pages — but always go through the cleaner.
                "extracted_text": body_text or rss_summary,
                "extraction_method": "html_body" if body_text else "rss_summary",
                "author": entry.get("author", ""),
                "tags": [
                    tag.get("term", "").strip()
                    for tag in entry.get("tags", [])
                    if tag.get("term")
                ],
            }
            # Skip entries without title or URL
            if article["title"] and article["url"]:
                articles.append(article)

        logger.info(
            f"RSS parsed {len(articles)} articles from {url} "
            f"(bodies_fetched={bodies_fetched}, fallback_to_summary={bodies_failed})"
        )
        return articles

    except Exception as e:
        logger.error(f"RSS feed fetch failed for {url}: {e}")
        return []


def fetch_carbon_brief_articles(max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Fetch recent articles from Carbon Brief RSS feed.

    Carbon Brief is a UK-based specialist on climate science and policy.

    Args:
        max_items: Max articles to return

    Returns:
        List of normalized article dicts.
    """
    articles = _parse_feed(CARBON_BRIEF_RSS, max_items)
    for a in articles:
        a["source_name"] = "Carbon Brief"
        a["source_domain"] = "carbonbrief.org"
        a["country_code"] = "GB"
    return articles


def fetch_eea_news(max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Fetch recent news from European Environment Agency RSS feed.

    EEA provides official EU environmental data and analysis.

    Args:
        max_items: Max articles to return

    Returns:
        List of normalized article dicts.
    """
    articles = _parse_feed(EEA_RSS, max_items)
    for a in articles:
        a["source_name"] = "European Environment Agency"
        a["source_domain"] = "eea.europa.eu"
        a["country_code"] = "EU"
    return articles


def fetch_feeds_from_registry(db, max_items_per_source: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch articles from all active feeds stored in the rss_feed_registry table.

    Queries the database for active feeds, calls _parse_feed() for each,
    and attaches source metadata from the registry row.

    Args:
        db: Database connection with execute_query() method.
        max_items_per_source: Max articles to pull per feed.

    Returns:
        Combined list of normalized article dicts across all registry feeds.
    """
    rows = db.execute_query(
        "SELECT * FROM rss_feed_registry WHERE is_active = true ORDER BY feed_name",
        {},
    )
    if not rows:
        logger.warning("RSS registry query returned no active feeds")
        return []

    combined: List[Dict[str, Any]] = []
    for row in rows:
        feed_name = row["feed_name"]
        feed_url = row["feed_url"]
        try:
            articles = _parse_feed(feed_url, max_items_per_source)
            for a in articles:
                a["source_name"] = feed_name
                a["source_domain"] = row.get("source_domain") or ""
                a["country_code"] = row.get("country_code") or "XX"
                a["reliability_tier"] = row.get("reliability_tier") or "public"
                a["region"] = row.get("region") or "global"
            combined.extend(articles)
            logger.info(f"RSS registry: fetched {len(articles)} from {feed_name}")
        except Exception as e:
            logger.warning(f"RSS registry: failed to fetch {feed_name}: {e}")

    logger.info(
        f"RSS registry: {len(combined)} total articles from {len(rows)} active feeds"
    )
    return combined


def sync_feed_registry_from_code(db) -> Dict[str, int]:
    """Seed/refresh rss_feed_registry from the in-code feed dict (P0 #2).

    The scheduled pollers (poll_rss_feeds, scheduled_rss_ingestion) ONLY read
    the rss_feed_registry table, but the rich feed set (215 feeds across 87
    countries incl. AU/ZA/NG/EG/SA) lives only in eu_feeds_registry.py and was
    never seeded into the table — so those countries had zero coverage.

    Idempotent: a feed is inserted only if neither its URL nor its name already
    exists (the table has UNIQUE on both), so existing rows — and their health /
    is_active state — are never disturbed. country_code is normalized to a
    storable alpha-2/'XX' (the table column is also CHAR(2)); the pan-regional
    grouping survives in the `region` column.
    """
    from app.domains.content.data_sources.eu_feeds_registry import get_all_feeds
    from app.tasks.ingestion import _normalize_country_code  # lazy: avoids import cycle

    feeds = get_all_feeds()
    inserted = skipped = errored = 0
    for f in feeds:
        name = (f.get("name") or "").strip()
        url = (f.get("url") or "").strip()
        if not name or not url:
            skipped += 1
            continue
        try:
            existing = db.execute_query(
                "SELECT 1 FROM rss_feed_registry WHERE feed_url = :u OR feed_name = :n LIMIT 1",
                {"u": url, "n": name[:255]},
            )
            if existing:
                skipped += 1
                continue
            db.execute_update(
                """
                INSERT INTO rss_feed_registry
                    (feed_name, feed_url, source_domain, country_code, region,
                     reliability_tier, is_active, is_system_feed)
                VALUES (:name, :url, :domain, :cc, :region, :tier, true, true)
                """,
                {
                    "name": name[:255],
                    "url": url,
                    "domain": ((f.get("domain") or "")[:255]) or None,
                    "cc": _normalize_country_code(f.get("country_code")),
                    "region": ((f.get("region") or "")[:50]) or None,
                    "tier": (f.get("tier") or "public")[:20],
                },
            )
            inserted += 1
        except Exception as exc:  # never let one bad feed abort the sync
            errored += 1
            logger.warning(f"feed-registry sync skipped {name!r}: {exc}")
    result = {
        "total_in_code": len(feeds),
        "inserted": inserted,
        "skipped_existing": skipped,
        "errored": errored,
    }
    logger.info(f"feed-registry sync: {result}")
    return result


def fetch_global_climate_feeds(
    max_items_per_source: int = 10,
    db=None,
) -> List[Dict[str, Any]]:
    """
    Fetch articles from global climate RSS feeds.

    When a database connection is provided, attempts to read active feeds from
    the rss_feed_registry table first. Falls back to the hardcoded
    GLOBAL_CLIMATE_FEEDS constant when the DB is unavailable or returns no rows.

    Args:
        max_items_per_source: Max articles to pull per feed.
        db: Optional database connection. When supplied, the registry is used
            as the primary feed source.

    Returns:
        Combined list of normalized article dicts across all sources.
    """
    # Attempt DB-driven registry when a connection is provided
    if db is not None:
        try:
            registry_articles = fetch_feeds_from_registry(db, max_items_per_source)
            if registry_articles:
                return registry_articles
            logger.info("RSS registry returned no results, falling back to hardcoded feeds")
        except Exception as e:
            logger.warning(f"RSS registry lookup failed, falling back to hardcoded feeds: {e}")

    # Fallback: iterate the hardcoded constant
    combined: List[Dict[str, Any]] = []
    for source_name, config in GLOBAL_CLIMATE_FEEDS.items():
        try:
            articles = _parse_feed(config["url"], max_items_per_source)
            for a in articles:
                a["source_name"] = source_name
                a["source_domain"] = config["source_domain"]
                a["country_code"] = config["country_code"]
                a["reliability_tier"] = config["reliability_tier"]
            combined.extend(articles)
            logger.info(f"Global RSS: fetched {len(articles)} from {source_name}")
        except Exception as e:
            logger.warning(f"Global RSS: failed to fetch {source_name}: {e}")

    logger.info(
        f"Global RSS (hardcoded): {len(combined)} total articles from {len(GLOBAL_CLIMATE_FEEDS)} sources"
    )
    return combined


def fetch_all_registered_feeds(
    max_items_per_source: int = 10,
    country_code: Optional[str] = None,
    tier: Optional[str] = None,
    db=None,
) -> List[Dict[str, Any]]:
    """
    Fetch articles from all registered climate feeds (EU + international).
    Supports filtering by country and reliability tier.
    """
    from app.domains.content.data_sources.eu_feeds_registry import (
        get_all_feeds, get_feeds_by_country, get_feeds_by_tier,
    )

    if country_code:
        feeds = get_feeds_by_country(country_code)
    elif tier:
        feeds = get_feeds_by_tier(tier)
    else:
        feeds = get_all_feeds()

    combined: List[Dict[str, Any]] = []
    for feed_config in feeds:
        try:
            articles = _parse_feed(feed_config["url"], max_items_per_source)
            for a in articles:
                a["source_name"] = feed_config["name"]
                a["source_domain"] = feed_config.get("source_domain", "")
                a["country_code"] = feed_config.get("country_code", "XX")
                a["reliability_tier"] = feed_config.get("reliability_tier", "public")
                a["language"] = feed_config.get("language", "en")
                a["region"] = feed_config.get("region", "global")
            combined.extend(articles)
            if articles:
                logger.info(f"Registry: fetched {len(articles)} from {feed_config['name']}")
        except Exception as e:
            logger.warning(f"Registry: failed to fetch {feed_config['name']}: {e}")

    logger.info(f"Registry total: {len(combined)} articles from {len(feeds)} feeds")
    return combined


def dedup_against_existing(articles: List[Dict], db) -> List[Dict]:
    """
    Filter out articles whose URLs already exist in the database.

    Args:
        articles: List of RSS article dicts (must have 'url' key)
        db: Database connection

    Returns:
        Filtered list of new articles.
    """
    if not articles:
        return []

    urls = [a["url"] for a in articles if a.get("url")]
    if not urls:
        return []

    try:
        existing = db.execute_query(
            "SELECT url FROM articles WHERE url = ANY(:urls)",
            {"urls": urls},
        )
        existing_urls = {r["url"] for r in (existing or [])}
        new_articles = [a for a in articles if a.get("url") not in existing_urls]
        logger.info(f"RSS dedup: {len(articles)} total, {len(new_articles)} new")
        return new_articles
    except Exception as e:
        logger.warning(f"RSS dedup query failed: {e}")
        return articles  # Return all if dedup fails
