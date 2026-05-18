"""
Celery ingestion tasks — discovers new climate articles and stores them.

Uses PerplexityNewsDiscovery when PERPLEXITY_API_KEY is set. Falls back
to querying existing articles from the database for pipeline testing.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.celery_app import app
from app.core.database import get_db
from app.core.logging import get_logger
from app.domains.content.source_profiles import SourceProfileService

logger = get_logger(__name__)


def _try_discover_via_perplexity(
    country: str,
    country_code: str,
    max_articles: int,
) -> Optional[List[Dict[str, Any]]]:
    """Attempt Perplexity-based news discovery. Returns None if unavailable."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        logger.info("PERPLEXITY_API_KEY not set — skipping live discovery")
        return None

    try:
        # Import from the ingestion service
        import sys
        from pathlib import Path

        service_path = Path(__file__).resolve().parents[2] / "services" / "ingestion_service" / "src"
        if str(service_path) not in sys.path:
            sys.path.insert(0, str(service_path))

        from perplexity_news_discovery import PerplexityNewsDiscovery

        discovery = PerplexityNewsDiscovery(api_key=api_key)

        # Map country codes to names — all continents
        country_names = {
            # Europe
            "FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
            "DE": "Germany", "FR": "France", "NL": "Netherlands", "ES": "Spain",
            "IT": "Italy", "PT": "Portugal", "PL": "Poland", "GB": "United Kingdom",
            "IE": "Ireland", "AT": "Austria", "BE": "Belgium", "CZ": "Czechia",
            "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania", "GR": "Greece",
            "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria", "HR": "Croatia",
            "SK": "Slovakia", "SI": "Slovenia", "LU": "Luxembourg", "MT": "Malta",
            "CY": "Cyprus", "IS": "Iceland", "CH": "Switzerland", "LI": "Liechtenstein",
            "TR": "Turkey", "UA": "Ukraine", "MD": "Moldova", "BY": "Belarus",
            "RS": "Serbia", "BA": "Bosnia and Herzegovina", "ME": "Montenegro",
            "MK": "North Macedonia", "AL": "Albania", "XK": "Kosovo",
            "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan",
            # US & North America
            "US": "United States", "CA": "Canada", "MX": "Mexico",
            # Latin America
            "BR": "Brazil", "AR": "Argentina", "CO": "Colombia", "CL": "Chile",
            "PE": "Peru", "EC": "Ecuador", "VE": "Venezuela", "UY": "Uruguay",
            "PY": "Paraguay", "BO": "Bolivia", "CR": "Costa Rica", "PA": "Panama",
            # Africa
            "KE": "Kenya", "NG": "Nigeria", "ZA": "South Africa", "GH": "Ghana",
            "TZ": "Tanzania", "UG": "Uganda", "RW": "Rwanda", "ET": "Ethiopia",
            "EG": "Egypt", "MA": "Morocco", "SN": "Senegal", "ZM": "Zambia",
            "MW": "Malawi", "MZ": "Mozambique", "CI": "Ivory Coast",
            # Asia
            "CN": "China", "IN": "India", "JP": "Japan", "KR": "South Korea",
            "ID": "Indonesia", "TH": "Thailand", "VN": "Vietnam", "PH": "Philippines",
            "SG": "Singapore", "MY": "Malaysia", "BD": "Bangladesh", "PK": "Pakistan",
            "AU": "Australia", "NZ": "New Zealand", "TW": "Taiwan",
            # Middle East
            "AE": "United Arab Emirates", "SA": "Saudi Arabia", "IL": "Israel",
            "JO": "Jordan", "LB": "Lebanon", "IQ": "Iraq", "IR": "Iran",
            "QA": "Qatar", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain",
        }
        country_name = country_names.get(country_code, country or "Finland")

        articles = discovery.discover_news(
            country=country_name,
            country_code=country_code,
            max_articles=max_articles,
        )
        return articles
    except Exception as exc:
        logger.warning("Perplexity discovery failed, falling back to DB", error=str(exc))
        return None


def _insert_discovered_articles(
    db,
    articles: List[Dict[str, Any]],
    country_code: str,
) -> List[str]:
    """Insert discovered articles into the database and return their IDs."""
    inserted_ids: List[str] = []

    for article in articles:
        article_id = str(uuid4())
        title = article.get("title", "Untitled")
        url = article.get("url", "")

        # Skip if URL already exists
        existing = db.execute_query(
            "SELECT article_id FROM articles WHERE url = :url LIMIT 1",
            {"url": url},
        )
        if existing:
            logger.info("Article already exists, skipping", url=url)
            inserted_ids.append(str(existing[0]["article_id"]))
            continue

        try:
            db.execute_update(
                """
                INSERT INTO articles (
                    article_id, title, url, source_name, excerpt, extracted_text,
                    country_code, published_date, claims_status, content_category,
                    created_at, updated_at
                ) VALUES (
                    :article_id, :title, :url, :source_name, :excerpt, :extracted_text,
                    :country_code, :published_date, 'pending', :content_category,
                    NOW(), NOW()
                )
                """,
                {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "source_name": article.get("source_name") or article.get("source", "Unknown"),
                    "excerpt": (article.get("summary") or article.get("excerpt") or "")[:500],
                    # Prefer article.extracted_text (set by rss_adapter._fetch_and_extract_article_body
                    # to the real article body). Fall back through content/summary/excerpt/title for
                    # sources that don't go through RSS extraction.
                    "extracted_text": (
                        article.get("extracted_text")
                        or article.get("content")
                        or article.get("summary")
                        or article.get("excerpt")
                        or title
                    ),
                    "country_code": article.get("country_code", country_code),
                    "published_date": article.get("published_date", datetime.utcnow()),
                    "content_category": article.get("content_category"),
                },
            )
            inserted_ids.append(article_id)
            logger.info("Inserted article", article_id=article_id, title=title[:80])

            # Detect and store content category
            try:
                from app.domains.content.category_service import detect_category
                tags_list = article.get("tags", [])
                category = detect_category(
                    title=title,
                    text=article.get("summary") or article.get("excerpt") or "",
                    tags=tags_list if isinstance(tags_list, list) else [],
                )
                db.execute_update(
                    "UPDATE articles SET content_category = :cat WHERE article_id = :aid",
                    {"cat": category, "aid": article_id},
                )
            except Exception as cat_exc:
                logger.warning("Category detection failed", error=str(cat_exc))

            # Upsert source profile for tracking
            try:
                source_svc = SourceProfileService(db)
                source_svc.upsert_from_article(
                    source_name=article.get("source", "Unknown"),
                    url=url,
                )
            except Exception as sp_exc:
                logger.warning("Source profile upsert failed", error=str(sp_exc))

            # Best-effort enrichment + embedding + entity extraction so newly
            # discovered articles are immediately queryable by chat / deep-search
            # / similarity. Failures don't block ingestion — the batch_enrich
            # admin task will retry later.
            try:
                import asyncio
                from app.domains.content.embedding_service import EmbeddingService
                emb_svc = EmbeddingService(db)
                asyncio.run(emb_svc.populate_embedding(article_id))
            except Exception as emb_exc:
                logger.warning("Post-ingest embedding failed", article_id=article_id, error=str(emb_exc))

            try:
                import asyncio
                from app.domains.intelligence.entity_extraction_service import EntityExtractionService
                entity_svc = EntityExtractionService(db)
                article_text = article.get("summary") or article.get("excerpt") or article.get("content") or ""
                if article_text.strip() or title.strip():
                    asyncio.run(entity_svc.extract_and_store(
                        article_id=article_id,
                        title=title,
                        text=article_text,
                    ))
            except Exception as kg_exc:
                logger.warning("Post-ingest entity extraction failed", article_id=article_id, error=str(kg_exc))
        except Exception as exc:
            logger.error("Failed to insert article", title=title[:80], error=str(exc))

    return inserted_ids


@app.task(bind=True, autoretry_for=(Exception,), max_retries=3, rate_limit="10/m")
def discover_articles(
    self,
    country: Optional[str] = "FI",
    max_articles: int = 10,
    seed_article_ids: Optional[List[str]] = None,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Entry task for the ingestion → verification workflow.

    1. If seed_article_ids are provided, use those directly.
    2. Otherwise, try Perplexity-based live discovery.
    3. Fall back to querying recent articles from the database.

    Returns:
        dict with task_id, article_ids, and discovery metadata
    """
    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"task-{uuid4()}"
    country_code = country or "FI"

    logger.info(
        "Ingestion task started",
        task_id=task_id,
        country=country_code,
        max_articles=max_articles,
        seed_count=len(seed_article_ids or []),
    )

    article_ids: List[str] = []

    # Path 1: Manual seed IDs
    if seed_article_ids:
        article_ids = seed_article_ids[:]
        discovery_method = "seed"

    # Path 2: Live discovery via Perplexity
    else:
        discovered = _try_discover_via_perplexity(
            country=country_code,
            country_code=country_code,
            max_articles=max_articles,
        )
        if discovered:
            db = get_db()
            article_ids = _insert_discovered_articles(db, discovered, country_code)
            discovery_method = "perplexity"
        else:
            # Path 3: Fallback — query existing unprocessed articles
            db = get_db()
            query = """
                SELECT article_id
                FROM articles
                WHERE (:country IS NULL OR country_code = :country)
                ORDER BY created_at DESC
                LIMIT :limit
            """
            rows = db.execute_query(
                query,
                {"country": country_code, "limit": max_articles},
            )
            article_ids = [str(row["article_id"]) for row in rows if row.get("article_id")]
            discovery_method = "database_fallback"

    payload = {
        "task_id": task_id,
        "country": country_code,
        "article_ids": article_ids,
        "discovery_method": discovery_method,
        "discovered_at": datetime.utcnow().isoformat(),
    }

    logger.info(
        "Ingestion task completed",
        task_id=task_id,
        article_count=len(article_ids),
        method=discovery_method,
    )
    return payload


@app.task(bind=True, max_retries=1)
def scheduled_multi_country_ingestion(
    self,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Master scheduler task: dispatches per-country ingestion tasks.

    Reads INGESTION_COUNTRIES from env, dispatches discover_articles for each
    country with 5-minute stagger to avoid API rate limits.
    """
    countries_str = os.getenv("INGESTION_COUNTRIES", "FI,SE,DE,FR,NL,ES,IT,NO,DK,PL,US,GB,KE,NG,ZA,BR,MX,IN,JP,AE")
    countries = [c.strip().upper() for c in countries_str.split(",") if c.strip()]
    max_per_country = int(os.getenv("MAX_ARTICLES_PER_COUNTRY", "5"))

    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"multi-{uuid4()}"

    logger.info(
        "Multi-country ingestion started",
        task_id=task_id,
        countries=countries,
        max_per_country=max_per_country,
    )

    dispatched = []
    for idx, country_code in enumerate(countries):
        countdown_seconds = idx * 300  # 5 minutes apart
        try:
            result = discover_articles.apply_async(
                kwargs={"country": country_code, "max_articles": max_per_country},
                countdown=countdown_seconds,
            )
            dispatched.append({
                "country": country_code,
                "celery_task_id": result.id,
                "scheduled_delay_seconds": countdown_seconds,
            })
            logger.info(
                "Dispatched country ingestion",
                country=country_code,
                delay_seconds=countdown_seconds,
            )
        except Exception as exc:
            logger.error(
                "Failed to dispatch country ingestion",
                country=country_code,
                error=str(exc),
            )

    return {
        "task_id": task_id,
        "countries_dispatched": len(dispatched),
        "dispatched": dispatched,
        "dispatched_at": datetime.utcnow().isoformat(),
    }


@app.task(bind=True, max_retries=2)
def scheduled_rss_ingestion(
    self,
    max_items_per_source: int = 10,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Periodic task: fetch articles from all global climate RSS feeds.

    Calls fetch_global_climate_feeds() with a DB connection so the registry
    table is preferred over the hardcoded fallback. Deduplicates against
    existing URLs and inserts new articles into the database.
    """
    from app.domains.content.data_sources.rss_adapter import (
        fetch_global_climate_feeds,
        dedup_against_existing,
    )

    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"rss-{uuid4()}"

    logger.info("RSS ingestion started", task_id=task_id)

    db = get_db()

    # Fetch from all global feeds — registry-first, hardcoded fallback
    all_articles = fetch_global_climate_feeds(
        max_items_per_source=max_items_per_source, db=db
    )

    if not all_articles:
        logger.info("RSS ingestion: no articles fetched")
        return {"task_id": task_id, "inserted": 0, "total_fetched": 0}

    # Deduplicate against existing database articles
    new_articles = dedup_against_existing(all_articles, db)

    # Insert new articles
    inserted_ids = _insert_discovered_articles(db, new_articles, country_code="XX")

    logger.info(
        "RSS ingestion completed",
        task_id=task_id,
        total_fetched=len(all_articles),
        new_articles=len(new_articles),
        inserted=len(inserted_ids),
    )

    return {
        "task_id": task_id,
        "total_fetched": len(all_articles),
        "new_after_dedup": len(new_articles),
        "inserted": len(inserted_ids),
        "article_ids": inserted_ids,
    }


@app.task(bind=True, max_retries=3, rate_limit="2/m")
def poll_rss_feeds(
    self,
    max_items_per_source: int = 10,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Periodic task: poll all active feeds from the rss_feed_registry table.

    For each active feed row:
      1. Calls _parse_feed() to retrieve articles.
      2. Deduplicates against existing article URLs in the database.
      3. Inserts new articles.
      4. Updates last_fetched_at and resets or increments fetch_error_count
         on the registry row based on success or failure.

    Returns a summary dict with counts per feed and overall totals.
    """
    from app.domains.content.data_sources.rss_adapter import (
        _parse_feed,
        dedup_against_existing,
    )

    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"poll-{uuid4()}"

    logger.info("poll_rss_feeds started", task_id=task_id)

    db = get_db()

    # Fetch all active registry rows
    try:
        feed_rows = db.execute_query(
            "SELECT * FROM rss_feed_registry WHERE is_active = true ORDER BY feed_name",
            {},
        )
    except Exception as exc:
        logger.error("poll_rss_feeds: failed to read registry", error=str(exc))
        raise

    if not feed_rows:
        logger.info("poll_rss_feeds: no active feeds in registry")
        return {
            "task_id": task_id,
            "feeds_polled": 0,
            "total_fetched": 0,
            "total_inserted": 0,
        }

    feed_summaries: List[Dict[str, Any]] = []
    total_fetched = 0
    total_inserted = 0

    for row in feed_rows:
        feed_id = str(row["feed_id"])
        feed_name = row["feed_name"]
        feed_url = row["feed_url"]
        source_domain = row.get("source_domain") or ""
        country_code = row.get("country_code") or "XX"
        reliability_tier = row.get("reliability_tier") or "public"
        region = row.get("region") or "global"

        fetch_success = False
        fetched_count = 0
        inserted_count = 0

        try:
            articles = _parse_feed(feed_url, max_items_per_source)
            for a in articles:
                a["source_name"] = feed_name
                a["source_domain"] = source_domain
                a["country_code"] = country_code
                a["reliability_tier"] = reliability_tier
                a["region"] = region

            fetched_count = len(articles)
            total_fetched += fetched_count

            if articles:
                new_articles = dedup_against_existing(articles, db)
                inserted_ids = _insert_discovered_articles(db, new_articles, country_code=country_code)
                inserted_count = len(inserted_ids)
                total_inserted += inserted_count

            fetch_success = True
            logger.info(
                "poll_rss_feeds: feed polled",
                feed=feed_name,
                fetched=fetched_count,
                inserted=inserted_count,
            )

        except Exception as exc:
            logger.warning(
                "poll_rss_feeds: feed fetch error",
                feed=feed_name,
                url=feed_url,
                error=str(exc),
            )

        # Update registry row: last_fetched_at and error count
        try:
            if fetch_success:
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           fetch_error_count = 0
                     WHERE feed_id = :feed_id
                    """,
                    {"feed_id": feed_id},
                )
            else:
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           fetch_error_count = fetch_error_count + 1
                     WHERE feed_id = :feed_id
                    """,
                    {"feed_id": feed_id},
                )
        except Exception as upd_exc:
            logger.warning(
                "poll_rss_feeds: failed to update registry row",
                feed_id=feed_id,
                error=str(upd_exc),
            )

        feed_summaries.append({
            "feed_id": feed_id,
            "feed_name": feed_name,
            "fetched": fetched_count,
            "inserted": inserted_count,
            "success": fetch_success,
        })

    logger.info(
        "poll_rss_feeds completed",
        task_id=task_id,
        feeds_polled=len(feed_rows),
        total_fetched=total_fetched,
        total_inserted=total_inserted,
    )

    return {
        "task_id": task_id,
        "feeds_polled": len(feed_rows),
        "total_fetched": total_fetched,
        "total_inserted": total_inserted,
        "feed_summaries": feed_summaries,
        "polled_at": datetime.utcnow().isoformat(),
    }


@app.task(bind=True, max_retries=2)
def scheduled_scientific_feed_ingestion(
    self,
    max_items_per_source: int = 15,
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Periodic task: fetch articles only from scientific-tier feeds in the registry.

    Queries rss_feed_registry for rows where reliability_tier = 'scientific',
    fetches, deduplicates, and inserts new articles. Updates registry metadata
    on each row after processing.

    Scientific feeds include IPCC, Nature Climate Change, UN Climate News,
    WMO, and any future feeds registered with tier 'scientific'.
    """
    from app.domains.content.data_sources.rss_adapter import (
        _parse_feed,
        dedup_against_existing,
    )

    task_id = (task_metadata or {}).get("task_id") or self.request.id or f"sci-{uuid4()}"

    logger.info("scheduled_scientific_feed_ingestion started", task_id=task_id)

    db = get_db()

    try:
        feed_rows = db.execute_query(
            """
            SELECT * FROM rss_feed_registry
             WHERE is_active = true
               AND reliability_tier = 'scientific'
             ORDER BY feed_name
            """,
            {},
        )
    except Exception as exc:
        logger.error(
            "scheduled_scientific_feed_ingestion: registry query failed",
            error=str(exc),
        )
        raise

    if not feed_rows:
        logger.info("scheduled_scientific_feed_ingestion: no active scientific feeds")
        return {
            "task_id": task_id,
            "feeds_polled": 0,
            "total_fetched": 0,
            "total_inserted": 0,
        }

    total_fetched = 0
    total_inserted = 0

    for row in feed_rows:
        feed_id = str(row["feed_id"])
        feed_name = row["feed_name"]
        feed_url = row["feed_url"]
        country_code = row.get("country_code") or "XX"
        fetch_success = False

        try:
            articles = _parse_feed(feed_url, max_items_per_source)
            for a in articles:
                a["source_name"] = feed_name
                a["source_domain"] = row.get("source_domain") or ""
                a["country_code"] = country_code
                a["reliability_tier"] = "scientific"
                a["region"] = row.get("region") or "global"

            total_fetched += len(articles)

            if articles:
                new_articles = dedup_against_existing(articles, db)
                inserted_ids = _insert_discovered_articles(
                    db, new_articles, country_code=country_code
                )
                total_inserted += len(inserted_ids)

            fetch_success = True
            logger.info(
                "Scientific feed ingested",
                feed=feed_name,
                fetched=len(articles),
            )

        except Exception as exc:
            logger.warning(
                "Scientific feed fetch failed",
                feed=feed_name,
                error=str(exc),
            )

        # Update registry metadata
        try:
            if fetch_success:
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           fetch_error_count = 0
                     WHERE feed_id = :feed_id
                    """,
                    {"feed_id": feed_id},
                )
            else:
                db.execute_update(
                    """
                    UPDATE rss_feed_registry
                       SET last_fetched_at = NOW(),
                           fetch_error_count = fetch_error_count + 1
                     WHERE feed_id = :feed_id
                    """,
                    {"feed_id": feed_id},
                )
        except Exception as upd_exc:
            logger.warning(
                "Scientific feed registry update failed",
                feed_id=feed_id,
                error=str(upd_exc),
            )

    logger.info(
        "scheduled_scientific_feed_ingestion completed",
        task_id=task_id,
        feeds_polled=len(feed_rows),
        total_fetched=total_fetched,
        total_inserted=total_inserted,
    )

    return {
        "task_id": task_id,
        "feeds_polled": len(feed_rows),
        "total_fetched": total_fetched,
        "total_inserted": total_inserted,
        "ingested_at": datetime.utcnow().isoformat(),
    }
