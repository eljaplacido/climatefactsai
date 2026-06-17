"use client";

import {
  BarChart3,
  Thermometer,
  ShieldAlert,
  Network,
  Leaf,
  Building2,
  type LucideIcon,
} from "lucide-react";

export type ActiveLayer =
  | "article_density"
  | "temperature_anomaly"
  | "climate_risk"
  | "source_diversity"
  | "corporate_density"
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
}

export const MAP_LAYERS: MapLayer[] = [
  {
    id: "article_density",
    label: "Article Density",
    description: "Number of climate articles per country",
    icon: BarChart3,
    personas: ["consumer", "professional", "policymaker", "researcher"],
    statKey: "article_count",
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
    legend: [
      { color: "bg-indigo-200", text: "1-2" },
      { color: "bg-indigo-300", text: "3-5" },
      { color: "bg-indigo-500", text: "6-10" },
      { color: "bg-indigo-700", text: "10+" },
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
