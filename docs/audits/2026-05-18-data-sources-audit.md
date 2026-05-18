# Data Source Sufficiency Audit — Climatefacts.ai

**Date:** 2026-05-18
**Scope:** Audit the 6 user-stated dimensions (climate news, consumer trends, sustainability, business, research, tourism) against current ingestion. Identify gaps + recommend integrations.

**Code surveyed:**
- `src/backend/app/domains/content/indicators/` (6 adapters: Climate TRACE, OWID, CAT, UNFCCC NDC, IRENA, ND-GAIN)
- `src/backend/app/domains/content/data_sources/rss_adapter.py`, `eu_feeds_registry.py`
- `src/backend/app/domains/content/data_sources/{copernicus,ecmwf,open_meteo,document}_adapter.py`
- `src/backend/app/tasks/ingestion.py`, `.env.example`

---

## 1. Climate news — verdict: **Mostly covered, gaps in Africa/Asia local-language tier**

Feed registry holds 13 EU-wide + 19 international + 20 US + ~26 Africa + 21 LATAM + 26 Asia + 16 ME + 15 research = **~156 feeds across ~87 distinct ISO-alpha-2 countries**. Coverage of UN-193 is shallow in Central Asia, francophone Africa, Pacific SIDS, and Caribbean. Most non-English feeds are missing — only ~10 % of feeds carry `language != en`.

**Gaps:**
- Francophone West Africa (CI, BF, ML, NE, GN, BJ, TG) — currently zero local feeds.
- Lusophone Africa (AO, MZ) — zero.
- Central Asia ex-USSR (KG, TJ, TM, MN) — zero.
- Caribbean SIDS (HT, DO, JM, TT, BB, GY, SR, CU) — zero.
- Pacific SIDS critical to sea-level narrative (FJ, TV, KI, MH, WS, TO, VU, SB, PG, PW, FM, NR) — zero.
- Central America (GT, HN, NI, SV, CR, PA, BZ) — zero.
- Andes (BO, EC, PY, UY, VE) — zero (LATAM list stops at PE).
- Maghreb/Sahel (DZ, TN, LY, SD, SS, TD, MR) — zero.
- Caucasus (already covered: GE, AM, AZ).
- North Korea (KP), Myanmar (MM), Cambodia (KH), Laos (LA), Sri Lanka (LK), Nepal (NP), Bhutan (BT), Maldives (MV) — zero (MV important for sea-level).

---

## 2. Consumer trends in climate/sustainability — verdict: **NOT COVERED**

Zero ingestion of consumer-sentiment or search-behaviour data today.

**Recommended additions** (all fit as new `data_sources/` adapters writing to a new table `consumer_sentiment_indicators` keyed by country-quarter):

- **Google Trends** (free, pseudo-API via `pytrends`) — climate keyword search-volume per country; daily polling possible.
- **Eurobarometer Special Surveys** (EU, biannual PDF + CSV) — climate sentiment by member state; scrape via document_adapter.
- **Edelman Trust Barometer** (annual PDF, 28 countries) — institutional trust on climate; manual quarterly refresh.
- **Pew Research Global Attitudes — Climate** (annual JSON download) — 26-country panel.
- **Yale Program on Climate Change Communication — Six Americas** (annual + monthly social-media tracker; US only but flagship).
- **Ipsos "Earth Day" Global Tracker** (annual PDF, 33 countries) — willingness-to-act metrics.

These are not real-time but pair well with article volume to build a *sentiment-vs-coverage* truth lens.

---

## 3. Sustainability (corporate disclosures) — verdict: **NOT COVERED**

No corporate-level data flows. Truth-machine on green transition needs this.

**Recommended additions** (new domain `domains/content/corporate/` with adapters writing to `company_climate_disclosures`):

- **CDP (Climate Disclosure Project)** — open response data via CDP Open Data Portal, ~20 k companies, annual JSON; high tier.
- **SBTi (Science Based Targets initiative)** — public commitment registry, CSV download monthly; high tier.
- **GRI Sustainability Disclosure Database** — searchable; scraped PDFs.
- **CSRD/ESRS filings** — official EU portal (ESAP from 2027 onwards); for now scrape national registries (Finland: tilinpäätös, France: INPI, Germany: Bundesanzeiger).
- **ISSB / IFRS S2 filings** — gradually appearing in national filings; pair with GRI scraper.
- **Net Zero Tracker** (Oxford / NewClimate / ECIU / Data-Driven EnviroLab) — open CSV of company + city + country pledges; refreshed weekly.

---

## 4. Business / corporate climate news — verdict: **Partial**

Macro business news comes via Reuters/Bloomberg-NEF/S&P/Mckinsey feeds already in registry. Per-company ESG ratings are absent and the commercial ones (MSCI, Sustainalytics) are paywalled.

**Recommended additions:**

- **MSCI ESG Public Search** — limited free tier, scraped to surface rating tier (AAA-CCC) per ticker; quarterly.
- **Sustainalytics public profiles** — free-tier risk score, scraped per company; quarterly.
- **Refinitiv ESG Scores public sample** — annual CSV.
- **Climate Action 100+ Net Zero Company Benchmark** — open CSV, 170 high-emitting firms; biannual.
- **As You Sow Climate Voting Tools** — open dataset, US-focused.
- **ISS ESG Voting Disclosure** — proxy-voting climate resolutions.

---

## 5. Research / peer-reviewed — verdict: **Partial**

Nature Climate Change, Science, Environmental Research Letters, AGU, Annual Review of Environment, PNAS feeds **are already in `RESEARCH_INDUSTRY_FEEDS`**. IPCC, NASA, NOAA, WMO are in `INTERNATIONAL_CLIMATE_FEEDS`. **Gap: pre-prints + dataset releases.**

**Recommended additions:**

- **arXiv physics.ao-ph + q-bio.PE** — OAI-PMH harvest, daily; free.
- **EarthArXiv pre-prints** — RSS, daily.
- **Copernicus C3S Climate Data Store** — already partial via `copernicus_adapter.py`; extend to dataset-release notifications (RSS on CDS news).
- **NASA GISS GISTEMP monthly bulletin** — flat-file pull, monthly.
- **NOAA Global Climate Report** — monthly text bulletin, scrapeable.
- **Berkeley Earth temperature dataset** — monthly CSV.
- **CrossRef API filtered for "climate" + "ESG"** — daily query, deep coverage of all journals.
- **Semantic Scholar API** — for citation graph + AI-assisted retrieval; daily.

---

## 6. Tourism climate impact — verdict: **NOT COVERED**

Niche but on user's list. No adapters today.

**Recommended additions:**

- **UNWTO Tourism Dashboard + climate briefs** — annual PDF + per-country CSV.
- **EU Eurostat tourism statistics (`tour_*` datasets)** — JSON API, monthly.
- **Mountain IT Snow Reliability Index (CIPRA/Alpine Convention)** — annual.
- **Climate-impact-on-ski-season** — Vanat *International Report on Snow & Mountain Tourism*, annual PDF.
- **NOAA Coral Reef Watch** — daily NetCDF for bleaching alerts (coastal/diving tourism).
- **EM-DAT extreme events** — already could pair with existing news; tourism-destination join.
- **Copernicus Marine Service sea-surface anomaly** — already partial via Copernicus adapter; extend.

---

## Sources to add — consolidated table

| Source | Dimension | Type | Tier | Effort (hrs) |
|---|---|---|---|---|
| Google Trends (`pytrends`) | Consumer trends | Pseudo-API | Public | 6 |
| Eurobarometer climate | Consumer trends | Document scrape | Government | 10 |
| Edelman Trust Barometer | Consumer trends | Annual PDF | Research | 8 |
| Pew Global Attitudes | Consumer trends | Annual JSON | Research | 6 |
| Ipsos Earth Day tracker | Consumer trends | Annual PDF | Research | 6 |
| CDP Open Data | Sustainability | JSON download | Scientific | 12 |
| SBTi Targets registry | Sustainability | CSV monthly | Scientific | 6 |
| Net Zero Tracker | Sustainability | CSV weekly | Research | 4 |
| GRI Disclosure DB | Sustainability | Scraped | Public | 14 |
| CSRD/ESRS national registries | Sustainability | Scraped per country | Government | 30 |
| MSCI ESG Public Search | Business | Scraped quarterly | Commercial | 12 |
| Sustainalytics public | Business | Scraped quarterly | Commercial | 12 |
| Climate Action 100+ | Business | CSV biannual | Research | 4 |
| arXiv + EarthArXiv | Research | OAI-PMH daily | Scientific | 8 |
| CrossRef + Semantic Scholar | Research | API daily | Scientific | 10 |
| NASA GISS GISTEMP | Research | Flat file monthly | Scientific | 4 |
| NOAA Global Climate Report | Research | Scrape monthly | Scientific | 4 |
| Berkeley Earth | Research | CSV monthly | Scientific | 4 |
| UNWTO climate briefs | Tourism | PDF annual | Government | 8 |
| Eurostat `tour_*` | Tourism | JSON monthly | Government | 6 |
| Vanat Snow & Mountain | Tourism | PDF annual | Research | 6 |
| NOAA Coral Reef Watch | Tourism | NetCDF daily | Scientific | 10 |
| Pacific SIDS RSS pack (12 countries) | News | RSS | Public | 6 |
| Francophone Africa RSS pack (7 countries) | News | RSS | Public | 6 |
| Caribbean RSS pack (8 countries) | News | RSS | Public | 6 |
| Central America RSS pack (7 countries) | News | RSS | Public | 5 |
| Central Asia RSS pack (4 countries) | News | RSS | Public | 4 |

**Total effort estimate:** ~217 engineer-hours (~5.5 weeks single-dev).

---

## Country coverage gap vs UN-193

Currently distinct alpha-2 codes in `eu_feeds_registry.py`: **~87**.
Codes from `.env.example` suggested global list: **~80** (overlaps with feeds but a few gaps).
**UN-193 minus current ~87 = ~106 countries with zero local feeds.**

**Highest-priority missing UN-193 members** (population × climate vulnerability):
- Sub-Saharan Africa: AO, MZ, ZW, BW, NA, CM, CI, ML, BF, NE, MR, SD, SS, SO, DJ, ER, CD, CG, GA, GQ, CF, TD, BJ, TG, LR, SL, GN, GW, GM, CV, ST, MG, MU, SC, KM
- Asia: MM, KH, LA, MN, NP, BT, LK, MV, AF, KG, TJ, TM, KP
- LATAM/Caribbean: BO, EC, PY, UY, VE, GT, HN, NI, SV, CR, PA, BZ, HT, DO, JM, TT, BB, GY, SR, CU, BS, GD, LC, VC, AG, DM, KN
- Pacific SIDS: FJ, PG, SB, VU, NC, NR, MH, FM, KI, TV, PW, WS, TO

Climate vulnerability disproportionately concentrates in this gap (SIDS, sub-Saharan, Andes). For a "one source of truth" mission this is the **single biggest credibility gap**.

---

## Update cadence proposal

| Source type | Cadence | Reason |
|---|---|---|
| RSS news feeds | Hourly (existing 6 h batch is too slow for breaking news) | Truth-machine must lead chatter |
| Open-Meteo / ECMWF / Copernicus | Daily | Weather + observation refresh rate |
| Google Trends | Daily | Trend smoothing window |
| arXiv / EarthArXiv / CrossRef | Daily | Pre-print velocity |
| NASA GISS / NOAA monthly bulletins | Monthly | Source publication rhythm |
| Climate TRACE, OWID, Climate Action Tracker, ND-GAIN | Quarterly | Datasets revise annually but errata land mid-year |
| IRENA, UNFCCC NDC | Quarterly | Slow-moving but policy windows matter |
| CDP, SBTi, Net Zero Tracker | Monthly | Corporate commitments accumulate |
| GRI, CSRD/ESRS scrapes | Quarterly | Filings cluster around fiscal-year close |
| MSCI / Sustainalytics public | Quarterly | Rating revision rhythm |
| Eurobarometer / Pew / Ipsos / Edelman | Annually (with quarterly recheck for new releases) | Survey cycle |
| UNWTO / Vanat / Eurostat tourism | Quarterly | Seasonal granularity |

---

## Recommended next-three sprint shape

1. **Sprint A — Coverage** (1 week): RSS packs for Pacific SIDS, francophone Africa, Caribbean, Central America, Central Asia. Adds ~38 countries; closes biggest credibility gap.
2. **Sprint B — Disclosure layer** (2 weeks): CDP + SBTi + Net Zero Tracker adapters + new `company_climate_disclosures` schema. Unlocks Sustainability + Business dimensions in one shot.
3. **Sprint C — Sentiment + research depth** (1.5 weeks): Google Trends + arXiv/EarthArXiv + CrossRef. Unlocks Consumer Trends + deepens Research dimension.

Tourism layer best deferred until the above three land — it leans on the SIDS RSS pack and Copernicus marine data already arriving in Sprint A.
