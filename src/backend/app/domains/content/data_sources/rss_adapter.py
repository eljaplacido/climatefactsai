"""
RSS Adapter — Global climate news RSS feed integration.

Parses Carbon Brief, EEA, and global climate RSS feeds as discovery sources.
Supports dynamic feed registry from the database with hardcoded fallback.
Deduplicates against existing articles by URL.
"""

from typing import Any, Dict, List, Optional

import feedparser

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default RSS feed URLs
CARBON_BRIEF_RSS = "https://www.carbonbrief.org/feed/"
EEA_RSS = "https://www.eea.europa.eu/api/rss"

# Global climate news feeds — 9 international sources
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
    """Parse an RSS feed and return normalized article entries."""
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse issue for {url}: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries[:max_items]:
            article = {
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", "").strip(),
                "published_date": entry.get("published", entry.get("updated", "")),
                "summary": entry.get("summary", "")[:500].strip(),
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

        logger.info(f"RSS parsed {len(articles)} articles from {url}")
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
