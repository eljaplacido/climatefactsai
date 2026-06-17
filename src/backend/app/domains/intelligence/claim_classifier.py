"""
Claim Classifier

Classifies claims by category and maps them to appropriate verification strategies.
Adapted from CARF's Cynefin router concept: different problem domains need different
analytical treatment. For climate news, claim types map to verification approaches.
"""

import re
from dataclasses import dataclass, field

from .schemas import ClaimCategory


# Keyword patterns for each claim category
CATEGORY_PATTERNS: dict[ClaimCategory, list[str]] = {
    ClaimCategory.SCIENTIFIC_CAUSAL: [
        r'\bcaus(e[sd]?|ing)\b', r'\blead[s]?\s+to\b', r'\bresult[s]?\s+in\b',
        r'\bdriv(e[sd]?|ing)\b', r'\bcontribut(e[sd]?|ing)\s+to\b',
        r'\bdue\s+to\b', r'\bbecause\s+of\b', r'\beffect[s]?\s+of\b',
        r'\bimpact[s]?\s+on\b', r'\bcorrelat(e[sd]?|ion)\b',
        r'\bgreenhouse\s+effect\b', r'\bfeedback\s+loop\b',
        r'\bwarming\s+caus\b', r'\bocean\s+acidif\b',
    ],
    ClaimCategory.STATISTICAL: [
        r'\b\d+[\.,]?\d*\s*(%|percent|per\s*cent)\b',
        r'\b\d+[\.,]?\d*\s*(billion|million|trillion|thousand)\b',
        r'\bincreas(e[sd]?|ing)\s+by\b', r'\bdecreas(e[sd]?|ing)\s+by\b',
        r'\brose\s+\d', r'\bfell\s+\d', r'\bdrop(ped)?\s+\d',
        r'\baverage\b', r'\bmedian\b', r'\brate\s+of\b',
        r'\brecord\s+(high|low|level)\b', r'\bdegrees?\s+(celsius|fahrenheit)\b',
        r'\bparts?\s+per\s+(million|billion)\b', r'\bppm\b',
    ],
    ClaimCategory.POLICY: [
        r'\bagreement\b', r'\btreaty\b', r'\bregulat(e|ion|ory)\b',
        r'\blegislat(e|ion)\b', r'\bpledg(e[sd]?|ing)\b',
        r'\bcommit(ted|ment|s)?\b', r'\btarget[s]?\b.*\b(emission|carbon|net.?zero)\b',
        r'\bparis\s+agreement\b', r'\bcop\s*\d+\b', r'\bndc\b',
        r'\beu\s+(green\s+deal|directive|regulation)\b',
        r'\bcarbon\s+(tax|pricing|market|trading)\b',
        r'\bnet.?zero\b', r'\bban(ned|ning|s)?\s+(fossil|coal|plastic)\b',
    ],
    ClaimCategory.PREDICTIVE: [
        r'\bwill\b.*\b(increase|decrease|rise|fall|reach|exceed)\b',
        r'\bby\s+20[3-9]\d\b', r'\bprojected?\b', r'\bforecast\b',
        r'\bexpected?\s+to\b', r'\bestimate[sd]?\s+to\b',
        r'\bscenario\b', r'\bmodel[s]?\s+(predict|suggest|show|indicate)\b',
        r'\bif\s+.*(continues?|trends?)\b', r'\bcould\s+(reach|lead|cause)\b',
    ],
    ClaimCategory.ANECDOTAL: [
        r'\bwitness(ed|es)?\b', r'\bsaid\b.*\b(local|resident|farmer|observer)\b',
        r'\baccording\s+to\s+(local|one|a)\b',
        r'\bfirst.?hand\b', r'\bpersonal\s+experience\b',
        r'\b(I|we)\s+(saw|noticed|observed|experienced)\b',
    ],
}


@dataclass
class VerificationStrategy:
    """Defines how a claim category should be verified."""
    primary_sources: list[str] = field(default_factory=list)
    evidence_weight_profile: dict[str, float] = field(default_factory=dict)
    min_evidence_pieces: int = 2
    confidence_ceiling: float = 1.0
    description: str = ""


# Strategy mapping for each claim category
VERIFICATION_STRATEGIES: dict[ClaimCategory, VerificationStrategy] = {
    ClaimCategory.SCIENTIFIC_CAUSAL: VerificationStrategy(
        primary_sources=["nasa", "noaa", "ipcc", "nature", "science"],
        evidence_weight_profile={
            "peer_reviewed": 1.0,
            "government_agency": 0.9,
            "news_outlet": 0.5,
            "claude_knowledge": 0.7,
        },
        min_evidence_pieces=3,
        confidence_ceiling=1.0,
        description="Causal claims require strong scientific evidence from peer-reviewed sources",
    ),
    ClaimCategory.STATISTICAL: VerificationStrategy(
        primary_sources=["climate_watch", "world_bank", "iea", "nasa"],
        evidence_weight_profile={
            "official_dataset": 1.0,
            "government_agency": 0.9,
            "peer_reviewed": 0.8,
            "claude_knowledge": 0.6,
        },
        min_evidence_pieces=2,
        confidence_ceiling=1.0,
        description="Statistical claims need verification against authoritative datasets",
    ),
    ClaimCategory.POLICY: VerificationStrategy(
        primary_sources=["unfccc", "eu_commission", "government"],
        evidence_weight_profile={
            "official_document": 1.0,
            "government_agency": 0.95,
            "news_outlet": 0.6,
            "claude_knowledge": 0.7,
        },
        min_evidence_pieces=2,
        confidence_ceiling=1.0,
        description="Policy claims are verified against official documents and government sources",
    ),
    ClaimCategory.ANECDOTAL: VerificationStrategy(
        primary_sources=["claude_knowledge", "news_outlet"],
        evidence_weight_profile={
            "peer_reviewed": 0.8,
            "news_outlet": 0.7,
            "claude_knowledge": 0.6,
        },
        min_evidence_pieces=1,
        confidence_ceiling=0.7,
        description="Anecdotal claims are inherently harder to verify; confidence is capped",
    ),
    ClaimCategory.PREDICTIVE: VerificationStrategy(
        primary_sources=["ipcc", "iea", "nasa", "met_office"],
        evidence_weight_profile={
            "climate_model": 1.0,
            "peer_reviewed": 0.9,
            "government_agency": 0.8,
            "claude_knowledge": 0.6,
        },
        min_evidence_pieces=2,
        confidence_ceiling=0.85,
        description="Predictive claims carry inherent uncertainty; verified against model consensus",
    ),
}


class ClaimClassifier:
    """
    Classifies claims into categories for routing to appropriate verification strategies.

    Uses keyword pattern matching as the primary classifier. For ambiguous cases,
    defaults to STATISTICAL (the most common claim type in climate news).
    """

    @staticmethod
    def classify(claim_text: str) -> ClaimCategory:
        """
        Classify a claim by matching against category-specific keyword patterns.

        Returns the category with the highest number of pattern matches.
        Ties are broken by priority: scientific_causal > statistical > policy > predictive > anecdotal.
        """
        text_lower = claim_text.lower()
        scores: dict[ClaimCategory, int] = {cat: 0 for cat in ClaimCategory}

        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    scores[category] += 1

        # Find the category with the highest score
        max_score = max(scores.values())
        if max_score == 0:
            return ClaimCategory.STATISTICAL  # default

        # Priority ordering for tie-breaking
        priority = [
            ClaimCategory.SCIENTIFIC_CAUSAL,
            ClaimCategory.STATISTICAL,
            ClaimCategory.POLICY,
            ClaimCategory.PREDICTIVE,
            ClaimCategory.ANECDOTAL,
        ]

        for cat in priority:
            if scores[cat] == max_score:
                return cat

        return ClaimCategory.STATISTICAL

    @staticmethod
    def get_strategy(category: ClaimCategory) -> VerificationStrategy:
        """Get the verification strategy for a claim category."""
        return VERIFICATION_STRATEGIES.get(category, VERIFICATION_STRATEGIES[ClaimCategory.STATISTICAL])

    @staticmethod
    def get_complexity_tier(claim_category: ClaimCategory) -> str:
        """
        Classify claims into complexity tiers for routing (Cynefin-lite).

        Inspired by CARF's Cynefin framework for problem categorisation:
        - Deterministic (simple facts): Direct data lookup, low token budget
        - Analytical (causal claims): Deeper LLM analysis, higher token budget
        - Exploratory (predictions): Bayesian-style with explicit uncertainty ranges

        Returns one of: "deterministic", "analytical", "exploratory"
        """
        tier_map = {
            ClaimCategory.SCIENTIFIC_CAUSAL: "analytical",
            ClaimCategory.STATISTICAL: "deterministic",
            ClaimCategory.POLICY: "analytical",
            ClaimCategory.ANECDOTAL: "deterministic",
            ClaimCategory.PREDICTIVE: "exploratory",
        }
        return tier_map.get(claim_category, "deterministic")

    @staticmethod
    def get_max_tokens_for_tier(tier: str) -> int:
        """
        Return the appropriate max_tokens budget for a complexity tier.

        - Deterministic: 600 tokens (simple lookups)
        - Analytical: 1200 tokens (deeper reasoning)
        - Exploratory: 1500 tokens (uncertainty modelling)
        """
        token_budgets = {
            "deterministic": 600,
            "analytical": 1200,
            "exploratory": 1500,
        }
        return token_budgets.get(tier, 1000)

    @staticmethod
    def classify_batch(claims: list[str]) -> dict[ClaimCategory, list[int]]:
        """
        Classify a batch of claims, returning indices grouped by category.

        Returns: {category: [list of claim indices]}
        """
        result: dict[ClaimCategory, list[int]] = {cat: [] for cat in ClaimCategory}
        for i, claim_text in enumerate(claims):
            category = ClaimClassifier.classify(claim_text)
            result[category].append(i)
        return result
