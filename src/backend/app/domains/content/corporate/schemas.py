"""Pydantic models for corporate climate data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CompanyProfile:
    company_id: str
    name: str
    ticker: Optional[str] = None
    country_code: Optional[str] = None
    sector_nace: Optional[str] = None
    disclosure_count: int = 0
    latest_disclosure_year: Optional[int] = None
    sbti_validated: bool = False
    net_zero_target_year: Optional[int] = None


@dataclass
class DisclosureRecord:
    company_id: str
    source: str
    reporting_year: int
    scope1_tco2e: Optional[float] = None
    scope2_tco2e_market: Optional[float] = None
    scope2_tco2e_location: Optional[float] = None
    scope3_tco2e: Optional[float] = None
    scope1_2_verified: bool = False
    sbti_validated: bool = False
    target_year: Optional[int] = None
    baseline_year: Optional[int] = None
    target_pct_reduction: Optional[float] = None
    net_zero_target_year: Optional[int] = None
    offset_based_claims: Optional[str] = None
    assurance_level: Optional[str] = None
    assurance_provider: Optional[str] = None
    methodology_version: Optional[str] = None
    raw_record: Optional[Dict[str, Any]] = None


@dataclass
class CompanyClaim:
    company_id: str
    claim_text: str
    claim_type: str
    verdict: str = "unverified"
    evidence_url: Optional[str] = None
    flag_reason: Optional[str] = None
    methodology_version: Optional[str] = None
