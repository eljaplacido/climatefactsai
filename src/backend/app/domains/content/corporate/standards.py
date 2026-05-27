"""Corporate sustainability reporting standards — Stage 5 / M6.

Five globally-recognized standards the platform checks corporate
sustainability claims against. Each standard has:
  - jurisdiction / scope (who it applies to)
  - mandatory disclosure points (what must be reported)
  - heuristic checks the in-platform adjudicator can run against
    company disclosures and / or claim text

User framing: "let's say we should aim for at least 5 most globally
recognized or now relevant corporate sustainability / climate
reporting standards. Besides the ready made given feed, there should
be an option to suggest a company to be analyzed (for advanced users)
and ask to analyze company report ... for verifying company x's
climate claims, get scoring and to which compliance standards etc.
they match."

This module is the data substrate. The adjudicator (corporate.analyzer)
imports STANDARDS and emits per-standard verdicts.
"""

from __future__ import annotations

from typing import Any


# Each standard is a dict so we can hot-swap a YAML loader later.
STANDARDS: list[dict[str, Any]] = [
    {
        "id": "CSRD",
        "name": "Corporate Sustainability Reporting Directive",
        "jurisdiction": "EU",
        "effective_from": "2024-01-01",
        "scope": (
            "Large EU companies, EU-listed companies (incl. non-EU subsidiaries "
            "meeting size thresholds), and non-EU groups with significant EU "
            "turnover. Phased rollout 2024-2028."
        ),
        "mandatory_disclosure": [
            "Scope 1 absolute emissions",
            "Scope 2 absolute emissions (location- AND market-based)",
            "Scope 3 absolute emissions across material categories",
            "Transition plan aligned with 1.5°C pathway",
            "Climate-related physical AND transition risk assessment",
            "Climate-related opportunities",
            "Third-party limited assurance (mandatory from FY2024)",
        ],
        "heuristic_checks": {
            "requires_scope1_2_3": True,
            "requires_assurance": True,
            "requires_15_alignment": True,
            "requires_double_materiality": True,
        },
        "evidence_url": "https://eur-lex.europa.eu/eli/dir/2022/2464/oj",
    },
    {
        "id": "SBTi",
        "name": "Science Based Targets initiative",
        "jurisdiction": "Global (voluntary)",
        "effective_from": "2015-01-01",
        "scope": (
            "Voluntary corporate target-setting initiative validated by the "
            "SBTi secretariat. Operates at near-term (5-10y) and net-zero "
            "horizons."
        ),
        "mandatory_disclosure": [
            "Near-term target (5-10y, validated)",
            "Net-zero target (by 2050 at latest)",
            "Scope 1+2 covered",
            "Scope 3 covered when ≥40% of total emissions",
            "Targets aligned with 1.5°C (well-below 2°C minimum)",
            "Annual progress reporting against baseline",
        ],
        "heuristic_checks": {
            "requires_validated_target": True,
            "requires_scope3_when_material": True,
            "rejects_offset_only_paths": True,
        },
        "evidence_url": "https://sciencebasedtargets.org/",
    },
    {
        "id": "TCFD",
        "name": "Task Force on Climate-related Financial Disclosures",
        "jurisdiction": "Global (recommendations); UK / NZ / JP / SG mandatory",
        "effective_from": "2017-06-01",
        "scope": (
            "Voluntary framework adopted by 4,000+ organisations; mandatory "
            "for UK premium listed (FY2022) and Japan Prime Market (FY2022). "
            "Largely subsumed by ISSB IFRS S2 going forward."
        ),
        "mandatory_disclosure": [
            "Governance (board oversight + management role on climate)",
            "Strategy (climate risks/opps + scenario analysis incl. 2°C)",
            "Risk management (identifying + assessing + integrating climate risk)",
            "Metrics & targets (Scope 1+2+3 + risk-aligned KPIs)",
        ],
        "heuristic_checks": {
            "requires_scenario_analysis": True,
            "requires_governance_disclosure": True,
            "requires_4_pillars": True,
        },
        "evidence_url": "https://www.fsb-tcfd.org/recommendations/",
    },
    {
        "id": "IFRS_S2",
        "name": "IFRS S2 Climate-related Disclosures",
        "jurisdiction": "Global (ISSB) — adoption pending per-country",
        "effective_from": "2024-01-01",
        "scope": (
            "ISSB-issued global baseline for climate disclosures. Adopted or "
            "in adoption: UK, EU (interoperable via CSRD), Singapore, Japan, "
            "Canada, Australia, Brazil, China (ongoing). Builds on TCFD."
        ),
        "mandatory_disclosure": [
            "Scope 1+2+3 emissions (with FY2025 Scope 3 transition relief)",
            "Climate-related risks AND opportunities",
            "Scenario analysis with at least one 2°C-or-lower scenario",
            "Industry-specific metrics (SASB-based)",
            "Capital expenditure aligned with transition plans",
            "Internal carbon prices used in decision-making",
        ],
        "heuristic_checks": {
            "requires_scope1_2_3": True,
            "requires_scenario_analysis": True,
            "requires_industry_metrics": True,
            "subsumes_tcfd": True,
        },
        "evidence_url": "https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/",
    },
    {
        "id": "GRI",
        "name": "Global Reporting Initiative Standards",
        "jurisdiction": "Global (voluntary, multi-stakeholder)",
        "effective_from": "2016-01-01",
        "scope": (
            "World's most widely-used voluntary sustainability reporting "
            "standard (used by ~73% of N100 companies). Multi-stakeholder "
            "scope: economic, environmental, social impacts."
        ),
        "mandatory_disclosure": [
            "GRI 305 (Emissions): Scope 1, 2, 3 absolute emissions + intensity",
            "GRI 305-5: GHG emissions reduction initiatives + achieved reductions",
            "GRI 302 (Energy): consumption inside + outside the organisation",
            "GRI 201-2: financial implications of climate change",
            "Material topics determined via stakeholder + impact analysis",
        ],
        "heuristic_checks": {
            "requires_scope1_2_3": True,
            "requires_materiality_analysis": True,
            "covers_broader_esg": True,
        },
        "evidence_url": "https://www.globalreporting.org/standards/",
    },
]

STANDARDS_BY_ID: dict[str, dict] = {s["id"]: s for s in STANDARDS}


def assess_disclosure_against_standards(disclosures: list[dict]) -> list[dict]:
    """Heuristic per-standard assessment of a company's disclosures.

    Lightweight pattern matching for the MVP — checks which mandatory
    disclosure points are present in the disclosure rows. The full
    machine-readable mapping is on the M6 roadmap; this gets the
    UI surface working with reasonable signal.

    Returns a list of per-standard records:
      { id, name, jurisdiction, status: 'aligned' | 'partial' | 'gap' | 'unknown',
        covered_points: [...], missing_points: [...], evidence_url: ... }
    """
    has_scope1 = any(d.get("scope1_tco2e") is not None for d in disclosures)
    has_scope2 = any(
        d.get("scope2_tco2e_market") is not None or d.get("scope2_tco2e_location") is not None
        for d in disclosures
    )
    has_scope3 = any(d.get("scope3_tco2e") is not None for d in disclosures)
    has_assurance = any(
        d.get("assurance_level") and d.get("assurance_level") not in ("none", "limited_neg")
        for d in disclosures
    )
    sbti_validated = any(d.get("sbti_validated") for d in disclosures)
    has_target = any(
        d.get("target_year") and d.get("target_pct_reduction")
        for d in disclosures
    )
    has_net_zero = any(d.get("net_zero_target_year") for d in disclosures)
    has_offsets = any(d.get("offset_based_claims") for d in disclosures)

    out: list[dict] = []
    for s in STANDARDS:
        sid = s["id"]
        covered: list[str] = []
        missing: list[str] = []
        if sid == "CSRD":
            (covered if has_scope1 else missing).append("Scope 1 emissions")
            (covered if has_scope2 else missing).append("Scope 2 (location + market)")
            (covered if has_scope3 else missing).append("Scope 3 across categories")
            (covered if has_target else missing).append("Transition plan / target")
            (covered if has_assurance else missing).append("Third-party assurance")
        elif sid == "SBTi":
            (covered if sbti_validated else missing).append("SBTi-validated target")
            (covered if has_scope1 and has_scope2 else missing).append("Scope 1+2 covered")
            (covered if has_scope3 else missing).append("Scope 3 covered")
            (covered if has_net_zero else missing).append("Net-zero target year set")
            if has_offsets:
                missing.append("Avoid offset-only pathways (offset claims flagged)")
            else:
                covered.append("No offset-only pathway claims detected")
        elif sid == "TCFD":
            (covered if has_target or has_net_zero else missing).append("Metrics & targets")
            (covered if has_scope1 and has_scope2 and has_scope3 else missing).append(
                "Scope 1+2+3 metrics"
            )
            missing.append("Governance disclosure (not in structured disclosure data)")
            missing.append("Scenario analysis (not in structured disclosure data)")
        elif sid == "IFRS_S2":
            (covered if has_scope1 and has_scope2 else missing).append("Scope 1+2 emissions")
            (covered if has_scope3 else missing).append("Scope 3 emissions")
            (covered if has_target else missing).append("Transition-aligned targets")
            missing.append("Scenario analysis (≥1 2°C-or-lower) — needs report parse")
            missing.append("Industry-specific (SASB) metrics — needs report parse")
        elif sid == "GRI":
            (covered if has_scope1 else missing).append("GRI 305-1 Scope 1")
            (covered if has_scope2 else missing).append("GRI 305-2 Scope 2")
            (covered if has_scope3 else missing).append("GRI 305-3 Scope 3")
            (covered if has_target else missing).append("GRI 305-5 reduction initiatives")
        # Compute status
        total = len(covered) + len(missing)
        if total == 0:
            status = "unknown"
        elif len(missing) == 0:
            status = "aligned"
        elif len(covered) == 0:
            status = "gap"
        elif len(covered) >= len(missing):
            status = "partial"
        else:
            status = "partial"
        out.append({
            "id": sid,
            "name": s["name"],
            "jurisdiction": s["jurisdiction"],
            "status": status,
            "covered_points": covered,
            "missing_points": missing,
            "evidence_url": s["evidence_url"],
        })
    return out
