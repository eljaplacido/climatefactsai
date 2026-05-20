"""Multi-LLM cross-verification — Phase 5 wave 1.

Runs the same extraction task with two LLMs in parallel and reports
agreement. A claim that two independently-prompted models both surface
is markedly more trustworthy than one that only one model produces;
this gives us a *measured* calibration signal instead of a self-reported
LLM confidence.

The module is deliberately a pure infrastructure layer: it takes the
two extractors as callables, so callers (url_analysis_routes,
deep_search_service, claim ingestion) wire their existing LLM clients in
without each path re-implementing the comparison logic.

# Why this moves the Calibration axis

Single-LLM confidence is self-reported — the model tells us its
importance score, and we have no independent check. The audit flagged
this as a calibration lie: "0.7 importance" from one model doesn't mean
the same thing as 0.7 from another, and a hallucinated claim can carry
0.9 importance because the model is confidently wrong.

Two independent models running the same extraction give a much harder
signal:

  * Both agree on a claim → external corroboration → confidence stays high.
  * Only primary surfaces → no external corroboration → confidence
    downgraded by `confidence_penalty_uncorroborated` (default 0.7).
  * Both disagree on framing but cover the same fact → still corroborated
    if Jaccard similarity ≥ threshold (default 0.5).

The aggregate `agreement_score` (corroborated / primary_total) is
useful as a per-document calibration signal: low agreement scores warn
the user that the extraction is contested, even before any individual
claim is fact-checked downstream.

# Failure modes

  * **Secondary unavailable** (None passed in): the primary's claims are
    returned with `corroborated=False` but `confidence=importance` —
    no penalty applied because absence of evidence isn't evidence of
    disagreement. `secondary_error="no_secondary_configured"` signals
    this in the result.
  * **Secondary times out**: same as unavailable; `secondary_error`
    captures the timeout duration.
  * **Secondary errors**: same as unavailable; `secondary_error`
    captures the exception type.
  * **Primary errors**: the exception propagates. We need primary claims
    to have anything to return.

# Why Jaccard similarity (not embeddings)

Jaccard on normalised token sets is:

  * Local — no model dependency, no API call, no embeddings cache.
  * Fast — O(n + m) per pair, where n + m are token counts (~20 tokens
    per claim).
  * Interpretable — "these two claims share 14/20 unique words" is a
    statement an auditor can verify by hand. Embedding similarity is a
    black box.

For climate-news claims (which are factual prose with shared technical
vocabulary — "renewable capacity", "emissions per capita", "1.5°C
budget"), token overlap is a strong signal. Future wave can replace with
embedding similarity behind the same interface for nuance, but the
calibration math doesn't require it.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, Tuple

_logger = logging.getLogger("multi_llm_verifier")


# ---------------------------------------------------------------------------
# Input / output shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractedClaim:
    """Minimal shape a primary or secondary extractor must yield.

    Adapters can wrap their own claim objects in this dataclass before
    handing them to verify_claims, or pass dicts that contain at least
    `text` and `importance` — see `_attr_or_item`.
    """
    text: str
    importance: float = 0.0
    raw: Optional[Any] = None


@dataclass
class CorroboratedClaim:
    """Primary claim annotated with secondary-corroboration data."""
    text: str
    importance: float            # original self-reported importance
    confidence: float            # adjusted: importance if corroborated, else × penalty
    corroborated: bool           # secondary produced a claim with similarity ≥ threshold
    similarity_to_best_match: Optional[float]  # 0–1, or None if no secondary
    matched_secondary_text: Optional[str]      # the secondary claim if corroborated
    raw: Optional[Any] = None    # passthrough of the original raw claim object
    numbers_in_claim: Tuple[float, ...] = ()   # numeric values extracted from claim text
    numeric_grounded: Optional[bool] = None    # None = no check ran or claim has no numbers


@dataclass
class CrossVerificationResult:
    """Full output of one verify_claims call."""
    primary_model: str
    secondary_model: Optional[str]
    primary_prompt_name: Optional[str] = None
    secondary_prompt_name: Optional[str] = None
    primary_claims: List[CorroboratedClaim] = field(default_factory=list)
    secondary_total_claims: Optional[int] = None
    agreement_score: Optional[float] = None
    similarity_threshold: float = 0.5
    secondary_error: Optional[str] = None
    greenwashing_flags: Optional[List[dict]] = None

    @property
    def primary_count(self) -> int:
        return len(self.primary_claims)

    @property
    def corroborated_count(self) -> int:
        return sum(1 for c in self.primary_claims if c.corroborated)

    def as_dict(self) -> dict:
        return {
            "primary_model": self.primary_model,
            "secondary_model": self.secondary_model,
            "primary_prompt_name": self.primary_prompt_name,
            "secondary_prompt_name": self.secondary_prompt_name,
            "primary_count": self.primary_count,
            "corroborated_count": self.corroborated_count,
            "agreement_score": (
                round(self.agreement_score, 3)
                if self.agreement_score is not None else None
            ),
            "secondary_total_claims": self.secondary_total_claims,
            "secondary_error": self.secondary_error,
            "similarity_threshold": self.similarity_threshold,
            "greenwashing_flags": self.greenwashing_flags,
            "claims": [
                {
                    "text": c.text,
                    "importance": round(c.importance, 3),
                    "confidence": round(c.confidence, 3),
                    "corroborated": c.corroborated,
                    "similarity_to_best_match": (
                        round(c.similarity_to_best_match, 3)
                        if c.similarity_to_best_match is not None else None
                    ),
                    "matched_secondary_text": c.matched_secondary_text,
                    "numbers_in_claim": list(c.numbers_in_claim),
                    "numeric_grounded": c.numeric_grounded,
                }
                for c in self.primary_claims
            ],
        }


# ---------------------------------------------------------------------------
# Similarity primitives
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def _normalise_text(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Numbers are preserved (so "35%" → "35" still matches "35%").
    """
    if not s:
        return ""
    out = s.lower().strip()
    out = _WORD_RE.sub(" ", out)
    out = _WS_RE.sub(" ", out).strip()
    return out


def _token_set(s: str) -> set:
    """Token set of normalised text. Empty string → empty set."""
    n = _normalise_text(s)
    if not n:
        return set()
    return set(n.split(" "))


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity over token sets. 0 = disjoint, 1 = identical sets.

    Two empty strings yield 1.0 (vacuously identical); one empty + one
    non-empty yield 0.0.
    """
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


# ---------------------------------------------------------------------------
# Coercion: accept dicts and dataclasses transparently
# ---------------------------------------------------------------------------

def _attr_or_item(obj: Any, key: str, default: Any = None) -> Any:
    """Attribute access with dict-subscript fallback."""
    if obj is None:
        return default
    try:
        return getattr(obj, key)
    except AttributeError:
        pass
    try:
        return obj[key]
    except (TypeError, KeyError):
        return default


def _to_extracted_claim(obj: Any) -> ExtractedClaim:
    """Normalise any claim-shaped input to ExtractedClaim."""
    if isinstance(obj, ExtractedClaim):
        return obj
    text = _attr_or_item(obj, "text") or _attr_or_item(obj, "claim_text") or ""
    importance = _attr_or_item(obj, "importance")
    if importance is None:
        importance = _attr_or_item(obj, "importance_score", 0.0)
    try:
        importance = float(importance) if importance is not None else 0.0
    except (TypeError, ValueError):
        importance = 0.0
    return ExtractedClaim(text=str(text), importance=importance, raw=obj)


# ---------------------------------------------------------------------------
# Core: verify_claims
# ---------------------------------------------------------------------------

ExtractorFn = Callable[[str, int], Awaitable[List[Any]]]

# A numeric grounding check: given a claim text + the numbers extracted from it,
# return True if the numbers are corroborated by trusted indicator data, False
# if not, or None if no check could be performed (e.g. no relevant indicators
# exist for the country). Used to catch the "both LLMs agree on a hallucinated
# number" failure mode — corroboration on shared bias collapses to truth if
# the numbers don't match country_indicators.
NumericGroundingFn = Callable[[str, List[float]], Optional[bool]]

# Match floats like "30%", "1.5 °C", "20 tCO2e", "2030", "1,500", etc.
# Captures the leading numeric — caller decides what it means.
_NUMBER_RE = re.compile(r"(?<![A-Za-z])(-?\d{1,3}(?:[,\.]\d{3})*(?:[\.,]\d+)?|\-?\d+(?:[\.,]\d+)?)")


def _extract_numbers_from_text(text: str) -> Tuple[float, ...]:
    """Return the numeric values mentioned in a claim. Empty tuple if none."""
    if not text:
        return ()
    out: List[float] = []
    for m in _NUMBER_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return tuple(out)


async def verify_claims(
    *,
    text: str,
    max_claims: int,
    primary_extractor: ExtractorFn,
    primary_model: str,
    primary_prompt_name: Optional[str] = None,
    secondary_extractor: Optional[ExtractorFn] = None,
    secondary_model: Optional[str] = None,
    secondary_prompt_name: Optional[str] = None,
    similarity_threshold: float = 0.5,
    secondary_timeout: float = 30.0,
    confidence_penalty_uncorroborated: float = 0.7,
    numeric_grounding_check: Optional[NumericGroundingFn] = None,
    numeric_ungrounded_penalty: float = 0.5,
) -> CrossVerificationResult:
    """Run claim extraction with up to two LLMs and report agreement.

    Primary is the canonical extractor; its claims form the output list.
    Each primary claim is matched against the secondary's claims by
    Jaccard similarity; the best-matching secondary claim with similarity
    ≥ `similarity_threshold` counts as corroboration.

    Confidence for uncorroborated claims is downgraded by
    `confidence_penalty_uncorroborated` (default 0.7). Corroborated claims
    keep their original importance as confidence.

    If `secondary_extractor` is None, runs single-LLM with no penalty
    (we don't know whether a missing model would have agreed).
    """
    # ---- Run primary; propagate errors (we need its claims). ----
    primary_raw: List[Any] = await primary_extractor(text, max_claims)
    primary_claims_norm: List[ExtractedClaim] = [
        _to_extracted_claim(c) for c in (primary_raw or [])
    ]

    # ---- No secondary: short-circuit ----
    if secondary_extractor is None:
        out_claims = [
            CorroboratedClaim(
                text=c.text,
                importance=c.importance,
                confidence=c.importance,   # no penalty without a comparator
                corroborated=False,
                similarity_to_best_match=None,
                matched_secondary_text=None,
                raw=c.raw,
            )
            for c in primary_claims_norm
        ]
        return CrossVerificationResult(
            primary_model=primary_model,
            secondary_model=None,
            primary_prompt_name=primary_prompt_name,
            secondary_prompt_name=None,
            primary_claims=out_claims,
            secondary_total_claims=None,
            agreement_score=None,
            similarity_threshold=similarity_threshold,
            secondary_error="no_secondary_configured",
        )

    # ---- Run secondary with timeout + error tolerance ----
    secondary_norm: List[ExtractedClaim] = []
    secondary_error: Optional[str] = None
    try:
        secondary_raw = await asyncio.wait_for(
            secondary_extractor(text, max_claims),
            timeout=secondary_timeout,
        )
        secondary_norm = [_to_extracted_claim(c) for c in (secondary_raw or [])]
    except asyncio.TimeoutError:
        secondary_error = f"secondary_timeout_{int(secondary_timeout)}s"
        _logger.warning(
            "Secondary extractor (%s) timed out after %ss; "
            "skipping corroboration",
            secondary_model, secondary_timeout,
        )
    except Exception as exc:
        secondary_error = f"secondary_error:{type(exc).__name__}"
        _logger.warning(
            "Secondary extractor (%s) raised %s; skipping corroboration",
            secondary_model, type(exc).__name__,
        )

    # If secondary failed, fall back to single-LLM semantics — no penalty.
    if secondary_error is not None:
        out_claims = [
            CorroboratedClaim(
                text=c.text,
                importance=c.importance,
                confidence=c.importance,
                corroborated=False,
                similarity_to_best_match=None,
                matched_secondary_text=None,
                raw=c.raw,
            )
            for c in primary_claims_norm
        ]
        return CrossVerificationResult(
            primary_model=primary_model,
            secondary_model=secondary_model,
            primary_prompt_name=primary_prompt_name,
            secondary_prompt_name=secondary_prompt_name,
            primary_claims=out_claims,
            secondary_total_claims=None,
            agreement_score=None,
            similarity_threshold=similarity_threshold,
            secondary_error=secondary_error,
        )

    # ---- Match each primary claim against secondary ----
    out_claims: List[CorroboratedClaim] = []
    corroborated_count = 0

    for p in primary_claims_norm:
        best_sim = 0.0
        best_match: Optional[ExtractedClaim] = None
        for s in secondary_norm:
            sim = _jaccard_similarity(p.text, s.text)
            if sim > best_sim:
                best_sim = sim
                best_match = s

        is_corroborated = best_sim >= similarity_threshold and best_match is not None
        if is_corroborated:
            corroborated_count += 1
            confidence = p.importance
        else:
            confidence = p.importance * confidence_penalty_uncorroborated

        # Numeric grounding: even when both LLMs corroborate a claim, if it
        # contains numbers that don't match `country_indicators`, the
        # corroboration is shared bias (or shared hallucination) — halve
        # confidence further. No penalty when numeric_grounding_check is
        # absent or the claim has no numeric content.
        numbers = _extract_numbers_from_text(p.text)
        grounded: Optional[bool] = None
        if numeric_grounding_check is not None and numbers:
            try:
                grounded = numeric_grounding_check(p.text, list(numbers))
            except Exception as exc:
                _logger.debug(f"numeric_grounding_check raised: {exc}")
                grounded = None
            if grounded is False:
                confidence = confidence * numeric_ungrounded_penalty

        out_claims.append(CorroboratedClaim(
            text=p.text,
            importance=p.importance,
            confidence=round(confidence, 3),
            corroborated=is_corroborated,
            similarity_to_best_match=(round(best_sim, 3) if best_sim > 0 else None),
            matched_secondary_text=(
                best_match.text if (is_corroborated and best_match is not None) else None
            ),
            raw=p.raw,
            numbers_in_claim=numbers,
            numeric_grounded=grounded,
        ))

    agreement_score = (
        corroborated_count / len(primary_claims_norm)
        if primary_claims_norm else None
    )

    return CrossVerificationResult(
        primary_model=primary_model,
        secondary_model=secondary_model,
        primary_prompt_name=primary_prompt_name,
        secondary_prompt_name=secondary_prompt_name,
        primary_claims=out_claims,
        secondary_total_claims=len(secondary_norm),
        agreement_score=agreement_score,
        similarity_threshold=similarity_threshold,
        secondary_error=None,
    )
