"""Real climate indicators — Phase 3 of the truth-machine roadmap.

Replaces the "article count → 0–10 coverage_index" placeholder with values
sourced from primary datasets:

  * Climate TRACE — sector emissions (satellite-verified)
  * Our World in Data — canonical climate CSVs
  * Climate Action Tracker — sovereign policy ratings
  * World Bank Climate Knowledge Portal — adaptation / exposure
  * UNFCCC NDC Registry — pledges + LT-LEDS targets
  * IRENA — renewable capacity

Each adapter writes to `country_indicators` (schema in migration 020) with
full source provenance: source_name, source_url, fetched_at,
methodology_version, raw_record. The scoring layer joins
`indicator_definitions` to know whether higher or lower is better per
indicator and what unit / methodology URL to surface.
"""

from .base import (
    IndicatorAdapter,
    IndicatorRecord,
    SyncResult,
)
from .climate_trace import ClimateTRACEAdapter
from .owid import OWIDAdapter

__all__ = [
    "IndicatorAdapter",
    "IndicatorRecord",
    "SyncResult",
    "ClimateTRACEAdapter",
    "OWIDAdapter",
]
