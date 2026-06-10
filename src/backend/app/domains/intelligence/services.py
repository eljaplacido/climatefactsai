"""
Intelligence Domain Services

Multi-stage verification pipeline:
1. ClaimExtractor - Decompose articles into atomic claims
2. EvidenceRetriever - Fetch supporting/contradicting evidence
3. VerdictAdjudicator - Compare claims against evidence and assign verdicts
4. VerificationService - Orchestrate the full pipeline
"""

import json
import os
import re
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

import httpx
from fastapi import HTTPException
try:
    import anthropic
except ImportError:
    anthropic = None

from app.core.logging import get_logger
from app.core.database import Database
from .schemas import (
    AtomicClaim, Evidence, Verdict, VerificationResult,
    ClaimCategory, DecomposedConfidence, EvidenceChainLink,
)
from .claim_classifier import ClaimClassifier
from .evidence_retriever import EvidenceOrchestrator
from .weather_claim_validator import WeatherClaimValidator
from .llm_client import get_llm_client, llm_chat

# Import claims status manager
from shared.claims_status_manager import ClaimsStatusManager

logger = get_logger(__name__)


# Backwards-compatible helpers that delegate to llm_client
def _get_deepseek_client():
    return get_llm_client()


def _deepseek_chat(client, model: str, prompt: str, max_tokens: int = 2000, temperature: float = 0.1) -> str:
    result = llm_chat(prompt, max_tokens=max_tokens, temperature=temperature, client=client, model=model)
    return result or ""


class ClaimParseError(ValueError):
    """Raised when an LLM claim-extraction reply can't be coerced to a JSON array."""


def _loads_claim_array(response_text: str) -> list:
    """Best-effort parse of an LLM reply into a list of claim dicts.

    The live audit (2026-06-09) measured ~34% of DeepSeek claim replies failing
    a bare ``json.loads`` — not because the content was bad, but because the
    model wrapped the array in markdown fences, a prose preamble ("Here are the
    claims:"), or a ``{"claims": [...]}`` envelope, or left a trailing comma.
    Each of those failures dropped the *entire* article to 0 claims. This helper
    tolerates all of those shapes; the caller retries with a stricter prompt
    only when even this can't recover an array.

    Raises:
        ClaimParseError: if no JSON array can be salvaged.
    """
    if not response_text or not response_text.strip():
        raise ClaimParseError("empty LLM response")

    s = response_text.strip()

    # 1. Unwrap the first fenced code block (```json ... ``` or bare ```).
    if "```" in s:
        parts = s.split("```")
        for i in range(1, len(parts), 2):  # odd indices = fenced content
            candidate = parts[i].strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("[") or candidate.startswith("{"):
                s = candidate
                break

    # 2. Build parse candidates in order of fidelity:
    #    (a) the string as-is — handles a clean array OR a clean {"claims":[...]}
    #        object envelope without mangling either;
    #    (b) the first '[' to last ']' slice — strips leading/trailing prose
    #        around a bare array.
    candidates = [s]
    start, end = s.find("["), s.rfind("]")
    if start != -1 and end > start and s[start:end + 1] != s:
        candidates.append(s[start:end + 1])

    data = None
    last_err: Optional[Exception] = None
    for cand in candidates:
        for attempt in (cand, re.sub(r",\s*([\]}])", r"\1", cand)):  # +trailing-comma repair
            try:
                data = json.loads(attempt)
                break
            except json.JSONDecodeError as exc:
                last_err = exc
        if data is not None:
            break
    if data is None:
        raise ClaimParseError(f"unparseable JSON: {last_err}")

    # 3. Some models wrap the array in an object — unwrap common keys.
    if isinstance(data, dict):
        for key in ("claims", "atomic_claims", "results", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        raise ClaimParseError("JSON object had no claims array")
    if not isinstance(data, list):
        raise ClaimParseError(f"expected a JSON array, got {type(data).__name__}")
    return data


class ClaimExtractor:
    """
    Extracts atomic, verifiable claims from article text using Claude.

    Uses structured output to ensure consistent claim format.
    """
    
    def __init__(self, model: str = "deepseek-chat"):
        self.deepseek_client, self.deepseek_model = _get_deepseek_client()
        self.model = self.deepseek_model or model
        # DeepSeek is the only LLM provider
        self.client = None  # Anthropic client disabled
        self.api_key = None  # Anthropic key not used
        self.use_deepseek = self.deepseek_client is not None
        if not self.deepseek_client:
            logger.error("DEEPSEEK_API_KEY not set - claim extraction unavailable")
        elif self.use_deepseek:
            logger.info("Using DeepSeek as primary LLM provider for claim extraction")
    
    async def decompose_claims(
        self,
        text: str,
        max_claims: int = 20,
        content_type: str = "news_article",
    ) -> list[AtomicClaim]:
        """
        Extract atomic claims from article text.

        Args:
            text: Article content
            max_claims: Maximum claims to extract
            content_type: Content type hint for prompt adjustment.
                          Use "research_report" or "preprint" for academic content.

        Returns:
            List of AtomicClaim objects

        Raises:
            HTTPException: If API key is missing or API call fails
        """
        # Check API key availability
        if not self.deepseek_client:
            logger.error("Claim extraction unavailable: DEEPSEEK_API_KEY not configured")
            raise HTTPException(
                status_code=503,
                detail="Claim extraction unavailable: DEEPSEEK_API_KEY not configured. Please set the API key in .env"
            )

        # Validate text length
        if len(text) < 100:
            logger.warning(f"Text too short for claim extraction: {len(text)} chars")
            return []

        # Use DeepSeek for all claim extraction
        try:
            claims = await self._extract_with_deepseek(text, max_claims)
            if claims:
                logger.info(f"Successfully extracted {len(claims)} claims using DeepSeek")
                return claims
            else:
                logger.warning("DeepSeek returned no claims")
                return []
        except Exception as e:
            logger.error(f"DeepSeek extraction failed: {type(e).__name__}: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Claim extraction failed: {type(e).__name__}. Please try again."
            )

    async def _extract_with_claude(
        self, text: str, max_claims: int, content_type: str = "news_article"
    ) -> list[AtomicClaim]:
        """Extract claims using Claude API."""

        # Build research-specific prompt preamble when content is academic
        research_preamble = ""
        if content_type in ("research_report", "preprint"):
            research_preamble = (
                "Focus on extracting: statistical claims with specific numbers, "
                "causal claims linking variables, uncertainty statements with confidence intervals, "
                "and methodology claims. Flag any claims that lack citation support.\n\n"
            )

        # Craft prompt for atomic claim extraction
        prompt = f"""{research_preamble}Analyze the following climate news article and extract atomic, verifiable claims.

ARTICLE TEXT:
{text[:4000]}

INSTRUCTIONS:
Extract factual claims that are:
1. Self-contained (understandable without context)
2. Singular (one assertion per claim)
3. Specific (includes numbers, dates, entities)
4. Verifiable (can be fact-checked)

For each claim, provide:
- claim_text: The exact claim
- claim_type: "factual", "opinion", or "prediction"
- claim_category: one of "scientific_causal", "statistical", "policy", "anecdotal", "predictive"
  - scientific_causal: cause-effect relationships (CO2 causes warming)
  - statistical: numeric data, percentages, measurements
  - policy: regulations, treaties, commitments
  - anecdotal: personal observations, eyewitness accounts
  - predictive: future projections, forecasts
- importance_score: 0.0-1.0 (how central to the article)
- claim_context: Surrounding sentence for context

IMPORTANT: Return ONLY a valid JSON array, no other text. Extract up to {max_claims} most important claims.

Example output format (return exactly this structure, no markdown, no explanations):
[
  {{
    "claim_text": "Arctic sea ice extent decreased by 13% per decade since 1979",
    "claim_type": "factual",
    "claim_category": "statistical",
    "importance_score": 0.9,
    "claim_context": "Scientists report that Arctic sea ice extent decreased by 13% per decade since 1979, based on satellite data."
  }}
]
"""
        
        # Call Claude with structured output
        logger.info(f"Calling Anthropic API with model: {self.model}")
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,  # Low temperature for factual extraction
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
        except anthropic.APIError as e:
            logger.error(f"Anthropic API call failed: {e.status_code} - {e.message}")
            # Try fallback models if primary fails
            fallback_models = [
                "claude-3-5-sonnet-20240620",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ]
            for fallback_model in fallback_models:
                if fallback_model == self.model:
                    continue
                try:
                    logger.info(f"Trying fallback model: {fallback_model}")
                    message = self.client.messages.create(
                        model=fallback_model,
                        max_tokens=2000,
                        temperature=0.1,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                    logger.info(f"Successfully used fallback model: {fallback_model}")
                    break
                except Exception as fallback_error:
                    logger.warning(f"Fallback model {fallback_model} also failed: {fallback_error}")
                    continue
            else:
                raise  # Re-raise if all models failed
        
        # Parse response
        if not message.content or len(message.content) == 0:
            logger.error("Empty response from Claude API")
            raise ValueError("Empty response from Claude API")
        
        response_text = message.content[0].text
        logger.debug(f"Raw Claude response (first 500 chars): {response_text[:500]}")
        
        # Extract JSON from response (handle markdown code blocks)
        json_str = None
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            # Try to find JSON in any code block
            parts = response_text.split("```")
            for i in range(1, len(parts), 2):  # Every odd index is code block content
                candidate = parts[i].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()  # Remove "json" prefix
                if candidate.startswith("[") or candidate.startswith("{"):
                    json_str = candidate
                    break
        else:
            json_str = response_text.strip()
        
        if not json_str:
            logger.error(f"Could not extract JSON from response. Full response: {response_text}")
            raise ValueError("Could not extract JSON from Claude response")
        
        # Try to parse JSON
        try:
            claims_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}. JSON string (first 1000 chars): {json_str[:1000]}")
            # Try to fix common issues
            # Remove any leading/trailing non-JSON text
            json_str_clean = json_str
            if json_str_clean.startswith("Here's") or json_str_clean.startswith("Here is"):
                # Find first [ or {
                for char in ['[', '{']:
                    idx = json_str_clean.find(char)
                    if idx != -1:
                        json_str_clean = json_str_clean[idx:]
                        break
            
            try:
                claims_data = json.loads(json_str_clean)
            except json.JSONDecodeError as e2:
                logger.error(f"Second JSON decode attempt also failed: {e2}")
                raise ValueError(f"Could not parse JSON from Claude response: {e2}")
        
        if not isinstance(claims_data, list):
            logger.error(f"Expected list but got {type(claims_data)}: {claims_data}")
            raise ValueError("Claude response is not a list of claims")
        
        # Build AtomicClaim objects
        claims = []
        for claim_dict in claims_data[:max_claims]:
            # Determine claim category: use LLM suggestion then validate/override with classifier
            llm_category = claim_dict.get("claim_category", "statistical")
            try:
                category = ClaimCategory(llm_category)
            except ValueError:
                category = ClaimClassifier.classify(claim_dict["claim_text"])

            claims.append(AtomicClaim(
                claim_text=claim_dict["claim_text"],
                claim_type=claim_dict.get("claim_type", "factual"),
                claim_category=category,
                importance_score=claim_dict.get("importance_score", 1.0),
                claim_context=claim_dict.get("claim_context"),
                extraction_model=self.model,
                extraction_confidence=0.9  # High confidence from Claude
            ))
        
        logger.info(f"Extracted {len(claims)} claims from article text ({len(text)} chars)")
        return claims

    async def _extract_with_deepseek(self, text: str, max_claims: int) -> list[AtomicClaim]:
        """Extract claims using DeepSeek API (OpenAI-compatible).

        Uses the centrally-registered `claim_extraction` prompt template
        (prompts.PROMPTS["claim_extraction"]) so the multi-LLM verifier
        measures cross-model agreement rather than prompt drift. Previous
        revision hardcoded the prompt inline, which meant any update to the
        registered template silently bypassed this primary extractor — the
        DeepSeek path kept producing 1-2 claims while the Anthropic
        secondary saw the v1.1 yield-target prompt and corroborated none of
        them.
        """
        from .prompts import get_prompt

        tmpl = get_prompt("claim_extraction")
        prompt = tmpl.format(text=text[:4000], max_claims=max_claims)
        max_tokens = tmpl.max_tokens or 2500
        base_temp = tmpl.temperature if tmpl.temperature is not None else 0.1
        logger.info(f"Calling DeepSeek API with model: {self.deepseek_model}")

        # Strict-JSON + one retry. ~34% of first replies wrapped the array in
        # prose/markdown and broke the old bare json.loads, dropping the whole
        # article to 0 claims (2026-06-09 audit P0 #3). Recover the array
        # tolerantly; if even that fails, retry once at temperature 0 with a
        # hard JSON-only reminder before giving up.
        claims_data: Optional[list] = None
        last_err: Optional[Exception] = None
        for attempt in range(2):
            call_prompt = prompt if attempt == 0 else (
                prompt
                + "\n\nREMINDER: Your previous reply could not be parsed. Output "
                "MUST be a raw JSON array — start with '[', end with ']'. No "
                "prose, no markdown code fences, no explanation. Only the array."
            )
            response_text = _deepseek_chat(
                self.deepseek_client,
                self.deepseek_model,
                call_prompt,
                max_tokens=max_tokens,
                temperature=0.0 if attempt else base_temp,
            )
            try:
                claims_data = _loads_claim_array(response_text)
                break
            except ClaimParseError as exc:
                last_err = exc
                logger.warning(
                    f"DeepSeek claim JSON parse failed "
                    f"(attempt {attempt + 1}/2): {exc}"
                )

        if claims_data is None:
            raise ValueError(
                f"DeepSeek claim extraction unparseable after retry: {last_err}"
            )

        claims = []
        for claim_dict in claims_data[:max_claims]:
            # Skip malformed elements (non-dict, or missing the one required
            # field) so a single bad entry can't sink the whole extraction.
            if not isinstance(claim_dict, dict) or not claim_dict.get("claim_text"):
                continue
            llm_category = claim_dict.get("claim_category", "statistical")
            try:
                category = ClaimCategory(llm_category)
            except ValueError:
                category = ClaimClassifier.classify(claim_dict["claim_text"])
            claims.append(AtomicClaim(
                claim_text=claim_dict["claim_text"],
                claim_type=claim_dict.get("claim_type", "factual"),
                claim_category=category,
                importance_score=claim_dict.get("importance_score", 1.0),
                claim_context=claim_dict.get("claim_context"),
                extraction_model=f"deepseek:{self.deepseek_model}",
                extraction_confidence=0.85
            ))

        logger.info(f"DeepSeek extracted {len(claims)} claims from article text ({len(text)} chars)")
        return claims


class EvidenceRetriever:
    """
    Retrieves evidence from multiple trusted sources.

    Sources:
    - Claude AI knowledge base (primary)
    - Google Fact Check Tools API (if configured)
    - Climate Watch API
    - NASA Earthdata
    - Semantic Scholar (future)
    """

    def __init__(self, model: str = "claude-3-opus-20240229"):
        self.google_factcheck_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")
        self.climate_watch_key = os.getenv("CLIMATE_WATCH_API_KEY")
        self.nasa_key = os.getenv("NASA_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.anthropic_key) if (anthropic and self.anthropic_key) else None
        self.deepseek_client, self.deepseek_model = _get_deepseek_client()
        # Use DeepSeek as primary when LLM_PROVIDER=deepseek or no Anthropic key
        llm_provider = os.getenv("LLM_PROVIDER", "").lower()
        self.use_deepseek = (llm_provider == "deepseek" and self.deepseek_client is not None) or (not self.anthropic_key and self.deepseek_client is not None)
        self.orchestrator = EvidenceOrchestrator()
    
    async def fetch_evidence(self, claim: AtomicClaim) -> list[Evidence]:
        """
        Fetch evidence for a claim from multiple sources.

        Args:
            claim: AtomicClaim to verify

        Returns:
            List of Evidence objects
        """
        evidence_list = []

        # Use orchestrator for external evidence (Open-Meteo, Perplexity, Google, EEA, Carbon Brief)
        try:
            country_code = getattr(claim, 'country_code', 'FI') or 'FI'
            orchestrated = await self.orchestrator.retrieve_all(claim.claim_text, country_code)
            evidence_list.extend(orchestrated)
            logger.info(f"Orchestrator retrieved {len(orchestrated)} evidence pieces")
        except Exception as e:
            logger.warning(f"Evidence orchestrator failed, falling back to individual sources: {e}")

        # Primary source: LLM knowledge base (DeepSeek first when configured, else Claude)
        try:
            if self.use_deepseek and self.deepseek_client:
                ds_evidence = await self._fetch_from_deepseek_knowledge(claim.claim_text)
                evidence_list.extend(ds_evidence)
                logger.info(f"DeepSeek knowledge base retrieved {len(ds_evidence)} evidence pieces")
            elif self.client:
                claude_evidence = await self._fetch_from_claude_knowledge(claim.claim_text)
                evidence_list.extend(claude_evidence)
                logger.info(f"Claude knowledge base retrieved {len(claude_evidence)} evidence pieces")
            elif self.deepseek_client:
                ds_evidence = await self._fetch_from_deepseek_knowledge(claim.claim_text)
                evidence_list.extend(ds_evidence)
                logger.info(f"DeepSeek knowledge base retrieved {len(ds_evidence)} evidence pieces")
        except Exception as e:
            logger.warning(f"LLM knowledge retrieval failed: {e}")

        # Try each external source
        try:
            # Google Fact Check Tools API
            if self.google_factcheck_key:
                google_evidence = await self._fetch_from_google_factcheck(claim.claim_text)
                evidence_list.extend(google_evidence)
        except Exception as e:
            logger.warning(f"Google Fact Check API failed: {e}")

        try:
            # Climate Watch API (for emissions/temperature data)
            climate_evidence = await self._fetch_from_climate_watch(claim.claim_text)
            evidence_list.extend(climate_evidence)
        except Exception as e:
            logger.warning(f"Climate Watch API failed: {e}")

        try:
            # NASA API (for satellite/climate data)
            if self.nasa_key:
                nasa_evidence = await self._fetch_from_nasa(claim.claim_text)
                evidence_list.extend(nasa_evidence)
        except Exception as e:
            logger.warning(f"NASA API failed: {e}")

        logger.info(f"Retrieved {len(evidence_list)} total pieces of evidence for claim")
        return evidence_list
    
    async def _fetch_from_google_factcheck(self, query: str) -> list[Evidence]:
        """Fetch from Google Fact Check Tools API."""
        if not self.google_factcheck_key:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                    params={
                        "key": self.google_factcheck_key,
                        "query": query,
                        "pageSize": 5
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                evidence = []
                for claim in data.get("claims", []):
                    for review in claim.get("claimReview", []):
                        evidence.append(Evidence(
                            source=review.get("publisher", {}).get("name", "Unknown"),
                            source_url=review.get("url", ""),
                            source_reliability="high",  # Google vetted sources
                            content_excerpt=review.get("textualRating", ""),
                            relevance_score=0.8,
                            retrieval_method="google_factcheck"
                        ))
                
                return evidence
        except Exception as e:
            logger.error(f"Google Fact Check API error: {e}")
            return []
    
    async def _fetch_from_climate_watch(self, query: str) -> list[Evidence]:
        """
        Fetch climate indicator data from Climate Watch Data API.

        Queries climatewatchdata.org for emissions and climate indicators.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Search for relevant indicators
                resp = await client.get(
                    "https://www.climatewatchdata.org/api/v1/data/historical_emissions",
                    params={
                        "source": "CAIT",
                        "gas": "All GHG",
                        "sector": "Total including LUCF",
                        "page": 1,
                        "per_page": 5,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(f"Climate Watch API returned {resp.status_code}")
                    return []

                data = resp.json()
                records = data.get("data", [])
                evidence = []
                for rec in records[:3]:
                    country = rec.get("country", "Global")
                    value = rec.get("value")
                    year = rec.get("year")
                    if value and year:
                        evidence.append(Evidence(
                            source=f"Climate Watch Data — {country}",
                            content_excerpt=f"GHG emissions for {country} in {year}: {value} MtCO2e (CAIT data)",
                            source_url=f"https://www.climatewatchdata.org/ghg-emissions?regions={country}",
                            retrieval_method="climate_watch",
                            source_reliability="high",
                            relevance_score=0.85,
                        ))
                return evidence
        except Exception as e:
            logger.error(f"Climate Watch API error: {e}")
            return []
    
    async def _fetch_from_nasa(self, query: str) -> list[Evidence]:
        """
        Fetch climate evidence from NASA GISS temperature API.

        Uses NASA GISS Surface Temperature Analysis (GISTEMP) data.
        """
        nasa_api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # NASA GISS global temperature anomaly data
                resp = await client.get(
                    "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    logger.warning(f"NASA GISS API returned {resp.status_code}")
                    return []

                # Parse CSV — last few rows contain recent years
                lines = resp.text.strip().split("\n")
                evidence = []
                # Skip header rows (first 2 lines)
                data_lines = [l for l in lines[2:] if l and not l.startswith("Year")]
                for line in data_lines[-3:]:  # Last 3 years
                    parts = line.split(",")
                    if len(parts) >= 14:
                        year = parts[0].strip()
                        jan_dec = parts[13].strip()  # J-D column = annual mean
                        if jan_dec and jan_dec != "***":
                            try:
                                anomaly = float(jan_dec)
                                evidence.append(Evidence(
                                    source="NASA GISS",
                                    content_excerpt=f"Global temperature anomaly in {year}: {anomaly:+.2f}\u00b0C relative to 1951-1980 baseline (GISTEMP v4)",
                                    source_url="https://data.giss.nasa.gov/gistemp/",
                                    retrieval_method="nasa",
                                    source_reliability="high",
                                    relevance_score=0.95,
                                ))
                            except ValueError:
                                pass
                return evidence
        except Exception as e:
            logger.error(f"NASA GISS API error: {e}")
            return []

    async def _fetch_from_claude_knowledge(self, claim_text: str) -> list[Evidence]:
        """
        Use Claude's knowledge base to find evidence for climate claims.

        This is the primary evidence source when external APIs aren't configured.
        """
        if not self.client:
            logger.warning("Claude client not available for evidence retrieval")
            return []

        try:
            prompt = f"""You are a climate science fact-checker with access to scientific databases and research.

CLAIM TO VERIFY:
"{claim_text}"

TASK:
Search your knowledge base for scientific evidence related to this claim. Provide 2-3 pieces of evidence from trusted sources (NASA, NOAA, IPCC, peer-reviewed journals).

For each evidence piece, provide:
1. The source (organization/publication)
2. Specific data, statistics, or findings
3. How it relates to the claim (supports, contradicts, or provides context)
4. Reliability rating (high/medium/low)

Respond ONLY with valid JSON array:
[
  {{
    "source": "NASA Climate Data",
    "source_url": "https://climate.nasa.gov/...",
    "reliability": "high",
    "content": "Specific finding or data point",
    "supports_claim": true/false
  }}
]

If you cannot find evidence, return an empty array [].
"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.2,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            if not message.content:
                logger.warning("Empty response from Claude for evidence retrieval")
                return []

            response_text = message.content[0].text

            # Extract JSON from response
            json_str = response_text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                parts = json_str.split("```")
                for i in range(1, len(parts), 2):
                    candidate = parts[i].strip()
                    if candidate.startswith("json"):
                        candidate = candidate[4:].strip()
                    if candidate.startswith("["):
                        json_str = candidate
                        break

            # Parse JSON
            try:
                evidence_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse evidence JSON: {e}. Response: {response_text[:500]}")
                return []

            if not isinstance(evidence_data, list):
                logger.warning(f"Evidence response is not a list: {type(evidence_data)}")
                return []

            # Convert to Evidence objects
            evidence_list = []
            for item in evidence_data[:5]:  # Limit to 5 pieces
                try:
                    evidence_list.append(Evidence(
                        source=item.get("source", "Unknown"),
                        source_url=item.get("source_url", ""),
                        source_reliability=item.get("reliability", "medium"),
                        content_excerpt=item.get("content", ""),
                        relevance_score=0.9 if item.get("supports_claim") else 0.7,
                        retrieval_method="claude_knowledge"
                    ))
                except Exception as e:
                    logger.warning(f"Failed to create Evidence object: {e}")
                    continue

            logger.info(f"Claude retrieved {len(evidence_list)} evidence pieces for claim")
            return evidence_list

        except Exception as e:
            logger.error(f"Claude evidence retrieval error: {e}", exc_info=True)
            return []

    async def _fetch_from_deepseek_knowledge(self, claim_text: str) -> list[Evidence]:
        """Use DeepSeek to find evidence for climate claims (fallback for Claude)."""
        if not self.deepseek_client:
            return []
        try:
            prompt = f"""You are a climate science fact-checker. Search your knowledge for scientific evidence related to this claim.

CLAIM: "{claim_text}"

Provide 2-3 pieces of evidence from trusted sources (NASA, NOAA, IPCC, peer-reviewed journals).
Return ONLY valid JSON array:
[{{"source": "...", "source_url": "...", "reliability": "high/medium/low", "content": "...", "supports_claim": true/false}}]
If no evidence, return [].
"""
            response_text = _deepseek_chat(
                self.deepseek_client, self.deepseek_model, prompt, max_tokens=1500, temperature=0.2
            )
            json_str = response_text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                parts = json_str.split("```")
                for i in range(1, len(parts), 2):
                    candidate = parts[i].strip()
                    if candidate.startswith("json"):
                        candidate = candidate[4:].strip()
                    if candidate.startswith("["):
                        json_str = candidate
                        break
            evidence_data = json.loads(json_str)
            if not isinstance(evidence_data, list):
                return []
            evidence_list = []
            for item in evidence_data[:5]:
                evidence_list.append(Evidence(
                    source=item.get("source", "Unknown"),
                    source_url=item.get("source_url", ""),
                    source_reliability=item.get("reliability", "medium"),
                    content_excerpt=item.get("content", ""),
                    relevance_score=0.85 if item.get("supports_claim") else 0.65,
                    retrieval_method="deepseek_knowledge"
                ))
            return evidence_list
        except Exception as e:
            logger.error(f"DeepSeek evidence retrieval error: {e}", exc_info=True)
            return []


class VerdictAdjudicator:
    """
    Adjudicates claims by comparing against evidence.
    
    Uses Claude to reason over evidence and assign verdicts with confidence scores.
    """
    
    def __init__(self, model: str = "deepseek-chat"):
        self.deepseek_client, self.deepseek_model = _get_deepseek_client()
        self.model = self.deepseek_model or model
        # DeepSeek is the only LLM provider
        self.client = None  # Anthropic client disabled
        self.api_key = None  # Anthropic key not used
        self.use_deepseek = self.deepseek_client is not None
    
    async def adjudicate(
        self,
        claim: AtomicClaim,
        evidence: list[Evidence]
    ) -> Verdict:
        """
        Adjudicate a claim based on evidence.
        
        Args:
            claim: The claim to verify
            evidence: List of evidence pieces
        
        Returns:
            Verdict with confidence score
        """
        if not self.client and not self.deepseek_client:
            logger.error("Cannot adjudicate - no LLM client initialized")
            return Verdict(
                verdict="unverified",
                confidence_score=0.0,
                justification="Verification service unavailable",
                evidence_summary="No evidence retrieved",
                model_used="none"
            )
        
        if not evidence:
            return Verdict(
                verdict="unverified",
                confidence_score=0.3,
                justification="No evidence found to verify this claim",
                evidence_summary="No sources available",
                model_used=self.model
            )
        
        try:
            # Build evidence summary for Claude
            evidence_text = "\n\n".join([
                f"Source: {e.source}\nURL: {e.source_url}\nReliability: {e.source_reliability}\nRetrieval method: {e.retrieval_method or 'unknown'}\nContent: {e.content_excerpt}"
                for e in evidence[:5]  # Limit to top 5 pieces
            ])

            # Complexity-aware claim routing (Phase 4B - Cynefin-lite)
            claim_category = getattr(claim, 'claim_category', ClaimCategory.STATISTICAL)
            complexity_tier = ClaimClassifier.get_complexity_tier(claim_category)
            adjudication_max_tokens = ClaimClassifier.get_max_tokens_for_tier(complexity_tier)
            logger.debug(
                f"Claim complexity tier: {complexity_tier} "
                f"(category={claim_category}, max_tokens={adjudication_max_tokens})"
            )

            # Build tier-specific instructions
            tier_instructions = ""
            if complexity_tier == "exploratory":
                tier_instructions = (
                    "\nEXPLORATORY CLAIM INSTRUCTIONS (predictive/forecast claims):\n"
                    "- You MUST include explicit uncertainty ranges in your justification "
                    '(e.g., "likely between X and Y")\n'
                    "- Confidence score should reflect inherent prediction uncertainty\n"
                    "- Evidence chain should reference model projections and their confidence "
                    "intervals where available\n"
                )
            elif complexity_tier == "deterministic":
                tier_instructions = (
                    "\nDETERMINISTIC CLAIM INSTRUCTIONS (simple factual/statistical claims):\n"
                    "- Focus on direct data lookups and exact figures\n"
                    "- Keep justification concise and data-driven\n"
                )
            elif complexity_tier == "analytical":
                tier_instructions = (
                    "\nANALYTICAL CLAIM INSTRUCTIONS (causal/policy claims):\n"
                    "- Provide deeper reasoning about cause-effect relationships or policy implications\n"
                    "- Cross-reference multiple authoritative sources\n"
                    "- Explain the mechanism or logic chain connecting evidence to claim\n"
                )

            prompt = f"""You are a fact-checker analyzing a climate-related claim.

CLAIM TO VERIFY:
"{claim.claim_text}"

CLAIM CATEGORY: {getattr(claim, 'claim_category', 'statistical')}
COMPLEXITY TIER: {complexity_tier}
{tier_instructions}
EVIDENCE RETRIEVED:
{evidence_text}

TASK:
1. Compare the claim against the evidence
2. Determine the verdict: verified, disputed, partially_true, or unverified
3. Assign a confidence score (0.0-1.0)
4. Provide decomposed confidence factors (each 0.0-1.0):
   - model_confidence: Your confidence in your own analysis
   - source_quality: Quality/authority of evidence sources
   - evidence_breadth: Diversity/number of independent evidence
   - cross_reference_score: Agreement across sources
   - temporal_relevance: How current the evidence is
5. Build an evidence chain with FULL PROVENANCE: for each evidence piece, note what it established,
   which API or retrieval method was used, and why the evidence is relevant to this specific claim
6. Provide a clear justification

RULES:
- "verified": Evidence strongly supports the claim (confidence >= 0.75)
- "partially_true": Evidence supports parts but not all (confidence 0.50-0.74)
- "disputed": Evidence contradicts the claim (confidence >= 0.70)
- "unverified": Insufficient evidence (confidence < 0.50)

EVIDENCE PROVENANCE REQUIREMENTS:
- Every evidence_chain entry MUST include source_url (the actual URL where data was found)
- Every evidence_chain entry MUST include retrieval_method (the API or tool that fetched it,
  e.g. "google_factcheck", "climate_watch", "nasa", "claude_knowledge", "deepseek_knowledge",
  "open_meteo", "perplexity", "eea", "carbon_brief")
- Every evidence_chain entry MUST include relevance_explanation (a sentence explaining
  why this specific evidence matters for verifying the claim)

Respond ONLY with valid JSON:
{{
  "verdict": "verified|disputed|partially_true|unverified",
  "confidence_score": 0.0-1.0,
  "justification": "Clear explanation of reasoning",
  "evidence_summary": "Key evidence that supports this verdict",
  "decomposed_confidence": {{
    "model_confidence": 0.0-1.0,
    "source_quality": 0.0-1.0,
    "evidence_breadth": 0.0-1.0,
    "cross_reference_score": 0.0-1.0,
    "temporal_relevance": 0.0-1.0
  }},
  "evidence_chain": [
    {{
      "step_number": 1,
      "description": "What this evidence established",
      "source": "Source name",
      "source_url": "URL where data was found",
      "retrieval_method": "API or tool that retrieved this evidence",
      "relevance_explanation": "Why this evidence matters for verifying the claim",
      "confidence": 0.0-1.0,
      "supports_claim": true
    }}
  ]
}}
"""
            
            if not self.deepseek_client:
                raise RuntimeError("No LLM client available — DEEPSEEK_API_KEY not configured")

            try:
                response_text = _deepseek_chat(
                    self.deepseek_client, self.deepseek_model, prompt, max_tokens=adjudication_max_tokens, temperature=0.1
                )
                used_model = f"deepseek:{self.deepseek_model}"
            except Exception as ds_err:
                logger.warning(f"DeepSeek {self.deepseek_model} failed: {ds_err}, retrying with deepseek-chat")
                response_text = _deepseek_chat(
                    self.deepseek_client, "deepseek-chat", prompt, max_tokens=adjudication_max_tokens, temperature=0.1
                )
                used_model = "deepseek:deepseek-chat"
            
            # Parse JSON
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            verdict_data = json.loads(json_str)
            
            # Categorize evidence
            supporting = [e for e in evidence if e.supports_claim is True]
            contradicting = [e for e in evidence if e.supports_claim is False]

            # Build decomposed confidence from LLM response
            dc_data = verdict_data.get("decomposed_confidence", {})
            dc = DecomposedConfidence(
                model_confidence=dc_data.get("model_confidence", verdict_data["confidence_score"]),
                source_quality=dc_data.get("source_quality", 0.5),
                evidence_breadth=dc_data.get("evidence_breadth", min(1.0, len(evidence) / 5)),
                cross_reference_score=dc_data.get("cross_reference_score", 0.5),
                temporal_relevance=dc_data.get("temporal_relevance", 0.7),
            )
            dc.overall = DecomposedConfidence.compute_overall(
                model_confidence=dc.model_confidence,
                source_quality=dc.source_quality,
                evidence_breadth=dc.evidence_breadth,
                cross_reference_score=dc.cross_reference_score,
                temporal_relevance=dc.temporal_relevance,
            )

            # Build evidence chain from LLM response (with provenance fields)
            chain_data = verdict_data.get("evidence_chain", [])
            evidence_chain = []
            for step in chain_data:
                evidence_chain.append(EvidenceChainLink(
                    step_number=step.get("step_number", len(evidence_chain) + 1),
                    description=step.get("description", ""),
                    source=step.get("source", "Unknown"),
                    source_url=step.get("source_url", ""),
                    retrieval_method=step.get("retrieval_method", "unknown"),
                    relevance_explanation=step.get("relevance_explanation", ""),
                    confidence=step.get("confidence", 0.5),
                    supports_claim=step.get("supports_claim"),
                ))

            # If LLM didn't return chain, build from evidence with provenance
            if not evidence_chain and evidence:
                for i, e in enumerate(evidence[:5], 1):
                    evidence_chain.append(EvidenceChainLink(
                        step_number=i,
                        description=e.content_excerpt[:200],
                        source=e.source,
                        source_url=e.source_url,
                        retrieval_method=e.retrieval_method or "unknown",
                        relevance_explanation=f"Retrieved from {e.source} via {e.retrieval_method or 'unknown'} with relevance {e.relevance_score:.2f}",
                        confidence=e.relevance_score,
                        supports_claim=e.supports_claim,
                    ))

            # Apply confidence ceiling from verification strategy
            claim_cat = getattr(claim, 'claim_category', ClaimCategory.STATISTICAL)
            strategy = ClaimClassifier.get_strategy(claim_cat)
            final_confidence = min(verdict_data["confidence_score"], strategy.confidence_ceiling)

            verdict = Verdict(
                verdict=verdict_data["verdict"],
                confidence_score=final_confidence,
                justification=verdict_data["justification"],
                evidence_summary=verdict_data["evidence_summary"],
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                decomposed_confidence=dc,
                evidence_chain=evidence_chain,
                claim_category=claim_cat.value if isinstance(claim_cat, ClaimCategory) else str(claim_cat),
                model_used=used_model,
                verified_at=datetime.utcnow()
            )

            # --- Guardian-lite policy checks (Phase 4C) ---
            # Check 1: Downgrade "verified" verdicts with insufficient source provenance
            if verdict.verdict == "verified":
                sourced_links = [
                    link for link in evidence_chain
                    if link.source_url and link.source_url.strip()
                ]
                if len(sourced_links) < 2:
                    logger.warning(
                        f"Guardian-lite: downgrading 'verified' to 'partially_verified' — "
                        f"only {len(sourced_links)} evidence chain entries have source_urls "
                        f"(minimum 2 required)"
                    )
                    verdict.verdict = "partially_verified"
                    verdict.justification = (
                        verdict.justification
                        + " [Guardian-lite: downgraded from 'verified' because fewer than 2 "
                        "evidence chain entries include verifiable source URLs.]"
                    )

            # Check 2: Flag contradictions when both supporting and contradicting evidence exist
            if supporting and contradicting and verdict.confidence_score > 0.7:
                contradiction_note = (
                    f" [Guardian-lite warning: both supporting ({len(supporting)}) and "
                    f"contradicting ({len(contradicting)}) evidence found with confidence "
                    f"{verdict.confidence_score:.2f} > 0.7 — review recommended.]"
                )
                logger.warning(
                    f"Guardian-lite: contradiction detected for claim — "
                    f"{len(supporting)} supporting vs {len(contradicting)} contradicting "
                    f"evidence at confidence {verdict.confidence_score:.2f}"
                )
                verdict.justification = verdict.justification + contradiction_note
            # --- End Guardian-lite checks ---

            # --- Phase 3: Weather Data Claim Validation ---
            # For claims containing weather-related keywords, query Open-Meteo archive
            # and add the result as an additional evidence piece in the chain.
            weather_keywords = [
                "temperature", "\u00b0c", "precipitation", "mm", "wind",
                "weather", "heatwave", "heat wave", "flood", "drought",
            ]
            claim_lower_for_weather = claim.claim_text.lower()
            if any(kw in claim_lower_for_weather for kw in weather_keywords):
                try:
                    country_code_for_weather = getattr(claim, "country_code", "FI") or "FI"
                    weather_result = await WeatherClaimValidator().validate(
                        claim.claim_text, country_code_for_weather
                    )
                    if weather_result.get("weather_validated"):
                        weather_verdict = weather_result.get("verdict", "INCONCLUSIVE")
                        weather_details = weather_result.get("details", "")
                        claimed_val = weather_result.get("claimed_value")
                        actual_val = weather_result.get("actual_value")
                        deviation = weather_result.get("deviation_pct")

                        # Determine supports_claim from weather verdict
                        weather_supports: Optional[bool] = None
                        if weather_verdict == "SUPPORTED":
                            weather_supports = True
                        elif weather_verdict == "CONTRADICTED":
                            weather_supports = False

                        # Derive relevance score: lower deviation = higher relevance
                        if deviation is not None:
                            weather_relevance = max(0.3, min(0.95, 1.0 - deviation / 100))
                        else:
                            weather_relevance = 0.5

                        weather_evidence = Evidence(
                            source="Open-Meteo Archive API (Weather Validation)",
                            source_url="https://archive-api.open-meteo.com/v1/archive",
                            source_reliability="high",
                            content_excerpt=weather_details,
                            relevance_score=weather_relevance,
                            supports_claim=weather_supports,
                            retrieval_method="weather_claim_validator",
                        )

                        # Add to appropriate evidence lists on the verdict
                        if weather_supports is True:
                            verdict.supporting_evidence.append(weather_evidence)
                        elif weather_supports is False:
                            verdict.contradicting_evidence.append(weather_evidence)

                        # Append as a new step in the evidence chain
                        next_step = len(verdict.evidence_chain) + 1
                        deviation_str = f"{deviation}%" if deviation is not None else "N/A"
                        verdict.evidence_chain.append(EvidenceChainLink(
                            step_number=next_step,
                            description=(
                                f"Weather archive validation: claimed={claimed_val}, "
                                f"actual={actual_val}, deviation={deviation_str}"
                            ),
                            source="Open-Meteo Archive API",
                            source_url="https://archive-api.open-meteo.com/v1/archive",
                            retrieval_method="weather_claim_validator",
                            relevance_explanation=(
                                f"Direct comparison of the claimed weather value against "
                                f"Open-Meteo ERA5 archive data. Result: {weather_verdict}. "
                                f"{weather_details}"
                            ),
                            confidence=weather_relevance,
                            supports_claim=weather_supports,
                        ))

                        logger.info(
                            f"Weather validation added to evidence chain: "
                            f"verdict={weather_verdict}, deviation={deviation_str}"
                        )
                    else:
                        logger.debug(
                            f"Weather validation inconclusive or skipped: "
                            f"{weather_result.get('details', '')}"
                        )
                except Exception as weather_err:
                    logger.warning(f"Weather claim validation failed (non-fatal): {weather_err}")
            # --- End Phase 3: Weather Data Claim Validation ---

            logger.info(f"Adjudicated claim: verdict={verdict.verdict}, confidence={verdict.confidence_score}")
            return verdict
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse adjudication response: {e}")
            return Verdict(
                verdict="unverified",
                confidence_score=0.0,
                justification="Error parsing verification result",
                evidence_summary="",
                model_used=self.model
            )
        except Exception as e:
            logger.error(f"Adjudication failed: {e}")
            return Verdict(
                verdict="unverified",
                confidence_score=0.0,
                justification="Verification temporarily unavailable — will be retried",
                evidence_summary="",
                model_used=self.model
            )


class VerificationService:
    """
    Orchestrates the complete verification pipeline.
    
    Coordinates claim extraction, evidence retrieval, and adjudication.
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.extractor = ClaimExtractor()
        self.retriever = EvidenceRetriever()
        self.adjudicator = VerdictAdjudicator()
        # Initialize claims status manager for tracking extraction status
        self.status_manager = ClaimsStatusManager(self.db)
    
    async def verify_article(self, article_id: UUID) -> VerificationResult:
        """
        Run complete verification pipeline on an article.
        
        Steps:
        1. Fetch article text
        2. Extract atomic claims
        3. For each claim:
           a. Retrieve evidence
           b. Adjudicate verdict
           c. Store in database
        4. Calculate aggregate credibility
        5. Update article credibility score
        
        Args:
            article_id: Article to verify
        
        Returns:
            VerificationResult with processing summary
        """
        start_time = datetime.utcnow()

        # Set status to processing before starting
        self.status_manager.set_processing(article_id)

        try:
            # Fetch article
            article_results = self.db.execute_query(
                """
                SELECT article_id, extracted_text
                FROM articles
                WHERE article_id = :article_id
                """,
                {"article_id": str(article_id)},
            )

            if not article_results:
                logger.error(f"Article {article_id} not found")
                self.status_manager.set_failed(article_id, "Article not found in database")
                return VerificationResult(
                    article_id=article_id,
                    processing_started_at=start_time,
                    status="failed",
                    error_message="Article not found"
                )

            article_text = article_results[0]["extracted_text"]

            # Step 1: Extract claims
            logger.info(f"Extracting claims from article {article_id}")
            try:
                claims = await self.extractor.decompose_claims(article_text)
            except HTTPException as e:
                # Handle API errors explicitly
                error_msg = f"Claim extraction failed: {e.detail}"
                logger.error(error_msg)
                self.status_manager.set_failed(article_id, error_msg)
                return VerificationResult(
                    article_id=article_id,
                    processing_started_at=start_time,
                    processing_completed_at=datetime.utcnow(),
                    total_processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    status="failed",
                    error_message=error_msg
                )
            except Exception as e:
                error_msg = f"Unexpected error during claim extraction: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.status_manager.set_failed(article_id, error_msg)
                return VerificationResult(
                    article_id=article_id,
                    processing_started_at=start_time,
                    processing_completed_at=datetime.utcnow(),
                    total_processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    status="failed",
                    error_message=error_msg
                )
            
            if not claims:
                logger.warning(f"No claims extracted from article {article_id}")
                self.status_manager.set_completed(
                    article_id,
                    claims_count=0,
                    verified_claims_count=0,
                )
                return VerificationResult(
                    article_id=article_id,
                    processing_started_at=start_time,
                    processing_completed_at=datetime.utcnow(),
                    total_processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    status="completed"
                )
            
            # Step 2-3: For each claim, retrieve evidence and adjudicate
            verified_count = 0
            disputed_count = 0
            unverified_count = 0
            total_confidence = 0.0
            claims_by_category: dict[str, int] = {}
            all_dc: list[DecomposedConfidence] = []

            for claim in claims:
                # Generate claim ID
                claim_id = uuid4()

                # Track category counts
                cat_val = claim.claim_category.value if isinstance(claim.claim_category, ClaimCategory) else str(claim.claim_category)
                claims_by_category[cat_val] = claims_by_category.get(cat_val, 0) + 1

                # Store claim with category
                claim_text_safe = claim.claim_text.replace("'", "''")
                context_safe = (claim.claim_context or '').replace("'", "''")

                self.db.execute_update(
                    f"""
                    INSERT INTO claims (
                        claim_id, article_id, claim_text, claim_type, claim_context, claim_category
                    ) VALUES (
                        '{str(claim_id)}', '{str(article_id)}', '{claim_text_safe}', '{claim.claim_type}', '{context_safe}', '{cat_val}'
                    )
                    ON CONFLICT (claim_id) DO NOTHING
                    """,
                    {}
                )

                # Retrieve evidence
                logger.info(f"Retrieving evidence for claim: {claim.claim_text[:50]}...")
                evidence = await self.retriever.fetch_evidence(claim)

                # Adjudicate
                verdict = await self.adjudicator.adjudicate(claim, evidence)

                # Store fact-check with decomposed confidence and evidence chain
                fact_check_id = uuid4()
                justification_safe = verdict.justification.replace("'", "''")
                evidence_json = json.dumps([e.dict() for e in verdict.supporting_evidence + verdict.contradicting_evidence]).replace("'", "''")
                dc_json = json.dumps(verdict.decomposed_confidence.dict() if verdict.decomposed_confidence else {}).replace("'", "''")
                chain_json = json.dumps([link.dict() for link in verdict.evidence_chain]).replace("'", "''")

                self.db.execute_update(
                    f"""
                    INSERT INTO fact_checks (
                        fact_check_id, claim_id, verification_status, confidence_score,
                        justification, evidence, decomposed_confidence, evidence_chain, verified_at
                    ) VALUES (
                        '{str(fact_check_id)}', '{str(claim_id)}', '{verdict.verdict}', {verdict.confidence_score},
                        '{justification_safe}', '{evidence_json}'::jsonb, '{dc_json}'::jsonb, '{chain_json}'::jsonb, NOW()
                    )
                    """,
                    {}
                )

                # Track counts and aggregates
                total_confidence += verdict.confidence_score
                if verdict.decomposed_confidence:
                    all_dc.append(verdict.decomposed_confidence)
                if verdict.verdict == "verified":
                    verified_count += 1
                elif verdict.verdict == "disputed":
                    disputed_count += 1
                else:
                    unverified_count += 1
            
            # Step 4: Calculate article credibility
            avg_confidence = total_confidence / len(claims) if claims else 0.0

            # Weighted credibility (verified claims count more)
            article_credibility = (
                (verified_count * 1.0 + unverified_count * 0.3 + disputed_count * 0.0)
                / len(claims)
            ) if claims else 0.5

            # Determine level via the single source of truth (seq-5):
            # was 0.75/0.45, now the canonical 0.80/0.50.
            from shared.credibility_thresholds import level_for_unit
            credibility_level = level_for_unit(article_credibility).lower()

            # Aggregate decomposed confidence across all claims
            article_dc = None
            if all_dc:
                n = len(all_dc)
                agg_factors = {
                    "model_confidence": sum(d.model_confidence for d in all_dc) / n,
                    "source_quality": sum(d.source_quality for d in all_dc) / n,
                    "evidence_breadth": sum(d.evidence_breadth for d in all_dc) / n,
                    "cross_reference_score": sum(d.cross_reference_score for d in all_dc) / n,
                    "temporal_relevance": sum(d.temporal_relevance for d in all_dc) / n,
                }
                article_dc = DecomposedConfidence(
                    **agg_factors,
                    overall=DecomposedConfidence.compute_overall(**agg_factors)
                )

            # Step 5: Update article credibility scores
            reliability_score = int(article_credibility * 100)
            dc_article_json = json.dumps(article_dc.dict() if article_dc else {}).replace("'", "''")
            self.db.execute_update(
                f"""
                UPDATE articles SET
                    reliability_score = {reliability_score},
                    overall_credibility = '{credibility_level}',
                    decomposed_confidence = '{dc_article_json}'::jsonb,
                    updated_at = NOW()
                WHERE article_id = '{str(article_id)}'
                """,
                {}
            )

            # Step 6: Mark claims extraction as completed (updates claims_count and verified_claims_count)
            self.status_manager.set_completed(
                article_id,
                claims_count=len(claims),
                verified_claims_count=verified_count
            )

            end_time = datetime.utcnow()

            logger.info(
                f"Verification completed for article {article_id}: "
                f"{len(claims)} claims, {verified_count} verified, "
                f"credibility={article_credibility:.2f}"
            )
            
            return VerificationResult(
                article_id=article_id,
                claims_extracted=len(claims),
                claims_verified=verified_count,
                claims_disputed=disputed_count,
                claims_unverified=unverified_count,
                average_confidence=avg_confidence,
                article_credibility=article_credibility,
                credibility_level=credibility_level,
                decomposed_confidence=article_dc,
                claims_by_category=claims_by_category,
                processing_started_at=start_time,
                processing_completed_at=end_time,
                total_processing_time_seconds=(end_time - start_time).total_seconds(),
                provenance={
                    "extraction_model": self.extractor.model,
                    "adjudication_model": self.adjudicator.model,
                    "evidence_sources": ["claude_knowledge", "google_factcheck", "climate_watch", "nasa"],
                },
                status="completed"
            )
            
        except Exception as e:
            logger.error(f"Verification failed for article {article_id}: {e}", exc_info=True)
            # Mark as failed in database
            self.status_manager.set_failed(article_id, str(e))
            return VerificationResult(
                article_id=article_id,
                processing_started_at=start_time,
                processing_completed_at=datetime.utcnow(),
                total_processing_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
                status="failed",
                error_message=str(e)
            )

