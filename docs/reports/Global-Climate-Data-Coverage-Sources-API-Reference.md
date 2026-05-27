# Global Climate Data Coverage for climatefacts.ai: Open Sources & APIs by Continent

## Executive Summary

Covering 95% of the world's countries (~185 of 195 UN-recognized states) with reliable climate data on your platform is **realistically achievable**, provided you layer global reanalysis datasets on top of national and regional observational networks. No single source achieves this alone, but a strategic three-tier stack — global reanalysis (ERA5, CHIRPS, NASA POWER), international aggregators (GHCN, WMO WWIS), and continent-specific open datasets — gives coverage for virtually every country and territory. The hard limits lie in data *quality* and *temporal granularity*, not availability per se: satellite-based and reanalysis products fill geographic gaps left by sparse ground-station networks, particularly across sub-Saharan Africa, the Pacific, and least-developed nations.

***

## Tier 1 — Global Baseline (Applies to All Regions)

These datasets function as the backbone for global climate platforms and cover every country via gridded or interpolated products. They should be your first integration layer before adding regional sources.

| Source | Coverage | Historical Depth | API / Access |
|--------|----------|-----------------|-------------|
| **ERA5 (ECMWF/Copernicus CDS)** | Global, 0.25° grid (~31 km) | 1940–present, hourly | [Python `cdsapi`](https://cds.climate.copernicus.eu/how-to-api) [^1][^2] |
| **Open-Meteo** | Global (30+ models, incl. CMA, BOM, ECMWF, NOAA) | 1940–present (ERA5 backend) | [open-meteo.com/docs](https://open-meteo.com/en/docs) — free, no API key [^3][^4] |
| **NOAA NCEI Climate Data Online (CDO)** | 180 countries, 100,000+ stations | 1800s–present | [CDO API v2](https://www.ncdc.noaa.gov/cdo-web/webservices) — token required [^5][^6] |
| **NOAA GHCN-Daily** | 180 countries, 100,000+ stations | Variable by station | [NCEI Access Data Service API](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation) [^7][^8] |
| **GHCN-Monthly Precipitation v4** | 120,000+ stations worldwide, 33,000+ active | 1800s–present | Via NCEI CDO API [^9] |
| **World Bank CCKP** | 196 countries/territories | 1950–2100 (obs + projections) | [REST API](https://climateknowledgeportal.worldbank.org/download-data) + AWS Open Data `s3://wbg-cckp` [^10][^11] |
| **NASA POWER** | Global, 0.5°–1° grid | 1981–present | [power.larc.nasa.gov API](https://power.larc.nasa.gov/docs/services/api/) — free, no key [^12][^13] |
| **Berkeley Earth** | Global country averages | 1750–present | Bulk CSV download at [berkeleyearth.org](https://berkeleyearth.org/data/) — CC BY-NC [^14][^15] |
| **WMO World Weather Information Service** | 2,800+ cities, all member states | Climatological normals | [JSON API](https://worldweather.wmo.int/en/dataguide.html) — free, per-city [^16] |
| **Open-Meteo Climate API** | Global, IPCC AR6 10 km downscaled | 1950–2050 projections | [open-meteo.com/en/docs/climate-api](https://open-meteo.com/en/docs/climate-api) [^17][^18] |
| **OpenAQ** | Global air quality (PM2.5, PM10, NO2, O3, etc.) | Real-time + historical | [docs.openaq.org](https://docs.openaq.org/about/about) — open REST API [^19] |

> **Practical note for climatefacts.ai:** ERA5 + Open-Meteo together provide gap-free global gridded coverage from 1940. GHCN-Daily/Monthly adds verified station-level granularity. World Bank CCKP adds forward-looking projections with country-level aggregations. This trio alone covers ~195 countries in a computationally tractable way.

***

## Europe

Europe is the best-covered continent with multiple mature, well-documented APIs and harmonized datasets. Temporal records often extend back to the 1700s.

**Coverage assessment: ~100% of countries (44/44) achievable**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **Copernicus Climate Data Store (CDS)** | All European + global | [`pip install cdsapi`](https://cds.climate.copernicus.eu/how-to-api) — free, token required [^20][^1] |
| **ECMWF ERA5** | Global (produced in Europe, optimized for EU) | CDS API, see above [^21][^22] |
| **ECA&D (European Climate Assessment & Dataset)** | 65+ European + Mediterranean countries | [eca.knmi.nl](https://www.ecad.eu/) — bulk download + REST [^23] |
| **Finnish Meteorological Institute (FMI)** | Finland, Scandinavia, Arctic | [OGC WFS/WMS API](https://en.ilmatieteenlaitos.fi/open-data-manual) — fully open [^24] |
| **MeteoSwiss** | Switzerland + Alpine region | [STAC API](https://data.geo.admin.ch/api/stac/v1/) — OGC standard [^25] |
| **DWD (German Weather Service)** | Germany + ICON global model | [opendata.dwd.de](https://opendata.dwd.de/) — open FTP/HTTP, integrated in Open-Meteo [^3] |
| **Météo-France** | France, DROM-COM territories | [AROME + ARPEGE via Open-Meteo](https://open-meteo.com/en/docs/meteofrance-api) — partially open [^3] |
| **UK Met Office** | UK, global GFS-derived | Open access datasets via [data.gov.uk](https://www.data.gov.uk/dataset/77e7e88e-b2f4-4e17-acb8-9a7c79fe23c1/uk-gridded-climate-observations) [^3] |
| **KNMI (Netherlands)** | Netherlands + European via ICA&D network | [HARMONIE AROME API via Open-Meteo](https://open-meteo.com/en/docs/knmi-api) [^26][^23] |
| **Copernicus Arctic Regional Reanalysis (CARRA)** | Arctic Europe, Iceland, Svalbard | [CDS Catalogue](https://cds.climate.copernicus.eu/) — monthly updated [^27] |

**Key gap:** Some micro-states (San Marino, Monaco, Liechtenstein, Vatican) lack standalone national meteorological services but are fully covered by surrounding national networks and ERA5 gridded data.

***

## North America

Coverage across the US, Canada, and Mexico is comprehensive through open government data services. Regional climate data for Central America and the Caribbean carries more variation.

**Coverage assessment: ~100% of countries (23/23 including Caribbean) via ERA5 + regional supplements**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **NOAA CDO & NCEI Data Service** | USA, global archive | [NCEI Access Data Service](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation) — free token [^6][^28] |
| **NWS Weather.gov API** | USA (real-time + forecasts) | [api.weather.gov](https://www.weather.gov/documentation/services-web-api) — free, no key [^29] |
| **MSC GeoMet (Environment Canada)** | Canada + some global | [api.weather.gc.ca](https://api.weather.gc.ca) — OGC API, free [^30][^31] |
| **MSC Datamart** | Canada (raw data) | [dd.weather.gc.ca](https://dd.weather.gc.ca/) — HTTPS/AMQP [^32] |
| **CONAGUA (Mexico)** | Mexico | [smn.conagua.gob.mx](https://smn.conagua.gob.mx/) — partial open access |
| **CIMH (Caribbean Institute for Meteorology & Hydrology)** | 16 Caribbean CARICOM states | [cimh.edu.bb](https://www.cimh.edu.bb) — supports NMHSs [^33] |
| **Caribbean Climate Information Tools** | Caribbean + Central America | [CLIE'nT portal](https://caribbeanclimate.org/tools/) — web-based datasets [^34] |
| **CopernicusLAC Panama** | Latin America & Caribbean | [copernicuslac-panama.eu](https://www.copernicuslac-panama.eu/) — EU-funded EO data [^35] |

**Key gaps:** Several Eastern Caribbean micro-states (e.g., Dominica, St. Kitts, Grenada) have limited national observation networks but are covered by CIMH regional data and ERA5. Cuba has data through WMO channels but national APIs are not publicly exposed.

***

## South America

Brazil and Argentina have the most developed open data infrastructure. The Andean and Amazonian nations have less accessible national portals but are covered through regional and satellite datasets.

**Coverage assessment: ~95% of countries (12/12) — all via ERA5 + GHCN; national APIs vary**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **INPE/CPTEC LatAm Dataset** | Brazil + South America, 0.25° resolution | [CPTEC FTP/HTTP](https://satelite.cptec.inpe.br/latamdataset) — daily updates [^36] |
| **INMET (Brazil)** | Brazil, 261+ stations | [portal.inmet.gov.br](https://portal.inmet.gov.br/) — open station data [^37] |
| **SENAMHI** | Peru, Bolivia, Paraguay, Colombia, Ecuador | National portals, partial open access; data also via GHCN [^38] |
| **SMN (Argentina)** | Argentina | [smn.gob.ar](https://www.smn.gob.ar/) — open data downloads |
| **IDEAM (Colombia)** | Colombia | [R package ColOpenData](https://epiverse-trace.github.io/ColOpenData/articles/climate_data.html) wrapping IDEAM API [^39] |
| **KNMI ICA&D Latin America** | Multiple LA countries | [icad-wmo.org](https://www.icad-wmo.org) — station + gridded [^23] |
| **DMC (Chile)** | Chile | [meteochile.gob.cl](https://www.meteochile.gob.cl/) — open access |
| **INAMEH (Venezuela)** | Venezuela | Partial access; supplement with ERA5 [^38] |

**Key gaps:** Venezuela, Suriname, and Guyana have limited public API access. All three are covered adequately by ERA5 reanalysis + GHCN station data. The Falkland Islands and French Guiana are covered by UK Met Office and Météo-France, respectively.

***

## Africa

Africa is the continent with the largest observational data gap. Station density is far below global standards, with many stations non-operational or reporting inconsistently. However, multiple satellite and reanalysis products provide acceptable coverage, and several regional institutions provide quality-controlled datasets.[^40]

**Coverage assessment: ~90–95% of countries (50–52/54) via satellite/reanalysis; station data is sparse**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **CHIRPS v2 (Climate Hazards Group / USGS)** | All Africa + global, daily/monthly precipitation | [DE Africa AWS Open Data](https://registry.opendata.aws/deafrica-chirps/) `s3://deafrica-input-datasets/` — free [^41][^42] |
| **Africa Data Hub Climate Observer** | All Africa (Berkeley Earth + GPCC) | [africadatahub.org/dashboards/climate-observer](https://www.africadatahub.org/dashboards/climate-observer) — CC BY-NC [^43] |
| **ICPAC (IGAD Climate Prediction Centre)** | 11 Greater Horn of Africa states | [icpac.net/open-data-sources](https://www.icpac.net/open-data-sources/) — open datasets [^44][^45] |
| **TAHMO (Trans-African Hydro-Meteorological Observatory)** | Sub-Saharan Africa, 600+ stations | [tahmo.org/climate-data](https://new.tahmo.org/climate-data/) — data portal, WMO interpolation [^46] |
| **ACMAD (African Centre of Meteorological Application)** | 53 African countries | ECMWF products via EUMETCast [^47][^48] |
| **ICA&D West Africa (KNMI/WMO)** | West Africa & Sahel station network | [west-africa.icad-wmo.org](https://west-africa.icad-wmo.org) — free for research [^49] |
| **AGRHYMET RCC** | 17 West Africa & Sahel countries | [agrhymet.cilss.int](http://ccr1-agrhymet.cilss.int/en/) — regional climate centre [^50][^51] |
| **Digital Earth Africa (DE Africa)** | Continental Africa | [docs.digitalearthafrica.org](https://docs.digitalearthafrica.org/) — open datacube + STAC API [^52] |
| **SAWS (South African Weather Service)** | South Africa | [weathersa.co.za](https://www.weathersa.co.za/) — partially open |
| **WMO SOFF Programme** | LDCs and SIDS in Africa | Infrastructure support; complements GHCN [^40] |

**Key gaps:** Central African Republic, South Sudan, Somalia, and Equatorial Guinea have very sparse station networks, with data reliability issues in GHCN. These countries are best served via ERA5 reanalysis + CHIRPS for precipitation. The WMO explicitly flagged in 2026 that Africa's surface station density remains "far below global standards".[^40]

***

## Asia

Asia is extremely heterogeneous in data accessibility — from Japan's gold-standard open data infrastructure to conflict-affected states with effectively no accessible climate records.

**Coverage assessment: ~90% of countries (42–44/49) via ERA5 + national sources**

### East Asia

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **CMA (China Meteorological Administration)** | China, global model (GFS GRAPES) | [data.cma.cn](https://data.cma.cn/en/) — requires registration; model via Open-Meteo[^53][^54] |
| **JMA (Japan Meteorological Agency)** | Japan, global model | Integrated in Open-Meteo; [JMBSC data](https://www.jmbsc.or.jp/) for commercial [^3] |
| **KMA (Korea Meteorological Administration)** | South Korea | Open-Meteo integration; [data.kma.go.kr](https://data.kma.go.kr) — open portal [^3] |

### South Asia

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **IMD (India Meteorological Department)** | India | [mausam.imd.gov.in/responsive/apis.php](https://mausam.imd.gov.in/responsive/apis.php) — official API [^55] |
| **MOSDAC (ISRO)** | India (satellite data) | [mosdac.gov.in](https://www.mosdac.gov.in) — satellite archive API [^56] |
| **SAARC Meteorological Research Centre** | Bangladesh, Nepal, Pakistan, Sri Lanka, Bhutan | Regional coordination body; supplement via ERA5 |

### Southeast Asia

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **SACA&D (KNMI/BMKG)** | 15 SE Asian countries, 10,000+ stations | [sacad.bmkg.go.id](https://sacad.bmkg.go.id) — 17% public, rest by request [^57][^58] |
| **BMKG (Indonesia)** | Indonesia | [dataonline.bmkg.go.id](https://dataonline.bmkg.go.id/) — open portal |

### Central Asia

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **Central Asia Water & Energy Data Portal** | Kazakhstan, Kyrgyzstan, Tajikistan, Uzbekistan, Turkmenistan | [spatialagent.org/CentralAsia](https://spatialagent.org/CentralAsia/) — aggregates World Bank, WMO, ERA5 [^59] |
| **CAIAG (Central Asian Inst. of Applied Geosciences)** | Central Asia multiparameter stations | [caiag.kg](http://www.caiag.kg/) — hydromet network [^60] |

**Key gaps:** Afghanistan, North Korea, Myanmar, Turkmenistan, and Yemen have extremely limited open climate data due to conflict, political restrictions, or infrastructure gaps. ERA5 reanalysis covers these geographically, but station-validated data is sparse or absent. North Korea represents the most significant hard gap globally.

***

## Middle East & North Africa (MENA)

MENA combines well-resourced Gulf states with fragile/conflict-affected nations where data availability is severely limited. The World Bank classifies the entire region as under extremely high water stress, making climate data particularly critical yet underserved.[^61]

**Coverage assessment: ~80–85% of countries (17–18/21) via ERA5 + WMO channels**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **WMO WWIS (World Weather Info Service)** | All MENA capitals with NMHSs | [worldweather.wmo.int](https://worldweather.wmo.int/en/dataguide.html) — JSON API [^16] |
| **World Bank CCKP** | All 21 MENA countries | REST API at [climateknowledgeportal.worldbank.org](https://climateknowledgeportal.worldbank.org) [^62][^63] |
| **ERA5 / Open-Meteo** | Full MENA region, 0.25° grid | [open-meteo.com](https://open-meteo.com) — no key needed [^3] |
| **ACMAD (North Africa members)** | Algeria, Egypt, Libya, Morocco, Tunisia | ECMWF products via WMO channels [^48] |
| **Israel Meteorological Service** | Israel | [ims.gov.il](https://ims.gov.il/) — partial open datasets |

**Key gaps:** Libya (post-2011 conflict), Yemen, Syria, and Iraq have severely disrupted national meteorological services. ERA5 reanalysis is the only reliable option for these countries. Saudi Arabia and UAE have national services but limited public data APIs.

***

## Oceania / Pacific

Australia and New Zealand have strong open data infrastructure. The ~14 Pacific Island sovereign states (Fiji, Vanuatu, Tonga, Samoa, etc.) represent some of the most severe data coverage challenges globally — only 25% of SIDS provide climate data at an advanced level.[^64]

**Coverage assessment: ~80% of sovereign entities fully covered; ~60–70% of SIDS at useful quality**

| Source | Countries | API / Integration |
|--------|-----------|------------------|
| **BoM (Bureau of Meteorology, Australia)** | Australia, Pacific Islands support | [bom.gov.au/resources/data-services](https://www.bom.gov.au/resources/data-services) — free basic + paid for full [^65][^66] |
| **BoM Pacific Climate Change Data Portal** | Pacific Islands + Timor-Leste | [bom.gov.au/climate/pccsp](https://www.bom.gov.au/climate/pccsp/) — historical + trend indices [^67] |
| **NIWA (New Zealand)** | New Zealand + SW Pacific | [niwa.co.nz/climate/](https://niwa.co.nz/climate) — open datasets |
| **SPREP Pacific Environment Data Portal** | 22 Pacific Island nations | [pacific-data.sprep.org](https://pacific-data.sprep.org) — open spatial datasets [^68] |
| **Pacific Data Hub (SPC)** | Pacific Islands + ocean data | [pacificdata.org](https://pacificdata.org) — open API [^69] |
| **NOAA Pacific Regional Climate Center** | US Pacific territories + regional | [prcichub.org](https://www.prcichub.org/) — open reports |
| **ERA5 + Open-Meteo** | Full Pacific, all islands | Global coverage including ocean [^3][^22] |

**Key gaps:** Kiribati, Tuvalu, Marshall Islands, Nauru, and Palau have extremely limited ground station networks. Only 39% of SIDS have multi-hazard early warning systems, reflecting the underlying data scarcity. For these nations, satellite products (ERA5, CHIRPS, CMORPH) are the only viable sources. The WMO's SOFF programme is currently funding infrastructure in 36 SIDS, which may improve availability through 2026–2028.[^64]

***

## Polar Regions (Arctic & Antarctic)

These are not sovereign countries but are relevant for platforms covering climate change and specific Arctic nations (Norway, Russia, Canada, Denmark/Greenland, USA, Finland, Iceland, Sweden).

| Source | Region | API / Integration |
|--------|--------|------------------|
| **Copernicus Arctic Regional Reanalysis (CARRA)** | Arctic (up to 2.5 km resolution) | [CDS catalogue](https://cds.climate.copernicus.eu/) — CARRA2 due 2025 [^27] |
| **NOAA Arctic/Antarctic Data** | Both polar regions | [ncei.noaa.gov/products/arctic-antarctic](https://www.ncei.noaa.gov/products/arctic-antarctic-products-data-information) [^70] |
| **FMI Arctic Open Data** | Arctic/Finland/Svalbard | [OGC API](https://en.ilmatieteenlaitos.fi/open-data-manual) [^24] |

***

## Feasibility Analysis: Can You Reach 95% Country Coverage?

The answer is **yes, with the right architecture**. Here is an honest breakdown:

| Tier | Countries Covered | Notes |
|------|------------------|-------|
| **ERA5 + Open-Meteo (gridded reanalysis)** | ~195/195 (100%) | Any coordinate on Earth, 0.25° resolution, 1940–present — no ground truth but physically consistent |
| **GHCN-Daily + GHCN-Monthly** | ~180/195 (92%) | 100,000+ stations across 180 countries; station density varies greatly [^7][^8] |
| **World Bank CCKP** | ~196/195 (100%+, incl. territories) | Country-level aggregations with API; projections to 2100 [^62] |
| **National/Regional open APIs** | ~60–80 major countries | Direct station data from NMHSs — supplementary, higher quality |
| **SIDS / conflict zones (hard gaps)** | ~10–15 countries | Limited to satellite/reanalysis only; station data missing or inaccessible |

**The 5% hard-to-reach countries** consist primarily of:
- North Korea (no accessible data)
- Somalia, South Sudan, Libya, Yemen, Syria (conflict-disrupted)
- Kiribati, Tuvalu, Nauru, Marshall Islands, Palau (micro-SIDS, sparse station networks)
- Turkmenistan, Eritrea (political access restrictions)

For these, ERA5 reanalysis and CHIRPS precipitation still provide *some* usable climate data, meaning even the "hard gaps" are partially coverable — just without station-validated ground truth.

***

## Recommended Integration Architecture for climatefacts.ai

Given your existing stack (Python, Google Cloud/Azure, Rust, semantic layers), the following tiered integration is recommended:

1. **Primary global baseline:** Copernicus CDS (`cdsapi`) for ERA5 — hourly 0.25° for historical, plus Open-Meteo's free REST API for real-time/forecast and IPCC projections. This alone covers 100% of geography.

2. **Station-level enrichment:** NOAA NCEI CDO API (token-based, 10,000 req/day) for GHCN-Daily data for all 180+ covered countries. Add Berkeley Earth country CSVs for extended historical coverage.

3. **Country-level aggregations:** World Bank CCKP REST API or AWS S3 (`s3://wbg-cckp`) for 196 countries × 70+ variables including projections — ideal for country profile pages.

4. **Regional precision layers:** Add CHIRPS (Africa/Americas precipitation), SACA&D (SE Asia), ICA&D (Europe/W.Africa/LA), IMD (India), MSC GeoMet (Canada) as regional enrichment layers.

5. **Air quality overlay:** OpenAQ API (global, free REST) for PM2.5/PM10/NO2 co-located with climate data.

6. **Licensing notes:** ERA5/Copernicus = free, CC-BY-4.0 (requires attribution); Berkeley Earth = CC BY-NC (no commercial use without license); NOAA/NCEI = US government public domain; World Bank = ODbL. Commercial use of Berkeley Earth requires a separate license agreement.

***

## Data Quality Caveats by Region

| Region | Observation Quality | Primary Gap Risk |
|--------|--------------------|--------------------|
| Europe | ★★★★★ High — long records, dense station networks | Near none |
| North America | ★★★★★ High — NOAA/MSC well-documented | Caribbean micro-states |
| South America | ★★★★☆ Good — gaps in Amazon/Andes | Venezuela, Guyana |
| East/SE Asia | ★★★★☆ Good — Japan/Korea excellent; SE Asia variable | North Korea, Myanmar |
| South/Central Asia | ★★★☆☆ Medium — India excellent; Central Asia limited | Afghanistan, Tajikistan |
| MENA | ★★★☆☆ Medium — Gulf states OK; conflict zones absent | Libya, Yemen, Syria |
| Sub-Saharan Africa | ★★☆☆☆ Limited — station density far below WMO standards | DRC, CAR, South Sudan |
| Pacific SIDS | ★★☆☆☆ Limited — only 25% provide advanced climate data [^64] | Kiribati, Tuvalu, Nauru |
| Arctic/Antarctica | ★★★☆☆ Medium — rapid improvement with CARRA2 | Remote Arctic interior |

***

## Conclusion

A 95% country coverage target for climatefacts.ai is **well within reach today** using the open-source stack described above. The strategic insight is that global reanalysis products (ERA5, Open-Meteo) eliminate pure geographic white spots — every country on Earth has *some* usable gridded climate data. The real challenge is not coverage breadth but coverage **depth**: station density, temporal resolution, and validation quality degrade significantly across Africa, Pacific SIDS, and conflict-affected states. For a climate platform, this is best communicated through transparent data quality scoring per country, distinguishing between "reanalysis-backed" and "station-validated" data, which also adds credibility and scientific rigor to your platform's approach.

---

## References

1. [CDSAPI setup - Climate Data Store - Copernicus](https://cds.climate.copernicus.eu/how-to-api) - The Climate Data Store (CDS) Application Program Interface (API) is a service providing programmatic...

2. [ecmwf/cdsapi: Python API to access the Copernicus Climate Data ...](https://github.com/ecmwf/cdsapi) - Get your Personal Access Token from your profile on the CDS portal at the address: https://cds.clima...

3. [Open-Meteo.com: 🌤️ Free Open-Source Weather API](https://open-meteo.com) - Open-Source ☀️️️️️️️️️️️️️️️️️️️️️️️️️️️️️ Weather API with free access for non-commercial use. No A...

4. [open-meteo/open-meteo: Free Weather Forecast API for ...](https://github.com/open-meteo/open-meteo) - Free Weather Forecast API for non-commercial use. Contribute to open-meteo/open-meteo development by...

5. [Climate Data Online (CDO)](https://www.ncei.noaa.gov/cdo-web/) - Climate Data Online (CDO) provides free access to NCDC's archive of global historical weather and cl...

6. [NCEI Web Services | Climate Data Online (CDO)](https://www.ncdc.noaa.gov/cdo-web/webservices) - Currently available Web Services from Climate Data Online (CDO).

7. [Global Historical Climatology Network daily (GHCNd)](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) - The Global Historical Climatology Network daily (GHCNd) is an integrated database of daily climate s...

8. [Global Historical Climatology Network (GHCN) - Drought.gov](https://www.drought.gov/data-maps-tools/global-historical-climatology-network-ghcn) - Global Historical Climatology Network (GHCN): an integrated database of daily climate summaries from...

9. [The Global Historical Climatology Network Monthly Precipitation Dataset, Version 4 - Scientific Data](https://www.nature.com/articles/s41597-024-03457-z) - The Global Historical Climatology Network (GHCN) monthly precipitation dataset contains historical t...

10. [Download Data | Climate Change Knowledge Portal - World Bank](https://climateknowledgeportal.worldbank.org/download-data) - CCKP offers spatially aggregated climate data for land at the country or territory level, sub-nation...

11. [World Bank Climate Change Knowledge Portal (CCKP) - AWS](https://aws.amazon.com/marketplace/pp/prodview-rgev6zyy6cj4y) - CCKP provides open access to a comprehensive suite of climate and climate change resources derived f...

12. [NASA POWER | Data Services | Climatology API | Docs - nasa power](https://power.larc.nasa.gov/docs/services/api/temporal/climatology/) - POWER Documentation Site

13. [nasapower: NASA POWER API Client - rOpenSci - R-universe](https://ropensci.r-universe.dev/nasapower) - {nasapower} aims to make it quick and easy to automate downloading of the NASA-POWER global meteorol...

14. [temperature-data/README.md at main · compgeolab/temperature-data](https://github.com/compgeolab/temperature-data/blob/main/README.md) - Download and create a subset of global country-average temperature data from Berkeley Earth - compge...

15. [GitHub - compgeolab/temperature-data: Download and create a subset of global country-average temperature data from Berkeley Earth](https://github.com/compgeolab/temperature-data) - Download and create a subset of global country-average temperature data from Berkeley Earth - compge...

16. [Download | World Weather Information Service](https://worldweather.wmo.int/en/dataguide.html) - This global web site presents OFFICIAL weather forecasts and climatological information for selected...

17. [Climate API | Open-Meteo.com](https://open-meteo.com/en/docs/climate-api) - Downscaled IPCC climate predictions specifically tailored to a 10 km resolution, going beyond the li...

18. [Climate Change API - by Patrick Zippenfenig - Open-Meteo](https://openmeteo.substack.com/p/climate-change-api) - High resolution IPCC climate models from the 6th assessment report

19. [About the API - OpenAQ Docs](https://docs.openaq.org/about/about) - Discover the OpenAQ API, which offers open access to global air quality data based on REST principle...

20. [The Climate Data Store | Copernicus](https://climate.copernicus.eu/climate-data-store) - It provides easy access to a wide range of climate datasets via a searchable catalogue. An online to...

21. [ECMWF Reanalysis v5 (ERA5)](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5) - ERA5 is the fifth generation ECMWF atmospheric reanalysis of the global climate covering the period ...

22. [ERA5 hourly data on single levels from 1940 to present](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download) - ERA5 is the fifth generation ECMWF reanalysis for the global climate and weather for the past 8 deca...

23. [The International Climate Assessment & Dataset - KNMI](https://www.knmi.nl/research/observations-data-technology/projects/the-international-climate-assessment-dataset) - A web-based information system that combines quality-controlled daily station data with derived clim...

24. [Open data manual - Finnish Meteorological Institute](https://en.ilmatieteenlaitos.fi/open-data-manual) - This evolving documentation is intended to give a good head start on developing applications using w...

25. [Download data - Open Data Documentation - MeteoSwiss](https://opendatadocs.meteoswiss.ch/general/download) - This Jupyter notebook shows a simplified workflow for downloading and processing ground-based measur...

26. [KNMI Weather Model API | Open-Meteo.com](https://open-meteo.com/en/docs/knmi-api) - KNMI provides weather forecasts from the HARMONIE AROME model with ECMWF IFS initialization. This is...

27. [Copernicus Polar Roadmap: C3S and CAMS data support Arctic ...](https://atmosphere.copernicus.eu/copernicus-polar-roadmap-c3s-and-cams-data-support-arctic-policymaking) - The roadmap, presented by the EU Polar Task Force, charts a strategic course for monitoring the Arct...

28. [Datatypes](https://github.com/partytax/ncei-api-guide) - A guide to the NCEIs suite of climate data APIs. Contribute to partytax/ncei-api-guide development b...

29. [API Web Service - National Weather Service](https://www.weather.gov/documentation/services-web-api) - National Weather Service API at api.weather.gov provides access to the latest forecasts and alerts, ...

30. [Readme en - MSC Open Data / Données ouvertes du SMC](https://eccc-msc.github.io/open-data/readme_en/) - Open data from the Meteorological Service of Canada (MSC) provides weather, environmental, water and...

31. [MSC GeoMet - GeoMet-OGC-API - Home](https://api.weather.gc.ca) - GeoMet-OGC-API provides public access to the Meteorological Service of Canada (MSC) and Environment ...

32. [MSC Datamart](https://eccc-msc.github.io/open-data/msc-datamart/readme_en/) - The Meteorological Service of Canada (MSC) HTTPS raw data server is a source of raw weather, water, ...

33. [CIMH | Caribbean Institute for Meteorology & Hydrology](https://www.cimh.edu.bb) - CIMH is providing outputs from its regional implementations of MM5V3 and WRF to National Meteorologi...

34. [Caribbean Climate Change Tools](https://caribbeanclimate.org/tools/) - The Clearinghouse Search Tool allows users to access, request, and contribute digital documents rela...

35. [Building Climate Resilience in Latin America and the Caribbean ...](https://www.copernicuslac-panama.eu/blog-en/the-copernicuslac-panama-centre-building-climate-resilience-in-latin-america-and-the-caribbean-with-free-and-open-earth-observation-data/) - The CopernicusLAC Panama Centre: Building Climate Resilience in Latin America and the Caribbean with...

36. [LatAm Dataset](https://satelite.cptec.inpe.br/latamdataset) - A new high-resolution, gauge-satellite-based analysis of daily precipitation over continental South ...

37. [GitHub - gustavobio/inmet: Climate data from 261 INMET (http://inmet.gov.br) stations across Brazil.](https://github.com/gustavobio/inmet) - Climate data from 261 INMET (http://inmet.gov.br) stations across Brazil. - gustavobio/inmet

38. [Observational Datasets in South America](https://ral.ucar.edu/projects/south-america-affinity-group-saag/observational-datasets) - Many of the regular precipitation and temperature observations in South America are operated by gove...

39. [How to download climate data using ColOpenData - Epiverse-TRACE](https://epiverse-trace.github.io/ColOpenData/articles/climate_data.html) - ColOpenData can be used to access open climate data from Colombia. This climate data is retrieved fr...

40. [Closing the gap in observations - WMO](https://wmo.int/site/world-meteorological-day-2026/closing-gap-observations)

41. [AWS Marketplace: Digital Earth Africa CHIRPS Rainfallaws.amazon.com › marketplace › prodview-dyfgxivjtjurk](https://aws.amazon.com/marketplace/pp/prodview-dyfgxivjtjurk) - Digital Earth Africa (DE Africa) provides free and open access to a copy of the Climate Hazards Grou...

42. [Digital Earth Africa CHIRPS Rainfall - Registry of Open Data on AWS](https://registry.opendata.aws/deafrica-chirps/)

43. [Climate Observer | Africa Data Hub](https://www.africadatahub.org/dashboards/climate-observer) - The Africa Data Hub Climate Observer is designed to help journalists and academics reporting and res...

44. [Open Data Sources - ICPAC](https://www.icpac.net/open-data-sources/) - A powerful and freely accessible online data repository and analysis tool that allows a user to view...

45. [ICPAC](https://github.com/icpac-igad) - IGAD Climate Prediction and Applications Centre - Delivering climate services to Eastern Africa. - I...

46. [Climate Data - TAHMO](https://new.tahmo.org/climate-data/) - TAHMO weather station data Interested in TAHMO data? Click here TAHMO data is available on Read more

47. [Datasets for African Center of Meteorological Application ... - ECMWF](https://www.ecmwf.int/en/forecasts/datasets/datasets-african-center-meteorological-application-development) - These products are available to the African Center of Meteorological Application for Development (AC...

48. [[PDF] Mapping climate change initiatives in the Middle East and North ...](https://assets.publishing.service.gov.uk/media/57a08afaed915d622c000a09/DEWPoint_A0372_Aug2010_Climate_change_in_the_MENA_region.pdf) - ACMAD is currently based in Niamey in Niger and its member states are the 53 African countries (thes...

49. [Data Policy - ICA&D - West Africa](https://west-africa.icad-wmo.org/data-policy) - UNFCCC advocates open access to data and the GEO has set principles for promoting the full and open ...

50. [AGRHYMET RCC-WAS – Portal of the Regional Climate Centre (RCC)](http://ccr1-agrhymet.cilss.int/en/) - Our services ; Climate monitoring. Daily data collection and production of monitoring tools (bulleti...

51. [AGRHYMET CCR-AOS: launch of a regional monitoring centre for 17](https://fsrp.araa.org/en/news/agrhymet-ccr-aos-launch-regional-monitoring-centre-17-countries-west-africa-and-sahel) - AGRHYMET CCR-AOS: launch of a regional monitoring centre for 17 countries in West Africa and the Sah...

52. [Rainfall - Climate Hazards Group InfraRed Precipitation with Station data (CHIRPS)](https://docs.digitalearthafrica.org/en/latest/sandbox/notebooks/Datasets/Rainfall_CHIRPS.html)

53. [CMA releases the 2025 Catalog of Popular Meteorological Data for ...](https://wmo.int/media/news-from-members/cma-releases-2025-catalog-of-popular-meteorological-data-open-sharing) - On February 26, the China Meteorological Administration (CMA) released the 2025 Catalog of Popular M...

54. [New Models: BOM, CMA, MeteoFrance and ERA5 Ocean](https://openmeteo.substack.com/p/new-models-bom-cma-meteofrance-and) - Welcoming More High-Resolution Weather Models to the Mix!

55. [IMD APIs | India Meteorological Department](https://mausam.imd.gov.in/responsive/apis.php) - The India Meteorological Department (IMD) has implemented various initiatives recently to improve da...

56. [Meteorological & Oceanographic Satellite Data Archival Centre](https://www.mosdac.gov.in) - Meteorological & Oceanographic Satellite Data Archival Centre · Services · City Weather · Cold Waves...

57. [Southeast Asian Climate Assessment & Dataset - Re3data.org](https://www.re3data.org/repository/r3d100010404) - This project is focusing on the digitization and use of high-resolution historical climate data from...

58. [Home Southeast Asian Climate Assessment & Dataset](https://sacad.bmkg.go.id) - KNMI Climate Explorer ... This project is focusing on the digitization and use of high-resolution hi...

59. [Central Asia Water and Energy Data Portal - spatialagent.org](https://spatialagent.org/CentralAsia/) - Central Asia Hydrometeorology Modernization Project, Lake Levels, Night Lights, Landscan Population ...

60. [Global Change Observatory Central Asia | GCOCA: GFZ](https://www.gfz.de/en/scientific-infrastructure/research-infrastructures/regional-observatories/global-change-observatory-central-asia-gcoca) - Central Asia is influenced by different atmospheric systems, and it has a significant influence on w...

61. [By 2050, every single country in the Middle East and North Africa ...](https://www.facebook.com/CSIS.org/posts/the-trends-are-clear-by-2050-every-single-country-in-the-middle-east-and-north-a/1092747759564000/) - "The trends are clear: By 2050, every single country in the Middle East and North Africa (MENA) will...

62. [Climate Change Knowledge Portal - Atlas](https://atlas.co/climate-tools/climate-change-knowledge-portal/) - The World Bank's Climate Change Knowledge Portal provides free access to comprehensive climate data,...

63. [Climate Change Knowledge Portal - World Bank](https://climateknowledgeportal.worldbank.org) - The Climate Change Knowledge Portal is the hub for global, climate-related data on historical and fu...

64. [Closing the Climate Information Gap: Scaling Up Early Warning ...](https://gca.org/closing-the-climate-information-gap-scaling-up-early-warning-systems-for-small-island-developing-states/) - Early warning systems and robust climate information and monitoring are crucial to protecting human ...

65. [Data services | The Bureau of Meteorology - BoM](https://www.bom.gov.au/resources/data-services) - Find out how to access our data services

66. [Climate Data Online - Map search - BoM](https://www.bom.gov.au/climate/data/) - Access to historical Australian climate data, statistics and maps

67. [Pacific Climate Change Data Portal - BoM](https://www.bom.gov.au/climate/pccsp/)

68. [Pacific Environment Data Portal - SPREP](https://pacific-data.sprep.org) - From digital atlases, interactive spatial data viewers to open access geospatial data repositories a...

69. [Pacific Data Hub](https://pacificdata.org) - Explore and analyse official Pacific indicators, including SDGs and key economic, social, health, an...

70. [Arctic, Antarctic, and Polar Data](https://www.ncei.noaa.gov/products/arctic-antarctic-products-data-information) - This page provides access to Arctic and Antarctic data, services, and information across NOAA line o...

