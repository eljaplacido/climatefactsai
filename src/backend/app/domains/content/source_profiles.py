"""
Source Profile Service

Manages reusable source trust profiles with historical reliability tracking.
Supports MVP Feature 5: Source trust metadata with historical reliability context.
"""

from typing import Optional
from urllib.parse import urlparse

from app.core.database import Database
from app.core.logging import get_logger


logger = get_logger(__name__)


# Tiers that denote a curated, high-quality source even before any articles
# have been analysed (institutional science / research bodies — EEA, IPCC, UN
# climate news, etc.). `reliability_tier` defaults to 'public', which is the
# neutral case, not a quality signal.
_HIGH_QUALITY_TIERS = {"scientific", "research"}

# Evidence-backed credibility tiers from `source_credibility_tiers` (mig 027 +
# the 3-axis scores in mig 041). These carry a public `evidence_url`, so a
# source classified T1/T2/T3 there is a genuine signal even when its
# `source_profiles` row has never had an article analysed.
_EVIDENCE_TIERS = {"t1", "t2", "t3"}

# Tier-level default 3-axis scores (editorial, factcheck, transparency), copied
# verbatim from migration 041. Used to fill an axis when a tier row carries no
# explicit score — the feed-expansion migrations (033/054/058/060/066/068)
# added tier rows AFTER 041 ran, so most have NULL axis scores even though the
# T1/T2/T3 level itself is evidence-backed. Keep in lockstep with migration 075.
_TIER_DEFAULT_AXIS_SCORES = {
    "t1": (90, 90, 90),
    "t2": (70, 75, 65),
    "t3": (55, 50, 60),
}


def _axis_editorial_band(score: float) -> str:
    """0-100 editorial_score -> editorial_standards label. Mirrors migration 075."""
    if score >= 75:
        return "rigorous"
    if score >= 50:
        return "moderate"
    return "limited"


def _axis_transparency_band(score: float) -> str:
    """0-100 transparency_score -> transparency_level label. Mirrors migration 075."""
    if score >= 75:
        return "high"
    if score >= 50:
        return "moderate"
    return "low"


def _axis_factcheck_band(score: float) -> str:
    """0-100 factcheck_score -> fact_check_record label. Mirrors migration 075."""
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "mixed"
    return "poor"


def _assessment_from_tier_scores(
    tier: Optional[str],
    editorial_score: Optional[float],
    factcheck_score: Optional[float],
    transparency_score: Optional[float],
) -> Optional[dict]:
    """Bridge an evidence-backed `source_credibility_tiers` row (tier + 3-axis
    scores) to the three `source_profiles` string labels.

    Fires for any evidence-backed tier (T1/T2/T3). Each axis uses the tier row's
    explicit score when present, else the tier-level default (mig 041) — the
    tier level is itself evidence-backed (public evidence_url), and most
    feed-added tier rows have NULL axis scores. Returns None for non-evidence
    tiers ('unknown'/'retracted'). Kept in lockstep with migration 075.
    """
    t = str(tier or "").strip().lower()
    if t not in _EVIDENCE_TIERS:
        return None
    de, dfc, dtr = _TIER_DEFAULT_AXIS_SCORES[t]
    ed = de if editorial_score is None else float(editorial_score)
    fc = dfc if factcheck_score is None else float(factcheck_score)
    tr = dtr if transparency_score is None else float(transparency_score)
    return {
        "editorial_standards": _axis_editorial_band(ed),
        "fact_check_record": _axis_factcheck_band(fc),
        "transparency_level": _axis_transparency_band(tr),
    }


def derive_source_assessment(
    *,
    credibility_score: Optional[float] = None,
    average_reliability_score: Optional[float] = None,
    reliability_tier: Optional[str] = None,
    false_claim_rate: Optional[float] = None,
    total_articles_analyzed: Optional[int] = None,
    tier: Optional[str] = None,
    tier_editorial_score: Optional[float] = None,
    tier_factcheck_score: Optional[float] = None,
    tier_transparency_score: Optional[float] = None,
) -> Optional[dict]:
    """Derive the three string assessment fields from a source's numeric/tier
    signals.

    ``source_profiles.editorial_standards`` / ``fact_check_record`` /
    ``transparency_level`` default to ``'unknown'`` and were populated by no
    code path, so the Sources UI rendered "Not assessed" for every source. The
    numeric/tier signals (``credibility_score``, ``average_reliability_score``,
    ``reliability_tier``, ``false_claim_rate``) DO exist on the same row, so we
    map them to the three labels.

    ML-12 (2026-07-02): when the profile itself carries no per-article signal
    (the majority — Reuters, Carbon Brief, the Guardian etc. rendered
    'unknown'), fall back to the evidence-backed ``source_credibility_tiers``
    classification (``tier`` + the 3-axis ``editorial/factcheck/transparency``
    scores, joined by domain/name). Those tiers hold T1/T2/T3 with a public
    ``evidence_url``, so bridging them is honest — a real signal, not invented.

    These labels are a defensible restatement of the platform's OWN reliability
    tiering and historical article analysis — NOT an independent third-party
    editorial or fact-check audit. The UI/methodology copy says so explicitly.

    Returns ``None`` when there is genuinely no signal, so callers keep
    ``'unknown'`` rather than inventing a rating.

    Vocabulary (matches the 005 schema comments + the frontend configs):
      * editorial_standards : rigorous | moderate | limited | unknown
      * fact_check_record   : excellent | good | mixed | poor | unknown
      * transparency_level  : high | moderate | low | unknown
    """
    tier_bridge = _assessment_from_tier_scores(
        tier, tier_editorial_score, tier_factcheck_score, tier_transparency_score
    )

    rel_tier = (reliability_tier or "").strip().lower()
    high_quality_tier = rel_tier in _HIGH_QUALITY_TIERS

    fcr = float(false_claim_rate) if false_claim_rate is not None else 0.0
    n_articles = int(total_articles_analyzed) if total_articles_analyzed is not None else 0

    # A profile only carries a genuine per-row signal once it has been analysed,
    # has a curated high-quality tier, or has a recorded false-claim rate.
    # Without any of those, credibility_score is just the schema default (50) —
    # so fall back to the evidence-backed credibility tier (if any) rather than
    # inventing a rating from the default score.
    has_signal = (
        n_articles > 0
        or average_reliability_score is not None
        or high_quality_tier
        or fcr > 0
    )
    if not has_signal:
        return tier_bridge

    score = credibility_score if credibility_score is not None else average_reliability_score
    score = float(score) if score is not None else None

    if high_quality_tier:
        band = "high"
    elif score is None:
        return None
    elif score >= 75:
        band = "high"
    elif score >= 50:
        band = "moderate"
    else:
        band = "low"

    editorial = {"high": "rigorous", "moderate": "moderate", "low": "limited"}[band]
    transparency = {"high": "high", "moderate": "moderate", "low": "low"}[band]

    # fact_check_record: an elevated false-claim rate dominates; otherwise fall
    # back to the credibility band. 'excellent' is reserved for a high band with
    # a genuinely strong score and no elevated false-claim rate. 'poor' only
    # appears when the recorded false-claim rate is actually high (>=15%) — we
    # never assert a poor fact-check record purely from low overall credibility.
    if fcr >= 0.15:
        fact_check = "poor"
    elif fcr >= 0.05:
        fact_check = "mixed"
    elif band == "high":
        fact_check = "excellent" if (score is not None and score >= 85) else "good"
    else:  # moderate or low band, low/zero recorded false-claim rate
        fact_check = "mixed"

    return {
        "editorial_standards": editorial,
        "fact_check_record": fact_check,
        "transparency_level": transparency,
    }


class SourceProfileService:
    """Service for managing source trust profiles."""

    def __init__(self, db: Database):
        self.db = db
        self._has_reliability_tier_column: Optional[bool] = None
        self._table_columns_cache: dict[str, set[str]] = {}

    def _get_table_columns(self, table_name: str) -> set[str]:
        """Best-effort table column lookup with per-instance caching."""
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached

        try:
            rows = self.db.execute_query(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                """,
                {"table_name": table_name},
            )
            columns = {
                str(row.get("column_name")).lower()
                for row in (rows or [])
                if row.get("column_name")
            }
        except Exception as exc:
            logger.warning(
                "Could not inspect table schema",
                table_name=table_name,
                error=str(exc),
            )
            columns = set()

        self._table_columns_cache[table_name] = columns
        return columns

    def _supports_reliability_tier(self) -> bool:
        """Check whether source_profiles.reliability_tier exists."""
        if self._has_reliability_tier_column is not None:
            return self._has_reliability_tier_column

        self._has_reliability_tier_column = "reliability_tier" in self._get_table_columns(
            "source_profiles"
        )

        return self._has_reliability_tier_column

    @staticmethod
    def _is_missing_schema_object_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            "does not exist" in msg
            or "undefined table" in msg
            or "undefined column" in msg
            or "no such table" in msg
            or "no such column" in msg
        )

    def _profile_select_clause(self) -> str:
        """Return a SELECT clause compatible with current DB schema."""
        tier_select = (
            "COALESCE(reliability_tier, 'public') as reliability_tier"
            if self._supports_reliability_tier()
            else "'public' as reliability_tier"
        )
        return f"""SELECT source_id, source_name, source_domain, credibility_score,
                          editorial_standards, fact_check_record, transparency_level,
                          total_articles_analyzed, average_reliability_score,
                          total_claims_verified, total_claims_disputed, false_claim_rate,
                          source_type, country_code, description, website_url,
                          first_seen_at, last_updated_at,
                          {tier_select}
                   FROM source_profiles"""

    @staticmethod
    def _is_schema_compatibility_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        if "reliability_tier" in msg and SourceProfileService._is_missing_schema_object_error(exc):
            return True
        return (
            "source_profiles" in msg
            and SourceProfileService._is_missing_schema_object_error(exc)
        )

    def _seed_profiles_from_articles(self, limit: int = 100) -> int:
        """Backfill source_profiles from existing articles when empty."""
        rows = self.db.execute_query(
            """
            SELECT source_name,
                   MIN(url) AS sample_url,
                   AVG(reliability_score) AS avg_reliability
            FROM articles
            WHERE COALESCE(source_name, '') <> ''
              AND COALESCE(url, '') <> ''
            GROUP BY source_name
            ORDER BY COUNT(*) DESC
            LIMIT :limit
            """,
            {"limit": int(limit)},
        )

        seeded = 0
        for row in rows or []:
            source_name = row.get("source_name")
            sample_url = row.get("sample_url")
            if not source_name or not sample_url:
                continue

            avg_reliability = row.get("avg_reliability")
            reliability_score = int(round(avg_reliability)) if avg_reliability is not None else None

            try:
                self.upsert_from_article(
                    source_name=source_name,
                    url=sample_url,
                    reliability_score=reliability_score,
                )
                seeded += 1
            except Exception as exc:
                logger.warning(
                    "Failed to seed source profile from article",
                    source_name=source_name,
                    error=str(exc),
                )

        if seeded:
            logger.info("Seeded source profiles from existing articles", seeded=seeded)

        return seeded

    def _fallback_profiles_from_articles(
        self,
        limit: int = 50,
        min_credibility: Optional[int] = None,
        source_type: Optional[str] = None,
    ) -> list[dict]:
        """Build source profile response directly from aggregated articles."""
        if source_type and source_type != "news_outlet":
            return []

        article_columns = self._get_table_columns("articles")
        include_reliability_score = not article_columns or "reliability_score" in article_columns
        include_claim_metrics = (
            not article_columns
            or (
                "claims_count" in article_columns
                and "verified_claims_count" in article_columns
            )
        )

        avg_reliability_expr = (
            "AVG(reliability_score) AS avg_reliability"
            if include_reliability_score
            else "NULL::float AS avg_reliability"
        )
        verified_claims_expr = (
            "COALESCE(SUM(verified_claims_count), 0)::int AS verified_claims"
            if include_claim_metrics
            else "0::int AS verified_claims"
        )
        disputed_claims_expr = (
            """
            COALESCE(
                SUM(
                    GREATEST(
                        COALESCE(claims_count, 0) - COALESCE(verified_claims_count, 0),
                        0
                    )
                ),
                0
            )::int AS disputed_claims
            """
            if include_claim_metrics
            else "0::int AS disputed_claims"
        )

        query = f"""
            SELECT source_name,
                   MIN(url) AS sample_url,
                   COUNT(*)::int AS article_count,
                   {avg_reliability_expr},
                   {verified_claims_expr},
                   {disputed_claims_expr}
            FROM articles
            WHERE COALESCE(source_name, '') <> ''
              AND COALESCE(url, '') <> ''
            GROUP BY source_name
            ORDER BY COUNT(*) DESC
            LIMIT :limit
        """

        try:
            rows = self.db.execute_query(query, {"limit": int(limit)})
        except Exception as exc:
            if not self._is_missing_schema_object_error(exc):
                raise

            logger.warning(
                "Article fallback query failed due to schema mismatch; retrying minimal projection",
                error=str(exc),
            )

            try:
                rows = self.db.execute_query(
                    """
                    SELECT source_name,
                           MIN(url) AS sample_url,
                           COUNT(*)::int AS article_count,
                           NULL::float AS avg_reliability,
                           0::int AS verified_claims,
                           0::int AS disputed_claims
                    FROM articles
                    WHERE COALESCE(source_name, '') <> ''
                      AND COALESCE(url, '') <> ''
                    GROUP BY source_name
                    ORDER BY COUNT(*) DESC
                    LIMIT :limit
                    """,
                    {"limit": int(limit)},
                )
            except Exception as retry_exc:
                if self._is_missing_schema_object_error(retry_exc):
                    logger.warning(
                        "Source profile article fallback unavailable due to schema mismatch",
                        error=str(retry_exc),
                    )
                    return []
                raise

        profiles: list[dict] = []
        for row in rows or []:
            source_name = row.get("source_name")
            sample_url = row.get("sample_url") or ""
            if not source_name:
                continue

            try:
                domain = urlparse(sample_url).netloc.lower().lstrip("www.")
            except Exception:
                domain = source_name.lower().replace(" ", "-")

            avg_reliability = row.get("avg_reliability")
            if avg_reliability is not None:
                credibility_score = int(round(float(avg_reliability)))
            else:
                credibility_score = 50

            if min_credibility is not None and credibility_score < int(min_credibility):
                continue

            verified_claims = int(row.get("verified_claims") or 0)
            disputed_claims = int(row.get("disputed_claims") or 0)
            total_claims = verified_claims + disputed_claims
            false_claim_rate = (disputed_claims / total_claims) if total_claims > 0 else 0.0

            profiles.append(
                {
                    "source_id": f"fallback-{domain or source_name.lower().replace(' ', '-')}",
                    "source_name": source_name,
                    "source_domain": domain,
                    "credibility_score": credibility_score,
                    "editorial_standards": "unknown",
                    "fact_check_record": "unknown",
                    "transparency_level": "unknown",
                    "total_articles_analyzed": int(row.get("article_count") or 0),
                    "average_reliability_score": float(avg_reliability) if avg_reliability is not None else None,
                    "total_claims_verified": verified_claims,
                    "total_claims_disputed": disputed_claims,
                    "false_claim_rate": false_claim_rate,
                    "source_type": "news_outlet",
                    "country_code": None,
                    "description": None,
                    "website_url": sample_url or None,
                    "first_seen_at": None,
                    "last_updated_at": None,
                    "reliability_tier": "public",
                }
            )

        profiles.sort(key=lambda p: p.get("credibility_score") or 0, reverse=True)
        return profiles[: int(limit)]

    @staticmethod
    def _norm_domain(value) -> str:
        """Lowercase + strip a leading www. prefix (not lstrip, which would
        eat any leading w/x/. char) so profile and tier domains join cleanly."""
        d = str(value or "").strip().lower()
        return d[4:] if d.startswith("www.") else d

    @staticmethod
    def _tier_rank(tier) -> int:
        """Order tiers so the *best* wins when a source matches >1 tier row
        (e.g. an outlet seeded under two domains, or matched by both name and
        domain). T1 > T2 > T3 > anything else."""
        return {"t1": 3, "t2": 2, "t3": 1}.get(str(tier or "").lower(), 0)

    def _attach_credibility_tiers(self, rows: list[dict]) -> list[dict]:
        """Enrich profile rows with source_credibility_tiers data (migration 027).

        Adds `tier`, `tier_prior_bonus`, and (when present) other tier signals
        as best-effort fields. Older clusters without migration 027 just see
        the tier fields absent from the response — the frontend treats them as
        "not assessed" rather than rendering broken UI.

        Called by `list_profiles` and the per-domain getter on 2026-05-23 as
        part of §3.7 (Sources page hardcoded-list deletion + DB-backed tiers).

        2026-06-02: match on `source_name` OR `domain`. The tier table is keyed
        by `domain`, but a large slice of `source_profiles` carries a fabricated
        slug domain (legacy seed pollution, e.g. `carbon-brief-c078`) that never
        joins, so vetted sources like Carbon Brief / DeSmog / Inside Climate News
        rendered as "Unrated" despite being tiered under their real domain. The
        tier table also stores `source_name`, and those phantom profiles keep the
        correct name — so a name match recovers the tier without touching data.
        """
        if not rows:
            return rows

        # Profile rows use `source_domain`; tier rows are keyed by `domain`.
        # Also collect names (lowercased) so a fabricated-domain profile can
        # still match its tier row by name.
        domains = sorted({
            self._norm_domain(row.get("source_domain"))
            for row in rows
            if row.get("source_domain")
        })
        names = sorted({
            str(row.get("source_name") or "").strip().lower()
            for row in rows
            if str(row.get("source_name") or "").strip()
        })
        if not domains and not names:
            return rows

        clauses: list[str] = []
        params: dict = {}
        if domains:
            clauses.append("domain = ANY(:domains)")
            params["domains"] = domains
        if names:
            clauses.append("LOWER(source_name) = ANY(:names)")
            params["names"] = names

        try:
            tier_rows = self.db.execute_query(
                "SELECT domain, source_name, prior_bonus, tier, "
                "editorial_score, factcheck_score, transparency_score, "
                "evidence_url, classification "
                "FROM source_credibility_tiers "
                f"WHERE {' OR '.join(clauses)}",
                params,
            )
        except Exception as exc:
            # Migration 027 not applied or column shape changed — fail soft.
            logger.debug(
                "source_credibility_tiers join skipped (table missing or schema drift): %s",
                exc,
            )
            return rows

        tier_by_domain: dict[str, dict] = {}
        tier_by_name: dict[str, dict] = {}
        for tr in tier_rows or []:
            payload = {
                "tier": tr.get("tier"),
                "tier_prior_bonus": tr.get("prior_bonus"),
                "editorial_score": tr.get("editorial_score"),
                "factcheck_score": tr.get("factcheck_score"),
                "transparency_score": tr.get("transparency_score"),
                # ML-12: surface the public evidence link + classification so the
                # Sources UI can render a "Why this tier?" link auditors can check.
                "evidence_url": tr.get("evidence_url"),
                "classification": tr.get("classification"),
            }
            d = self._norm_domain(tr.get("domain"))
            n = str(tr.get("source_name") or "").strip().lower()
            rank = self._tier_rank(payload["tier"])
            if d and rank >= self._tier_rank(tier_by_domain.get(d, {}).get("tier")):
                tier_by_domain[d] = payload
            if n and rank >= self._tier_rank(tier_by_name.get(n, {}).get("tier")):
                tier_by_name[n] = payload

        enriched: list[dict] = []
        for row in rows:
            merged = dict(row)
            d = self._norm_domain(row.get("source_domain"))
            n = str(row.get("source_name") or "").strip().lower()
            # Prefer a domain match (most specific), fall back to a name match.
            match = (tier_by_domain.get(d) if d else None) or (
                tier_by_name.get(n) if n else None
            )
            if match:
                merged.update(match)
            else:
                merged.setdefault("tier", None)
                merged.setdefault("tier_prior_bonus", None)
            enriched.append(merged)
        return enriched

    def list_profiles(
        self,
        limit: int = 50,
        min_credibility: Optional[int] = None,
        source_type: Optional[str] = None,
    ) -> list[dict]:
        """List source profiles ordered by credibility."""
        conditions = []
        params = {"limit": int(limit)}

        if min_credibility is not None:
            conditions.append("credibility_score >= :min_credibility")
            params["min_credibility"] = int(min_credibility)
        if source_type:
            conditions.append("source_type = :source_type")
            params["source_type"] = source_type

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            {self._profile_select_clause()}
            {where}
            ORDER BY credibility_score DESC NULLS LAST
            LIMIT :limit
        """

        try:
            rows = self.db.execute_query(query, params)
        except Exception as exc:
            if not self._is_schema_compatibility_error(exc):
                raise

            logger.warning(
                "Source profiles query failed due to schema mismatch; using article fallback",
                error=str(exc),
            )
            return self._attach_credibility_tiers(
                self._fallback_profiles_from_articles(
                    limit=limit,
                    min_credibility=min_credibility,
                    source_type=source_type,
                )
            )

        if rows:
            return self._attach_credibility_tiers(rows)

        # Best-effort backfill from articles when table exists but is empty.
        try:
            seeded = self._seed_profiles_from_articles(limit=max(int(limit), 100))
            if seeded > 0:
                rows = self.db.execute_query(query, params)
                if rows:
                    return self._attach_credibility_tiers(rows)
        except Exception as exc:
            logger.warning("Source profile backfill attempt failed", error=str(exc))

        return self._attach_credibility_tiers(
            self._fallback_profiles_from_articles(
                limit=limit,
                min_credibility=min_credibility,
                source_type=source_type,
            )
        )

    def get_profile_by_domain(self, domain: str) -> Optional[dict]:
        """Get source profile by domain name."""
        safe_domain = domain.lower().strip()
        query = f"""
            {self._profile_select_clause()}
            WHERE source_domain = :source_domain
            LIMIT 1
        """

        try:
            rows = self.db.execute_query(query, {"source_domain": safe_domain})
            if rows:
                return rows[0]
        except Exception as exc:
            if not self._is_schema_compatibility_error(exc):
                raise
            logger.warning("Source profile lookup by domain fell back to articles", error=str(exc))

        fallback_rows = self._fallback_profiles_from_articles(limit=500)
        for row in fallback_rows:
            if (row.get("source_domain") or "").lower() == safe_domain:
                return row
        return None

    def get_profile_by_name(self, name: str) -> Optional[dict]:
        """Get source profile by source name."""
        safe_name = name.strip()
        query = f"""
            {self._profile_select_clause()}
            WHERE LOWER(source_name) = LOWER(:source_name)
            LIMIT 1
        """

        try:
            rows = self.db.execute_query(query, {"source_name": safe_name})
            if rows:
                return rows[0]
        except Exception as exc:
            if not self._is_schema_compatibility_error(exc):
                raise
            logger.warning("Source profile lookup by name fell back to articles", error=str(exc))

        fallback_rows = self._fallback_profiles_from_articles(limit=500)
        for row in fallback_rows:
            if (row.get("source_name") or "").lower() == safe_name.lower():
                return row
        return None

    def upsert_from_article(self, source_name: str, url: str, reliability_score: Optional[int] = None) -> dict:
        """
        Create or update source profile from article data.
        Called during article ingestion to maintain source stats.
        """
        # Extract domain from URL
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            # CNT-6: strip the "www." PREFIX, not any leading {w,.} chars —
            # lstrip("www.") turned "wired.com" into "ired.com".
            domain = netloc[4:] if netloc.startswith("www.") else netloc
        except Exception:
            domain = source_name.lower().replace(" ", "-")

        # Upsert profile (bound params — url/source_name/domain must never be
        # interpolated; the raw {url} was a SQL-injection vector — CNT-6).
        self.db.execute_update(
            """INSERT INTO source_profiles (source_name, source_domain, website_url)
                VALUES (:name, :domain, :url)
                ON CONFLICT (source_domain) DO UPDATE SET
                    total_articles_analyzed = source_profiles.total_articles_analyzed + 1,
                    last_updated_at = CURRENT_TIMESTAMP""",
            {"name": source_name, "domain": domain, "url": url[:2048]},
        )

        # Update rolling average reliability if provided
        if reliability_score is not None:
            self.db.execute_update(
                """UPDATE source_profiles SET
                        average_reliability_score = COALESCE(
                            (average_reliability_score * (total_articles_analyzed - 1) + :rel)
                            / NULLIF(total_articles_analyzed, 0),
                            :rel
                        ),
                        credibility_score = COALESCE(
                            (credibility_score * 0.8 + :rel * 0.2)::int,
                            :rel
                        )
                    WHERE source_domain = :domain""",
                {"rel": int(reliability_score), "domain": domain},
            )

        # Derive the editorial / fact-check / transparency string labels from
        # the freshly-updated numeric + tier signals so the Sources UI stops
        # showing "Not assessed" for every source (data-completeness Fix A).
        self._apply_derived_assessment(domain, source_name)

        # Auto-sync to source_credibility table
        self._sync_to_credibility(source_name, domain, url)

        return self.get_profile_by_domain(domain) or {}

    def _lookup_tier_scores(
        self, domain: Optional[str], name: Optional[str]
    ) -> Optional[dict]:
        """Best-effort fetch of the evidence-backed `source_credibility_tiers`
        row (tier + 3-axis scores) for a source, matched by domain OR name.

        Mirrors `_attach_credibility_tiers`' join semantics (normalised domain,
        else source_name) and returns the best (highest) tier when several
        match. Fails soft to None when the table is absent (older clusters).
        """
        nd = self._norm_domain(domain)
        nm = str(name or "").strip().lower()
        clauses: list[str] = []
        params: dict = {}
        if nd:
            clauses.append(
                r"regexp_replace(lower(coalesce(domain, '')), '^www\.', '') = :nd"
            )
            params["nd"] = nd
        if nm:
            clauses.append("lower(source_name) = :nm")
            params["nm"] = nm
        if not clauses:
            return None

        try:
            rows = self.db.execute_query(
                "SELECT tier, editorial_score, factcheck_score, transparency_score "
                "FROM source_credibility_tiers "
                f"WHERE {' OR '.join(clauses)}",
                params,
            )
        except Exception as exc:
            logger.debug("tier-score lookup skipped (table missing / drift): %s", exc)
            return None

        best: Optional[dict] = None
        best_rank = -1
        for r in rows or []:
            rank = self._tier_rank(r.get("tier"))
            if rank > best_rank:
                best, best_rank = r, rank
        return best

    def _apply_derived_assessment(
        self, domain: str, source_name: Optional[str] = None
    ) -> None:
        """Populate editorial_standards / fact_check_record / transparency_level
        from the row's numeric + tier signals (see ``derive_source_assessment``).

        Written by no other code path, those columns otherwise stay 'unknown'
        forever. The derived values restate the platform's own reliability
        tiering — they are NOT an independent third-party audit (the UI says
        so). Fails soft on any schema drift so ingestion is never blocked.
        """
        tier_select = (
            "reliability_tier"
            if self._supports_reliability_tier()
            else "NULL AS reliability_tier"
        )
        try:
            rows = self.db.execute_query(
                f"""SELECT credibility_score, average_reliability_score,
                           {tier_select}, false_claim_rate, total_articles_analyzed
                    FROM source_profiles
                    WHERE source_domain = :domain
                    LIMIT 1""",
                {"domain": domain},
            )
        except Exception as exc:
            logger.warning(f"Derived assessment lookup failed for {domain}: {exc}")
            return

        if not rows:
            return

        p = rows[0]
        # ML-12: bridge the evidence-backed credibility tier when the profile
        # has no per-article signal of its own.
        tier_row = self._lookup_tier_scores(domain, source_name) or {}
        derived = derive_source_assessment(
            credibility_score=p.get("credibility_score"),
            average_reliability_score=p.get("average_reliability_score"),
            reliability_tier=p.get("reliability_tier"),
            false_claim_rate=p.get("false_claim_rate"),
            total_articles_analyzed=p.get("total_articles_analyzed"),
            tier=tier_row.get("tier"),
            tier_editorial_score=tier_row.get("editorial_score"),
            tier_factcheck_score=tier_row.get("factcheck_score"),
            tier_transparency_score=tier_row.get("transparency_score"),
        )
        if not derived:
            return

        try:
            self.db.execute_update(
                """UPDATE source_profiles SET
                       editorial_standards = :editorial_standards,
                       fact_check_record   = :fact_check_record,
                       transparency_level  = :transparency_level,
                       last_updated_at     = CURRENT_TIMESTAMP
                   WHERE source_domain = :domain""",
                {**derived, "domain": domain},
            )
        except Exception as exc:
            logger.warning(f"Derived assessment write failed for {domain}: {exc}")

    def _sync_to_credibility(self, source_name: str, domain: str, url: str) -> None:
        """Sync source_profiles data into the source_credibility table.

        This ensures sources that appear as 'not assessed' in the UI get
        automatically populated from auto-seeded profile data.
        """
        try:
            profile = self.db.execute_query(
                """SELECT credibility_score, average_reliability_score,
                          reliability_tier, false_claim_rate
                   FROM source_profiles
                   WHERE source_domain = :domain
                   LIMIT 1""",
                {"domain": domain},
            )
            if not profile:
                return

            p = profile[0]
            score = p.get("credibility_score") or p.get("average_reliability_score") or 50
            tier = p.get("reliability_tier") or "assessed"
            false_rate = p.get("false_claim_rate") or 0

            factual_score = max(0, min(100, int(100 - false_rate * 100)))
            transparency = max(20, min(80, score))

            self.db.execute_update(
                """INSERT INTO source_credibility
                   (source_name, source_url, overall_score, factual_reporting_score,
                    transparency_score, reliability_tier)
                   VALUES (:name, :url, :score, :factual, :transparency, :tier)
                   ON CONFLICT (source_name) DO UPDATE SET
                       overall_score = EXCLUDED.overall_score,
                       factual_reporting_score = EXCLUDED.factual_reporting_score,
                       transparency_score = EXCLUDED.transparency_score,
                       reliability_tier = EXCLUDED.reliability_tier,
                       updated_at = CURRENT_TIMESTAMP""",
                {
                    "name": source_name,
                    "url": url,
                    "score": int(score),
                    "factual": factual_score,
                    "transparency": transparency,
                    "tier": tier,
                },
            )
        except Exception as e:
            logger.warning(f"Source credibility sync failed for {source_name}: {e}")

    def update_claim_stats(self, source_domain: str, verified: int = 0, disputed: int = 0) -> None:
        """Update claim verification stats for a source."""
        safe_domain = source_domain.replace("'", "''").lower()
        total = verified + disputed
        if total == 0:
            return

        self.db.execute_update(
            f"""UPDATE source_profiles SET
                    total_claims_verified = total_claims_verified + {int(verified)},
                    total_claims_disputed = total_claims_disputed + {int(disputed)},
                    false_claim_rate = CASE
                        WHEN (total_claims_verified + total_claims_disputed + {total}) > 0
                        THEN (total_claims_disputed + {int(disputed)})::float
                             / (total_claims_verified + total_claims_disputed + {total})
                        ELSE 0.0
                    END,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE source_domain = '{safe_domain}'""",
            {},
        )
