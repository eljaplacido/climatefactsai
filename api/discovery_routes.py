from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth_routes import require_admin
from shared.database import get_postgres
from shared.logger import setup_logging

router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = setup_logging("discovery-admin")


class DiscoverNewsRequest(BaseModel):
    country_code: str = Field(default="FI", min_length=2, max_length=2)
    country_name: Optional[str] = None
    keywords: List[str] = Field(default_factory=list, description="Keywords/tags to focus the discovery")
    max_articles: int = Field(default=10, ge=1, le=25)
    days_back: int = Field(default=3, ge=1, le=14)
    verify: bool = Field(default=False, description="Queue verification for inserted articles")


class DiscoverNewsResponse(BaseModel):
    task_id: str
    inserted: int
    article_ids: List[str]


def _extract_json_block(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start:end])


def _to_pg_array(items: List[str]) -> str:
    if not items:
        return "{}"
    escaped = ['"' + str(item).replace('"', '\\"') + '"' for item in items if item]
    return "{" + ",".join(escaped) + "}"


def _resolve_country_name(country_code: str) -> Optional[str]:
    db = get_postgres()
    try:
        rows = db.execute_query(
            """
            SELECT country_name
            FROM countries
            WHERE country_code = :code
            LIMIT 1
            """,
            {"code": country_code.upper()},
        )
        if rows:
            return rows[0].get("country_name")
    except Exception:
        return None
    return None


def _perplexity_discover(
    *,
    api_key: str,
    country_name: str,
    country_code: str,
    keywords: List[str],
    max_articles: int,
    days_back: int,
) -> List[Dict[str, Any]]:
    base_url = "https://api.perplexity.ai"
    model = os.getenv("PERPLEXITY_MODEL", "sonar")

    keywords_part = ""
    if keywords:
        keywords_part = f"\nFocus keywords/tags: {', '.join(keywords)}"

    prompt = f"""Find the most important climate change related news from {country_name} from the last {days_back} days.{keywords_part}

Requirements:
1. Focus on the last {days_back} days
2. Prioritize credible sources
3. For EACH article found, provide:
   - Exact title
   - Brief summary (2-3 sentences)
   - Source URL
   - Source name
   - Publication date (YYYY-MM-DD if available)
   - Main topics/themes

Respond ONLY in this JSON format:
{{
  "articles": [
    {{
      "title": "Exact article title",
      "summary": "Brief summary of the article",
      "url": "Direct link to article",
      "source_name": "Name of news outlet",
      "published_date": "YYYY-MM-DD",
      "topics": ["climate", "emissions"],
      "language": "en"
    }}
  ]
}}

Find up to {max_articles} most relevant and recent articles."""

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4000,
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]

    parsed = _extract_json_block(content)
    articles = parsed.get("articles") or []
    normalized: List[Dict[str, Any]] = []
    for item in articles:
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        summary = (item.get("summary") or "").strip()
        source_name = (item.get("source_name") or "Perplexity Research").strip()
        language = (item.get("language") or "en").strip()[:2]
        topics = item.get("topics") or []
        tags_raw = ["climate"] + keywords + topics
        tags = [t.strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        # De-duplicate while preserving order
        seen = set()
        tags = [t for t in tags if not (t.lower() in seen or seen.add(t.lower()))][:10]
        normalized.append(
            {
                "url": url,
                "title": title,
                "source_name": source_name,
                "published_date": item.get("published_date"),
                "excerpt": summary[:280] if summary else None,
                "extracted_text": summary or title,
                "language_code": language,
                "country_code": country_code.upper(),
                "tags": tags,
            }
        )
    return normalized


@router.post("/discover-news", response_model=DiscoverNewsResponse)
async def discover_news(
    request_body: DiscoverNewsRequest,
    request: Request,
    current_user: dict = Depends(require_admin),  # API-09: /api/admin/* must be admin-gated (Perplexity cost vector)
) -> DiscoverNewsResponse:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="PERPLEXITY_API_KEY not set. Add it to .env to enable on-demand discovery.",
        )

    country_code = request_body.country_code.upper()
    country_name = request_body.country_name or _resolve_country_name(country_code) or country_code
    task_id = f"discover-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"

    # Enforce discovery query limits if user is authenticated
    from api.rate_limiter import UsageTracker, RateLimitMiddleware

    # Resolve the authenticated user from the bearer token so the real
    # tier drives discovery limits. Previously every caller was treated as
    # freemium, making tier-aware limits dead code.
    user = RateLimitMiddleware._resolve_user_from_token(request)
    if user:
        user_tier = user.get("subscription_tier", "freemium")
        user_id = str(user.get("user_id"))
    else:
        user_tier = "freemium"
        user_id = f"anon-{request.client.host if hasattr(request, 'client') and request.client else 'unknown'}"

    # Check discovery limit
    allowed, used, limit = UsageTracker.check_discovery_limit(user_id, user_tier)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily discovery limit exceeded ({used}/{limit}). Upgrade your plan for more queries.",
        )

    # Check country access
    country_allowed, _, country_limit = UsageTracker.check_country_access(
        user_tier, [country_code]
    )

    # Log discovery usage
    try:
        UsageTracker.log_usage(
            user_id=user_id,
            usage_type="discovery_query",
            resource_id=task_id,
            metadata={"country_code": country_code, "max_articles": request_body.max_articles},
        )
    except Exception:
        pass  # Don't fail the request if usage logging fails

    logger.info(
        "Discovering news via Perplexity",
        task_id=task_id,
        country_code=country_code,
        country_name=country_name,
        max_articles=request_body.max_articles,
        days_back=request_body.days_back,
        keywords=request_body.keywords,
    )

    try:
        articles = _perplexity_discover(
            api_key=api_key,
            country_name=country_name,
            country_code=country_code,
            keywords=request_body.keywords,
            max_articles=request_body.max_articles,
            days_back=request_body.days_back,
        )
    except requests.RequestException as exc:
        logger.error("Perplexity discovery failed", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Perplexity request failed") from exc
    except Exception as exc:
        logger.error("Perplexity discovery parse failed", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Unable to parse discovery response") from exc

    db = get_postgres()
    inserted_ids: List[str] = []

    insert_sql = """
        INSERT INTO articles (
            url, title, author, published_date, source_name,
            extracted_text, excerpt, language_code, country_code, task_id,
            source_credibility_score, tags, created_at
        ) VALUES (
            :url, :title, :author, :published_date, :source_name,
            :extracted_text, :excerpt, :language_code, :country_code, :task_id,
            :source_credibility_score, :tags, CURRENT_TIMESTAMP
        )
        ON CONFLICT (url) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP,
            country_code = EXCLUDED.country_code,
            tags = EXCLUDED.tags
        RETURNING article_id
    """

    # End2End audit gap (2026-05-27, Section II): stamp the real tier-band
    # credibility score per article instead of the constant 50 that made the
    # reliability scorer's 50% source weighting collapse to neutral. Lazy
    # import to keep the route module light when the helper isn't available.
    try:
        from app.domains.trust.source_tier_service import get_source_credibility_score
    except Exception:  # pragma: no cover - defensive
        get_source_credibility_score = None  # type: ignore[assignment]

    # End2End audit gap (2026-05-27, Task D): clean HTML from extracted_text
    # before persisting so the Full Article panel doesn't surface raw
    # `<img>` / `<p>` markup the way it does for Premium Times feeds.
    try:
        from shared.html_cleaner import clean_article_text
    except Exception:  # pragma: no cover
        clean_article_text = None  # type: ignore[assignment]

    for article in articles:
        try:
            published_date = None
            if article.get("published_date"):
                # Allow YYYY-MM-DD strings; DB will coerce or reject.
                published_date = article["published_date"]

            source_name = article["source_name"]
            credibility_score = 50
            if get_source_credibility_score is not None:
                try:
                    credibility_score = get_source_credibility_score(
                        db, source_name, article.get("url"),
                    )
                except Exception as exc:
                    logger.debug(
                        "tier_credibility_lookup_failed",
                        source=source_name, error=str(exc),
                    )

            extracted = article["extracted_text"]
            excerpt = article.get("excerpt")
            if clean_article_text is not None:
                try:
                    extracted = clean_article_text(extracted)
                    if excerpt:
                        excerpt = clean_article_text(excerpt)[:500]
                except Exception as exc:
                    logger.debug("html_cleaner failed", url=article.get("url"), error=str(exc))

            result = db.execute_query(
                insert_sql,
                params={
                    "url": article["url"],
                    "title": article["title"],
                    "author": None,
                    "published_date": published_date,
                    "source_name": source_name,
                    "extracted_text": extracted,
                    "excerpt": excerpt,
                    "language_code": article.get("language_code") or "en",
                    "country_code": country_code,
                    "task_id": task_id,
                    "source_credibility_score": credibility_score,
                    "tags": _to_pg_array(article.get("tags") or []),
                },
            )
            if result and result[0].get("article_id"):
                inserted_ids.append(str(result[0]["article_id"]))
        except Exception as exc:
            logger.warning("Insert failed", task_id=task_id, url=article.get("url"), error=str(exc))

    if request_body.verify and inserted_ids:
        try:
            from app.tasks.processing import verify_claims
            from opentelemetry import propagate

            headers: Dict[str, str] = {}
            propagate.inject(headers)
            verify_claims.apply_async(args=[{"task_id": task_id, "article_ids": inserted_ids}], headers=headers)
        except Exception as exc:
            logger.warning("Unable to queue verification", task_id=task_id, error=str(exc))

    return DiscoverNewsResponse(task_id=task_id, inserted=len(inserted_ids), article_ids=inserted_ids)
