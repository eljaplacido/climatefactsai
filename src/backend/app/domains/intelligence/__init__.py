"""
Intelligence Domain

Core IP: Multi-stage fact-checking and verification pipeline.
Decomposes articles into atomic claims, retrieves evidence, and assigns verdicts.
Includes CARF-inspired decomposed confidence scoring and claim classification.
"""

from .schemas import (
    AtomicClaim, Evidence, Verdict, VerificationResult,
    ClaimCategory, DecomposedConfidence, EvidenceChainLink, ReliabilityBreakdown,
)
from .services import ClaimExtractor, EvidenceRetriever, VerdictAdjudicator, VerificationService
from .claim_classifier import ClaimClassifier
from .analysis_engine import AnalysisEngine

__all__ = [
    "AtomicClaim",
    "Evidence",
    "Verdict",
    "VerificationResult",
    "ClaimCategory",
    "DecomposedConfidence",
    "EvidenceChainLink",
    "ReliabilityBreakdown",
    "ClaimExtractor",
    "EvidenceRetriever",
    "VerdictAdjudicator",
    "VerificationService",
    "ClaimClassifier",
    "AnalysisEngine",
]

