"""Country biome + Köppen-Geiger climate map — Phase 11 (2026-05-25).

Backs the new map layer (climate-zone colour fill + biome emoji
markers at country centroids). Per-country data is curated; everything
not in COUNTRY_BIOME_MAP falls through to a generic "unclassified"
marker.

Data lineage:
  - biome_type: WWF Terrestrial Ecoregions of the World, simplified
    to the 15 visually-distinct biome categories below
  - climate_zone: Köppen-Geiger primary first-letter
    (A=Tropical, B=Arid, C=Temperate, D=Continental, E=Polar)
  - emoji: chosen to read at small sizes on the map

When a country spans multiple biomes (large countries — US, CA, RU,
CN, AU), we record the DOMINANT biome by population + the dominant
climate zone. Edge nations (small islands, archipelagos) pick the
biome of the most populated atoll/island.

Used by:
  - GET /api/map/biome-overview — returns all 195 countries
  - GET /api/map/country/{cc}/biome — single country
  - Frontend MapLayerControl — "Biomes" layer renders this
"""
from __future__ import annotations



# ---------------------------------------------------------------------------
# Biome taxonomy (simplified WWF terrestrial ecoregions)
# ---------------------------------------------------------------------------

BIOME_TYPES = {
    "tropical_rainforest":     {"label": "Tropical rainforest",     "emoji": "🌴"},
    "tropical_dry_forest":     {"label": "Tropical dry forest",     "emoji": "🌳"},
    "tropical_savanna":        {"label": "Tropical savanna",        "emoji": "🦁"},
    "temperate_forest":        {"label": "Temperate broadleaf forest", "emoji": "🍂"},
    "boreal_forest":           {"label": "Boreal forest (taiga)",   "emoji": "🌲"},
    "tundra":                  {"label": "Tundra",                  "emoji": "❄️"},
    "mediterranean":           {"label": "Mediterranean shrubland", "emoji": "🫒"},
    "desert_arid":             {"label": "Hyper-arid desert",       "emoji": "🏜️"},
    "desert_semiarid":         {"label": "Semi-arid desert / steppe", "emoji": "🌵"},
    "temperate_grassland":     {"label": "Temperate grassland",     "emoji": "🌾"},
    "montane":                 {"label": "Montane / alpine",        "emoji": "⛰️"},
    "wetlands":                {"label": "Wetlands / floodplains",  "emoji": "🦆"},
    "coral_atoll":             {"label": "Coral atoll / small island", "emoji": "🪸"},
    "coastal_maritime":        {"label": "Coastal maritime",        "emoji": "🌊"},
    "polar":                   {"label": "Polar / ice sheet",       "emoji": "🐻‍❄️"},
    "unclassified":            {"label": "Unclassified",            "emoji": "📍"},
}

# Köppen-Geiger primary climate zones (first letter)
KOPPEN_ZONES = {
    "A": {"label": "Tropical",    "color": "#E76F51", "description": "Hot, humid year-round"},
    "B": {"label": "Arid",        "color": "#F4A261", "description": "Desert + steppe"},
    "C": {"label": "Temperate",   "color": "#2A9D8F", "description": "Mild winters, warm summers"},
    "D": {"label": "Continental", "color": "#264653", "description": "Cold winters, distinct seasons"},
    "E": {"label": "Polar",       "color": "#A8DADC", "description": "Tundra + ice cap"},
    "U": {"label": "Unclassified","color": "#9CA3AF", "description": "No primary classification recorded"},
}


# ---------------------------------------------------------------------------
# Per-country mapping (195 entries — UN-193 + Vatican + Taiwan)
# ---------------------------------------------------------------------------
#
# Tuple shape: (biome_type, koppen_primary)
# Both fields fall through to "unclassified" / "U" via the resolver.

COUNTRY_BIOME_MAP: dict[str, tuple[str, str]] = {
    # ── Africa ────────────────────────────────────────────────────────
    "DZ": ("desert_arid",         "B"),  # Algeria
    "AO": ("tropical_savanna",    "A"),  # Angola
    "BJ": ("tropical_savanna",    "A"),  # Benin
    "BW": ("desert_semiarid",     "B"),  # Botswana
    "BF": ("tropical_savanna",    "A"),  # Burkina Faso
    "BI": ("tropical_savanna",    "A"),  # Burundi
    "CV": ("coral_atoll",         "B"),  # Cabo Verde
    "CM": ("tropical_rainforest", "A"),  # Cameroon
    "CF": ("tropical_savanna",    "A"),  # Central African Republic
    "TD": ("desert_semiarid",     "B"),  # Chad
    "KM": ("tropical_rainforest", "A"),  # Comoros
    "CG": ("tropical_rainforest", "A"),  # Republic of the Congo
    "CD": ("tropical_rainforest", "A"),  # DR Congo
    "CI": ("tropical_rainforest", "A"),  # Côte d'Ivoire
    "DJ": ("desert_arid",         "B"),  # Djibouti
    "EG": ("desert_arid",         "B"),  # Egypt
    "GQ": ("tropical_rainforest", "A"),  # Equatorial Guinea
    "ER": ("desert_semiarid",     "B"),  # Eritrea
    "SZ": ("tropical_savanna",    "C"),  # Eswatini
    "ET": ("montane",             "B"),  # Ethiopia
    "GA": ("tropical_rainforest", "A"),  # Gabon
    "GM": ("tropical_savanna",    "A"),  # Gambia
    "GH": ("tropical_savanna",    "A"),  # Ghana
    "GN": ("tropical_savanna",    "A"),  # Guinea
    "GW": ("tropical_savanna",    "A"),  # Guinea-Bissau
    "KE": ("tropical_savanna",    "A"),  # Kenya
    "LS": ("montane",             "C"),  # Lesotho
    "LR": ("tropical_rainforest", "A"),  # Liberia
    "LY": ("desert_arid",         "B"),  # Libya
    "MG": ("tropical_rainforest", "A"),  # Madagascar
    "MW": ("tropical_savanna",    "A"),  # Malawi
    "ML": ("desert_semiarid",     "B"),  # Mali
    "MR": ("desert_arid",         "B"),  # Mauritania
    "MU": ("tropical_rainforest", "A"),  # Mauritius
    "MA": ("mediterranean",       "C"),  # Morocco
    "MZ": ("tropical_savanna",    "A"),  # Mozambique
    "NA": ("desert_arid",         "B"),  # Namibia
    "NE": ("desert_semiarid",     "B"),  # Niger
    "NG": ("tropical_savanna",    "A"),  # Nigeria
    "RW": ("montane",             "A"),  # Rwanda
    "ST": ("tropical_rainforest", "A"),  # São Tomé and Príncipe
    "SN": ("tropical_savanna",    "A"),  # Senegal
    "SC": ("tropical_rainforest", "A"),  # Seychelles
    "SL": ("tropical_rainforest", "A"),  # Sierra Leone
    "SO": ("desert_semiarid",     "B"),  # Somalia
    "ZA": ("mediterranean",       "B"),  # South Africa (Cape biome dominant by economy)
    "SS": ("tropical_savanna",    "A"),  # South Sudan
    "SD": ("desert_semiarid",     "B"),  # Sudan
    "TZ": ("tropical_savanna",    "A"),  # Tanzania
    "TG": ("tropical_savanna",    "A"),  # Togo
    "TN": ("mediterranean",       "C"),  # Tunisia
    "UG": ("tropical_savanna",    "A"),  # Uganda
    "ZM": ("tropical_savanna",    "A"),  # Zambia
    "ZW": ("tropical_savanna",    "A"),  # Zimbabwe

    # ── Americas ─────────────────────────────────────────────────────
    "AG": ("coral_atoll",         "A"),  # Antigua and Barbuda
    "AR": ("temperate_grassland", "C"),  # Argentina (Pampas)
    "BS": ("coral_atoll",         "A"),  # Bahamas
    "BB": ("coral_atoll",         "A"),  # Barbados
    "BZ": ("tropical_rainforest", "A"),  # Belize
    "BO": ("tropical_rainforest", "A"),  # Bolivia (Amazon + Altiplano)
    "BR": ("tropical_rainforest", "A"),  # Brazil
    "CA": ("boreal_forest",       "D"),  # Canada
    "CL": ("temperate_forest",    "C"),  # Chile (multiple, but temperate dominant)
    "CO": ("tropical_rainforest", "A"),  # Colombia
    "CR": ("tropical_rainforest", "A"),  # Costa Rica
    "CU": ("tropical_dry_forest", "A"),  # Cuba
    "DM": ("tropical_rainforest", "A"),  # Dominica
    "DO": ("tropical_dry_forest", "A"),  # Dominican Republic
    "EC": ("tropical_rainforest", "A"),  # Ecuador
    "SV": ("tropical_dry_forest", "A"),  # El Salvador
    "GD": ("coral_atoll",         "A"),  # Grenada
    "GT": ("tropical_rainforest", "A"),  # Guatemala
    "GY": ("tropical_rainforest", "A"),  # Guyana
    "HT": ("tropical_dry_forest", "A"),  # Haiti
    "HN": ("tropical_rainforest", "A"),  # Honduras
    "JM": ("tropical_dry_forest", "A"),  # Jamaica
    "MX": ("desert_semiarid",     "B"),  # Mexico (Chihuahuan dominant by area; tropical in south)
    "NI": ("tropical_rainforest", "A"),  # Nicaragua
    "PA": ("tropical_rainforest", "A"),  # Panama
    "PY": ("tropical_savanna",    "A"),  # Paraguay (Chaco)
    "PE": ("tropical_rainforest", "A"),  # Peru (Amazon + Andes)
    "KN": ("coral_atoll",         "A"),  # St. Kitts and Nevis
    "LC": ("tropical_rainforest", "A"),  # St. Lucia
    "VC": ("tropical_rainforest", "A"),  # St. Vincent and the Grenadines
    "SR": ("tropical_rainforest", "A"),  # Suriname
    "TT": ("tropical_rainforest", "A"),  # Trinidad and Tobago
    "US": ("temperate_forest",    "C"),  # USA (multiple; temperate dominant by population)
    "UY": ("temperate_grassland", "C"),  # Uruguay
    "VE": ("tropical_rainforest", "A"),  # Venezuela

    # ── Asia ─────────────────────────────────────────────────────────
    "AF": ("desert_semiarid",     "B"),  # Afghanistan
    "AM": ("montane",             "D"),  # Armenia
    "AZ": ("desert_semiarid",     "B"),  # Azerbaijan
    "BH": ("desert_arid",         "B"),  # Bahrain
    "BD": ("wetlands",            "A"),  # Bangladesh (Ganges/Brahmaputra delta)
    "BT": ("montane",             "C"),  # Bhutan
    "BN": ("tropical_rainforest", "A"),  # Brunei
    "KH": ("tropical_rainforest", "A"),  # Cambodia
    "CN": ("temperate_forest",    "D"),  # China (multiple; continental dominant)
    "CY": ("mediterranean",       "C"),  # Cyprus
    "GE": ("temperate_forest",    "C"),  # Georgia
    "IN": ("tropical_savanna",    "A"),  # India (multiple; tropical dominant by population)
    "ID": ("tropical_rainforest", "A"),  # Indonesia
    "IR": ("desert_arid",         "B"),  # Iran
    "IQ": ("desert_arid",         "B"),  # Iraq
    "IL": ("mediterranean",       "C"),  # Israel
    "JP": ("temperate_forest",    "C"),  # Japan
    "JO": ("desert_arid",         "B"),  # Jordan
    "KZ": ("temperate_grassland", "D"),  # Kazakhstan (steppe)
    "KW": ("desert_arid",         "B"),  # Kuwait
    "KG": ("montane",             "D"),  # Kyrgyzstan
    "LA": ("tropical_rainforest", "A"),  # Laos
    "LB": ("mediterranean",       "C"),  # Lebanon
    "MY": ("tropical_rainforest", "A"),  # Malaysia
    "MV": ("coral_atoll",         "A"),  # Maldives
    "MN": ("desert_semiarid",     "D"),  # Mongolia
    "MM": ("tropical_rainforest", "A"),  # Myanmar
    "NP": ("montane",             "C"),  # Nepal
    "KP": ("temperate_forest",    "D"),  # North Korea
    "OM": ("desert_arid",         "B"),  # Oman
    "PK": ("desert_arid",         "B"),  # Pakistan
    "PS": ("mediterranean",       "C"),  # Palestine
    "PH": ("tropical_rainforest", "A"),  # Philippines
    "QA": ("desert_arid",         "B"),  # Qatar
    "SA": ("desert_arid",         "B"),  # Saudi Arabia
    "SG": ("tropical_rainforest", "A"),  # Singapore
    "KR": ("temperate_forest",    "C"),  # South Korea
    "LK": ("tropical_rainforest", "A"),  # Sri Lanka
    "SY": ("mediterranean",       "C"),  # Syria
    "TW": ("tropical_rainforest", "A"),  # Taiwan
    "TJ": ("montane",             "D"),  # Tajikistan
    "TH": ("tropical_rainforest", "A"),  # Thailand
    "TL": ("tropical_rainforest", "A"),  # Timor-Leste
    "TR": ("mediterranean",       "C"),  # Türkiye
    "TM": ("desert_arid",         "B"),  # Turkmenistan
    "AE": ("desert_arid",         "B"),  # UAE
    "UZ": ("desert_arid",         "B"),  # Uzbekistan
    "VN": ("tropical_rainforest", "A"),  # Vietnam
    "YE": ("desert_arid",         "B"),  # Yemen

    # ── Europe ───────────────────────────────────────────────────────
    "AL": ("mediterranean",       "C"),  # Albania
    "AD": ("montane",             "C"),  # Andorra
    "AT": ("temperate_forest",    "C"),  # Austria
    "BY": ("boreal_forest",       "D"),  # Belarus
    "BE": ("temperate_forest",    "C"),  # Belgium
    "BA": ("temperate_forest",    "C"),  # Bosnia and Herzegovina
    "BG": ("temperate_forest",    "C"),  # Bulgaria
    "HR": ("mediterranean",       "C"),  # Croatia
    "CZ": ("temperate_forest",    "C"),  # Czechia
    "DK": ("coastal_maritime",    "C"),  # Denmark
    "EE": ("boreal_forest",       "D"),  # Estonia
    "FI": ("boreal_forest",       "D"),  # Finland
    "FR": ("temperate_forest",    "C"),  # France
    "DE": ("temperate_forest",    "C"),  # Germany
    "GR": ("mediterranean",       "C"),  # Greece
    "HU": ("temperate_grassland", "C"),  # Hungary
    "IS": ("tundra",              "E"),  # Iceland
    "IE": ("temperate_forest",    "C"),  # Ireland
    "IT": ("mediterranean",       "C"),  # Italy
    "LV": ("boreal_forest",       "D"),  # Latvia
    "LI": ("montane",             "C"),  # Liechtenstein
    "LT": ("boreal_forest",       "D"),  # Lithuania
    "LU": ("temperate_forest",    "C"),  # Luxembourg
    "MT": ("mediterranean",       "C"),  # Malta
    "MD": ("temperate_grassland", "C"),  # Moldova
    "MC": ("mediterranean",       "C"),  # Monaco
    "ME": ("temperate_forest",    "C"),  # Montenegro
    "NL": ("coastal_maritime",    "C"),  # Netherlands
    "MK": ("temperate_forest",    "C"),  # North Macedonia
    "NO": ("boreal_forest",       "D"),  # Norway
    "PL": ("temperate_forest",    "D"),  # Poland
    "PT": ("mediterranean",       "C"),  # Portugal
    "RO": ("temperate_forest",    "C"),  # Romania
    "RU": ("boreal_forest",       "D"),  # Russia
    "SM": ("mediterranean",       "C"),  # San Marino
    "RS": ("temperate_forest",    "C"),  # Serbia
    "SK": ("temperate_forest",    "C"),  # Slovakia
    "SI": ("temperate_forest",    "C"),  # Slovenia
    "ES": ("mediterranean",       "C"),  # Spain
    "SE": ("boreal_forest",       "D"),  # Sweden
    "CH": ("montane",             "C"),  # Switzerland
    "UA": ("temperate_grassland", "D"),  # Ukraine
    "GB": ("temperate_forest",    "C"),  # United Kingdom
    "VA": ("mediterranean",       "C"),  # Vatican City

    # ── Oceania ──────────────────────────────────────────────────────
    "AU": ("desert_arid",         "B"),  # Australia (interior dominant by area)
    "FJ": ("tropical_rainforest", "A"),  # Fiji
    "KI": ("coral_atoll",         "A"),  # Kiribati
    "MH": ("coral_atoll",         "A"),  # Marshall Islands
    "FM": ("coral_atoll",         "A"),  # Micronesia
    "NR": ("coral_atoll",         "A"),  # Nauru
    "NZ": ("temperate_forest",    "C"),  # New Zealand
    "PW": ("coral_atoll",         "A"),  # Palau
    "PG": ("tropical_rainforest", "A"),  # Papua New Guinea
    "WS": ("tropical_rainforest", "A"),  # Samoa
    "SB": ("tropical_rainforest", "A"),  # Solomon Islands
    "TO": ("coral_atoll",         "A"),  # Tonga
    "TV": ("coral_atoll",         "A"),  # Tuvalu
    "VU": ("tropical_rainforest", "A"),  # Vanuatu
}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def country_biome_map_entry(country_code: str) -> dict:
    """Return the biome+climate-zone payload for a country.

    For unknown countries returns the 'unclassified' fallback so the
    map layer renders every country deterministically.
    """
    cc = (country_code or "").upper()
    if cc in COUNTRY_BIOME_MAP:
        biome_id, koppen_id = COUNTRY_BIOME_MAP[cc]
    else:
        biome_id, koppen_id = "unclassified", "U"

    biome_meta = BIOME_TYPES.get(biome_id, BIOME_TYPES["unclassified"])
    koppen_meta = KOPPEN_ZONES.get(koppen_id, KOPPEN_ZONES["U"])

    return {
        "country_code": cc,
        "biome_id": biome_id,
        "biome_label": biome_meta["label"],
        "biome_emoji": biome_meta["emoji"],
        "koppen_id": koppen_id,
        "koppen_label": koppen_meta["label"],
        "koppen_color": koppen_meta["color"],
        "koppen_description": koppen_meta["description"],
    }


def biome_overview_payload() -> dict:
    """Full payload for GET /api/map/biome-overview — every country's
    biome + climate-zone in a single response, plus the taxonomy
    metadata so the frontend can render a legend without a second
    round-trip."""
    countries = [
        country_biome_map_entry(cc) for cc in sorted(COUNTRY_BIOME_MAP.keys())
    ]
    return {
        "countries": countries,
        "biome_taxonomy": [
            {"id": k, "label": v["label"], "emoji": v["emoji"]}
            for k, v in BIOME_TYPES.items() if k != "unclassified"
        ],
        "koppen_taxonomy": [
            {"id": k, "label": v["label"], "color": v["color"],
             "description": v["description"]}
            for k, v in KOPPEN_ZONES.items() if k != "U"
        ],
        "total_countries": len(countries),
    }


def supported_country_codes() -> list[str]:
    """Country codes with a curated biome+climate mapping."""
    return sorted(COUNTRY_BIOME_MAP.keys())
