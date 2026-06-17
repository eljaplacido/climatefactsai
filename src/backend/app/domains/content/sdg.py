"""UN Sustainable Development Goals taxonomy + tagger (Stage 6 / M7).

User framing: "platform entirely misses insights on progress towards
UN's sustainable development goals, which I believe should span all
categories of analysis; Related to articles, research and company
climate trackers."

This module provides:
  - Canonical SDG taxonomy (17 goals + colours + descriptions)
  - tag_text() — keyword-based tagger that returns the SDG goal_ids a
    text snippet most likely relates to, with a per-goal confidence
    (count of matched keywords / total keywords for that goal)
  - SDG_KEYWORDS — the underlying mapping (extendable)

Pure-function, no DB. Caller decides when to tag (ingest-time, on the
fly, etc.) and where to persist (sdg_tags column or sidecar table).

For climate platform purposes, SDG 13 (Climate Action) is the spine,
but most climate stories also touch SDGs 6, 7, 11, 12, 14, 15. Multi-
label tagging is the right call — an article on solar deployment in
Kenya touches 7, 9, 11, 13.
"""

from __future__ import annotations

import re


SDG_GOALS: list[dict] = [
    {"id": 1,  "title": "No Poverty",                                "color": "#E5243B", "icon": "👤"},
    {"id": 2,  "title": "Zero Hunger",                               "color": "#DDA63A", "icon": "🌾"},
    {"id": 3,  "title": "Good Health and Well-being",                "color": "#4C9F38", "icon": "❤️"},
    {"id": 4,  "title": "Quality Education",                         "color": "#C5192D", "icon": "📚"},
    {"id": 5,  "title": "Gender Equality",                           "color": "#FF3A21", "icon": "⚥"},
    {"id": 6,  "title": "Clean Water and Sanitation",                "color": "#26BDE2", "icon": "💧"},
    {"id": 7,  "title": "Affordable and Clean Energy",               "color": "#FCC30B", "icon": "⚡"},
    {"id": 8,  "title": "Decent Work and Economic Growth",           "color": "#A21942", "icon": "💼"},
    {"id": 9,  "title": "Industry, Innovation and Infrastructure",    "color": "#FD6925", "icon": "🏭"},
    {"id": 10, "title": "Reduced Inequalities",                      "color": "#DD1367", "icon": "⚖️"},
    {"id": 11, "title": "Sustainable Cities and Communities",        "color": "#FD9D24", "icon": "🏙️"},
    {"id": 12, "title": "Responsible Consumption and Production",     "color": "#BF8B2E", "icon": "♻️"},
    {"id": 13, "title": "Climate Action",                            "color": "#3F7E44", "icon": "🌍"},
    {"id": 14, "title": "Life Below Water",                          "color": "#0A97D9", "icon": "🌊"},
    {"id": 15, "title": "Life on Land",                              "color": "#56C02B", "icon": "🌳"},
    {"id": 16, "title": "Peace, Justice and Strong Institutions",     "color": "#00689D", "icon": "⚖️"},
    {"id": 17, "title": "Partnerships for the Goals",                "color": "#19486A", "icon": "🤝"},
]

SDG_BY_ID: dict[int, dict] = {g["id"]: g for g in SDG_GOALS}


# Keyword mappings — multi-label by design. Lower-case match, word-
# boundary applied at runtime. Curated for the climate-platform corpus
# (heavy on 6/7/11/12/13/14/15). Coverage of 1/4/5/10/16/17 is sparser
# because climate news rarely surfaces those primarily.
SDG_KEYWORDS: dict[int, list[str]] = {
    1:  ["poverty", "extreme poor", "vulnerable population", "informal settlement", "slum"],
    2:  ["food security", "hunger", "famine", "crop yield", "agriculture",
         "agroforestry", "smallholder", "livestock", "fisheries"],
    3:  ["public health", "air quality", "pollution health", "heat-related death",
         "vector-borne", "respiratory", "wet bulb", "mortality"],
    4:  ["climate education", "literacy", "school", "university", "training"],
    5:  ["gender", "women", "girl", "matriarchal"],
    6:  ["water", "drought", "aquifer", "wastewater", "sanitation",
         "watershed", "river basin", "groundwater"],
    7:  ["renewable", "solar", "wind", "hydropower", "hydroelectric",
         "geothermal", "biomass", "nuclear", "electricity", "grid",
         "off-grid", "battery", "energy storage", "fossil fuel",
         "coal", "oil", "natural gas", "lng", "energy access",
         "re100", "ppa"],
    8:  ["green job", "just transition", "decent work", "labor", "labour", "wage"],
    9:  ["infrastructure", "industrial", "manufacturing", "ev battery",
         "hydrogen", "carbon capture", "cement", "steel", "aluminium",
         "supply chain", "innovation", "r&d"],
    10: ["inequality", "indigenous", "marginalised", "minority"],
    11: ["city", "cities", "urban", "transport", "transit", "housing",
         "building code", "smart city", "resilient city",
         "heat island", "climate-resilient housing"],
    12: ["circular econom", "recycle", "reuse", "waste", "single-use",
         "plastic", "consumption", "production", "sustainable consumption",
         "supply chain transparency", "extended producer responsibility"],
    13: ["climate", "carbon", "emission", "ghg", "greenhouse",
         "warming", "global warming", "net zero", "net-zero", "decarbon",
         "paris agreement", "ipcc", "cop28", "cop29", "cop30", "cop31",
         "unfccc", "mitigation", "adaptation", "resilien",
         "climate finance", "loss and damage", "carbon market",
         "carbon price", "sbti", "tcfd", "ifrs s2", "csrd"],
    14: ["ocean", "sea level", "marine", "reef", "coral", "fish stock",
         "mangrove", "kelp", "blue carbon", "seabed", "high seas"],
    15: ["forest", "deforest", "rainforest", "amazon", "boreal", "savanna",
         "biodiversity", "species", "wildlife", "habitat", "conservation",
         "rewild", "reforestation", "tropical", "land use",
         "soil", "peatland", "wetland", "mangrove forest"],
    16: ["governance", "rule of law", "corruption", "transparency",
         "litigation", "court", "human rights"],
    17: ["partnership", "multi-stakeholder", "south-south", "ngo coalition",
         "development cooperation", "official development assistance",
         "climate finance pledge"],
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    # Collapse whitespace + lowercase; keep most punctuation since
    # keyword matches use word boundaries.
    return re.sub(r"\s+", " ", text).lower()


def tag_text(text: str, min_match_count: int = 1) -> list[dict]:
    """Return SDGs the text relates to, sorted by match strength.

    Each result is { goal_id, title, matched_count, total_keywords,
    confidence }. Word-boundary match so "deforest" matches
    "deforestation" but not "Forestalia".

    `min_match_count` defaults to 1 — surface any signal. Bump to 2
    when you want stricter relevance (caller's policy).
    """
    norm = _normalize_text(text)
    if not norm:
        return []

    out: list[dict] = []
    for goal_id, keywords in SDG_KEYWORDS.items():
        matched = 0
        for kw in keywords:
            kw_l = kw.lower()
            # Use word boundary on alphanumeric chars only; phrases pass
            # through `in` since `\b` doesn't work mid-phrase.
            if " " in kw_l or "-" in kw_l:
                if kw_l in norm:
                    matched += 1
            else:
                if re.search(r"\b" + re.escape(kw_l) + r"\b", norm):
                    matched += 1
        if matched >= min_match_count:
            total = len(keywords)
            out.append({
                "goal_id": goal_id,
                "title": SDG_BY_ID[goal_id]["title"],
                "color": SDG_BY_ID[goal_id]["color"],
                "icon": SDG_BY_ID[goal_id]["icon"],
                "matched_count": matched,
                "total_keywords": total,
                "confidence": round(matched / total, 3),
            })
    out.sort(key=lambda r: (r["matched_count"], r["confidence"]), reverse=True)
    return out


def tag_to_goal_ids(text: str, min_match_count: int = 1) -> list[int]:
    """Convenience — just return the goal_ids (sorted)."""
    return [r["goal_id"] for r in tag_text(text, min_match_count=min_match_count)]
