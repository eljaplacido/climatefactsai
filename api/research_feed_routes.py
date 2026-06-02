"""Research feed — subscribe to research topics + CrossRef poller.

Deferred audit item #13 (Slice "research-feed", 2026-05-25). The user
asked for "a research analysis feed exactly like the news feed, but
just of research and user could choose area, topic to follow". Three
public endpoints + one admin poller:

  POST   /api/research/subscriptions          — subscribe to a topic
  GET    /api/research/subscriptions          — list mine
  DELETE /api/research/subscriptions/{id}     — unsubscribe
  GET    /api/research/feed                   — recent items, mine
  POST   /api/admin/research-poll             — token-gated batch poll

The poller hits CrossRef (free, no auth) and writes new (subscription,
DOI) rows into research_feed_items (mig 047). One paper survives at
most once per subscription via the uq_research_feed_doi constraint
plus a partial-unique title index for NULL-DOI preprints.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from shared.database import get_postgres

logger = logging.getLogger("research-feed")

router = APIRouter(prefix="/api/research", tags=["Research Feed"])
admin_router = APIRouter(prefix="/api/admin/research-poll", tags=["Admin / Research"])

# Per-tier soft caps so freemium users don't spawn 100s of subscriptions.
TIER_SUB_CAPS = {
    "freemium": 2,
    "free": 2,
    "anonymous": 0,
    "basic": 10,
    "standard": 10,
    "professional": 50,
    "enterprise": None,  # unlimited
}

# CrossRef has no auth requirement but expects a polite User-Agent
# with a mailto: contact (https://api.crossref.org/swagger-ui/).
USER_AGENT = (
    "ClimatefactsResearchFeed/1.0 "
    "(+https://climatefacts.ai/about/crawler; mailto:noreply@climatefacts.ai)"
)
CROSSREF_BASE = "https://api.crossref.org/works"
DEFAULT_POLL_ROWS = 25


class SubscribeRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200,
                       description="Short label — 'Arctic sea ice', 'CBAM compliance'")
    keywords: Optional[List[str]] = Field(default=None, max_length=15)
    notification_email: bool = Field(default=False)


class SubscriptionResponse(BaseModel):
    subscription_id: str
    topic: str
    keywords: List[str]
    notification_email: bool
    is_active: bool
    last_polled_at: Optional[str]
    created_at: str


class FeedItemResponse(BaseModel):
    item_id: str
    subscription_id: str
    topic: str
    doi: Optional[str] = None
    title: str
    authors: List[str]
    abstract: Optional[str] = None
    journal: Optional[str] = None
    published_date: Optional[str] = None
    crossref_url: Optional[str] = None
    source: str
    discovered_at: str


def _auth_admin(
    token: Optional[str], scheduler_secret: Optional[str] = None
) -> None:
    """Accept either the CORPORATE_SYNC_TOKEN (operator curl) or the
    SCHEDULER_SECRET that all Cloud Scheduler jobs send via
    X-Scheduler-Secret. End2End audit (2026-05-27 §1.4) added
    cn-research-poll to provision-infra.sh; the scheduler-update step
    sets X-Scheduler-Secret on every job."""
    corp_expected = os.environ.get("CORPORATE_SYNC_TOKEN")
    sched_expected = os.environ.get("SCHEDULER_SECRET")
    if not corp_expected and not sched_expected:
        raise HTTPException(
            status_code=503,
            detail="Research-poll admin endpoint disabled — set CORPORATE_SYNC_TOKEN or SCHEDULER_SECRET",
        )
    if corp_expected and token == corp_expected:
        return
    if sched_expected and scheduler_secret == sched_expected:
        return
    raise HTTPException(status_code=401, detail="Invalid admin token")


def _row_to_subscription(r: dict) -> SubscriptionResponse:
    return SubscriptionResponse(
        subscription_id=str(r["subscription_id"]),
        topic=r["topic"],
        keywords=list(r.get("keywords") or []),
        notification_email=bool(r.get("notification_email")),
        is_active=bool(r.get("is_active", True)),
        last_polled_at=str(r["last_polled_at"]) if r.get("last_polled_at") else None,
        created_at=str(r["created_at"]),
    )


# ---------------------------------------------------------------------------
# Default research topics — curated catalogue + bulk-subscribe (2026-05-27)
# ---------------------------------------------------------------------------

class DefaultTopicResponse(BaseModel):
    topic_id: str
    slug: str
    label: str
    description: Optional[str] = None
    keywords: List[str] = []
    category: Optional[str] = None
    sort_order: int = 100


@router.get("/default-topics", response_model=List[DefaultTopicResponse])
async def list_default_topics():
    """Public catalogue of curated climate-research topics (mig 048).

    Open endpoint — anyone can browse the catalogue. Users subscribe to a
    subset via POST /subscriptions or in bulk via POST /subscriptions/default.
    """
    db = get_postgres()
    try:
        rows = db.execute_query(
            """SELECT topic_id, slug, label, description, keywords,
                      category, sort_order
                 FROM default_research_topics
                WHERE is_active = TRUE
                ORDER BY sort_order, label""",
            {},
        )
    except Exception as exc:
        logger.warning(f"list_default_topics failed: {exc}")
        return []
    return [
        DefaultTopicResponse(
            topic_id=str(r["topic_id"]),
            slug=r["slug"],
            label=r["label"],
            description=r.get("description"),
            keywords=list(r.get("keywords") or []),
            category=r.get("category"),
            sort_order=int(r.get("sort_order") or 100),
        )
        for r in (rows or [])
    ]


class BulkSubscribeRequest(BaseModel):
    slugs: List[str] = Field(..., min_length=1, max_length=20,
                             description="default_research_topics slugs to subscribe to")


@router.post("/subscriptions/default", status_code=201)
async def bulk_subscribe_defaults(
    request: BulkSubscribeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Bulk-subscribe the current user to a set of default topics.

    Looks up the topic catalogue, then INSERTs one research_subscriptions
    row per topic with ON CONFLICT DO NOTHING (so re-running is safe and
    pre-existing manual subscriptions are preserved). Respects the per-tier
    subscription cap.
    """
    user_id = current_user["user_id"]
    tier = str(current_user.get("subscription_tier", "freemium"))
    cap = TIER_SUB_CAPS.get(tier, 2)

    db = get_postgres()
    rows = db.execute_query(
        """SELECT slug, label, keywords FROM default_research_topics
            WHERE slug = ANY(:slugs) AND is_active = TRUE""",
        {"slugs": request.slugs},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No matching default topics")

    # Subscriptions remaining before hitting the tier cap.
    if cap is not None:
        used = db.execute_query(
            "SELECT COUNT(*) AS n FROM research_subscriptions "
            "WHERE user_id = :uid AND is_active = TRUE",
            {"uid": user_id},
        )
        used_count = int(used[0]["n"]) if used else 0
        remaining = max(0, cap - used_count)
        if remaining == 0:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "research_subscription_tier_limit",
                    "tier": tier,
                    "used": used_count,
                    "limit": cap,
                    "upgrade_url": "/dashboard/subscription",
                },
            )
        rows = rows[:remaining]

    created = 0
    skipped = 0
    for r in rows:
        try:
            updated = db.execute_update(
                """INSERT INTO research_subscriptions
                       (user_id, topic, keywords, notification_email)
                   VALUES (:uid, :topic, :kw, FALSE)
                   ON CONFLICT (user_id, topic) DO NOTHING""",
                {
                    "uid": user_id,
                    "topic": r["label"],
                    "kw": list(r.get("keywords") or []),
                },
            )
            if updated:
                created += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning(f"bulk_subscribe insert failed for {r.get('slug')}: {exc}")

    return {
        "created": created,
        "skipped": skipped,
        "total_requested": len(request.slugs),
        "note": "Skipped slugs already had an active subscription for this user.",
    }


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    request: SubscribeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new research-topic subscription for the current user."""
    user_id = current_user["user_id"]
    tier = str(current_user.get("subscription_tier", "freemium"))
    cap = TIER_SUB_CAPS.get(tier, 2)

    db = get_postgres()
    if cap is not None:
        used = db.execute_query(
            "SELECT COUNT(*) AS n FROM research_subscriptions "
            "WHERE user_id = :uid AND is_active = TRUE",
            {"uid": user_id},
        )
        used_count = int(used[0]["n"]) if used else 0
        if used_count >= cap:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "research_subscription_tier_limit",
                    "tier": tier,
                    "used": used_count,
                    "limit": cap,
                    "upgrade_url": "/dashboard/subscription",
                    "message": (
                        f"Free tier supports up to {cap} research subscriptions. "
                        f"Upgrade for unlimited."
                    ),
                },
            )

    keywords = list(request.keywords or [])

    try:
        rows = db.execute_query(
            """INSERT INTO research_subscriptions
                   (user_id, topic, keywords, notification_email)
               VALUES (:uid, :topic, :kw, :email)
               ON CONFLICT (user_id, topic) DO UPDATE SET
                   keywords = EXCLUDED.keywords,
                   notification_email = EXCLUDED.notification_email,
                   is_active = TRUE,
                   updated_at = NOW()
               RETURNING subscription_id, topic, keywords,
                         notification_email, is_active,
                         last_polled_at, created_at""",
            {
                "uid": user_id,
                "topic": request.topic.strip(),
                "kw": keywords,
                "email": request.notification_email,
            },
        )
    except Exception as exc:
        logger.error(f"create_subscription failed: {exc}")
        raise HTTPException(status_code=500, detail="Subscription create failed")

    return _row_to_subscription(rows[0])


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(current_user: dict = Depends(get_current_user)):
    db = get_postgres()
    rows = db.execute_query(
        """SELECT subscription_id, topic, keywords, notification_email,
                  is_active, last_polled_at, created_at
           FROM research_subscriptions
           WHERE user_id = :uid
           ORDER BY created_at DESC""",
        {"uid": current_user["user_id"]},
    )
    return [_row_to_subscription(r) for r in (rows or [])]


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        UUID(subscription_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid subscription_id")

    db = get_postgres()
    deleted = db.execute_update(
        "DELETE FROM research_subscriptions "
        "WHERE subscription_id = :sid AND user_id = :uid",
        {"sid": subscription_id, "uid": current_user["user_id"]},
    )
    if not deleted:
        return {"message": "No matching subscription"}
    return {"message": "Unsubscribed"}


@router.get("/feed", response_model=List[FeedItemResponse])
async def get_feed(
    topic: Optional[str] = Query(default=None,
                                 description="Filter to one subscription by exact topic"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Recent papers across the current user's subscriptions."""
    db = get_postgres()
    params: dict = {"uid": current_user["user_id"], "lim": limit}
    extra_filter = ""
    if topic:
        extra_filter = " AND s.topic = :topic"
        params["topic"] = topic

    rows = db.execute_query(
        f"""SELECT
                i.item_id, i.subscription_id, s.topic, i.doi, i.title,
                i.authors, i.abstract, i.journal, i.published_date,
                i.crossref_url, i.source, i.discovered_at
            FROM research_feed_items i
            JOIN research_subscriptions s ON s.subscription_id = i.subscription_id
            WHERE s.user_id = :uid AND s.is_active = TRUE{extra_filter}
            ORDER BY i.discovered_at DESC
            LIMIT :lim""",
        params,
    )
    return [
        FeedItemResponse(
            item_id=str(r["item_id"]),
            subscription_id=str(r["subscription_id"]),
            topic=r["topic"],
            doi=r.get("doi"),
            title=r["title"],
            authors=list(r.get("authors") or []),
            abstract=r.get("abstract"),
            journal=r.get("journal"),
            published_date=str(r["published_date"]) if r.get("published_date") else None,
            crossref_url=r.get("crossref_url"),
            source=r.get("source") or "crossref",
            discovered_at=str(r["discovered_at"]),
        )
        for r in (rows or [])
    ]


# ---------------------------------------------------------------------------
# CrossRef poller — used by the admin endpoint + future Cloud Scheduler.
# ---------------------------------------------------------------------------


def _crossref_to_item(work: dict) -> Optional[dict]:
    """Map a CrossRef /works result row to a feed_item insert payload."""
    title_list = work.get("title") or []
    if not title_list:
        return None
    authors = []
    for a in work.get("author", []) or []:
        name = " ".join(filter(None, [a.get("given"), a.get("family")]))
        if name:
            authors.append(name)

    issued = (work.get("issued") or {}).get("date-parts") or [[None]]
    pub_date = None
    if issued and issued[0] and issued[0][0]:
        parts = issued[0] + [1, 1]  # YYYY-MM-DD with sensible defaults
        try:
            pub_date = datetime(int(parts[0]), int(parts[1] or 1), int(parts[2] or 1)).date()
        except (ValueError, TypeError):
            pub_date = None

    journal_list = work.get("container-title") or []
    return {
        "doi": work.get("DOI"),
        "title": title_list[0],
        "authors": authors,
        "abstract": work.get("abstract"),
        "journal": journal_list[0] if journal_list else None,
        "published_date": pub_date,
        "crossref_url": work.get("URL"),
    }


async def _poll_crossref(query: str, rows: int = DEFAULT_POLL_ROWS) -> List[dict]:
    """Single CrossRef call. Returns list of insert payloads."""
    if not query.strip():
        return []
    try:
        async with httpx.AsyncClient(
            timeout=20.0, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(
                CROSSREF_BASE,
                params={
                    "query": query,
                    "rows": min(max(rows, 1), 100),
                    "sort": "published",
                    "order": "desc",
                    # Academic-only whitelist by publication type (OR-ed):
                    # peer-reviewed journals, conference papers, theses/
                    # dissertations (Theseus-class MSc/PhD), preprints, book
                    # chapters and reports. Excludes news/blog/dataset/other.
                    "filter": (
                        "type:journal-article,type:proceedings-article,"
                        "type:dissertation,type:posted-content,"
                        "type:book-chapter,type:report,type:reference-entry"
                    ),
                },
            )
        if resp.status_code != 200:
            logger.warning(f"CrossRef HTTP {resp.status_code} for query={query!r}")
            return []
        data = resp.json()
        items = (data.get("message") or {}).get("items") or []
        out = []
        for w in items:
            payload = _crossref_to_item(w)
            if payload and payload.get("title"):
                out.append(payload)
        return out
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.warning(f"CrossRef transport error: {exc}")
        return []
    except Exception as exc:
        logger.error(f"CrossRef unexpected error: {exc}")
        return []


@admin_router.post("")
async def run_research_poll(
    batch_size: int = Query(default=20, ge=1, le=100),
    x_corporate_sync_token: Optional[str] = Header(default=None),
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Run a batched CrossRef poll across the oldest-polled active subscriptions.

    Token-gated. Operator workflow + Cloud Scheduler cron same shape as
    POST /api/admin/link-check (see Slice 5a). Per subscription, queries
    CrossRef with (topic + keywords joined), inserts up to
    DEFAULT_POLL_ROWS new feed items via ON CONFLICT DO NOTHING.
    """
    _auth_admin(x_corporate_sync_token, x_scheduler_secret)
    db = get_postgres()

    subs = db.execute_query(
        """SELECT subscription_id, topic, keywords
           FROM research_subscriptions
           WHERE is_active = TRUE
           ORDER BY last_polled_at NULLS FIRST
           LIMIT :n""",
        {"n": batch_size},
    )
    if not subs:
        return {"polled": 0, "discovered": 0, "note": "No active subscriptions due."}

    sem = asyncio.Semaphore(4)  # CrossRef tolerates higher; 4 is polite

    async def _poll_one(sub_row: dict) -> int:
        async with sem:
            query_parts = [sub_row["topic"]] + list(sub_row.get("keywords") or [])
            query = " ".join(filter(None, query_parts))
            items = await _poll_crossref(query, rows=DEFAULT_POLL_ROWS)
        new_count = 0
        for it in items:
            try:
                rowcount = db.execute_update(
                    """INSERT INTO research_feed_items
                           (subscription_id, doi, title, authors, abstract,
                            journal, published_date, crossref_url, source)
                       VALUES (:sid, :doi, :title, :authors, :abstract,
                               :journal, :pub, :url, 'crossref')
                       ON CONFLICT (subscription_id, doi) DO NOTHING""",
                    {
                        "sid": sub_row["subscription_id"],
                        "doi": it.get("doi"),
                        "title": it["title"],
                        "authors": it.get("authors") or [],
                        "abstract": it.get("abstract"),
                        "journal": it.get("journal"),
                        "pub": it.get("published_date"),
                        "url": it.get("crossref_url"),
                    },
                )
                if rowcount:
                    new_count += 1
            except Exception as exc:
                logger.debug(
                    f"feed_items insert failed for sub={sub_row['subscription_id']} "
                    f"doi={it.get('doi')}: {exc}"
                )
        # Update poll timestamp regardless — empty results still mean polled.
        db.execute_update(
            "UPDATE research_subscriptions SET last_polled_at = NOW() "
            "WHERE subscription_id = :sid",
            {"sid": sub_row["subscription_id"]},
        )
        return new_count

    new_counts = await asyncio.gather(*[_poll_one(s) for s in subs])
    total_new = sum(new_counts)
    logger.info(
        f"research-poll: polled {len(subs)} subscriptions, discovered "
        f"{total_new} new items total"
    )
    return {
        "polled": len(subs),
        "discovered": total_new,
        "per_subscription": [
            {"subscription_id": str(s["subscription_id"]),
             "topic": s["topic"], "new_items": n}
            for s, n in zip(subs, new_counts)
        ],
    }
