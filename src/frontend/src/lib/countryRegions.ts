/**
 * World-region grouping for country selectors (F5e).
 *
 * The old CountrySelector grouped countries by EU membership, labelling every
 * non-EU country "Other European countries" — wrong for the US, China, Brazil,
 * etc. This maps ISO-3166 alpha-2 codes to coarse world regions so selectors
 * can group logically by geography.
 *
 * Regions are pragmatic (climate-platform oriented), not a strict UN M49 cut:
 * transcontinental states are placed where users most expect them
 * (e.g. Turkey → Middle East, Cyprus → Europe, Egypt → Africa).
 * Unknown codes fall back to "Other".
 */

export type WorldRegion =
  | "Europe"
  | "North America"
  | "Latin America & Caribbean"
  | "Middle East"
  | "Africa"
  | "Asia"
  | "Oceania";

/** Display order for optgroups. */
export const REGION_ORDER: WorldRegion[] = [
  "Europe",
  "North America",
  "Latin America & Caribbean",
  "Middle East",
  "Africa",
  "Asia",
  "Oceania",
];

// ISO-3166 alpha-2 (uppercase) -> region. Kept explicit for auditability.
const CODE_TO_REGION: Record<string, WorldRegion> = {
  // --- Europe ---
  AL: "Europe", AD: "Europe", AT: "Europe", BY: "Europe", BE: "Europe",
  BA: "Europe", BG: "Europe", HR: "Europe", CY: "Europe", CZ: "Europe",
  DK: "Europe", EE: "Europe", FI: "Europe", FR: "Europe", DE: "Europe",
  GR: "Europe", HU: "Europe", IS: "Europe", IE: "Europe", IT: "Europe",
  XK: "Europe", LV: "Europe", LI: "Europe", LT: "Europe", LU: "Europe",
  MT: "Europe", MD: "Europe", MC: "Europe", ME: "Europe", NL: "Europe",
  MK: "Europe", NO: "Europe", PL: "Europe", PT: "Europe", RO: "Europe",
  RU: "Europe", SM: "Europe", RS: "Europe", SK: "Europe", SI: "Europe",
  ES: "Europe", SE: "Europe", CH: "Europe", UA: "Europe", GB: "Europe",
  VA: "Europe", FO: "Europe", GI: "Europe", IM: "Europe", JE: "Europe",
  GG: "Europe", AX: "Europe",

  // --- North America ---
  US: "North America", CA: "North America", GL: "North America",
  BM: "North America", PM: "North America",

  // --- Latin America & Caribbean ---
  MX: "Latin America & Caribbean", GT: "Latin America & Caribbean",
  BZ: "Latin America & Caribbean", SV: "Latin America & Caribbean",
  HN: "Latin America & Caribbean", NI: "Latin America & Caribbean",
  CR: "Latin America & Caribbean", PA: "Latin America & Caribbean",
  CO: "Latin America & Caribbean", VE: "Latin America & Caribbean",
  EC: "Latin America & Caribbean", PE: "Latin America & Caribbean",
  BO: "Latin America & Caribbean", BR: "Latin America & Caribbean",
  PY: "Latin America & Caribbean", UY: "Latin America & Caribbean",
  AR: "Latin America & Caribbean", CL: "Latin America & Caribbean",
  GY: "Latin America & Caribbean", SR: "Latin America & Caribbean",
  GF: "Latin America & Caribbean",
  CU: "Latin America & Caribbean", HT: "Latin America & Caribbean",
  DO: "Latin America & Caribbean", JM: "Latin America & Caribbean",
  TT: "Latin America & Caribbean", BS: "Latin America & Caribbean",
  BB: "Latin America & Caribbean", AG: "Latin America & Caribbean",
  DM: "Latin America & Caribbean", GD: "Latin America & Caribbean",
  KN: "Latin America & Caribbean", LC: "Latin America & Caribbean",
  VC: "Latin America & Caribbean", PR: "Latin America & Caribbean",
  AW: "Latin America & Caribbean", CW: "Latin America & Caribbean",
  KY: "Latin America & Caribbean", VG: "Latin America & Caribbean",
  VI: "Latin America & Caribbean", TC: "Latin America & Caribbean",
  AI: "Latin America & Caribbean", MS: "Latin America & Caribbean",
  BQ: "Latin America & Caribbean", SX: "Latin America & Caribbean",
  MF: "Latin America & Caribbean", BL: "Latin America & Caribbean",
  GP: "Latin America & Caribbean", MQ: "Latin America & Caribbean",

  // --- Middle East (Western Asia: Gulf, Levant, Anatolia, Iran) ---
  BH: "Middle East", IR: "Middle East", IQ: "Middle East", IL: "Middle East",
  JO: "Middle East", KW: "Middle East", LB: "Middle East", OM: "Middle East",
  PS: "Middle East", QA: "Middle East", SA: "Middle East", SY: "Middle East",
  TR: "Middle East", AE: "Middle East", YE: "Middle East",

  // --- Africa (incl. North Africa) ---
  DZ: "Africa", AO: "Africa", BJ: "Africa", BW: "Africa", BF: "Africa",
  BI: "Africa", CV: "Africa", CM: "Africa", CF: "Africa", TD: "Africa",
  KM: "Africa", CG: "Africa", CD: "Africa", CI: "Africa", DJ: "Africa",
  EG: "Africa", GQ: "Africa", ER: "Africa", SZ: "Africa", ET: "Africa",
  GA: "Africa", GM: "Africa", GH: "Africa", GN: "Africa", GW: "Africa",
  KE: "Africa", LS: "Africa", LR: "Africa", LY: "Africa", MG: "Africa",
  MW: "Africa", ML: "Africa", MR: "Africa", MU: "Africa", MA: "Africa",
  MZ: "Africa", NA: "Africa", NE: "Africa", NG: "Africa", RW: "Africa",
  ST: "Africa", SN: "Africa", SC: "Africa", SL: "Africa", SO: "Africa",
  ZA: "Africa", SS: "Africa", SD: "Africa", TZ: "Africa", TG: "Africa",
  TN: "Africa", UG: "Africa", ZM: "Africa", ZW: "Africa", EH: "Africa",
  RE: "Africa", YT: "Africa",

  // --- Asia (South, East, Central, SE Asia + Caucasus) ---
  AF: "Asia", AM: "Asia", AZ: "Asia", BD: "Asia", BT: "Asia", BN: "Asia",
  KH: "Asia", CN: "Asia", GE: "Asia", IN: "Asia", ID: "Asia", JP: "Asia",
  KZ: "Asia", KG: "Asia", LA: "Asia", MY: "Asia", MV: "Asia", MN: "Asia",
  MM: "Asia", NP: "Asia", KP: "Asia", PK: "Asia", PH: "Asia", SG: "Asia",
  KR: "Asia", LK: "Asia", TW: "Asia", TJ: "Asia", TH: "Asia", TM: "Asia",
  UZ: "Asia", VN: "Asia", HK: "Asia", MO: "Asia",

  // --- Oceania ---
  AU: "Oceania", FJ: "Oceania", KI: "Oceania", MH: "Oceania", FM: "Oceania",
  NR: "Oceania", NZ: "Oceania", PW: "Oceania", PG: "Oceania", WS: "Oceania",
  SB: "Oceania", TO: "Oceania", TV: "Oceania", VU: "Oceania", NC: "Oceania",
  PF: "Oceania", GU: "Oceania", MP: "Oceania", AS: "Oceania", CK: "Oceania",
  NU: "Oceania", TL: "Oceania",
};

/**
 * Resolve a country code to its world region.
 * Case-insensitive; unknown codes return "Other".
 */
export function REGION_FOR(countryCode: string | null | undefined): WorldRegion | "Other" {
  if (!countryCode) return "Other";
  return CODE_TO_REGION[countryCode.trim().toUpperCase()] ?? "Other";
}
