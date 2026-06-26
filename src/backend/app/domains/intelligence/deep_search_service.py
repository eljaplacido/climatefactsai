"""
Deep Search Service — User-facing Perplexity-type search with corpus synthesis.

Combines internal corpus search (pgvector), external web search (Perplexity),
and weather context enrichment into a synthesized answer with citations.

Gated to Professional+ tiers.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.database import Database
from app.core.logging import get_logger
from app.domains.content.embedding_service import EmbeddingService
from app.domains.intelligence.evidence_retriever import (
    OpenMeteoEvidenceRetriever,
)

logger = get_logger(__name__)


class DeepSearchService:
    """
    User-facing deep search combining internal corpus + external sources.

    Unlike the internal evidence retriever (which verifies claims),
    this service answers user research questions with synthesized responses.
    """

    def __init__(self, db: Database):
        self.db = db
        self.embedding_service = EmbeddingService(db)
        self.perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    async def search(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        include_weather: bool = True,
        limit: int = 10,
        include_hallucination_check: bool = True,
        include_refinements: bool = True,
        platform_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform a deep search combining multiple sources.

        Returns a synthesized answer with citations from internal articles,
        external web sources, and optionally weather data.
        """
        # Phase 4 wave 4: mint a session id at the start of the request so
        # every provenance row written by this call (synthesis, hallucination
        # check, cynefin classification if invoked) shares the same id. The
        # audit-trail endpoint can then group them.
        import uuid as _uuid
        deep_search_session_id = str(_uuid.uuid4())

        # Run all searches concurrently. When platform_only=True (F5a), skip
        # external Perplexity enrichment entirely — substitute an empty result
        # at index 1 so all downstream result-index logic stays unchanged.
        async def _no_external() -> Dict[str, Any]:
            return {}

        tasks = [
            self._search_internal_corpus(query, country=country, category=category, limit=limit),
            _no_external() if platform_only else self._search_perplexity(query, country=country),
        ]
        if include_weather and self._has_weather_keywords(query):
            tasks.append(self._get_weather_context(query, country=country))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        internal_results = results[0] if not isinstance(results[0], Exception) else []
        perplexity_results = results[1] if not isinstance(results[1], Exception) else {}
        internal_error = results[0] if isinstance(results[0], Exception) else None
        external_error = results[1] if isinstance(results[1], Exception) else None
        weather_context = None
        if len(results) > 2 and not isinstance(results[2], Exception):
            weather_context = results[2]

        if internal_error:
            logger.warning(f"Internal deep-search retrieval failed: {internal_error}")
        if external_error:
            logger.warning(f"External deep-search retrieval failed: {external_error}")

        # Build citations from internal articles
        citations = []
        for art in (internal_results or []):
            citations.append({
                "type": "internal_article",
                "article_id": art.get("article_id"),
                "title": art.get("title", ""),
                "source_name": art.get("source_name", ""),
                "published_date": art.get("published_date"),
                "credibility": art.get("overall_credibility"),
                "reliability_score": art.get("reliability_score"),
                "relevance_score": art.get("relevance_score", 0),
                "excerpt": (art.get("excerpt") or "")[:200],
            })

        # Add Perplexity citations — End2End audit (2026-05-27) flagged
        # external citations as un-tiered: deep-search showed Perplexity URLs
        # with no visible credibility chip, so a CDN-hosted blog ranked the
        # same as a peer-reviewed journal. Lookup each external URL's
        # domain in source_credibility_tiers and surface tier + score.
        if perplexity_results.get("citations"):
            try:
                from app.domains.trust.source_tier_service import (
                    get_source_credibility_score,
                    get_source_tier_prior,
                )
            except Exception:  # pragma: no cover
                get_source_credibility_score = None  # type: ignore[assignment]
                get_source_tier_prior = None  # type: ignore[assignment]

            for url in perplexity_results["citations"]:
                ext_domain = _domain_from_url(url)
                tier = None
                cred_score = None
                if get_source_tier_prior is not None and get_source_credibility_score is not None:
                    try:
                        _bonus, tier_label = get_source_tier_prior(self.db, ext_domain, ext_domain)
                        tier = tier_label
                        cred_score = get_source_credibility_score(self.db, ext_domain, ext_domain)
                    except Exception as exc:
                        logger.debug(f"external citation tier lookup failed for {ext_domain}: {exc}")

                citations.append({
                    "type": "external_web",
                    "source_url": url,
                    "source_name": ext_domain,
                    "credibility_tier": tier,        # "T1" | "T2" | "T3" | "unknown" | None
                    "credibility_score": cred_score, # 0-100 or None
                })

        internal_count = len(internal_results or [])
        external_count = len(perplexity_results.get("citations", []))

        # Phase 0 day 3 (2026-05-23, §3.3 fix). When evidence is thin we
        # route to the dedicated low-evidence prompt that returns a
        # sentence-grounded JSON envelope instead of free-form markdown.
        # Threshold matches the compare-side `aggregate_weak` rule (< 3).
        sentence_grounding: Optional[List[Dict[str, Any]]] = None
        confidence_envelope: Optional[Dict[str, Any]] = None
        low_evidence_refinements: Optional[List[str]] = None
        # `structured` is only produced by the high-evidence branch below;
        # initialise it here so the low-evidence path does not raise
        # UnboundLocalError when the response dict references it (this 500'd
        # every thin-evidence deep-search query).
        structured: Optional[Dict[str, Any]] = None

        if internal_count + external_count < 3:
            low_eval = await self._synthesize_low_evidence_answer(
                query=query,
                internal_articles=internal_results or [],
                perplexity_answer=perplexity_results.get("answer", ""),
                weather_context=weather_context,
            )
            synthesis = low_eval.get("answer_markdown") or low_eval.get("raw_text") or ""
            sentence_grounding = low_eval.get("sentence_grounding")
            confidence_envelope = {
                "confidence": low_eval.get("confidence") or "low",
                "reason": low_eval.get("confidence_reason"),
            } if low_eval.get("confidence") or low_eval.get("confidence_reason") else None
            low_evidence_refinements = low_eval.get("suggested_refinements")
        else:
            raw_synthesis = await self._synthesize_answer(
                query=query,
                internal_articles=internal_results or [],
                perplexity_answer=perplexity_results.get("answer", ""),
                weather_context=weather_context,
            )
            # v2.0 structured prompt — try JSON parse; fall back to markdown.
            structured = None
            try:
                cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_synthesis).strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "prose_answer" in parsed:
                    synthesis = parsed.get("prose_answer") or raw_synthesis
                    structured = {
                        "summary": parsed.get("summary", ""),
                        "key_findings": parsed.get("key_findings") or [],
                        "agreement_areas": parsed.get("agreement_areas") or [],
                        "disagreement_areas": parsed.get("disagreement_areas") or [],
                        "evidence_strength": parsed.get("evidence_strength", "unknown"),
                        "limitations": parsed.get("limitations") or [],
                        "confidence_score": parsed.get("confidence_score"),
                    }
                else:
                    synthesis = raw_synthesis
            except (json.JSONDecodeError, TypeError, Exception):
                synthesis = raw_synthesis

        # Hallucination grounding check (T4 — the detector was implemented
        # but never called on this path; the audit flagged the resulting
        # "trust me" synthesis as a P1 calibration gap). Entity-overlap and
        # statistic-verification checks run locally; the LLM-grounding
        # sub-check degrades to risk=0.5 gracefully when no LLM key is set.
        hallucination_check: Optional[Dict[str, Any]] = None
        if include_hallucination_check:
            try:
                if synthesis:
                    source_texts: List[str] = []
                    for art in internal_results or []:
                        chunk = (
                            f"{art.get('title', '')}\n{art.get('excerpt') or ''}".strip()
                        )
                        if chunk:
                            source_texts.append(chunk)
                    external_answer = perplexity_results.get("answer") if isinstance(perplexity_results, dict) else ""
                    if external_answer:
                        source_texts.append(external_answer)

                    if source_texts:
                        from app.domains.intelligence.hallucination_detector import (
                            HallucinationDetector,
                        )

                        detector = HallucinationDetector(self.db)
                        hallucination_check = await detector.check(synthesis, source_texts)
            except Exception as exc:
                logger.warning(f"Hallucination check failed; continuing without it: {exc}")
                hallucination_check = None

        # Methodology: how the answer was assembled. Surfaced in the UI's
        # "How this was answered" drawer so users can audit our pipeline.
        # Phase 4 wave 1 (2026-05-16): prompts_used records the versioned
        # template that produced the synthesis so old answers stay
        # reproducible / auditable even after the prompt evolves.
        # Phase 0 day 3 (2026-05-23): when we routed to the low-evidence
        # prompt, record THAT version under prompts_used.synthesis so the
        # audit trail reflects which variant actually ran.
        prompts_used: Dict[str, Any] = {}
        try:
            from app.domains.intelligence.prompts import get_prompt
            synth_prompt_name = (
                "deep_search_synthesis_low_evidence"
                if sentence_grounding is not None
                else "deep_search_synthesis"
            )
            synth_prompt = get_prompt(synth_prompt_name)
            prompts_used["synthesis"] = synth_prompt.as_audit_dict()
        except Exception as exc:
            logger.debug(f"Prompt registry lookup failed (non-fatal): {exc}")

        methodology = {
            "queries_run": [
                {"layer": "internal_corpus", "scope": {"country": country, "category": category}, "hits": internal_count},
                {"layer": "perplexity_external", "skipped": not bool(self.perplexity_key), "hits": external_count},
            ],
            "retrieval_strategy": (
                "internal_corpus(fts+semantic) + perplexity_external + weather_context"
                if weather_context
                else "internal_corpus(fts+semantic) + perplexity_external"
            ),
            "weather_used": bool(weather_context),
            # Honest provenance (audit INT-02): report the provider/model that
            # actually produced the synthesis when known, not key presence.
            "synthesis_model": (
                getattr(self, "_last_synthesis_model", None)
                or ("anthropic" if self.anthropic_key else ("deepseek" if os.getenv("DEEPSEEK_API_KEY") else "none"))
            ),
            # The live semantic path embeds with bge-m3 (1024-dim), not ada-002.
            "embedding_model": "bge-m3",
            "external_provider_configured": bool(self.perplexity_key),
            "sources_consulted": sorted({c.get("source_name") for c in citations if c.get("source_name")}),
            # Hallucination check block (may be None if no sources were available
            # or the detector errored — clients should treat absence as "not run").
            "hallucination_check": hallucination_check,
            # Phase 4 wave 1: versioned prompt fingerprints used during this answer.
            "prompts_used": prompts_used,
        }

        llm_unavailable = not self.anthropic_key and not os.getenv("DEEPSEEK_API_KEY")
        has_any_results = internal_count > 0 or external_count > 0
        retrieval_issue = bool(internal_error) or bool(external_error)
        suspiciously_weak_coverage = (
            internal_count > 0
            and external_count == 0
            and all((c.get("relevance_score") or 0) <= 0.15 for c in citations[:8])
        )

        guidance: Optional[Dict[str, Any]] = None
        if llm_unavailable:
            guidance = {
                "status": "limited",
                "reason": "llm_unavailable",
                "message": (
                    "AI synthesis is currently unavailable. Results are retrieval-only; "
                    "connect a configured LLM provider for full analysis rigor."
                ),
                "suggested_actions": [
                    "Ask the assistant for query refinement",
                    "Narrow by country or timeframe",
                    "Retry once provider connectivity is restored",
                ],
            }
        elif retrieval_issue:
            guidance = {
                "status": "partial",
                "reason": "retrieval_error",
                "message": (
                    "Part of the retrieval pipeline failed. The response may miss "
                    "important evidence from one source layer."
                ),
                "suggested_actions": [
                    "Retry the same query",
                    "Run a comparison query for triangulation",
                    "Use chat help to reformulate with explicit constraints",
                ],
            }
        elif not has_any_results:
            guidance = {
                "status": "empty",
                "reason": "no_matching_evidence",
                "message": (
                    "No matching evidence was found in the internal corpus or "
                    "external retrieval layer for this query."
                ),
                "suggested_actions": [
                    "Pick one of the suggested clarifications",
                    "Specify geography + timeframe",
                    "Open chat help for query design guidance",
                ],
            }
        elif suspiciously_weak_coverage:
            guidance = {
                "status": "weak",
                "reason": "low_relevance_retrieval",
                "message": (
                    "Retrieved evidence has weak query match. Treat conclusions as "
                    "low-confidence and refine scope before decision-making."
                ),
                "suggested_actions": [
                    "Constrain by country and years",
                    "Use domain-specific terms (e.g., SPI, SPEI, sea-ice extent)",
                    "Ask chat to suggest scientifically robust query variants",
                ],
            }

        if guidance:
            methodology["guidance"] = guidance

        # Clarification: when the corpus + external search both miss, suggest
        # scope refinements the user can pick. Cheap to compute (one LLM call)
        # and only fires when both sides return zero — so it doesn't add cost
        # to the happy path.
        clarification_needed: Optional[List[str]] = None
        if include_refinements:
            if internal_count == 0 and external_count == 0:
                clarification_needed = await self._suggest_scope_refinements(query, country)

            if guidance and guidance.get("status") in {"partial", "weak"}:
                fallback_refinements = await self._suggest_scope_refinements(query, country)
                if fallback_refinements:
                    clarification_needed = (clarification_needed or []) + fallback_refinements
                    seen: set[str] = set()
                    clarification_needed = [
                        s for s in clarification_needed
                        if isinstance(s, str) and s and (s not in seen and not seen.add(s))
                    ][:5]

        # Phase 4 wave 4: record one provenance row for this deep-search
        # response. Best-effort; never fails the request.
        try:
            from app.domains.intelligence.provenance import (
                EXTRACTION_DEEP_SEARCH,
                ProvenanceRecord,
                record_provenance,
            )
            from app.domains.intelligence.prompts import get_prompt

            synth_tmpl = get_prompt("deep_search_synthesis")
            source_ids = [
                str(c.get("article_id")) for c in citations
                if c.get("article_id") is not None
            ]
            _h_check = methodology.get("hallucination_check") if methodology else None
            record_provenance(self.db, ProvenanceRecord(
                extraction_method=EXTRACTION_DEEP_SEARCH,
                deep_search_session_id=deep_search_session_id,
                model_name=methodology.get("synthesis_model") if methodology else None,
                prompt_name=synth_tmpl.name,
                prompt_version=synth_tmpl.version,
                prompt_fingerprint=synth_tmpl.fingerprint,
                retrieval_strategy=methodology.get("retrieval_strategy") if methodology else None,
                source_article_ids=source_ids or None,
                hallucination_score=(
                    _h_check.get("hallucination_risk") if isinstance(_h_check, dict) else None
                ),
                raw_metadata={
                    "query": query[:500],
                    "country": country,
                    "category": category,
                    "internal_count": internal_count,
                    "external_count": external_count,
                    "weather_used": bool(weather_context),
                },
            ))
        except Exception as _prov_exc:
            logger.debug(
                "deep_search record_provenance failed (non-fatal): %s",
                _prov_exc,
            )

        # Merge low-evidence refinements into the existing clarification list.
        if low_evidence_refinements:
            merged = list(clarification_needed or []) + list(low_evidence_refinements)
            seen: set[str] = set()
            clarification_needed = [
                s for s in merged
                if isinstance(s, str) and s and not (s in seen or seen.add(s))
            ][:6]

        return {
            "query": query,
            "answer": synthesis,
            # Phase 0 day 3 (2026-05-23, §3.3): per-sentence grounding
            # tags + confidence envelope, present only when the
            # low-evidence prompt ran. Clients render per-sentence pills.
            "sentence_grounding": sentence_grounding,
            "confidence_envelope": confidence_envelope,
            # v2.0 structured synthesis (2026-06-14): present when the
            # high-evidence prompt returned parseable JSON. Renders as
            # visual blocks (key findings, agreement diff, evidence gauge).
            "structured_synthesis": structured,
            "citations": citations,
            "internal_articles_count": internal_count,
            "external_sources_count": external_count,
            "weather_context": weather_context,
            "filters": {
                "country": country,
                "category": category,
            },
            "methodology": methodology,
            "clarification_needed": clarification_needed,
            "deep_search_session_id": deep_search_session_id,
            "searched_at": datetime.utcnow().isoformat(),
        }

    async def compare(
        self,
        query_a: str,
        query_b: str,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare two topics/queries side by side.

        Returns results for both queries plus a comparative analysis.
        If one side fails, partial results are still returned.
        """
        def _read_timeout(name: str, default: float) -> float:
            raw = os.getenv(name)
            if raw is None or raw == "":
                return default
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return default
            return value if value > 0 else default

        side_timeout = _read_timeout("DEEP_SEARCH_COMPARE_SIDE_TIMEOUT_SECONDS", 18.0)
        synthesis_timeout = _read_timeout("DEEP_SEARCH_COMPARE_SYNTHESIS_TIMEOUT_SECONDS", 8.0)

        async def _run_side(query: str):
            return await asyncio.wait_for(
                self.search(
                    query,
                    country=country,
                    include_weather=False,
                    limit=5,
                    include_hallucination_check=False,
                    include_refinements=False,
                ),
                timeout=side_timeout,
            )

        raw_a, raw_b = await asyncio.gather(
            _run_side(query_a),
            _run_side(query_b),
            return_exceptions=True,
        )

        empty_result = {
            "query": "",
            "answer": "Search failed for this topic.",
            "citations": [],
            "internal_articles_count": 0,
            "external_sources_count": 0,
            "weather_context": None,
            "filters": {},
            "searched_at": datetime.utcnow().isoformat(),
        }

        result_a: Dict[str, Any] = empty_result.copy() if isinstance(raw_a, Exception) else raw_a
        result_b: Dict[str, Any] = empty_result.copy() if isinstance(raw_b, Exception) else raw_b

        if isinstance(raw_a, Exception):
            result_a["query"] = query_a
            logger.warning(f"Compare side A failed: {raw_a}")
        if isinstance(raw_b, Exception):
            result_b["query"] = query_b
            logger.warning(f"Compare side B failed: {raw_b}")

        # Phase 0 (2026-05-23, §3.1): aggregate guidance + low-evidence fallback.
        # Previously `compare` always invoked the LLM comparative synthesis even
        # when both sides had 0 sources — producing the "no data available"
        # comparison the user saw on Arctic-vs-Antarctic. Now we:
        #   1. Roll the per-side coverage into an aggregate `guidance` block
        #      with status precedence empty > weak > partial > ok
        #   2. When BOTH sides are fully empty, skip the LLM comparative and
        #      emit a deterministic explainer
        #   3. When the aggregate is empty/weak, run a single unified
        #      `_suggest_scope_refinements` call (cheap: bounded one LLM call)
        #      and surface chips at the compare level
        #   4. When exactly one side is empty, tag the structured comparative
        #      with `low_confidence: true` so the UI can render an honesty pill
        internal_a = int(result_a.get("internal_articles_count") or 0)
        external_a = int(result_a.get("external_sources_count") or 0)
        internal_b = int(result_b.get("internal_articles_count") or 0)
        external_b = int(result_b.get("external_sources_count") or 0)
        total_a = internal_a + external_a
        total_b = internal_b + external_b
        aggregate_total = total_a + total_b

        both_sides_empty = (total_a == 0 and total_b == 0)
        one_side_empty = (total_a == 0) ^ (total_b == 0)
        aggregate_weak = aggregate_total < 4 and not both_sides_empty

        async def _run_bounded(coro):
            return await asyncio.wait_for(coro, timeout=synthesis_timeout)

        comparative_default = (
            f'Comparison between "{query_a}" and "{query_b}" could not be generated. '
            "Both individual analyses are available above."
        )

        # Branch 1 — both sides empty. Skip the LLM call entirely and emit a
        # deterministic explainer + unified refinement chips. This is the
        # path the Arctic-vs-Antarctic screenshot hit.
        if both_sides_empty:
            comparative = (
                f'We could not find evidence in our verified corpus or external sources '
                f'for either "{query_a}" or "{query_b}". A side-by-side comparison would '
                f'be unreliable here — instead, try one of the refined queries below.'
            )
            try:
                refinements_a, refinements_b = await asyncio.gather(
                    _run_bounded(self._suggest_scope_refinements(query_a, country)),
                    _run_bounded(self._suggest_scope_refinements(query_b, country)),
                    return_exceptions=True,
                )
            except Exception:
                refinements_a, refinements_b = None, None

            chips: List[str] = []
            for ref_set in (refinements_a, refinements_b):
                if isinstance(ref_set, list):
                    chips.extend(s for s in ref_set if isinstance(s, str) and s)
            # dedupe preserving order, cap at 6
            seen: set[str] = set()
            chips = [s for s in chips if not (s in seen or seen.add(s))][:6]

            comparative_structured = None
            comparative_raw_result = comparative
            comparative_structured_raw = None
        else:
            comparative_raw_result, comparative_structured_raw = await asyncio.gather(
                _run_bounded(self._generate_comparison(query_a, query_b, result_a, result_b)),
                _run_bounded(self._generate_comparison_structured(query_a, query_b, result_a, result_b)),
                return_exceptions=True,
            )

            if isinstance(comparative_raw_result, Exception):
                logger.warning(f"Comparison synthesis failed: {comparative_raw_result}")
                comparative = comparative_default
            else:
                comparative = comparative_raw_result or comparative_default

            if isinstance(comparative_structured_raw, Exception):
                logger.warning(
                    f"Structured comparison synthesis failed: {comparative_structured_raw}"
                )
                comparative_structured = None
            else:
                comparative_structured = comparative_structured_raw

            # Tag the structured payload with a low_confidence flag when one
            # side has no evidence — the UI uses this to render an explicit
            # honesty pill ("Topic B has no sources — comparison reflects
            # Topic A's findings against a gap").
            if comparative_structured and one_side_empty:
                if isinstance(comparative_structured, dict):
                    comparative_structured = {
                        **comparative_structured,
                        "low_confidence": True,
                        "low_confidence_reason": (
                            f'Topic {"A" if total_a == 0 else "B"} returned 0 sources; '
                            "the comparison reflects an asymmetric evidence base."
                        ),
                    }

            # If aggregate evidence is weak (but not empty), still emit
            # refinement chips at compare level so the user can sharpen scope.
            chips = []
            if aggregate_weak:
                try:
                    weak_refinements = await _run_bounded(
                        self._suggest_scope_refinements(
                            f"{query_a} vs {query_b}",
                            country,
                        )
                    )
                    if isinstance(weak_refinements, list):
                        chips = [
                            s for s in weak_refinements
                            if isinstance(s, str) and s
                        ][:5]
                except Exception as ref_exc:
                    logger.debug(
                        f"Compare-level refinement suggestion failed: {ref_exc}"
                    )

        # Build the aggregate guidance block — same shape as single-search so
        # the UI's amber-box renderer can reuse the existing component.
        guidance: Optional[Dict[str, Any]] = None
        if both_sides_empty:
            guidance = {
                "status": "empty",
                "reason": "no_matching_evidence_either_side",
                "message": (
                    "Neither topic returned matching evidence from the verified "
                    "corpus or external research. The comparative analysis below "
                    "is a deterministic explainer — not a synthesised finding. "
                    "Pick a refined query to get a substantive answer."
                ),
                "suggested_actions": [
                    "Constrain by country and timeframe",
                    "Use domain-specific terms (e.g. SPI, SPEI, sea-ice extent)",
                    "Pick one of the refined queries below",
                ],
                "per_side": {
                    "a": {"internal": internal_a, "external": external_a},
                    "b": {"internal": internal_b, "external": external_b},
                },
            }
        elif one_side_empty:
            empty_label = "A" if total_a == 0 else "B"
            empty_query = query_a if total_a == 0 else query_b
            guidance = {
                "status": "asymmetric",
                "reason": "one_side_empty",
                "message": (
                    f'Topic {empty_label} ("{empty_query}") returned 0 sources, '
                    "so the comparison is structurally asymmetric. Treat any "
                    "contrast claim about that topic as low-confidence."
                ),
                "suggested_actions": [
                    f"Refine Topic {empty_label} with country + timeframe",
                    "Switch to single-topic Research mode for the empty side",
                ],
                "per_side": {
                    "a": {"internal": internal_a, "external": external_a},
                    "b": {"internal": internal_b, "external": external_b},
                },
            }
        elif aggregate_weak:
            guidance = {
                "status": "weak",
                "reason": "low_aggregate_coverage",
                "message": (
                    f"Combined evidence base is thin "
                    f"({aggregate_total} sources across both topics). The "
                    "comparison should be treated as low-confidence — sharpen "
                    "scope before relying on conclusions."
                ),
                "suggested_actions": [
                    "Add geographic and temporal constraints",
                    "Pick a refined query below to re-run with sharper scope",
                ],
                "per_side": {
                    "a": {"internal": internal_a, "external": external_a},
                    "b": {"internal": internal_b, "external": external_b},
                },
            }

        return {
            "query_a": query_a,
            "query_b": query_b,
            "result_a": result_a,
            "result_b": result_b,
            "comparative_analysis": comparative if not both_sides_empty else comparative_raw_result,
            "comparative_analysis_structured": comparative_structured,
            # Top-level aggregate guidance + refinement chips (§3.1 fix).
            "guidance": guidance,
            "clarification_needed": chips or None,
            "low_confidence": both_sides_empty or one_side_empty or aggregate_weak,
            "compared_at": datetime.utcnow().isoformat(),
        }

    # Relevance thresholds (2026-05-25 fix — user reported "Slovenian
    # celebrity articles returned for India heatwave query"). Below
    # these floors the corpus has nothing genuinely on-topic and the
    # honest surface is "0 internal hits" rather than top-N noise.
    #
    # MIN_SEMANTIC_SIMILARITY: cosine similarity to query embedding.
    #   ada-002 embeddings + climate-news corpus → on-topic articles
    #   typically score 0.75+. Below 0.55 means the top result is
    #   mostly stop-word/grammar overlap, not actual topic match.
    # MIN_FTS_RANK: ts_rank floor — ts_rank is normalised 0-1 by
    #   pg's default `ts_rank_cd` heuristics. 0.01 = "at least one
    #   query token actually appears in the doc."
    MIN_SEMANTIC_SIMILARITY = 0.55
    MIN_FTS_RANK = 0.01

    async def _search_internal_corpus(
        self,
        query: str,
        country: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Search internal article corpus using hybrid FTS + semantic search.

        Relevance fence (2026-05-25): semantic results below
        MIN_SEMANTIC_SIMILARITY (cosine) and FTS results below
        MIN_FTS_RANK are dropped. If both layers return nothing
        relevant, the function returns [] rather than cherry-picking
        the top-N closest noise. Callers MUST check the empty list
        and surface "no relevant hits in the corpus" — see the
        synthesis path that previously fabricated answers from
        zero-relevance Slovenian celebrity articles for India queries.
        """
        # Live column is bge-m3 (2026-06-11 audit); ada-002 is unpopulated.
        embedding = await self.embedding_service.generate_bge_m3_embedding(query)

        results = []

        # Semantic search if embeddings available
        if embedding:
            filters = []
            params: Dict[str, Any] = {
                "limit": limit,
                "min_sim": self.MIN_SEMANTIC_SIMILARITY,
            }

            if country:
                filters.append("a.country_code = :country")
                params["country"] = country.upper()
            if category:
                filters.append("a.content_category = :category")
                params["category"] = category

            where_clause = " AND ".join(filters) if filters else "TRUE"
            vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
            params["embedding"] = vector_str

            sql = f"""
                SELECT
                    a.article_id, a.title, a.source_name, a.country_code,
                    a.content_category, a.overall_credibility, a.reliability_score,
                    a.published_date, a.excerpt,
                    1 - (a.embedding_bge_m3 <=> :embedding::vector) AS similarity
                FROM articles a
                WHERE a.embedding_bge_m3 IS NOT NULL
                  AND (1 - (a.embedding_bge_m3 <=> :embedding::vector)) >= :min_sim
                  AND {where_clause}
                ORDER BY a.embedding_bge_m3 <=> :embedding::vector
                LIMIT :limit
            """

            try:
                rows = self.db.execute_query(sql, params)
                for r in (rows or []):
                    results.append({
                        "article_id": str(r["article_id"]),
                        "title": r.get("title", ""),
                        "source_name": r.get("source_name", ""),
                        "country_code": r.get("country_code"),
                        "content_category": r.get("content_category"),
                        "overall_credibility": r.get("overall_credibility"),
                        "reliability_score": r.get("reliability_score"),
                        "published_date": str(r["published_date"]) if r.get("published_date") else None,
                        "excerpt": r.get("excerpt"),
                        "relevance_score": round(float(r.get("similarity", 0)), 4),
                    })
            except Exception as e:
                logger.error(f"Internal corpus search failed: {e}")

        # Fallback to FTS if no semantic results survived the threshold.
        # FTS rank now floored at MIN_FTS_RANK so an article matching one
        # stop-word doesn't get treated as on-topic.
        if not results:
            fts_filters = []
            fts_params: Dict[str, Any] = {
                "query": query,
                "limit": limit,
                "min_rank": self.MIN_FTS_RANK,
            }
            if country:
                fts_filters.append("a.country_code = :country")
                fts_params["country"] = country.upper()

            fts_where = " AND ".join(fts_filters) if fts_filters else "TRUE"

            # Try websearch_to_tsquery first (supports OR/phrase), fall back to plainto
            for tsq_func in ["websearch_to_tsquery", "plainto_tsquery"]:
                if results:
                    break
                fts_sql = f"""
                    SELECT a.article_id, a.title, a.source_name, a.country_code,
                           a.content_category, a.overall_credibility, a.reliability_score,
                           a.published_date, a.excerpt,
                           ts_rank(
                               a.search_tsv,
                               {tsq_func}('simple', :query)
                           ) AS text_rank
                    FROM articles a
                    WHERE a.search_tsv
                          @@ {tsq_func}('simple', :query)
                      AND ts_rank(
                              a.search_tsv,
                              {tsq_func}('simple', :query)
                          ) >= :min_rank
                      AND {fts_where}
                    ORDER BY text_rank DESC LIMIT :limit
                """
                try:
                    rows = self.db.execute_query(fts_sql, fts_params)
                    for r in (rows or []):
                        results.append({
                            "article_id": str(r["article_id"]),
                            "title": r.get("title", ""),
                            "source_name": r.get("source_name", ""),
                            "country_code": r.get("country_code"),
                            "overall_credibility": r.get("overall_credibility"),
                            "reliability_score": r.get("reliability_score"),
                            "published_date": str(r["published_date"]) if r.get("published_date") else None,
                            "excerpt": r.get("excerpt"),
                            "relevance_score": round(float(r.get("text_rank", 0)), 4),
                        })
                except Exception as e:
                    logger.warning(f"FTS search ({tsq_func}) failed: {e}")

        # ILIKE fallback removed (2026-05-25) — it returned a constant
        # text_rank=0.1 for any keyword match in title/excerpt/body,
        # which is exactly the "Slovenian celebrity article for India
        # heatwave query" noise the user reported. If semantic + FTS
        # both find nothing genuinely relevant, return empty so the
        # caller surfaces an honest "no internal hits — try a broader
        # query or rely on external sources" rather than fabricating
        # sources. Kept the block deletion comment-only for an audit
        # trail of the change.
        # Relevance guardrail: if none of the key query terms appear in the
        # retrieved texts and semantic relevance is weak, drop the result set.
        if results:
            filtered = self._filter_results_by_query_relevance(query, results)
            if filtered:
                results = filtered[:limit]
            else:
                logger.info(
                    "Deep search relevance guardrail removed internal results: "
                    f"query={query[:120]!r}, candidate_count={len(results)}"
                )
                results = []

        return results

    @staticmethod
    def _normalized_query_terms(query: str) -> List[str]:
        import re

        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "into",
            "about", "what", "how", "when", "where", "which", "is", "are",
            "was", "were", "can", "could", "should", "would", "does", "did",
        }

        raw = re.findall(r"[\w]{3,}", (query or "").lower())
        return [t for t in raw if t not in stopwords][:14]

    @classmethod
    def _filter_results_by_query_relevance(
        cls,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Reject articles whose lexical overlap AND semantic similarity
        are both weak. Replaces the prior `overlap >= 0.1 OR rel >= 0.2`
        gate which was permissive enough to let Slovenian celebrity
        articles pass for an "India extreme heat" query (one shared
        common token + neutral embedding similarity sufficed).

        New thresholds (2026-05-25):
          - MIN_LEXICAL_OVERLAP = 0.25 — at least 25 % of non-stopword
            query terms must appear somewhere in title/excerpt/category.
          - MIN_RELEVANCE_RESCUE = 0.5 — OR semantic similarity must be
            strong enough that the embedding model thinks the article
            covers the same topic.

        An article keeps if EITHER threshold is met. Both being weak
        means the article doesn't deserve to be cited.
        """
        MIN_LEXICAL_OVERLAP = 0.25
        MIN_RELEVANCE_RESCUE = 0.5

        terms = cls._normalized_query_terms(query)
        if not terms:
            return results

        kept: List[Dict[str, Any]] = []
        for art in results:
            haystack = (
                f"{art.get('title', '')} "
                f"{art.get('excerpt', '')} "
                f"{art.get('content_category', '')}"
            ).lower()

            hit_count = sum(1 for t in terms if t in haystack)
            overlap = hit_count / max(1, len(terms))

            rel = art.get("relevance_score")
            try:
                rel_score = float(rel) if rel is not None else 0.0
            except (TypeError, ValueError):
                rel_score = 0.0

            if overlap >= MIN_LEXICAL_OVERLAP or rel_score >= MIN_RELEVANCE_RESCUE:
                kept.append(art)

        return kept

    async def _search_perplexity(
        self, query: str, country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search external sources via Perplexity Sonar."""
        if not self.perplexity_key:
            logger.warning(
                "PERPLEXITY_API_KEY not configured; deep search will skip external citations."
            )
            return {"answer": "", "citations": []}

        country_context = f" Focus on {country} region." if country else ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("PERPLEXITY_MODEL", "sonar"),
                        "messages": [{
                            "role": "user",
                            "content": (
                                f"Research this climate/environment topic thoroughly: \"{query}\".{country_context} "
                                "Provide a comprehensive answer with specific data points, statistics, "
                                "and findings from credible sources (scientific papers, government agencies, "
                                "international organizations). Include temporal context (when data is from)."
                            ),
                        }],
                        "temperature": 0.1,
                        "max_tokens": 1500,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])

                return {
                    "answer": content,
                    "citations": citations,
                }
        except Exception as e:
            logger.warning(f"Perplexity deep search failed: {e}")
            return {"answer": "", "citations": []}

    async def _get_weather_context(
        self, query: str, country: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather context relevant to the query.

        Uses the explicitly requested country, or tries to extract a country
        code from the query text, before falling back to a global context.
        """
        retriever = OpenMeteoEvidenceRetriever()
        cc = country or self._extract_country_from_query(query)
        if not cc:
            return None
        evidence_list = await retriever.retrieve(query, cc)

        if not evidence_list:
            return None

        return {
            "country_code": cc,
            "data_points": [
                {
                    "source": e.source,
                    "content": e.content_excerpt,
                    "reliability": e.source_reliability,
                    "retrieval_method": e.retrieval_method,
                }
                for e in evidence_list
            ],
        }

    async def _synthesize_low_evidence_answer(
        self,
        query: str,
        internal_articles: List[Dict],
        perplexity_answer: str,
        weather_context: Optional[Dict],
    ) -> Dict[str, Any]:
        """Synthesize a low-evidence answer with per-sentence grounding tags.

        Routed to from `search()` when internal_count + external_count < 3.
        The dedicated `deep_search_synthesis_low_evidence` prompt (v1.0,
        added 2026-05-23) instructs the LLM to:
          * generate an answer despite the evidence gap
          * tag every sentence with HIGH/MEDIUM/LOW/NONE grounding
          * wrap in a `confidence: low` envelope
          * suggest 3-5 refined queries

        Returns a dict with keys: answer_markdown, sentence_grounding[],
        confidence, confidence_reason, suggested_refinements[]. On parse
        failure (LLM emitted prose instead of JSON), falls back to a
        synthetic envelope so the UI still surfaces *something*.
        """
        import json as _json
        import re as _re

        # Build context exactly the same way as the high-evidence path so
        # the LLM gets identical input — only the prompt + parsing differ.
        articles_context = ""
        if internal_articles:
            for i, art in enumerate(internal_articles[:5], 1):
                cred = art.get("overall_credibility", "UNKNOWN")
                rel = art.get("reliability_score")
                rel_str = ""
                if rel is not None:
                    try:
                        rel_float = float(rel)
                        rel_pct = rel_float * 100.0 if rel_float <= 1.0 else rel_float
                        rel_pct = max(0.0, min(100.0, rel_pct))
                        rel_str = f", reliability: {rel_pct:.0f}%"
                    except (TypeError, ValueError):
                        rel_str = ""
                articles_context += (
                    f"\n{i}. [{cred}{rel_str}] \"{art.get('title', '')}\""
                    f"\n   Source: {art.get('source_name', 'Unknown')}"
                    f"\n   Excerpt: {(art.get('excerpt') or '')[:150]}\n"
                )
        if not articles_context:
            articles_context = "(none)"

        weather_section = ""
        if weather_context and weather_context.get("data_points"):
            weather_section = "\nWEATHER DATA:\n"
            for dp in weather_context["data_points"]:
                weather_section += f"- {dp['content']}\n"

        from app.domains.intelligence.prompts import get_prompt
        tmpl = get_prompt("deep_search_synthesis_low_evidence")
        prompt = tmpl.format(
            query=query,
            internal_count=len(internal_articles or []),
            external_count=1 if (perplexity_answer or "").strip() else 0,
            articles_context=articles_context,
            perplexity_answer=(perplexity_answer or "(none)"),
            weather_section=weather_section,
        )

        raw_text: Optional[str] = None

        # Try Claude first (mirrors the high-evidence path)
        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=tmpl.max_tokens or 1200,
                    temperature=tmpl.temperature if tmpl.temperature is not None else 0.2,
                    system=tmpl.system,
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    raw_text = message.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Claude low-evidence synthesis failed: {e}")

        # Fallback to DeepSeek
        if raw_text is None:
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key:
                try:
                    from openai import OpenAI as OpenAIClient
                    client = OpenAIClient(
                        api_key=deepseek_key,
                        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                        timeout=15.0,
                    )
                    response = client.chat.completions.create(
                        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                        messages=[
                            {"role": "system", "content": tmpl.system or "Return strict JSON."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=tmpl.max_tokens or 1200,
                        temperature=tmpl.temperature if tmpl.temperature is not None else 0.2,
                    )
                    raw_text = response.choices[0].message.content.strip()
                except Exception as e:
                    logger.warning(f"DeepSeek low-evidence synthesis failed: {e}")

        # No LLM available — synthetic envelope so the UI still works
        if raw_text is None:
            return {
                "answer_markdown": (
                    f'We do not currently have verified evidence in our corpus or external '
                    f'research layer for "{query}". The LLM synthesis layer is also '
                    'offline — please try one of the refined queries below or wait for '
                    'LLM availability to return.'
                ),
                "sentence_grounding": [
                    {
                        "text": f'We do not currently have verified evidence in our corpus or external research layer for "{query}".',
                        "level": "HIGH",
                        "reason": "platform-introspection",
                    },
                    {
                        "text": "The LLM synthesis layer is also offline — please try one of the refined queries below or wait for LLM availability to return.",
                        "level": "HIGH",
                        "reason": "platform-introspection",
                    },
                ],
                "confidence": "low",
                "confidence_reason": "no_llm_available_and_no_retrieved_evidence",
                "suggested_refinements": [],
            }

        # Parse the JSON envelope. LLMs sometimes wrap in code fences or
        # add a stray prose preamble — strip generously before json.loads.
        candidate = raw_text
        # Strip ```json ... ``` fences
        fence_match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, _re.DOTALL)
        if fence_match:
            candidate = fence_match.group(1)
        else:
            # Find the first {...} block by greedy braces match
            brace_match = _re.search(r"\{.*\}", candidate, _re.DOTALL)
            if brace_match:
                candidate = brace_match.group(0)

        try:
            parsed = _json.loads(candidate)
            # Light shape validation
            if not isinstance(parsed.get("answer_markdown"), str):
                raise ValueError("answer_markdown missing or wrong type")
            grounding = parsed.get("sentence_grounding")
            if grounding is not None and not isinstance(grounding, list):
                parsed["sentence_grounding"] = None
            return parsed
        except Exception as exc:
            logger.warning(
                "Low-evidence synthesis returned unparseable JSON; "
                f"falling back to raw_text. detail={exc!r}"
            )
            return {
                "answer_markdown": raw_text,
                "sentence_grounding": None,
                "confidence": "low",
                "confidence_reason": "llm_response_unparseable",
                "suggested_refinements": [],
                "raw_text": raw_text,
            }

    async def _synthesize_answer(
        self,
        query: str,
        internal_articles: List[Dict],
        perplexity_answer: str,
        weather_context: Optional[Dict],
    ) -> str:
        """Synthesize a unified answer from all sources using Claude or DeepSeek."""
        # Tool-output compaction (Headroom): the external Perplexity payload can
        # be ~1.5K tokens of verbose prose injected verbatim into the synthesis
        # prompt (the highest-cost path the cost endpoint watches). Cap it first.
        # `_last_synthesis_model` records which provider actually ran so the
        # methodology/provenance can report it honestly (audit INT-02).
        from app.domains.intelligence.context_compaction import compact_text
        perplexity_answer = compact_text(perplexity_answer or "", 400)
        self._last_synthesis_model = None
        # Build context from internal articles
        articles_context = ""
        if internal_articles:
            for i, art in enumerate(internal_articles[:5], 1):
                cred = art.get("overall_credibility", "UNKNOWN")
                rel = art.get("reliability_score")
                rel_str = ""
                if rel is not None:
                    try:
                        rel_float = float(rel)
                        rel_pct = rel_float * 100.0 if rel_float <= 1.0 else rel_float
                        rel_pct = max(0.0, min(100.0, rel_pct))
                        rel_str = f", reliability: {rel_pct:.0f}%"
                    except (TypeError, ValueError):
                        rel_str = ""
                articles_context += (
                    f"\n{i}. [{cred}{rel_str}] \"{art.get('title', '')}\""
                    f"\n   Source: {art.get('source_name', 'Unknown')}"
                    f"\n   Excerpt: {(art.get('excerpt') or '')[:150]}\n"
                )

        weather_section = ""
        if weather_context and weather_context.get("data_points"):
            weather_section = "\nWEATHER DATA:\n"
            for dp in weather_context["data_points"]:
                weather_section += f"- {dp['content']}\n"

        # Phase 4 wave 1: resolve the versioned prompt from the registry.
        from app.domains.intelligence.prompts import get_prompt
        tmpl = get_prompt("deep_search_synthesis")
        prompt = tmpl.format(
            query=query,
            articles_context=(articles_context or 'No matching articles found.'),
            perplexity_answer=(perplexity_answer or 'No external sources available.'),
            weather_section=weather_section,
        )
        system_prompt = tmpl.system

        # Try Claude first
        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=tmpl.max_tokens or 1500,
                    temperature=tmpl.temperature if tmpl.temperature is not None else 0.2,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    self._last_synthesis_model = (
                        f"anthropic:{os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5')}"
                    )
                    return message.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Claude synthesis failed: {e}")

        # Fallback to DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=15.0,
                )
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": system_prompt or "Synthesize climate research concisely."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=tmpl.max_tokens or 1500,
                    temperature=tmpl.temperature if tmpl.temperature is not None else 0.2,
                )
                self._last_synthesis_model = (
                    f"deepseek:{os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')}"
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"DeepSeek synthesis failed: {e}")

        # No LLM available — return raw concatenation
        parts = []
        if internal_articles:
            parts.append(f"Found {len(internal_articles)} related articles in our corpus.")
        if perplexity_answer:
            parts.append(f"External research:\n{perplexity_answer[:500]}")
        if weather_context:
            for dp in weather_context.get("data_points", []):
                parts.append(dp["content"])
        return "\n\n".join(parts) if parts else "No results found for this query."

    async def _generate_comparison(
        self,
        query_a: str,
        query_b: str,
        result_a: Dict,
        result_b: Dict,
    ) -> str:
        """Generate a comparative analysis between two search results."""
        prompt = f"""Compare these two climate topics:

TOPIC A: "{query_a}"
- {result_a.get('internal_articles_count', 0)} internal articles found
- Answer summary: {(result_a.get('answer') or '')[:300]}

TOPIC B: "{query_b}"
- {result_b.get('internal_articles_count', 0)} internal articles found
- Answer summary: {(result_b.get('answer') or '')[:300]}

Provide a structured comparison covering:
1. Key similarities and differences
2. Which topic has stronger evidence/coverage
3. How they relate to each other
4. Notable gaps in either topic

Be concise and factual. Use markdown."""

        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                message = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=1000,
                    temperature=0.2,
                    system="You compare climate topics with factual precision.",
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    return message.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Comparison synthesis (Claude) failed: {e}")

        # Fallback to DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=15.0,
                )
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "You compare climate topics with factual precision."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.2,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Comparison synthesis (DeepSeek) failed: {e}")

        return f"Comparison between \"{query_a}\" and \"{query_b}\" could not be generated. Both individual analyses are available above."

    @staticmethod
    def _extract_country_from_query(query: str) -> Optional[str]:
        """Try to extract a 2-letter country code from the query text.

        Handles explicit codes like 'US', 'DE', common country name mentions,
        and regional terms like 'southern europe' (returns a representative
        country for weather context).
        """
        import re

        query_lower = query.lower()

        # Regional terms -> representative country code for weather context
        REGION_TO_CODE = {
            "southern europe": "ES", "south europe": "ES",
            "northern europe": "SE", "north europe": "SE",
            "western europe": "FR", "west europe": "FR",
            "eastern europe": "PL", "east europe": "PL",
            "central europe": "DE",
            "mediterranean": "IT",
            "iberian peninsula": "ES", "iberia": "ES",
            "scandinavia": "SE", "nordic": "SE", "nordics": "SE",
            "balkans": "RS", "balkan": "RS",
            "southeast asia": "TH", "south east asia": "TH",
            "east asia": "JP", "eastern asia": "JP",
            "south asia": "IN", "southern asia": "IN",
            "central asia": "KZ",
            "middle east": "SA", "mideast": "SA",
            "north africa": "EG", "northern africa": "EG",
            "west africa": "NG", "western africa": "NG",
            "east africa": "KE", "eastern africa": "KE",
            "southern africa": "ZA", "south africa": "ZA",
            "central africa": "CD",
            "sub-saharan africa": "KE", "subsaharan": "KE",
            "latin america": "BR", "south america": "BR",
            "central america": "MX",
            "caribbean": "JM",
            "oceania": "AU", "pacific islands": "NZ",
            "arctic": "NO", "antarctic": "AQ",
        }

        for region, code in REGION_TO_CODE.items():
            if region in query_lower:
                return code

        # Common country name -> code mapping
        NAME_TO_CODE = {
            "united states": "US", "usa": "US", "america": "US",
            "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
            "germany": "DE", "france": "FR", "italy": "IT", "spain": "ES",
            "canada": "CA", "australia": "AU", "japan": "JP", "china": "CN",
            "india": "IN", "brazil": "BR", "russia": "RU", "mexico": "MX",
            "finland": "FI", "sweden": "SE", "norway": "NO", "denmark": "DK",
            "netherlands": "NL", "belgium": "BE", "austria": "AT",
            "switzerland": "CH", "portugal": "PT", "greece": "GR",
            "poland": "PL", "ireland": "IE", "south korea": "KR",
            "nigeria": "NG", "egypt": "EG",
            "kenya": "KE", "indonesia": "ID", "philippines": "PH",
            "turkey": "TR", "argentina": "AR", "colombia": "CO",
            "chile": "CL", "new zealand": "NZ", "pakistan": "PK",
            "thailand": "TH", "vietnam": "VN", "malaysia": "MY",
            "saudi arabia": "SA", "iran": "IR", "iraq": "IQ",
            "ukraine": "UA", "romania": "RO", "czech republic": "CZ",
            "hungary": "HU", "croatia": "HR", "serbia": "RS",
            "bulgaria": "BG", "slovakia": "SK", "slovenia": "SI",
            "estonia": "EE", "latvia": "LV", "lithuania": "LT",
            "cyprus": "CY", "malta": "MT", "luxembourg": "LU",
            "iceland": "IS", "morocco": "MA", "tunisia": "TN",
            "algeria": "DZ", "ethiopia": "ET", "tanzania": "TZ",
            "ghana": "GH", "senegal": "SN", "ivory coast": "CI",
            "peru": "PE", "venezuela": "VE", "ecuador": "EC",
            "bolivia": "BO", "paraguay": "PY", "uruguay": "UY",
            "cuba": "CU", "costa rica": "CR", "panama": "PA",
            "jamaica": "JM", "singapore": "SG", "bangladesh": "BD",
            "nepal": "NP", "sri lanka": "LK", "myanmar": "MM",
            "cambodia": "KH", "mongolia": "MN", "kazakhstan": "KZ",
        }

        for name, code in NAME_TO_CODE.items():
            if name in query_lower:
                return code

        # Check for explicit 2-letter code pattern (e.g. "in US", "for DE")
        code_match = re.search(r'\b([A-Z]{2})\b', query.upper())
        if code_match:
            candidate = code_match.group(1)
            skip_words = {"IN", "IT", "IS", "OR", "AN", "AT", "AS", "IF", "ON",
                          "TO", "UP", "NO", "SO", "DO", "BY", "OF", "BE", "ME",
                          "MY", "HE", "WE", "AM", "VS"}
            if candidate not in skip_words:
                return candidate

        return None

    async def _suggest_scope_refinements(
        self, query: str, country: Optional[str]
    ) -> Optional[List[str]]:
        """Suggest 3 specific scope refinements when a search returns no results.

        Triggered only on the empty-result path so it doesn't add cost to the
        happy path. Frontend renders these as clickable chips that re-submit
        the query with the refinement appended.
        """
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_key and not self.anthropic_key:
            return None

        prompt = (
            f"User query: \"{query}\"\n"
            f"Country filter applied: {country or 'none'}\n\n"
            "This query returned zero results. Suggest exactly 3 specific scope "
            "refinements the user could click to retry. Each refinement should "
            "be a short noun phrase that narrows the query (a country, a "
            "timeframe, a specific technology, or an industry sub-segment). "
            "Return ONLY a JSON array of 3 strings, no prose. Example: "
            "[\"Spain (last 12 months)\", \"Italy offshore wind\", \"Greece solar 2024\"]."
        )

        try:
            if deepseek_key:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=10.0,
                )
                resp = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "Return only valid JSON arrays of 3 short strings."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=200,
                    temperature=0.4,
                )
                raw = resp.choices[0].message.content.strip()
            else:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=10.0)
                msg = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=200,
                    temperature=0.4,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text.strip() if msg.content else ""

            # Strip ```json fences if present
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            import json as _json
            parsed = _json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed[:3]
        except Exception as e:
            logger.warning(f"Scope refinement suggestion failed: {e}")
        return None

    async def _generate_comparison_structured(
        self,
        query_a: str,
        query_b: str,
        result_a: Dict,
        result_b: Dict,
    ) -> Optional[Dict[str, Any]]:
        """Structured comparative analysis (similarities/differences/strength).

        Frontend prefers this over the markdown blob when present.
        """
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_key and not self.anthropic_key:
            return None

        prompt = f"""Compare these two climate research topics and return ONLY a JSON object.

TOPIC A: "{query_a}"
- internal_articles: {result_a.get('internal_articles_count', 0)}
- external_sources: {result_a.get('external_sources_count', 0)}
- answer summary: {(result_a.get('answer') or '')[:400]}

TOPIC B: "{query_b}"
- internal_articles: {result_b.get('internal_articles_count', 0)}
- external_sources: {result_b.get('external_sources_count', 0)}
- answer summary: {(result_b.get('answer') or '')[:400]}

Return JSON with exactly these keys:
{{
  "summary": "<two-sentence overview>",
  "similarities": ["<short bullet>", ...3-5 items],
  "differences": ["<short bullet>", ...3-5 items],
  "evidence_strength": "balanced" | "topic_a_stronger" | "topic_b_stronger" | "weak",
  "common_gaps": ["<short bullet>", ...0-3 items]
}}
No prose outside the JSON."""

        try:
            if deepseek_key:
                from openai import OpenAI as OpenAIClient
                client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=15.0,
                )
                resp = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    messages=[
                        {"role": "system", "content": "Return only valid JSON. No prose, no code fences."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content.strip()
            else:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=15.0)
                msg = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                    max_tokens=1000,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text.strip() if msg.content else ""

            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            import json as _json
            parsed = _json.loads(raw)
            if isinstance(parsed, dict):
                return {
                    "summary": str(parsed.get("summary", ""))[:500],
                    "similarities": [str(x) for x in (parsed.get("similarities") or [])][:5],
                    "differences": [str(x) for x in (parsed.get("differences") or [])][:5],
                    "evidence_strength": str(parsed.get("evidence_strength", "balanced")),
                    "common_gaps": [str(x) for x in (parsed.get("common_gaps") or [])][:3],
                }
        except Exception as e:
            logger.warning(f"Structured comparison failed: {e}")
        return None

    def _has_weather_keywords(self, text: str) -> bool:
        """Check if text contains weather-related keywords."""
        keywords = [
            "weather", "temperature", "precipitation", "rainfall", "wind",
            "heatwave", "heat wave", "flood", "drought", "storm", "hurricane",
            "typhoon", "cyclone", "snow", "frost", "ice", "cold wave",
            "forecast", "meteorolog", "climate data", "°c", "celsius",
            "climate", "warming", "cooling", "solar", "energy",
            "renewable", "emission", "carbon",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)


def _domain_from_url(url: str) -> str:
    """Extract domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url
