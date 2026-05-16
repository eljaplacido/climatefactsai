"""Anthropic-based claim extractor — Phase 5 wave 2.

Sibling to `services.ClaimExtractor` (DeepSeek-based). Same prompt
template (registered as `claim_extraction` in prompts.PROMPTS) and same
`AtomicClaim` output shape, so the multi-LLM verifier can compare their
outputs side-by-side and the measured divergence is attributable to
model behaviour, not prompt drift.

The DeepSeek path stays the production primary; this Anthropic path is
the secondary verifier. When the secondary disagrees with the primary,
the primary's confidence is downgraded (see multi_llm_verifier.py).

Failure modes:
  * `ANTHROPIC_API_KEY` not set → returns empty list (callers treat as
    "secondary unavailable" and fall back to single-LLM semantics).
  * `anthropic` package not installed → returns empty list.
  * Anthropic API call fails → propagates as exception so the caller
    (verify_claims) can convert to `secondary_error`.
  * Malformed JSON → empty list with debug log.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from .schemas import AtomicClaim, ClaimCategory

try:
    import anthropic
except ImportError:  # pragma: no cover - test envs have anthropic
    anthropic = None  # type: ignore[assignment]

_logger = logging.getLogger("anthropic_claim_extractor")


class AnthropicClaimExtractor:
    """Extracts climate-news claims via Anthropic Claude.

    Args:
        model: Overridden by ANTHROPIC_MODEL env when set. Defaults to
            'claude-sonnet-4-5' matching the platform's primary Claude
            model.
        client: Optional injected `anthropic.Anthropic` instance for
            tests; production usage instantiates one from the env key.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        client: Optional["anthropic.Anthropic"] = None,
    ) -> None:
        self.model = (
            model
            or os.getenv("ANTHROPIC_MODEL")
            or "claude-sonnet-4-5"
        )
        self._injected_client = client
        self._api_key = os.getenv("ANTHROPIC_API_KEY")

    @property
    def available(self) -> bool:
        """True if this extractor can serve requests right now."""
        if self._injected_client is not None:
            return True
        if anthropic is None:
            return False
        return bool(self._api_key)

    def _build_client(self) -> Optional["anthropic.Anthropic"]:
        if self._injected_client is not None:
            return self._injected_client
        if anthropic is None or not self._api_key:
            return None
        return anthropic.Anthropic(api_key=self._api_key, timeout=30.0)

    async def decompose_claims(
        self,
        text: str,
        max_claims: int = 20,
    ) -> List[AtomicClaim]:
        """Extract up to `max_claims` AtomicClaim objects from `text`.

        Returns an empty list when:
          * Anthropic isn't configured (no key / no package).
          * The article text is too short (<100 chars).
          * The model returns malformed JSON we can't tolerate.

        Raises whatever Anthropic raises on API failure (so the multi-LLM
        verifier can convert it to `secondary_error`).
        """
        if not text or len(text) < 100:
            return []

        client = self._build_client()
        if client is None:
            _logger.debug(
                "AnthropicClaimExtractor unavailable: no client / no key. "
                "Returning empty list."
            )
            return []

        # Resolve the versioned prompt template — same template as the
        # DeepSeek primary so we measure agreement, not prompt drift.
        from .prompts import get_prompt

        tmpl = get_prompt("claim_extraction")
        prompt = tmpl.format(text=text[:4000], max_claims=max_claims)

        # synchronous SDK call — wrap in run_in_executor if we need to
        # avoid blocking the event loop on heavy load. For Phase 5 wave 2
        # the simple call is fine; the multi-LLM verifier already runs
        # this concurrently with the primary via asyncio.gather.
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=tmpl.max_tokens or 2000,
                temperature=tmpl.temperature if tmpl.temperature is not None else 0.1,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            raise  # let the verifier observe the error type

        if not getattr(message, "content", None):
            _logger.debug("Empty content from Anthropic; no claims extracted")
            return []

        # Anthropic SDK returns a list of content blocks; the first
        # text block carries the JSON.
        first_block = message.content[0]
        response_text = getattr(first_block, "text", "") or ""

        return self._parse_claims(response_text, max_claims)

    # ------------------------------------------------------------------
    # JSON parsing — tolerant to ```json``` fences and prose preambles
    # ------------------------------------------------------------------

    def _parse_claims(self, response_text: str, max_claims: int) -> List[AtomicClaim]:
        from .claim_classifier import ClaimClassifier  # local import — heavy

        json_str = response_text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in json_str:
            parts = json_str.split("```")
            for i in range(1, len(parts), 2):
                candidate = parts[i].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("["):
                    json_str = candidate
                    break

        # Strip a leading prose preamble like "Here are the claims: [...]"
        if not json_str.startswith("["):
            idx = json_str.find("[")
            if idx >= 0:
                json_str = json_str[idx:]

        try:
            claims_data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            _logger.debug(
                "AnthropicClaimExtractor JSON parse failed: %s. Excerpt: %s",
                exc, response_text[:200],
            )
            return []

        if not isinstance(claims_data, list):
            _logger.debug(
                "AnthropicClaimExtractor: expected list, got %s",
                type(claims_data).__name__,
            )
            return []

        out: List[AtomicClaim] = []
        for claim_dict in claims_data[:max_claims]:
            if not isinstance(claim_dict, dict):
                continue
            claim_text = claim_dict.get("claim_text") or claim_dict.get("text")
            if not claim_text:
                continue

            llm_category = claim_dict.get("claim_category") or "statistical"
            try:
                category = ClaimCategory(llm_category)
            except ValueError:
                category = ClaimClassifier.classify(claim_text)

            try:
                importance = float(claim_dict.get("importance_score", 0.9))
            except (TypeError, ValueError):
                importance = 0.9
            importance = max(0.0, min(1.0, importance))

            out.append(AtomicClaim(
                claim_text=claim_text,
                claim_type=str(claim_dict.get("claim_type") or "factual"),
                claim_category=category,
                importance_score=importance,
                claim_context=claim_dict.get("claim_context"),
                extraction_model=f"anthropic:{self.model}",
                extraction_confidence=0.9,
            ))
        return out
