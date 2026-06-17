"""
Conversation Engine for Article Q&A

Uses Claude with article text + verified claims + evidence as grounded context.
Only answers based on article content — no hallucination beyond provided facts.
"""

from typing import Optional
from uuid import UUID

from app.core.logging import get_logger
from app.core.database import Database
from .llm_client import get_llm_client

logger = get_logger(__name__)


class ConversationEngine:
    """
    Grounded Q&A engine that answers questions about analyzed articles.

    Uses the article text, extracted claims, and verification results as
    context to ensure answers are grounded in the source material.
    """

    def __init__(self, db: Database, model: str = "deepseek-chat"):
        self.db = db
        self.deepseek_client, self.deepseek_model = get_llm_client()
        self.model = self.deepseek_model or model
        # DeepSeek only — no Anthropic
        self.client = None
        self.api_key = None
        self.use_deepseek = self.deepseek_client is not None
        if self.use_deepseek:
            logger.info("ConversationEngine using DeepSeek LLM")

    async def ask(
        self,
        article_id: UUID,
        question: str,
        user_id: Optional[UUID] = None,
        conversation_context: Optional[list[dict]] = None,
        scope: str = "article",
    ) -> dict:
        """
        Answer a question about an article using grounded context.

        Args:
            article_id: The article to ask about
            question: User's question
            user_id: Optional user ID for tracking
            scope: "article" = article-only context; "external" = includes deep search

        Returns:
            Dict with answer, confidence, context_used, conversation_id
        """
        if not self.client and not self.deepseek_client:
            return {
                "answer": "Q&A service unavailable: no API key configured.",
                "confidence": 0.0,
                "context_used": [],
                "error": "no_api_key",
                "scope": scope,
            }

        # Fetch article context
        context = await self._build_context(article_id)
        if not context["article_text"]:
            return {
                "answer": "Article not found or has no content available for Q&A.",
                "confidence": 0.0,
                "context_used": [],
                "error": "article_not_found",
                "scope": scope,
            }

        # External search: run a lean deep search for cross-referencing
        external_context = ""
        if scope == "external":
            try:
                external_context = await self._run_external_search(question, context)
            except Exception as e:
                logger.warning(f"External search for Q&A failed: {e}")

        # Build grounded prompt with optional conversation history
        prompt = self._build_prompt(question, context, conversation_context, external_context)

        # Agentic actions (2026-06-10 audit): let the article assistant suggest
        # next-step skills (explore_entity, explain_connection, flag_off_topic…)
        # so the chat ACTS on article pages, not just answers. The trailing JSON
        # block is stripped from the stored/displayed answer below.
        from app.domains.intelligence.chat_actions import (
            actions_prompt_suffix, split_actions,
        )
        prompt = f"{prompt}{actions_prompt_suffix()}"

        if scope == "external":
            system_prompt = (
                "You are Climatefacts.ai's research analyst. Answer the user's question "
                "using the provided article content, claims, and verification results as "
                "primary context. The EXTERNAL SEARCH RESULTS section contains broader "
                "information from the platform's climate corpus. Use it to enrich and "
                "cross-reference your answer, but clearly distinguish between article-specific "
                "facts and external context. If information across sources conflicts, note the "
                "discrepancy. Never make up facts. Be concise and factual."
            )
        else:
            system_prompt = (
                "You are Climatefacts.ai's article analysis assistant. You ONLY answer "
                "questions based on the provided article content, claims, and verification "
                "results. If the article doesn't contain information to answer the question, "
                "say so clearly and suggest switching to 'Research' mode for broader context. "
                "Never make up facts or cite sources not in the context. "
                "Be concise, factual, and reference specific claims or evidence when possible."
            )

        try:
            answer = None
            used_model = self.model

            # Try DeepSeek first when configured as primary
            if self.use_deepseek and self.deepseek_client:
                try:
                    response = self.deepseek_client.chat.completions.create(
                        model=self.deepseek_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=800,
                        temperature=0.2,
                    )
                    answer = response.choices[0].message.content.strip()
                    used_model = f"deepseek:{self.deepseek_model}"
                except Exception as e:
                    logger.warning(f"DeepSeek Q&A failed, falling back to Claude: {e}")
                    answer = None

            # Retry with deepseek-chat if primary model failed
            if answer is None and self.deepseek_client:
                try:
                    response = self.deepseek_client.chat.completions.create(
                        model=self.deepseek_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=800,
                        temperature=0.2,
                    )
                    answer = response.choices[0].message.content.strip()
                    used_model = f"deepseek:{self.deepseek_model}"
                except Exception as e:
                    logger.error(f"DeepSeek fallback Q&A also failed: {e}")

            if not answer:
                return {
                    "answer": "An error occurred while processing your question. Please try again.",
                    "confidence": 0.0,
                    "context_used": [],
                    "error": "all_providers_failed",
                    "scope": scope,
                }

            # Split the trailing JSON actions block out before storing/scoring,
            # so the stored answer + confidence estimate use clean text.
            answer, actions = split_actions(answer)

            # Estimate confidence based on context relevance
            confidence = self._estimate_confidence(question, context, answer)

            # Store conversation
            conversation_id = await self._store_conversation(
                article_id=article_id,
                user_id=user_id,
                question=question,
                answer=answer,
                context_used=context.get("sources_used", []),
                confidence=confidence,
            )

            return {
                "conversation_id": str(conversation_id) if conversation_id else None,
                "answer": answer,
                "actions": actions,
                "confidence": confidence,
                "context_used": context.get("sources_used", []),
                "model": used_model,
                "scope": scope,
            }

        except Exception as e:
            logger.error(f"Conversation engine error: {e}")
            return {
                "answer": "An error occurred while processing your question.",
                "confidence": 0.0,
                "context_used": [],
                "error": str(e),
                "scope": scope,
            }

    async def _build_context(self, article_id: UUID) -> dict:
        """Build grounded context from article data."""
        # Fetch article
        rows = self.db.execute_query(
            """SELECT title, excerpt, COALESCE(extracted_text, '') as text,
                      source_name, insight_summary, overall_credibility,
                      reliability_score, analysis_article_html
               FROM articles WHERE article_id = :id""",
            {"id": str(article_id)},
        )
        if not rows:
            return {"article_text": None}

        article = rows[0]

        # Fetch claims and verdicts
        claims_rows = self.db.execute_query(
            """SELECT claim_text, claim_category, fc.verification_status, fc.confidence_score,
                      fc.justification
               FROM claims c
               LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
               WHERE c.article_id = :id""",
            {"id": str(article_id)},
        )

        claims_text = ""
        sources_used = [article.get("source_name", "Unknown")]
        if claims_rows:
            for i, c in enumerate(claims_rows, 1):
                status = c.get("verification_status", "unverified")
                conf = c.get("confidence_score") or 0
                claims_text += (
                    f"\n{i}. [{status}] (confidence: {conf:.0%}) {c.get('claim_text', '')}"
                )
                if c.get("justification"):
                    claims_text += f"\n   Justification: {c['justification'][:200]}"

        return {
            "article_text": article.get("text") or article.get("excerpt") or "",
            "title": article.get("title", ""),
            "source_name": article.get("source_name", ""),
            "insight_summary": article.get("insight_summary", ""),
            "credibility": article.get("overall_credibility", "UNKNOWN"),
            "reliability_score": article.get("reliability_score"),
            "claims_text": claims_text,
            "sources_used": sources_used,
        }

    async def _run_external_search(self, question: str, context: dict) -> str:
        """Run a lean internal corpus search to enrich Q&A with broader context."""
        try:
            from app.domains.intelligence.deep_search_service import DeepSearchService
            service = DeepSearchService(self.db)
            result = await service.search(
                question,
                country=None,
                include_weather=False,
                limit=3,
                include_hallucination_check=False,
                include_refinements=False,
            )
            if not isinstance(result, dict):
                return ""
            answer = result.get("answer", "")
            citations = result.get("citations", [])
            parts = []
            if answer:
                parts.append(f"External corpus synthesis:\n{answer[:500]}")
            if citations:
                parts.append("\nRelated articles found:")
                for c in citations[:5]:
                    if c.get("title"):
                        parts.append(
                            f"- {c['title']} ({c.get('source_name', 'unknown')}, "
                            f"credibility: {c.get('credibility', 'N/A')})"
                        )
            return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.warning(f"External search failed in Q&A: {e}")
            return ""

    def _build_prompt(
        self, question: str, context: dict, conversation_context: Optional[list[dict]] = None,
        external_context: str = "",
    ) -> str:
        """Build the grounded prompt with article context and conversation history."""
        # Build conversation history section if multi-turn
        history_section = ""
        if conversation_context:
            turns = []
            for turn in conversation_context[-5:]:  # Keep last 5 turns max
                q = turn.get("question", "")
                a = turn.get("answer", "")
                if q and a:
                    turns.append(f"Q: {q}\nA: {a[:300]}")
            if turns:
                history_section = (
                    "\nPREVIOUS CONVERSATION:\n"
                    + "\n---\n".join(turns)
                    + "\n---\n"
                )

        external_block = ""
        if external_context:
            external_block = f"""
EXTERNAL SEARCH RESULTS:
{external_context}
"""

        only_clause = (
            "Answer the question using ONLY the information provided above." if not external_context
            else "Use the article content as primary source. Supplement with external search "
                 "results where the article lacks coverage. Clearly indicate when information "
                 "comes from external context vs the article itself."
        )

        return f"""ARTICLE TITLE: {context['title']}
SOURCE: {context['source_name']}
CREDIBILITY: {context['credibility']}

ARTICLE TEXT:
{context['article_text'][:3000]}

VERIFIED CLAIMS:{context['claims_text'] or ' None extracted yet.'}

ANALYSIS SUMMARY:
{context.get('insight_summary') or 'Not yet available.'}{external_block}
{history_section}
---

USER QUESTION: {question}

{only_clause} \
If there is conversation history, use it for context but always ground answers in the \
article data. Format your answer using markdown for readability."""

    def _estimate_confidence(self, question: str, context: dict, answer: str) -> float:
        """Estimate answer confidence based on context overlap."""
        # Simple keyword overlap heuristic
        q_words = set(question.lower().split())
        ctx_words = set((context.get("article_text", "") + context.get("claims_text", "")).lower().split())

        overlap = len(q_words & ctx_words)
        total = len(q_words) if q_words else 1

        base_confidence = min(0.9, 0.4 + (overlap / total) * 0.5)

        # Boost if claims were verified
        if context.get("claims_text") and "verified" in context["claims_text"].lower():
            base_confidence = min(0.95, base_confidence + 0.1)

        return round(base_confidence, 2)

    async def _store_conversation(
        self,
        article_id: UUID,
        user_id: Optional[UUID],
        question: str,
        answer: str,
        context_used: list,
        confidence: float,
    ) -> Optional[str]:
        """Store conversation in the database."""
        try:
            from uuid import uuid4
            conv_id = str(uuid4())

            self.db.execute_update(
                """INSERT INTO article_conversations
                   (conversation_id, article_id, user_id, question, answer, context_used, confidence)
                   VALUES (:id, :article_id, :user_id, :question, :answer, :context, :confidence)""",
                {
                    "id": conv_id,
                    "article_id": str(article_id),
                    "user_id": str(user_id) if user_id else None,
                    "question": question,
                    "answer": answer,
                    "context": "{" + ",".join(f'"{s}"' for s in context_used) + "}",
                    "confidence": confidence,
                },
            )
            return conv_id
        except Exception as e:
            logger.warning(f"Failed to store conversation: {e}")
            return None

    async def get_history(self, article_id: UUID, limit: int = 10) -> list[dict]:
        """Get conversation history for an article."""
        rows = self.db.execute_query(
            """SELECT conversation_id, question, answer, confidence, created_at
               FROM article_conversations
               WHERE article_id = :id
               ORDER BY created_at DESC
               LIMIT :limit""",
            {"id": str(article_id), "limit": limit},
        )
        return [dict(r) for r in rows] if rows else []
