"""
Hallucination Detection Service.

Checks AI-generated text against source documents for:
- Entity overlap (do entities in generated text appear in sources?)
- Statistic verification (do numbers match?)
- Semantic alignment (are generated claims supported by sources?)
- Unsupported claim detection (flag sentences with no backing evidence)
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.database import Database

logger = get_logger(__name__)


class HallucinationDetector:
    """Check generated text for hallucinations against source documents."""

    def __init__(self, db: Database):
        self.db = db

    async def check(
        self,
        generated_text: str,
        source_texts: List[str],
        source_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Check generated text for hallucinations against source documents.

        Args:
            generated_text: The AI-generated text to verify.
            source_texts: List of source document texts for grounding.
            source_metadata: Optional metadata for each source.

        Returns:
            Dict with hallucination risk, flagged segments, and scores.
        """
        if not generated_text or not source_texts:
            return self._empty_result()

        # Run all checks
        entity_result = self._check_entity_overlap(generated_text, source_texts)
        statistic_result = self._check_statistics(generated_text, source_texts)
        llm_result = await self._llm_grounding_check(generated_text, source_texts)

        # Combine flagged segments
        all_flags = (
            entity_result.get("flagged", [])
            + statistic_result.get("flagged", [])
            + llm_result.get("flagged_segments", [])
        )

        # Calculate composite risk score
        entity_score = entity_result.get("overlap_score", 0.5)
        stat_score = statistic_result.get("accuracy_score", 0.5)
        llm_risk = llm_result.get("hallucination_risk", 0.5)

        # Lower entity/stat scores = higher risk
        hallucination_risk = round(
            0.3 * (1.0 - entity_score)
            + 0.3 * (1.0 - stat_score)
            + 0.4 * llm_risk,
            3,
        )

        overall_confidence = round(1.0 - hallucination_risk, 3)
        is_grounded = hallucination_risk < 0.4

        result = {
            "hallucination_risk": hallucination_risk,
            "is_grounded": is_grounded,
            "flagged_segments": all_flags,
            "entity_overlap_score": entity_score,
            "statistic_accuracy": stat_score,
            "overall_confidence": overall_confidence,
            "checks_performed": ["entity_overlap", "statistic_verification", "llm_grounding"],
        }

        logger.info(
            "Hallucination check complete",
            risk=hallucination_risk,
            grounded=is_grounded,
            flags=len(all_flags),
        )
        return result

    # ------------------------------------------------------------------
    # Entity overlap check
    # ------------------------------------------------------------------

    def _check_entity_overlap(
        self,
        generated: str,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Check that entities in generated text appear in source texts."""
        gen_entities = self._extract_simple_entities(generated)
        source_entities = set()
        for src in sources:
            source_entities.update(self._extract_simple_entities(src))

        if not gen_entities:
            return {"overlap_score": 1.0, "flagged": []}

        matched = gen_entities & source_entities
        unmatched = gen_entities - source_entities

        overlap = len(matched) / len(gen_entities) if gen_entities else 1.0

        flagged = []
        for entity in unmatched:
            flagged.append(
                {
                    "text": entity,
                    "reason": f"Entity '{entity}' not found in any source document",
                    "severity": "medium",
                }
            )

        return {"overlap_score": round(overlap, 3), "flagged": flagged}

    # spaCy NER pipeline — loaded once, cached at class level. None if spaCy
    # or the model isn't installed; the regex fallback below handles that case.
    # Audit (2026-05-18) flagged the regex heuristic as the entity check's
    # weakest link (over-flags paraphrases, under-flags hallucinated proper
    # nouns that look uncapitalised). When spaCy is available we extract
    # PERSON/ORG/GPE/LOC/PRODUCT/EVENT entities at semantic level.
    _spacy_nlp = None
    _spacy_load_attempted = False

    @classmethod
    def _get_spacy(cls):
        if cls._spacy_load_attempted:
            return cls._spacy_nlp
        cls._spacy_load_attempted = True
        try:
            import spacy
            try:
                cls._spacy_nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger", "lemmatizer"])
            except OSError:
                # Model not downloaded — bail to the regex fallback. Operator
                # can `python -m spacy download en_core_web_sm` to enable.
                cls._spacy_nlp = None
        except ImportError:
            cls._spacy_nlp = None
        return cls._spacy_nlp

    @classmethod
    def _extract_simple_entities(cls, text: str) -> set:
        """Extract candidate entities.

        Primary path: spaCy NER (PERSON/ORG/GPE/LOC/PRODUCT/EVENT/NORP/FAC).
        Fallback: capitalised-n-gram regex when spaCy or the model is absent.
        """
        nlp = cls._get_spacy()
        if nlp is not None:
            try:
                doc = nlp(text[:100_000])  # spaCy default max is 1e6 chars; cap defensively
                wanted = {"PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "NORP", "FAC"}
                return {ent.text for ent in doc.ents if ent.label_ in wanted and ent.text.strip()}
            except Exception:
                # Any spaCy runtime issue → fall through to regex
                pass

        # Regex fallback: capitalised multi-word sequences + ALL-CAPS acronyms.
        entities = set()
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            entities.add(match.group(1))
        for match in re.finditer(r"\b([A-Z]{2,})\b", text):
            entities.add(match.group(1))
        return entities

    # ------------------------------------------------------------------
    # Statistic verification
    # ------------------------------------------------------------------

    def _check_statistics(
        self,
        generated: str,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Verify that numbers and statistics in generated text appear in sources."""
        gen_numbers = self._extract_numbers(generated)
        if not gen_numbers:
            return {"accuracy_score": 1.0, "flagged": []}

        source_text_combined = " ".join(sources)
        source_numbers = self._extract_numbers(source_text_combined)

        matched = 0
        flagged = []

        for num_str, context in gen_numbers:
            if self._number_found_in_sources(num_str, source_numbers, source_text_combined):
                matched += 1
            else:
                flagged.append(
                    {
                        "text": context,
                        "reason": f"Statistic '{num_str}' not found in source documents",
                        "severity": "high",
                    }
                )

        accuracy = matched / len(gen_numbers) if gen_numbers else 1.0

        return {"accuracy_score": round(accuracy, 3), "flagged": flagged}

    @staticmethod
    def _extract_numbers(text: str) -> List[tuple]:
        """Extract numbers with surrounding context from text."""
        results = []
        # Match percentages, temperatures, large numbers, decimals
        for match in re.finditer(
            r"(\d+(?:\.\d+)?)\s*(%|degrees?|°[CF]|billion|million|trillion|GtCO2|ppm|Mt|GW|TWh)",
            text,
        ):
            num_str = match.group(0)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((num_str, context))

        # Also match standalone significant numbers
        for match in re.finditer(r"\b(\d{2,}(?:\.\d+)?)\b", text):
            num_str = match.group(1)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            results.append((num_str, context))

        return results

    @staticmethod
    def _number_found_in_sources(
        num_str: str,
        source_numbers: List[tuple],
        source_text: str,
    ) -> bool:
        """Check if a number from generated text exists in source text."""
        # Direct string match
        if num_str in source_text:
            return True

        # Numeric value match (within 5% tolerance for rounding)
        try:
            # Extract the numeric part
            num_val = float(re.search(r"[\d.]+", num_str).group())
            for src_num_str, _ in source_numbers:
                src_val = float(re.search(r"[\d.]+", src_num_str).group())
                if src_val != 0 and abs(num_val - src_val) / abs(src_val) < 0.05:
                    return True
        except (ValueError, AttributeError):
            pass

        return False

    # ------------------------------------------------------------------
    # LLM grounding check
    # ------------------------------------------------------------------

    async def _llm_grounding_check(
        self,
        generated: str,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Use LLM to assess if generated text is grounded in sources.

        Phase 4 wave 1 (2026-05-16): prompt resolved via the central
        registry so its version + fingerprint show up in audit trails.
        """
        try:
            from app.domains.intelligence.llm_client import llm_chat
            from app.domains.intelligence.prompts import get_prompt

            tmpl = get_prompt("hallucination_grounding")
            truncated_gen = generated[:3000]
            source_excerpts = "\n---\n".join(s[:1500] for s in sources[:5])

            prompt = tmpl.format(
                generated_text=truncated_gen,
                source_excerpts=source_excerpts,
            )

            response = llm_chat(
                prompt=prompt,
                system_prompt=tmpl.system,
                max_tokens=tmpl.max_tokens or 800,
                temperature=tmpl.temperature if tmpl.temperature is not None else 0.0,
            )

            if not response:
                return {
                    "hallucination_risk": 0.5,
                    "flagged_segments": [],
                    "prompt": tmpl.as_audit_dict(),
                }

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            parsed = json.loads(cleaned)
            parsed["prompt"] = tmpl.as_audit_dict()
            return parsed

        except json.JSONDecodeError:
            return {"hallucination_risk": 0.5, "flagged_segments": []}
        except Exception as e:
            logger.debug(f"LLM grounding check failed: {e}")
            return {"hallucination_risk": 0.5, "flagged_segments": []}

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return an empty/default result when inputs are insufficient."""
        return {
            "hallucination_risk": 0.0,
            "is_grounded": True,
            "flagged_segments": [],
            "entity_overlap_score": 1.0,
            "statistic_accuracy": 1.0,
            "overall_confidence": 1.0,
            "checks_performed": [],
        }
