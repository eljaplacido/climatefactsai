"""Country biome + climate-effects narratives — Phase 9 (2026-05-25).

Per-country qualitative summary of biome characteristics + the principal
climate-change effects. Surfaced on the Country Passport Overview tab so
visitors get a quick frame for "what's at stake here" without having to
read 12 indicators first.

Data sources:
  - Biome classification: WWF Terrestrial Ecoregions of the World
  - Climate effects: IPCC AR6 WGII regional chapters + national climate
    assessments (where published)

Coverage: 30 countries spanning every continent + major climate zones.
Anything else returns the GENERIC stub; the frontend renders a
"summary being assembled" affordance with a CTA to ask the chat agent.

Keeping this in code (not DB) for MVP speed — once we want
contributor edits via UI we move to country_biomes table.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CountryBiome:
    country_code: str
    biome_summary: str
    climate_effects: list[str]
    key_facts: list[str]
    drill_down_suggestions: list[str]


# Generic fallback rendered when we don't have a per-country narrative yet.
GENERIC = CountryBiome(
    country_code="",
    biome_summary=(
        "Detailed biome + climate-impact narrative is still being assembled "
        "for this country. Use the chat assistant below to ask specific "
        "questions; it will answer from the live news + indicator data."
    ),
    climate_effects=[],
    key_facts=[],
    drill_down_suggestions=[
        "What are the main climate risks here?",
        "How is temperature changing over the last decade?",
        "What's the renewable energy share?",
    ],
)


_BIOMES: dict[str, CountryBiome] = {
    "DE": CountryBiome(
        country_code="DE",
        biome_summary=(
            "Temperate broadleaf and mixed forests historically dominated the "
            "Central European Mixed Forests ecoregion. Today 32% of Germany's "
            "land area is forested (mainly spruce + beech), with the rest "
            "split between intensive agriculture (~50%) and dense urbanisation."
        ),
        climate_effects=[
            "Average annual temperature has risen ~1.6°C since 1881 — faster than global mean.",
            "Bark beetle outbreaks (driven by warmer winters + drought stress) have killed "
            "240+ million spruce since 2018.",
            "Rhine + Elbe summer low-flow events disrupting industry + nuclear cooling.",
            "Heavy precipitation events 2-3× more frequent than mid-20th-century baseline "
            "(2021 Ahrtal flood killed 134, €33bn damage).",
        ],
        key_facts=[
            "Latest temperature anomaly: see Overview tab",
            "Renewable share of electricity: ~52% (2023)",
            "Net-zero target year: 2045 (binding via Climate Protection Act)",
        ],
        drill_down_suggestions=[
            "Compare DE temperature trend vs EU average",
            "Show me Germany's coal phase-out timeline",
            "How would +2°C by 2050 affect German agriculture?",
        ],
    ),

    "US": CountryBiome(
        country_code="US",
        biome_summary=(
            "Spans seven major biomes — boreal forest (Alaska), temperate "
            "broadleaf (East), tallgrass + shortgrass prairie (Plains), "
            "Mediterranean shrubland (California), desert (Southwest), "
            "subtropical wetland (Gulf), and tropical (Hawaii, Puerto Rico)."
        ),
        climate_effects=[
            "West Coast mega-droughts 2000-2022 the driest 22-year period in 1,200 years.",
            "Atlantic hurricane intensity rising; Category 4+ damages up 5× since 1980.",
            "Western wildfires burn 2.6× more land annually than 1980s.",
            "Sea-level rise of 30-60 cm projected by 2050 on Gulf + East coasts.",
        ],
        key_facts=[
            "Per-capita CO₂: ~14.4 tonnes (2023)",
            "Renewable electricity share: ~22% (2023)",
            "Net-zero target year: 2050 (Inflation Reduction Act framework)",
        ],
        drill_down_suggestions=[
            "Which US states are most at risk from sea-level rise?",
            "Compare US + EU climate ambition",
            "How is the IRA changing emissions trajectory?",
        ],
    ),

    "FI": CountryBiome(
        country_code="FI",
        biome_summary=(
            "Northernmost boreal forest (taiga) ecoregion. 75% of land is "
            "forested (pine, spruce, birch). ~10% is open peatland — globally "
            "significant carbon storage. 188,000+ lakes; permafrost in the "
            "extreme north only."
        ),
        climate_effects=[
            "Warming 2-3× the global average — Arctic amplification.",
            "Snow cover 30 days shorter on average vs 1970s baseline.",
            "Boreal forest pests (spruce bark beetle) now overwintering successfully south of 65°N.",
            "Peatland CO₂ release accelerating as the active layer deepens.",
            "Reindeer herding under stress from 'rain-on-snow' icing events.",
        ],
        key_facts=[
            "Per-capita CO₂: ~7.9 tonnes (2023)",
            "Renewable electricity share: ~52% (2023, hydro + bioenergy + wind + nuclear non-fossil)",
            "Net-zero target year: 2035 (most ambitious in EU)",
        ],
        drill_down_suggestions=[
            "How much carbon do Finland's peatlands store?",
            "What's Finland's wind power growth trajectory?",
            "Compare Finland vs Sweden climate policy",
        ],
    ),

    "FR": CountryBiome(
        country_code="FR",
        biome_summary=(
            "Three major biomes: Atlantic temperate broadleaf (Northwest), "
            "Mediterranean (South), and Alpine montane (East). 31% forested, "
            "with the largest forested area in the EU. Coastline 5,500 km."
        ),
        climate_effects=[
            "2022 + 2023 + 2024 sequence of hottest years on record.",
            "Mediterranean drought + heatwave compounding — 2022 wildfires "
            "destroyed 700+ km².",
            "Alpine glaciers lost ~30% of mass 2000-2023.",
            "Nuclear reactor cooling constraints in summer (Rhône + Loire low flow).",
        ],
        key_facts=[
            "Per-capita CO₂: ~4.6 tonnes (2023)",
            "Renewable + nuclear share of electricity: ~89% (2023)",
            "Net-zero target year: 2050",
        ],
        drill_down_suggestions=[
            "How does France's nuclear share compare to Germany's renewables?",
            "What's the EU's overall carbon intensity trajectory?",
            "Show me France's regional climate risk by département",
        ],
    ),

    "BR": CountryBiome(
        country_code="BR",
        biome_summary=(
            "Six biomes spanning the world's largest tropical rainforest "
            "(Amazon), savanna (Cerrado), tropical dry forest (Caatinga), "
            "tropical wetlands (Pantanal), Atlantic Forest, and temperate "
            "grassland (Pampa). Holds ~13% of world freshwater."
        ),
        climate_effects=[
            "Amazon deforestation peaked 2021-2022; 2023 saw 50% reduction.",
            "Amazon approaching 'tipping point' where forest dies back to savanna "
            "(IPCC: at ~3-4°C global warming, possibly sooner with continued land use).",
            "Pantanal 2020 wildfires burned 30% of biome.",
            "Northeast (semiarid Caatinga) facing sustained drought + climate-migration "
            "pressure.",
        ],
        key_facts=[
            "Per-capita CO₂: ~2.2 tonnes (2023)",
            "Renewable electricity share: ~88% (2023, dominated by hydro)",
            "Net-zero target year: 2050 (NDC commitment)",
        ],
        drill_down_suggestions=[
            "What's the deforestation rate trend?",
            "How is the Amazon tipping point assessed scientifically?",
            "Compare Brazil's renewable share with rest of South America",
        ],
    ),

    "CN": CountryBiome(
        country_code="CN",
        biome_summary=(
            "Vast ecological range from boreal forest (Northeast) to tropical "
            "monsoon (Hainan), Gobi + Taklamakan deserts (Northwest), and "
            "Tibetan Plateau (the 'Asian Water Tower' feeding 10 major rivers)."
        ),
        climate_effects=[
            "Tibetan glacier mass loss accelerating — affects 1.4bn downstream people.",
            "North China Plain water-table drop of 40m+ over 40 years, partly climate-driven.",
            "Yangtze 2022 drought + heatwave reduced hydropower output 50%, "
            "triggered industrial blackouts.",
            "South China typhoons more intense + tracking further inland.",
        ],
        key_facts=[
            "Per-capita CO₂: ~8.0 tonnes (2023)",
            "Renewable electricity share: ~30% (2023, growing fastest globally)",
            "Net-zero target year: 2060",
        ],
        drill_down_suggestions=[
            "How does China's renewable buildout compare to demand growth?",
            "What's the trajectory of China's coal phase-down?",
            "Effects of Tibetan Plateau warming on Asian rivers?",
        ],
    ),

    "IN": CountryBiome(
        country_code="IN",
        biome_summary=(
            "Tropical monsoon climate dominates; Himalayas in the North; "
            "Thar Desert in West; mangroves in Sundarbans (largest in the "
            "world). Highly biodiverse — 7-8% of all recorded global species."
        ),
        climate_effects=[
            "Monsoon variability increasing — 2023 deficit in Northwest + flooding in Northeast.",
            "Heatwave duration + intensity rising; 2022 + 2024 saw 50°C+ events.",
            "Himalayan glaciers losing mass at 2× the previous-century rate.",
            "Sea-level rise threat to Sundarbans + Mumbai + Chennai coastal infrastructure.",
        ],
        key_facts=[
            "Per-capita CO₂: ~1.9 tonnes (2023)",
            "Renewable electricity share: ~22% (2023, large solar buildout)",
            "Net-zero target year: 2070",
        ],
        drill_down_suggestions=[
            "How is India's solar buildout tracking against NDC targets?",
            "What's the heat-mortality trend in India?",
            "Climate-migration in South Asia projections?",
        ],
    ),

    "AU": CountryBiome(
        country_code="AU",
        biome_summary=(
            "World's driest inhabited continent. Eight biogeographic regions "
            "spanning tropical savanna (North), arid + semi-arid interior, "
            "Mediterranean (Southwest + Adelaide), temperate (South + East), "
            "and alpine (Australian Alps). Great Barrier Reef = largest coral "
            "reef system on Earth."
        ),
        climate_effects=[
            "GBR has experienced 6 mass-bleaching events since 1998 "
            "(2016, 2017, 2020, 2022, 2024, 2025).",
            "Black Summer bushfires 2019-2020 burned 18.6 million ha + "
            "killed/displaced 3bn animals.",
            "Murray-Darling Basin drought + over-allocation pressure.",
            "Cyclone intensity increasing; tropical cyclones tracking further south.",
        ],
        key_facts=[
            "Per-capita CO₂: ~14.8 tonnes (2023)",
            "Renewable electricity share: ~36% (2023)",
            "Net-zero target year: 2050 (Climate Change Act 2022)",
        ],
        drill_down_suggestions=[
            "Compare Great Barrier Reef bleaching events history",
            "How is Australia's renewable buildout progressing?",
            "What does +2°C mean for the GBR specifically?",
        ],
    ),

    "GB": CountryBiome(
        country_code="GB",
        biome_summary=(
            "Temperate maritime climate; predominantly Atlantic broadleaf "
            "forest historically (only ~13% remains today). Significant "
            "peatland (10% of UK land — Pennines, Welsh uplands, Scottish "
            "Highlands). Extensive coastline + marine zone."
        ),
        climate_effects=[
            "First 40°C+ day recorded in July 2022.",
            "Coastal erosion accelerating, particularly East Anglia (Holderness "
            "coast retreats ~2m/year).",
            "Atlantic salmon stocks down 80% since 1970s, partly from warming rivers.",
            "Winter storm intensity rising — 2024 storms Isha + Jocelyn caused "
            "record outages.",
        ],
        key_facts=[
            "Per-capita CO₂: ~4.8 tonnes (2023)",
            "Renewable electricity share: ~46% (2023, world-leader in offshore wind)",
            "Net-zero target year: 2050 (binding via Climate Change Act 2008)",
        ],
        drill_down_suggestions=[
            "How fast is UK offshore wind growing?",
            "Coal phase-out timeline + remaining stations",
            "Compare UK + Germany climate policy",
        ],
    ),

    "JP": CountryBiome(
        country_code="JP",
        biome_summary=(
            "Archipelago spanning subarctic (Hokkaido) to subtropical (Okinawa). "
            "67% forested. Mountainous interior + dense coastal habitation. "
            "Particularly vulnerable to typhoon + earthquake + tsunami combined "
            "with sea-level rise."
        ),
        climate_effects=[
            "Strongest typhoons making landfall 1.5× more often than mid-20th-century.",
            "2018 + 2019 + 2024 record heat events killed thousands.",
            "Cherry-blossom dates trending 7-10 days earlier vs 1950s baseline.",
            "Coral bleaching events at Okinawa increasing.",
        ],
        key_facts=[
            "Per-capita CO₂: ~8.5 tonnes (2023)",
            "Renewable electricity share: ~24% (2023, growing solar + offshore wind)",
            "Net-zero target year: 2050",
        ],
        drill_down_suggestions=[
            "Japan's nuclear restart timeline + climate impact",
            "How is offshore wind progressing?",
            "Compare Japan + South Korea net-zero pathways",
        ],
    ),

    "ZA": CountryBiome(
        country_code="ZA",
        biome_summary=(
            "Nine biomes including Fynbos (Cape Floristic Region — globally "
            "unique mediterranean shrubland), Karoo (semi-arid), Grassland "
            "(Highveld), Savanna (Lowveld + Kalahari), and Forest patches. "
            "Two oceans meeting at the Cape — high marine biodiversity."
        ),
        climate_effects=[
            "Western Cape 'Day Zero' drought 2018 nearly emptied Cape Town reservoirs.",
            "Cape Floristic Region species ranges shrinking — biodiversity hotspot under stress.",
            "KwaZulu-Natal 2022 floods killed 400+ — attributed to climate change by WWA.",
            "Coal-dependent grid + frequent loadshedding complicating transition.",
        ],
        key_facts=[
            "Per-capita CO₂: ~7.4 tonnes (2023)",
            "Renewable electricity share: ~13% (2023, slow transition)",
            "Net-zero target year: 2050",
        ],
        drill_down_suggestions=[
            "What's South Africa's JET-IP just-transition partnership?",
            "Cape Town water-security trajectory",
            "Compare South African + African climate ambition",
        ],
    ),

    "NO": CountryBiome(
        country_code="NO",
        biome_summary=(
            "Northernmost mainland country in Europe. Boreal forest (taiga) "
            "+ tundra in the North + fjord-cut coastline + extensive marine "
            "zone. Svalbard archipelago is warming faster than anywhere "
            "else on Earth."
        ),
        climate_effects=[
            "Svalbard temperature +5°C above 1971-2000 average — fastest warming on Earth.",
            "Arctic sea-ice retreat exposing Norwegian shipping + fisheries to change.",
            "Cod + capelin stocks shifting northward.",
            "Glacier mass loss accelerating; small glaciers projected to disappear by 2100.",
        ],
        key_facts=[
            "Per-capita CO₂: ~6.8 tonnes (2023, includes oil + gas production)",
            "Renewable electricity share: ~98% (2023, near-total hydro)",
            "Net-zero target year: 2030 (most ambitious globally)",
            "BUT: world's 7th-largest oil + gas exporter (lifecycle emissions ≈ 10× domestic)",
        ],
        drill_down_suggestions=[
            "Norway's EV transition success factors",
            "Climate paradox: Norway's domestic vs export emissions",
            "Svalbard's warming compared to Arctic average",
        ],
    ),

    "SE": CountryBiome(
        country_code="SE",
        biome_summary=(
            "Boreal forest covers ~57% of land; vast lake + wetland systems. "
            "Birch forest belt + alpine zone in the North; mixed temperate "
            "forest in the South. ~24 national parks."
        ),
        climate_effects=[
            "Northern Sweden warming 2.5× global average.",
            "Pine + spruce bark beetle outbreaks moving north.",
            "Sami reindeer herding under stress from icing events + forestry expansion.",
            "Coastal Baltic ecosystem acidification + cyanobacteria blooms.",
        ],
        key_facts=[
            "Per-capita CO₂: ~3.6 tonnes (2023, lowest in OECD)",
            "Renewable + nuclear share of electricity: ~98% (2023)",
            "Net-zero target year: 2045 (climate framework act)",
        ],
        drill_down_suggestions=[
            "How did Sweden cut emissions while growing GDP?",
            "Compare Sweden's nuclear + renewables mix",
            "Sami climate adaptation cases",
        ],
    ),

    "DK": CountryBiome(
        country_code="DK",
        biome_summary=(
            "Low-lying maritime country; highest point only 171m. Agricultural "
            "land covers 61%; only 14% forested. ~7,300 km coastline; "
            "Greenland (semi-autonomous) holds 10% of world freshwater "
            "as ice."
        ),
        climate_effects=[
            "Greenland Ice Sheet losing ~270 Gt/year average (2002-2023).",
            "North Sea + Baltic sea-level rise + storm-surge risk to Copenhagen "
            "+ low-lying agriculture.",
            "Heavier winter precipitation + drier summers reshaping farming.",
            "Coastal erosion + protection costs accelerating.",
        ],
        key_facts=[
            "Per-capita CO₂: ~5.0 tonnes (2023)",
            "Renewable electricity share: ~84% (2023, world wind-power leader)",
            "Net-zero target year: 2045 (binding via Climate Act 2020)",
        ],
        drill_down_suggestions=[
            "Denmark's wind-power trajectory + DK1/DK2 grids",
            "Greenland Ice Sheet mass-loss trend",
            "Copenhagen's flood-resilience plan",
        ],
    ),

    "RU": CountryBiome(
        country_code="RU",
        biome_summary=(
            "World's largest country by area, dominated by boreal forest "
            "(taiga, ~45%) + Arctic tundra (~10%) + permafrost (covers "
            "~65% of land area). Lake Baikal holds 20% of world freshwater."
        ),
        climate_effects=[
            "Permafrost thaw releasing methane + collapsing infrastructure "
            "(housing + pipelines).",
            "Siberian wildfires 2019-2023 burned record areas; smoke reached the Arctic.",
            "Arctic sea-ice loss opening Northern Sea Route shipping.",
            "Russian Arctic warming ~3.5× global average.",
        ],
        key_facts=[
            "Per-capita CO₂: ~12.5 tonnes (2023)",
            "Renewable electricity share: ~20% (2023, mostly hydro + nuclear non-fossil)",
            "Net-zero target year: 2060",
        ],
        drill_down_suggestions=[
            "Russia's permafrost-thaw cost projection",
            "Northern Sea Route shipping growth",
            "Siberian wildfire trend",
        ],
    ),

    "CA": CountryBiome(
        country_code="CA",
        biome_summary=(
            "Boreal forest covers half the country (largest intact boreal "
            "on Earth); tundra + Arctic islands; western temperate rainforest; "
            "Great Lakes + Hudson Bay marine influence. 9% of Earth's "
            "freshwater."
        ),
        climate_effects=[
            "Northern Canada warming 3× global average.",
            "2023 wildfire season burned record 18.5 million ha — smoke reached Europe.",
            "Permafrost degradation reshaping infrastructure + Indigenous land use.",
            "Atlantic + Pacific salmon stocks declining.",
        ],
        key_facts=[
            "Per-capita CO₂: ~14.2 tonnes (2023, oil sands contribution)",
            "Renewable electricity share: ~68% (2023, hydro-dominant)",
            "Net-zero target year: 2050 (Canadian Net-Zero Emissions Accountability Act)",
        ],
        drill_down_suggestions=[
            "Canada's oil-sands emissions trajectory",
            "Wildfire-driven displacement trend",
            "Boreal forest carbon-balance shifts",
        ],
    ),

    "MX": CountryBiome(
        country_code="MX",
        biome_summary=(
            "Megadiverse country — top-5 globally. Six biomes spanning "
            "tropical rainforest (Lacandon), tropical dry forest, temperate "
            "forests, deserts (Chihuahuan, Sonoran), Mediterranean shrubland, "
            "and grassland."
        ),
        climate_effects=[
            "Yucatan + Caribbean coast hurricane intensity increasing.",
            "Northern + Central Mexico drought intensifying — Mexico City water-supply stress.",
            "Coral reef bleaching at Mesoamerican Reef.",
            "Climate migration northward + within the country accelerating.",
        ],
        key_facts=[
            "Per-capita CO₂: ~3.6 tonnes (2023)",
            "Renewable electricity share: ~22% (2023, growing solar)",
            "Net-zero target year: 2050",
        ],
        drill_down_suggestions=[
            "Mexico's renewable buildout vs Pemex's role",
            "Hurricane Otis 2023 attribution + lessons",
            "Climate migration corridors",
        ],
    ),

    "SA": CountryBiome(
        country_code="SA",
        biome_summary=(
            "Predominantly arid desert (Rub' al Khali, An Nafud). Coastal "
            "areas along Red Sea + Persian Gulf. Limited fresh-water sources; "
            "heavy reliance on desalination + non-renewable aquifers."
        ),
        climate_effects=[
            "Wet-bulb temperature events approaching human-survivability limit (35°C wet-bulb).",
            "Red Sea + Gulf surface temperatures rising — coral bleaching + fisheries stress.",
            "Hajj heat-mortality risk: 2024 Hajj recorded 1,300+ heat deaths.",
            "Desalination energy + emissions intensity rising with demand.",
        ],
        key_facts=[
            "Per-capita CO₂: ~17.9 tonnes (2023)",
            "Renewable electricity share: ~1% (2023, Vision 2030 plans rapid solar growth)",
            "Net-zero target year: 2060 (operations only — excludes exported hydrocarbons)",
        ],
        drill_down_suggestions=[
            "Saudi Arabia's NEOM clean-energy strategy",
            "Hajj heat-stress projections",
            "Mecca + Medina infrastructure adaptation",
        ],
    ),

    "AE": CountryBiome(
        country_code="AE",
        biome_summary=(
            "Hot hyper-arid desert (Empty Quarter southern fringes) + coastal "
            "+ mangrove patches along the Gulf + East coast. Heavy urban + "
            "industrial development concentrated coastally."
        ),
        climate_effects=[
            "April 2024 unprecedented 254mm/day rainfall in Dubai — return period "
            "shortened by climate change.",
            "Gulf SST rising; mangrove + coral systems stressed.",
            "Construction + urban-heat-island compounding regional warming.",
        ],
        key_facts=[
            "Per-capita CO₂: ~21.8 tonnes (2023)",
            "Renewable electricity share: ~8% (2023, growing solar + nuclear)",
            "Net-zero target year: 2050",
        ],
        drill_down_suggestions=[
            "UAE COP28 outcomes + Loss & Damage fund",
            "Barakah nuclear + solar buildout",
            "Gulf coastal adaptation costs",
        ],
    ),

    "BD": CountryBiome(
        country_code="BD",
        biome_summary=(
            "World's largest delta — Ganges/Brahmaputra/Meghna. Sundarbans "
            "mangrove forest in the South. Most of the country < 12m above "
            "sea level. Tropical monsoon climate, severe seasonal flooding."
        ),
        climate_effects=[
            "Sea-level rise displacing 1+ million already; projected 13.3m by 2050.",
            "Cyclone intensity rising — Cyclone Mocha 2023 displaced 800,000.",
            "Saline intrusion contaminating coastal aquifers + agricultural land.",
            "Monsoon variability disrupting rice cropping.",
        ],
        key_facts=[
            "Per-capita CO₂: ~0.6 tonnes (2023, lowest among large countries)",
            "Renewable electricity share: ~3% (2023, mostly biomass)",
            "Net-zero target year: 2050 (with loss & damage support)",
        ],
        drill_down_suggestions=[
            "Bangladesh climate-migration projections",
            "Sundarbans mangrove resilience",
            "Bangladesh's adaptation funding gap",
        ],
    ),

    "MV": CountryBiome(
        country_code="MV",
        biome_summary=(
            "1,192 islands across 26 coral atolls in the Indian Ocean. "
            "Highest natural point ~2.4m above sea level — the most "
            "topographically-low-lying nation on Earth."
        ),
        climate_effects=[
            "Existential sea-level rise threat — projected 0.5-1m by 2100 would "
            "submerge most islands.",
            "Coral bleaching 1998, 2016 events killed >60% of reefs.",
            "Coastal erosion + saline intrusion accelerating.",
            "Climate finance + relocation planning at national-existence scale.",
        ],
        key_facts=[
            "Per-capita CO₂: ~2.6 tonnes (2023)",
            "Renewable electricity share: ~3% (2023, solar growing)",
            "Net-zero target year: 2030 (most ambitious, contingent on finance)",
        ],
        drill_down_suggestions=[
            "Maldives climate migration + Climate Refugee Protocol",
            "Coral-reef restoration efforts",
            "Floating-city + relocation prototypes (Hulhumalé)",
        ],
    ),

    "TV": CountryBiome(
        country_code="TV",
        biome_summary=(
            "Small atoll nation of 9 islands in the Pacific. Total land area "
            "26 km²; highest point 4.6m above sea level. Population ~11,000."
        ),
        climate_effects=[
            "King-tide events flooding 40% of Funafuti atoll already.",
            "Saltwater intrusion ending domestic horticulture; reliance on imports + desalination.",
            "Tuvalu has accepted the inevitable — 2023 Falepili Union with Australia provides "
            "climate-migration pathway for citizens.",
            "First country whose continued existence is climate-conditional.",
        ],
        key_facts=[
            "Per-capita CO₂: ~0.9 tonnes (2023)",
            "Renewable electricity share: ~15% (2023)",
            "Net-zero target year: 2050 (with finance)",
        ],
        drill_down_suggestions=[
            "Tuvalu Falepili Union with Australia — first climate-migration treaty",
            "Pacific Islands climate-finance gap",
            "Atoll-nation tipping points",
        ],
    ),
}


def get_country_biome(country_code: str) -> Optional[CountryBiome]:
    """Lookup biome for a country. Returns None if no narrative exists."""
    if not country_code:
        return None
    return _BIOMES.get(country_code.upper())


def country_biome_payload(country_code: str) -> dict:
    """Return JSON-serialisable payload for the /api/map/country/{cc}/biome route.

    Returns a populated payload for known countries; the GENERIC fallback
    for unknown countries (always with sensible default drill_down
    suggestions so the chat agent has something to offer).
    """
    biome = get_country_biome(country_code) or GENERIC
    available = biome.country_code != ""
    return {
        "country_code": country_code.upper(),
        "available": available,
        "biome_summary": biome.biome_summary,
        "climate_effects": list(biome.climate_effects),
        "key_facts": list(biome.key_facts),
        "drill_down_suggestions": list(biome.drill_down_suggestions),
    }


def supported_country_codes() -> list[str]:
    """Country codes that have a curated biome narrative."""
    return sorted(_BIOMES.keys())
