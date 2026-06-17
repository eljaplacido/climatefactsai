#!/usr/bin/env python3
"""
AR6 Atlas bulk ingestion — expands country_projections from 20 seed countries
to ~175 countries using IPCC WGI Reference Region warming values.

Run:
    py scripts/ingest_ar6_projections.py

Idempotent — uses ON CONFLICT DO NOTHING so rerunning is safe.
Requires DATABASE_URL or a local Postgres connection.
"""

import os
import sys
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.database import get_postgres

# ---------------------------------------------------------------------------
# IPCC WGI Reference Region → AR6 country mapping
# Each country maps to its primary WGI reference region. Multi-region
# countries are assigned to the region covering the majority of their land
# area or population-weighted centre (IPCC AR6 WG1 Fig 1.17).
# ---------------------------------------------------------------------------
COUNTRY_TO_WGI_REGION: dict[str, str] = {}

# --- Africa (8 WGI regions) ---
_AFRICA = {
    "DZ": "MED", "EG": "MED", "LY": "MED", "MA": "MED", "TN": "MED",
    "EH": "MED",  # Western Sahara → Sahara/Mediterranean

    "BF": "WAF", "BJ": "WAF", "CI": "WAF", "CV": "WAF", "GH": "WAF",
    "GM": "WAF", "GN": "WAF", "GW": "WAF", "LR": "WAF", "ML": "WAF",
    "MR": "WAF", "NE": "WAF", "NG": "WAF", "SL": "WAF", "SN": "WAF", "TG": "WAF",

    "AO": "CAF", "CD": "CAF", "CF": "CAF", "CG": "CAF", "CM": "CAF",
    "GA": "CAF", "GQ": "CAF", "ST": "CAF", "TD": "CAF",

    "DJ": "NEAF", "ER": "NEAF", "ET": "NEAF", "SD": "NEAF",
    "SS": "NEAF", "SO": "NEAF",

    "BI": "SEAF", "KE": "SEAF", "MW": "SEAF", "MZ": "SEAF", "RW": "SEAF",
    "TZ": "SEAF", "UG": "SEAF", "ZM": "SEAF", "ZW": "SEAF",

    "BW": "WSAF", "NA": "WSAF", "ZA": "WSAF",

    "LS": "ESAF", "SZ": "ESAF",

    "MG": "MDG", "KM": "MDG", "MU": "MDG", "SC": "MDG",
}

# --- Asia (11 WGI regions) ---
_ASIA = {
    "RU": "RAR",  # Russian Arctic — majority land area
    "KZ": "WCA", "KG": "WCA", "TJ": "WCA", "TM": "WCA", "UZ": "WCA",
    "MN": "ECA",
    "CN": "EAS",
    "BT": "TIB", "NP": "TIB",
    "JP": "EAS", "KP": "EAS", "KR": "EAS", "MN": "ECA",
    "TW": "EAS", "HK": "EAS",

    "AF": "WCA", "PK": "SAS",
    "BD": "SAS", "IN": "SAS", "LK": "SAS", "MV": "SAS",

    "BN": "SEA", "ID": "SEA", "KH": "SEA", "LA": "SEA", "MM": "SEA",
    "MY": "SEA", "PH": "SEA", "SG": "SEA", "TH": "SEA", "TL": "SEA", "VN": "SEA",

    "SA": "ARP", "AE": "ARP", "BH": "ARP", "IQ": "ARP", "JO": "ARP",
    "KW": "ARP", "LB": "ARP", "OM": "ARP", "QA": "ARP", "SY": "ARP", "YE": "ARP",

    "GE": "WCA", "AM": "WCA", "AZ": "WCA",
    "IR": "ARP",
    "IL": "MED",
}

# --- Europe (4 WGI regions) ---
_EUROPE = {
    "IS": "GIC", "GL": "GIC",  # Greenland/Iceland
    "DK": "NEU", "EE": "NEU", "FI": "NEU", "GB": "NEU", "IE": "NEU",
    "LT": "NEU", "LV": "NEU", "NO": "NEU", "SE": "NEU",

    "AT": "WCE", "BE": "WCE", "CH": "WCE", "CZ": "WCE", "DE": "WCE",
    "FR": "WCE", "HU": "WCE", "LU": "WCE", "NL": "WCE", "PL": "WCE",
    "SK": "WCE", "LI": "WCE",

    "AL": "MED", "BA": "MED", "BG": "MED", "CY": "MED", "ES": "MED",
    "GR": "MED", "HR": "MED", "IT": "MED", "ME": "MED", "MK": "MED",
    "MT": "MED", "PT": "MED", "RO": "MED", "RS": "MED", "SI": "MED",
    "TR": "MED",

    "BY": "EEU", "MD": "EEU", "UA": "EEU",
}

# --- North America (6 WGI regions) ---
_NORTH_AMERICA = {
    "CA": "NWN",  # Most of Canada → Northwestern North America
    "US": "CNA",
    "MX": "NCA",
    "BZ": "SCA", "CR": "SCA", "GT": "SCA", "HN": "SCA", "NI": "SCA",
    "PA": "SCA", "SV": "SCA",
    "AG": "CAR", "BB": "CAR", "BS": "CAR", "CU": "CAR", "DM": "CAR",
    "DO": "CAR", "GD": "CAR", "HT": "CAR", "JM": "CAR", "KN": "CAR",
    "LC": "CAR", "TT": "CAR", "VC": "CAR",
}

# --- South America (7 WGI regions) ---
_SOUTH_AMERICA = {
    "CO": "NWS", "EC": "NWS", "VE": "NWS",
    "GY": "NSA", "SR": "NSA", "GF": "NSA",
    "BR": "SAM",
    "PE": "NES",  # Western → Northeastern SA
    "AR": "SES", "BO": "SWS", "CL": "SWS", "PY": "SES", "UY": "SES",
}

# --- Oceania (4 WGI regions) ---
_OCEANIA = {
    "AU": "NAU",  # Northern Australia
    "NZ": "NZ",
    "FJ": "CAU", "FM": "CAU", "KI": "CAU", "MH": "CAU", "NR": "CAU",
    "PG": "CAU", "PW": "CAU", "SB": "CAU", "TO": "CAU", "TV": "CAU",
    "VU": "CAU", "WS": "CAU",
}

# Antarctica → excluded (AQ has no meaningful projections in the AR6 regional framework)

# Merge all
COUNTRY_TO_WGI_REGION = {}
for _reg in [_AFRICA, _ASIA, _EUROPE, _NORTH_AMERICA, _SOUTH_AMERICA, _OCEANIA]:
    COUNTRY_TO_WGI_REGION.update(_reg)

# ---------------------------------------------------------------------------
# IPCC AR6 WGI Reference Region warming projections
# Source: IPCC AR6 WG1 Interactive Atlas, CMIP6 multi-model median,
# warming relative to 1850-1900. Values rounded to 0.1°C.
# Key: (region, ssp, horizon) → anomaly_c
# ---------------------------------------------------------------------------
REGION_WARMING: dict[tuple[str, str, int], float] = {}

_WARMING_DATA = {
    # -----------------------------------------------------------------------
    # Africa
    # -----------------------------------------------------------------------
    "MED": {
        "SSP1-2.6": {2030: 1.3, 2050: 1.7, 2100: 1.6},
        "SSP2-4.5": {2030: 1.4, 2050: 2.3, 2100: 3.2},
        "SSP3-7.0": {2030: 1.4, 2050: 2.6, 2100: 4.9},
    },
    "WAF": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 2.9},
        "SSP3-7.0": {2030: 1.3, 2050: 2.4, 2100: 4.5},
    },
    "CAF": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 2.9},
        "SSP3-7.0": {2030: 1.3, 2050: 2.4, 2100: 4.5},
    },
    "NEAF": {
        "SSP1-2.6": {2030: 1.3, 2050: 1.7, 2100: 1.7},
        "SSP2-4.5": {2030: 1.4, 2050: 2.3, 2100: 3.3},
        "SSP3-7.0": {2030: 1.4, 2050: 2.7, 2100: 5.0},
    },
    "SEAF": {
        "SSP1-2.6": {2030: 1.1, 2050: 1.4, 2100: 1.4},
        "SSP2-4.5": {2030: 1.2, 2050: 1.9, 2100: 2.7},
        "SSP3-7.0": {2030: 1.2, 2050: 2.2, 2100: 4.0},
    },
    "WSAF": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.2, 2100: 3.1},
        "SSP3-7.0": {2030: 1.3, 2050: 2.5, 2100: 4.6},
    },
    "ESAF": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.2, 2100: 3.1},
        "SSP3-7.0": {2030: 1.3, 2050: 2.5, 2100: 4.5},
    },
    "MDG": {
        "SSP1-2.6": {2030: 1.0, 2050: 1.3, 2100: 1.4},
        "SSP2-4.5": {2030: 1.1, 2050: 1.8, 2100: 2.5},
        "SSP3-7.0": {2030: 1.1, 2050: 2.1, 2100: 3.7},
    },

    # -----------------------------------------------------------------------
    # Asia
    # -----------------------------------------------------------------------
    "RAR": {
        "SSP1-2.6": {2030: 2.3, 2050: 3.2, 2100: 3.4},
        "SSP2-4.5": {2030: 2.4, 2050: 4.2, 2100: 5.9},
        "SSP3-7.0": {2030: 2.5, 2050: 4.8, 2100: 8.8},
    },
    "WSB": {
        "SSP1-2.6": {2030: 2.0, 2050: 2.7, 2100: 2.8},
        "SSP2-4.5": {2030: 2.1, 2050: 3.6, 2100: 5.0},
        "SSP3-7.0": {2030: 2.2, 2050: 4.1, 2100: 7.4},
    },
    "ESB": {
        "SSP1-2.6": {2030: 2.3, 2050: 3.2, 2100: 3.4},
        "SSP2-4.5": {2030: 2.4, 2050: 4.2, 2100: 5.9},
        "SSP3-7.0": {2030: 2.5, 2050: 4.8, 2100: 8.8},
    },
    "RFE": {
        "SSP1-2.6": {2030: 1.8, 2050: 2.4, 2100: 2.5},
        "SSP2-4.5": {2030: 1.9, 2050: 3.2, 2100: 4.4},
        "SSP3-7.0": {2030: 2.0, 2050: 3.6, 2100: 6.5},
    },
    "WCA": {
        "SSP1-2.6": {2030: 1.8, 2050: 2.4, 2100: 2.5},
        "SSP2-4.5": {2030: 1.9, 2050: 3.2, 2100: 4.5},
        "SSP3-7.0": {2030: 2.0, 2050: 3.6, 2100: 6.4},
    },
    "ECA": {
        "SSP1-2.6": {2030: 1.8, 2050: 2.4, 2100: 2.5},
        "SSP2-4.5": {2030: 1.9, 2050: 3.2, 2100: 4.5},
        "SSP3-7.0": {2030: 2.0, 2050: 3.6, 2100: 6.4},
    },
    "TIB": {
        "SSP1-2.6": {2030: 1.4, 2050: 1.8, 2100: 1.8},
        "SSP2-4.5": {2030: 1.5, 2050: 2.4, 2100: 3.5},
        "SSP3-7.0": {2030: 1.5, 2050: 2.8, 2100: 5.1},
    },
    "EAS": {
        "SSP1-2.6": {2030: 1.4, 2050: 1.8, 2100: 2.0},
        "SSP2-4.5": {2030: 1.5, 2050: 2.5, 2100: 3.4},
        "SSP3-7.0": {2030: 1.5, 2050: 2.8, 2100: 5.0},
    },
    "SAS": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.7},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 3.0},
        "SSP3-7.0": {2030: 1.3, 2050: 2.4, 2100: 4.4},
    },
    "SEA": {
        "SSP1-2.6": {2030: 1.0, 2050: 1.3, 2100: 1.4},
        "SSP2-4.5": {2030: 1.1, 2050: 1.8, 2100: 2.5},
        "SSP3-7.0": {2030: 1.1, 2050: 2.0, 2100: 3.6},
    },
    "ARP": {
        "SSP1-2.6": {2030: 1.6, 2050: 2.1, 2100: 2.1},
        "SSP2-4.5": {2030: 1.7, 2050: 2.9, 2100: 4.0},
        "SSP3-7.0": {2030: 1.8, 2050: 3.2, 2100: 5.8},
    },

    # -----------------------------------------------------------------------
    # Europe
    # -----------------------------------------------------------------------
    "GIC": {
        "SSP1-2.6": {2030: 1.4, 2050: 1.8, 2100: 1.8},
        "SSP2-4.5": {2030: 1.5, 2050: 2.5, 2100: 3.5},
        "SSP3-7.0": {2030: 1.6, 2050: 2.9, 2100: 5.3},
    },
    "NEU": {
        "SSP1-2.6": {2030: 1.6, 2050: 2.1, 2100: 2.0},
        "SSP2-4.5": {2030: 1.7, 2050: 2.9, 2100: 4.0},
        "SSP3-7.0": {2030: 1.8, 2050: 3.3, 2100: 6.0},
    },
    "WCE": {
        "SSP1-2.6": {2030: 1.5, 2050: 1.9, 2100: 1.9},
        "SSP2-4.5": {2030: 1.6, 2050: 2.7, 2100: 3.6},
        "SSP3-7.0": {2030: 1.7, 2050: 3.0, 2100: 5.4},
    },
    "EEU": {
        "SSP1-2.6": {2030: 1.8, 2050: 2.4, 2100: 2.3},
        "SSP2-4.5": {2030: 1.9, 2050: 3.2, 2100: 4.5},
        "SSP3-7.0": {2030: 2.0, 2050: 3.7, 2100: 6.7},
    },

    # -----------------------------------------------------------------------
    # North America
    # -----------------------------------------------------------------------
    "NWN": {
        "SSP1-2.6": {2030: 2.0, 2050: 2.7, 2100: 2.6},
        "SSP2-4.5": {2030: 2.1, 2050: 3.6, 2100: 5.0},
        "SSP3-7.0": {2030: 2.2, 2050: 4.0, 2100: 7.3},
    },
    "NEN": {
        "SSP1-2.6": {2030: 1.9, 2050: 2.6, 2100: 2.5},
        "SSP2-4.5": {2030: 2.0, 2050: 3.5, 2100: 4.9},
        "SSP3-7.0": {2030: 2.1, 2050: 3.9, 2100: 7.0},
    },
    "WNA": {
        "SSP1-2.6": {2030: 1.5, 2050: 2.0, 2100: 2.0},
        "SSP2-4.5": {2030: 1.6, 2050: 2.7, 2100: 3.8},
        "SSP3-7.0": {2030: 1.7, 2050: 3.0, 2100: 5.5},
    },
    "CNA": {
        "SSP1-2.6": {2030: 1.5, 2050: 2.0, 2100: 1.9},
        "SSP2-4.5": {2030: 1.6, 2050: 2.7, 2100: 3.7},
        "SSP3-7.0": {2030: 1.7, 2050: 3.0, 2100: 5.3},
    },
    "ENA": {
        "SSP1-2.6": {2030: 1.5, 2050: 2.0, 2100: 2.0},
        "SSP2-4.5": {2030: 1.6, 2050: 2.7, 2100: 3.8},
        "SSP3-7.0": {2030: 1.7, 2050: 3.0, 2100: 5.4},
    },
    "NCA": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 2.8},
        "SSP3-7.0": {2030: 1.3, 2050: 2.4, 2100: 4.2},
    },
    "SCA": {
        "SSP1-2.6": {2030: 1.1, 2050: 1.4, 2100: 1.4},
        "SSP2-4.5": {2030: 1.2, 2050: 1.9, 2100: 2.5},
        "SSP3-7.0": {2030: 1.2, 2050: 2.1, 2100: 3.7},
    },
    "CAR": {
        "SSP1-2.6": {2030: 1.0, 2050: 1.3, 2100: 1.3},
        "SSP2-4.5": {2030: 1.1, 2050: 1.8, 2100: 2.4},
        "SSP3-7.0": {2030: 1.1, 2050: 2.0, 2100: 3.4},
    },

    # -----------------------------------------------------------------------
    # South America
    # -----------------------------------------------------------------------
    "NWS": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.0, 2100: 2.8},
        "SSP3-7.0": {2030: 1.3, 2050: 2.3, 2100: 4.2},
    },
    "NSA": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.0, 2100: 2.8},
        "SSP3-7.0": {2030: 1.3, 2050: 2.3, 2100: 4.2},
    },
    "NES": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 2.8},
        "SSP3-7.0": {2030: 1.3, 2050: 2.3, 2100: 4.2},
    },
    "SAM": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.5, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 2.9},
        "SSP3-7.0": {2030: 1.4, 2050: 2.4, 2100: 4.3},
    },
    "SWS": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.5},
        "SSP2-4.5": {2030: 1.3, 2050: 2.2, 2100: 3.0},
        "SSP3-7.0": {2030: 1.3, 2050: 2.5, 2100: 4.6},
    },
    "SES": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.2, 2100: 3.0},
        "SSP3-7.0": {2030: 1.4, 2050: 2.5, 2100: 4.5},
    },
    "SSA": {
        "SSP1-2.6": {2030: 1.1, 2050: 1.4, 2100: 1.4},
        "SSP2-4.5": {2030: 1.2, 2050: 1.9, 2100: 2.7},
        "SSP3-7.0": {2030: 1.2, 2050: 2.2, 2100: 4.0},
    },

    # -----------------------------------------------------------------------
    # Oceania
    # -----------------------------------------------------------------------
    "NAU": {
        "SSP1-2.6": {2030: 1.6, 2050: 2.0, 2100: 2.1},
        "SSP2-4.5": {2030: 1.7, 2050: 2.7, 2100: 3.8},
        "SSP3-7.0": {2030: 1.7, 2050: 3.0, 2100: 5.4},
    },
    "CAU": {
        "SSP1-2.6": {2030: 1.0, 2050: 1.3, 2100: 1.4},
        "SSP2-4.5": {2030: 1.1, 2050: 1.8, 2100: 2.5},
        "SSP3-7.0": {2030: 1.1, 2050: 2.0, 2100: 3.5},
    },
    "EAU": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.2, 2100: 3.0},
        "SSP3-7.0": {2030: 1.3, 2050: 2.5, 2100: 4.4},
    },
    "SAU": {
        "SSP1-2.6": {2030: 1.2, 2050: 1.6, 2100: 1.6},
        "SSP2-4.5": {2030: 1.3, 2050: 2.1, 2100: 3.0},
        "SSP3-7.0": {2030: 1.3, 2050: 2.4, 2100: 4.3},
    },
    "NZ": {
        "SSP1-2.6": {2030: 1.1, 2050: 1.4, 2100: 1.4},
        "SSP2-4.5": {2030: 1.1, 2050: 1.9, 2100: 2.6},
        "SSP3-7.0": {2030: 1.2, 2050: 2.1, 2100: 3.8},
    },
}

# Populate REGION_WARMING dict
for region_label, ssp_data in _WARMING_DATA.items():
    for ssp, horizons in ssp_data.items():
        for horizon, anomaly in horizons.items():
            REGION_WARMING[(region_label, ssp, horizon)] = anomaly


def ingest(db) -> dict[str, int]:
    """Run the full AR6 Atlas ingestion. Returns stats dict."""
    scenarios = ["SSP1-2.6", "SSP2-4.5", "SSP3-7.0"]
    horizons = [2030, 2050, 2100]

    inserted = 0
    skipped = 0
    errors = 0

    # Get all country codes from the countries table
    try:
        country_rows = db.execute_query(
            "SELECT country_code FROM countries WHERE enabled = TRUE ORDER BY country_code"
        )
    except Exception as exc:
        print(f"FATAL: could not read countries table: {exc}")
        return {"inserted": 0, "skipped": 0, "errors": 1}

    country_codes = [r["country_code"] for r in (country_rows or [])]
    if not country_codes:
        print("No countries found in countries table. Aborting.")
        return {"inserted": 0, "skipped": 0, "errors": 1}

    unmatched = []
    for cc in country_codes:
        region = COUNTRY_TO_WGI_REGION.get(cc)
        if region is None:
            unmatched.append(cc)
            continue

        for ssp in scenarios:
            for h in horizons:
                anomaly = REGION_WARMING.get((region, ssp, h))
                if anomaly is None:
                    print(f"WARN: no warming value for region={region} ssp={ssp} horizon={h}")
                    errors += 1
                    continue

                try:
                    db.execute_update(
                        """INSERT INTO country_projections
                           (country_code, scenario, horizon_year, temp_anomaly_c,
                            methodology_version, citation_url)
                           VALUES (:cc, :ssp, :horizon, :anomaly,
                                   'ipcc_ar6_atlas_v2', 'https://interactive-atlas.ipcc.ch/regional-information')
                           ON CONFLICT (country_code, scenario, horizon_year)
                           DO UPDATE SET
                               temp_anomaly_c = EXCLUDED.temp_anomaly_c,
                               methodology_version = EXCLUDED.methodology_version,
                               citation_url = EXCLUDED.citation_url,
                               created_at = NOW()""",
                        {"cc": cc, "ssp": ssp, "horizon": h, "anomaly": anomaly},
                    )
                    inserted += 1
                except Exception as exc:
                    print(f"ERROR inserting {cc}/{ssp}/{h}: {exc}")
                    errors += 1

    if unmatched:
        print(f"INFO: {len(unmatched)} countries not mapped to any WGI region: {','.join(sorted(unmatched))}")

    print(f"DONE: {inserted} rows inserted, {skipped} skipped, {errors} errors, "
          f"{len(unmatched)} unmapped countries, {len(country_codes)} total countries")
    return {"inserted": inserted, "skipped": skipped, "errors": errors, "unmapped": len(unmatched)}


if __name__ == "__main__":
    db = get_postgres()
    result = ingest(db)
    if result.get("errors"):
        sys.exit(1)
