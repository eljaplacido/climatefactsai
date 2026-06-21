"use client";

import {
  BarChart3,
  Thermometer,
  ShieldAlert,
  Network,
  Leaf,
  Building2,
  Radio,
  Target,
  ShieldOff,
  type LucideIcon,
} from "lucide-react";

export type ActiveLayer =
  | "article_density"
  | "temperature_anomaly"
  | "climate_risk"
  | "source_diversity"
  | "corporate_density"
  | "news_events"
  | "ndc_status"
  | "warming_outlook"
  | "adaptation_gap"
  | "biomes";

export type Persona = "consumer" | "professional" | "policymaker" | "researcher";

export interface LayerCoverage {
  coveredCountries: number;
  totalCountries: number;
  note: string;
}

export interface MapLayer {
  id: ActiveLayer;
  label: string;
  description: string;
  icon: LucideIcon;
  personas: Persona[];
  /** Backend endpoint for lazy-loading layer data (e.g. "/api/map/layers/temperature-anomaly"). */
  dataEndpoint?: string;
  /** Key on CountryStatEntry that drives the color scale. */
  statKey: string;
  /** Legend swatches displayed in the corner legend. */
  legend: { color: string; text: string }[];
  /** Honesty gate — only set when layer has incomplete country coverage. */
  coverage?: LayerCoverage;
  /** Methodology provenance shown in the layer legend. */
  provenance?: {
    sourceName: string;
    sourceUrl?: string;
    methodologyVersion?: string;
    datasetYear?: string;
    uncertainty?: string;
    methodologyNote?: string;
    uncertaintyNote?: string;
    note?: string;
  };
}

export const MAP_LAYERS: MapLayer[] = [
  {
    id: "article_density",
    label: "Article Density",
    description: "Number of climate articles per country",
    icon: BarChart3,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    statKey: "article_count",
    provenance: {
      sourceName: "Climatefacts.ai article corpus",
      sourceUrl: "https://climatenews-frontend-srzwxdzmaq-ez.a.run.app/methodology",
      methodologyVersion: "live-index",
      uncertainty: "Article count reflects indexed content; coverage varies by country and language.",
    },
    legend: [
      { color: "bg-teal-200", text: "Low" },
      { color: "bg-teal-300", text: "Medium" },
      { color: "bg-teal-500", text: "High" },
      { color: "bg-teal-600", text: "Very High" },
    ],
  },
  {
    id: "temperature_anomaly",
    label: "Temperature Anomaly",
    description: "Deviation from historical temperature averages",
    icon: Thermometer,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    dataEndpoint: "/api/map/layers/temperature-anomaly",
    statKey: "temperature_anomaly",
    provenance: {
      sourceName: "Open-Meteo",
      sourceUrl: "https://open-meteo.com/",
      methodologyVersion: "v1.0",
      note: "Current temperature compared to same month last year — not a 30-year baseline. Multi-decade ERA5 reanalysis is planned (Phase 3).",
    },
    legend: [
      { color: "bg-blue-500", text: "< -1°C" },
      { color: "bg-blue-200", text: "-1 to 0°C" },
      { color: "bg-yellow-200", text: "0 to +1°C" },
      { color: "bg-yellow-400", text: "+1 to +2°C" },
      { color: "bg-orange-500", text: "+2 to +3°C" },
      { color: "bg-red-600", text: "> +3°C" },
    ],
  },
  {
    id: "climate_risk",
    label: "Climate Risk",
    description: "Composite climate risk score by country",
    icon: ShieldAlert,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    statKey: "climate_risk_score",
    provenance: {
      sourceName: "Climatefacts.ai verification pipeline",
      sourceUrl: "https://climatenews-frontend-srzwxdzmaq-ez.a.run.app/methodology",
      methodologyVersion: "v3.0",
      note: "Score derived from article volume, claim dispute ratio, and source reliability — not an independent hazard model.",
    },
    legend: [
      { color: "bg-green-300", text: "Low" },
      { color: "bg-yellow-400", text: "Moderate" },
      { color: "bg-orange-500", text: "High" },
      { color: "bg-red-600", text: "Very High" },
    ],
  },
  {
    id: "source_diversity",
    label: "Source Diversity",
    description: "Number of distinct sources covering each country",
    icon: Network,
    personas: ["consumer", "professional", "researcher"],
    statKey: "source_count",
    provenance: {
      sourceName: "Climatefacts.ai Corpus",
      sourceUrl: "/methodology#source-tiers",
      methodologyNote: "Source diversity is measured as the count of distinct sources with articles about each country, relative to the global maximum.",
      uncertaintyNote: "Sources are counted by name; syndication and republishing across outlets may inflate counts for widely-carried stories.",
    },
    legend: [
      { color: "bg-violet-100", text: "1-2" },
      { color: "bg-violet-300", text: "3-5" },
      { color: "bg-violet-400", text: "6-10" },
      { color: "bg-violet-600", text: "10+" },
    ],
  },
  {
    id: "corporate_density",
    label: "Corporate Density",
    description: "Companies with climate disclosures by country",
    icon: Building2,
    personas: ["professional", "policymaker", "researcher"],
    dataEndpoint: "/api/map/layers/corporate-density",
    statKey: "company_count",
    provenance: {
      sourceName: "CDP / SBTi / Net Zero Tracker",
      sourceUrl: "https://sciencebasedtargets.org/companies-taking-action",
      methodologyVersion: "v1.0",
      note: "Based on registered headquarters; supply chain and operational footprint geolocation is pending (Phase 2).",
    },
    legend: [
      { color: "bg-indigo-200", text: "1-2" },
      { color: "bg-indigo-300", text: "3-5" },
      { color: "bg-indigo-500", text: "6-10" },
      { color: "bg-indigo-700", text: "10+" },
    ],
  },
  {
    id: "news_events",
    label: "News Events",
    description: "Recent climate news intensity and controversy hotspots",
    icon: Radio,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    dataEndpoint: "/api/map/layers/news-events",
    statKey: "controversy_score",
    provenance: {
      sourceName: "Climatefacts.ai article corpus",
      sourceUrl: "https://climatenews-frontend-srzwxdzmaq-ez.a.run.app/methodology",
      methodologyVersion: "v1.0",
      note: "Based on 21-day rolling article volume and disputed claim ratio; time-decayed. Not a real-time breaking-news feed.",
    },
    legend: [
      { color: "bg-amber-200", text: "Low" },
      { color: "bg-amber-500", text: "Medium" },
      { color: "bg-orange-500", text: "High" },
      { color: "bg-red-600", text: "Very High" },
    ],
  },
  {
    id: "ndc_status",
    label: "NDC Targets",
    description: "Country climate pledges — net-zero, NDC ambition, and CAT rating",
    icon: Target,
    personas: ["policymaker", "professional", "researcher"],
    dataEndpoint: "/api/map/layers/ndc-status",
    statKey: "cat_overall_rating",
    provenance: {
      sourceName: "UNFCCC NDC Registry / Climate Action Tracker",
      sourceUrl: "https://climateactiontracker.org/",
      methodologyVersion: "v1.0",
      note: "Based on synced CAT ratings and submitted NDC targets. Coverage is limited to ~36 CAT-rated and ~190 NDC-submitting countries.",
    },
    legend: [
      { color: "bg-emerald-600", text: "Net-zero" },
      { color: "bg-emerald-400", text: "Strong" },
      { color: "bg-amber-400", text: "Moderate" },
      { color: "bg-red-400", text: "Weak" },
      { color: "bg-slate-600", text: "No data" },
    ],
  },
  {
    id: "warming_outlook",
    label: "Warming Outlook",
    description: "Projected temperature rise by 2050 under SSP2-4.5 (middle path)",
    icon: Thermometer,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    dataEndpoint: "/api/map/layers/warming-outlook?horizon_year=2050",
    statKey: "best_estimate_c",
    provenance: {
      sourceName: "IPCC AR6 WG1 Interactive Atlas",
      sourceUrl: "https://interactive-atlas.ipcc.ch/regional-information",
      methodologyVersion: "ipcc_ar6_atlas_v2",
      note: "CMIP6 multi-model median under SSP2-4.5 (middle path). Coverage gate applies — only countries in the AR6 Atlas ingestion are coloured.",
    },
    legend: [
      { color: "bg-blue-200", text: "< +1.5°C" },
      { color: "bg-yellow-300", text: "+1.5 to +2.5°C" },
      { color: "bg-orange-500", text: "+2.5 to +3.5°C" },
      { color: "bg-red-600", text: "> +3.5°C" },
    ],
  },
  {
    id: "adaptation_gap",
    label: "Adaptation Gap",
    description: "Adaptation finance gap estimated from ND-GAIN country index",
    icon: ShieldOff,
    personas: ["policymaker", "researcher"],
    dataEndpoint: "/api/map/layers/adaptation-finance-gap",
    statKey: "adaptation_gap_score",
    provenance: {
      sourceName: "Notre Dame Global Adaptation Initiative (ND-GAIN)",
      sourceUrl: "https://gain.nd.edu/our-work/country-index/",
      methodologyVersion: "v1.0",
      note: "Adaptation gap derived from inverted ND-GAIN index (0-100 → gap 0-10). This is a proxy, not actual finance-flow data. UNEP Adaptation Gap Report data (12-14× finance gap) is planned for Phase 3.",
    },
    legend: [
      { color: "bg-red-700", text: "Severe" },
      { color: "bg-orange-500", text: "High" },
      { color: "bg-amber-400", text: "Moderate" },
      { color: "bg-green-400", text: "Low" },
      { color: "bg-slate-600", text: "No data" },
    ],
  },
  {
    id: "biomes",
    label: "Biomes & Climate",
    description: "Biome type + Köppen climate zone per country",
    icon: Leaf,
    personas: ["consumer", "researcher"],
    dataEndpoint: "/api/map/biome-overview",
    statKey: "biome_zone",
    provenance: {
      sourceName: "Köppen-Geiger Climate Classification",
      sourceUrl: "https://www.nature.com/articles/sdata2018214",
      methodologyNote: "Biome categories mapped from the Köppen-Geiger climate classification at 1 km resolution (Beck et al. 2018). Emoji symbols are a visual shorthand for non-expert audiences.",
      uncertaintyNote: "Köppen zones are long-term climate averages (1980-2016 baseline). Short-term weather events are not reflected.",
    },
    legend: [
      { color: "bg-[#E76F51]", text: "Tropical" },
      { color: "bg-[#F4A261]", text: "Arid" },
      { color: "bg-[#2A9D8F]", text: "Temperate" },
      { color: "bg-[#264653]", text: "Continental" },
      { color: "bg-[#A8DADC]", text: "Polar" },
    ],
  },
];

export function getLayer(id: ActiveLayer): MapLayer | undefined {
  return MAP_LAYERS.find((l) => l.id === id);
}

export function getLayersByPersona(persona: Persona): MapLayer[] {
  return MAP_LAYERS.filter((l) => l.personas.includes(persona));
}

export function isLayerCoverageGated(layer: MapLayer): boolean {
  return layer.coverage !== undefined && layer.coverage.coveredCountries < layer.coverage.totalCountries;
}
