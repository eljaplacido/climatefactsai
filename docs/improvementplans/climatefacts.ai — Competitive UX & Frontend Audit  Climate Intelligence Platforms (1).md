# climatefacts.ai — Competitive UX & Frontend Audit: Climate Intelligence Platforms

## Executive Summary

The climate intelligence platform space has produced a small set of genuinely world-class UX examples — and a much larger set of data-dense, expert-only portals that fail general audiences. The best competitors succeed because they resolve a fundamental tension in climate data: the data is scientific and dense, but the audience is broad and emotionally motivated. This audit reviews the eight most relevant competitors to climatefacts.ai across five UX dimensions — information architecture, map and data visualization, country/entity profiles, personalization and alerts, and data storytelling — and translates each competitor's best practices into concrete implementation recommendations.

***

## The Competitor Landscape

Before diving into individual platforms, it is important to distinguish the three product archetypes represented across this space:

- **Civic/public science platforms** (Our World in Data, Climate Central, Carbon Brief): optimized for credibility, accessibility, and media reuse
- **Policy/data portals** (Climate Watch/WRI, Copernicus C3S Atlas, World Bank CCKP): optimized for country-level professional analysis and data download
- **Commercial risk intelligence platforms** (Climate TRACE, IQAir, Jupiter Intelligence, Cervest): optimized for operational decisions with premium UX budgets

climatefacts.ai sits at the intersection of all three archetypes — public-facing truth with professional depth — which means it can borrow the best pattern from each tier without inheriting their weaknesses.

***

## Competitor 1: Our World in Data (OWID)

**URL:** ourworldindata.org

### What they do exceptionally well

Our World in Data built the most trusted open-data platform in the civic science space, primarily through their in-house **Grapher** tool — a fully open-source, embeddable interactive chart and map system. Their 2023 Grapher redesign is one of the most instructive UX case studies in this space.

**UX strengths:**
- **Multi-view consistency**: every chart offers chart, map, and table views of the same dataset via tabs in the upper left corner — users explore the same truth from three perspectives without leaving context
- **Dynamic sharing**: sharing a chart preserves the exact configuration — country selection, year range, view type — as a URL. Social previews on Twitter/LinkedIn/Slack show the exact chart configuration, not just the page title
- **Prominent data provenance**: every chart displays the source prominently; clicking "Learn more about this data" opens a provenance overlay with full methodology
- **Full-screen exploration**: one-click expansion of any chart to full-browser-window for deep analysis
- **Axis alignment controls**: "Align axis scales" toggle lets users compare countries either on a common Y-axis (for comparison) or auto-scaled per country (for per-country trends)
- **Country selector with custom groups**: click-through country/entity selector with region groups, continental aggregates, and custom combinations
- **Open source everything**: all Grapher code is MIT-licensed on GitHub — the entire codebase can be studied, forked, and reused

**UX weaknesses:**
- No personalization layer: no user accounts, no followed countries/topics, no notification system
- News/text content not well integrated with charts
- Mobile experience lags behind desktop significantly

### Implementation recommendations for climatefacts.ai

| OWID Pattern | climatefacts.ai Adaptation |
|---|---|
| Multi-view tabs (chart / map / table) | Apply to every data panel: one dataset, three representations. Default to map for geographic data, line chart for temporal, table for download. |
| Persistent URL state | Encode all user selections (country, variable, year, chart type) in URL query params. Every state is shareable. |
| Provenance overlay | Every visualization and KPI card links to a provenance drawer: source name, dataset version, last updated, methodology link, license type. |
| Source credit in chart footer | Add a compact source badge (e.g., "ERA5 · Copernicus CDS") beneath every chart. Clicking expands methodology. |
| Country selector with regions | Build a hierarchical picker: World → Continent → Country → Region. Include preset groups (G20, SIDS, EU, LDCs, top emitters). |

***

## Competitor 2: Climate Watch (WRI)

**URL:** climatewatchdata.org

### What they do exceptionally well

Climate Watch is the most comprehensive open policy data platform for climate, offering 150 years of GHG emissions, NDC tracking, country profiles, and scenario pathways. It is the closest structural analogue to climatefacts.ai's ambition, though focused on policy rather than climate facts.

**UX strengths:**
- **Country Profile pages**: each country gets a structured, tabbed profile covering emissions, NDCs, vulnerability, policy, and sectoral data — a modular "climate passport" per nation
- **Data Explorer**: users can build custom multi-country, multi-variable cross-comparisons with downloadable output
- **My Climate Watch**: saved views, shared visualizations, downloadable configs — lightweight personalization without requiring full accounts
- **Embeddable charts**: unique share URLs and embed codes for every visualization
- **Linkages layer**: maps NDC commitments to SDG targets — connecting data to policy narrative
- **Modular sections**: country profiles are broken into discrete tabs (emissions, policies, risks, targets) rather than a single scrolling wall of data

**UX weaknesses:**
- Very heavy cognitive load; optimized for experts, not general audiences
- Visual design is utilitarian — prioritizes function over engagement
- No news or real-time signal integration
- Navigation can feel disorienting across the many tools

### Implementation recommendations for climatefacts.ai

| Climate Watch Pattern | climatefacts.ai Adaptation |
|---|---|
| Country profile with tabbed sections | Adopt a "Climate Passport" page per country: tabs for Temperature, Precipitation, Extreme Events, Emissions, Policy, News. Each tab is independently linkable. |
| "My Climate Watch" saved views | Implement a lightweight watchlist: users follow countries and topics; a personalized dashboard assembles their feed. Can be unauthenticated (localStorage-backed) first, account-backed later. |
| Data Explorer | Build a cross-country chart builder: select variable → select countries → select time range → generate shareable chart. Start simple, add complexity iteratively. |
| NDC → SDG linkage | Implement a "data cross-links" layer: for each climate fact (e.g., sea level rise trend), show linked policy, related news, and connected indicators. This is the semantic graph layer. |

***

## Competitor 3: Climate Central

**URL:** app.climatecentral.org

### What they do exceptionally well

Climate Central is the gold standard for translating complex climate science into communicable, local-first visuals for media partners and the public. Their redesign — executed by Radish Lab — is one of the most instructive cases of information architecture solved through user research rather than data priority.

**UX strengths:**
- **Local-first framing**: every visualization is localized to the user's city or region — national and global trends are secondary to "what does this mean for me?"
- **Media-ready exports**: every graphic is designed to be downloaded and used by journalists and broadcasters. Resolution, labeling, and aspect ratios are publication-ready
- **Weekly Climate Matters**: a curated weekly digest of climate impact graphics distributed to thousands of media partners — a high-leverage distribution model
- **Observable Framework for complex products**: for multi-page, high-performance data products (e.g., urban heat island explorer), they use Observable Framework rather than traditional CMS — enabling code-driven, interactive multi-page experiences without the overhead of a full app
- **Narrative architecture**: content strategy redesign organized around the organization's story rather than data categories — moving from "here is our data" to "here is what we found"

**UX weaknesses:**
- Heavy production overhead for each graphic; hard to scale
- Not a self-serve platform; primarily a media tool
- No country comparison or global explorer mode

### Implementation recommendations for climatefacts.ai

| Climate Central Pattern | climatefacts.ai Adaptation |
|---|---|
| Local-first framing | Default map to user's inferred location (IP geolocation). First-open experience should show "Your country's climate signal" before zooming out to global view. |
| Media-ready export | Every chart includes a "Download for publication" button: exports PNG at 2×, with title, source credit, and platform watermark baked in. Embeddable iframes for all charts. |
| Weekly curated digest | Implement a scheduled digest: "This week's climate signal for [your followed countries]" — delivered as email or in-app notification. Each item links to a data visualization. |
| Narrative-first IA | Design landing experience as a story-entry, not a data portal. Headline: "The planet this week" with 3–5 lead insights, then invite users to explore deeper. |

***

## Competitor 4: Global Forest Watch (GFW)

**URL:** globalforestwatch.org

### What they do exceptionally well

Global Forest Watch — built by WRI and Vizzuality — is the most sophisticated near-real-time environmental monitoring web application in the civic space. Its map-first experience is the benchmark for interactive environmental data products.

**UX strengths:**
- **Map-first, layer-based architecture**: users arrive at a full-screen interactive map and add layers — tree cover, fires, biodiversity, climate, land use — incrementally. Each layer is independently toggleable and explained inline
- **Area of Interest (AOI) alerts**: users draw or select a geographic area and subscribe to alerts when data changes — weekly fire alerts, deforestation flags, etc.
- **Temporal animation**: multi-year data encoded into single map tiles, enabling smooth animation of historical change without re-downloading per frame — a key performance pattern for large temporal datasets
- **30m × 30m precision**: near-real-time (weekly) updates at half-football-pitch scale demonstrates what's possible when satellite data is properly pipeline-engineered
- **Continuous iteration**: the platform has undergone continuous iterative development based on user feedback rather than big-bang releases
- **Sector-specific sub-portals**: commodities map, fires map, watershed map, forest atlases — same data engine, specialized entry points for different user contexts

**UX weaknesses:**
- Layer complexity can overwhelm first-time users
- Onboarding for new users is weak; the power of the tool is not immediately obvious
- Mobile experience is significantly limited

### Implementation recommendations for climatefacts.ai

| GFW Pattern | climatefacts.ai Adaptation |
|---|---|
| Map-first, layer system | Build the global map as a layer stack: Temperature Anomaly, Precipitation, Extreme Events, Air Quality, Emissions. Each layer has an info card, source badge, time slider. |
| Area of Interest (AOI) alerts | Let users draw a region, a country, or select an administrative boundary and subscribe to climate signal changes. Email or push when thresholds are crossed. |
| Temporal tile animation | Encode historical climate variables into animated map sequences. Use deck.gl's `TripsLayer` or tile-based temporal animation for performance at global scale. |
| Sector sub-portals | Plan domain entry points: "Climate & Water", "Extreme Weather", "Temperature Trends", "Emissions & Carbon", "Air Quality" — each with a curated first experience for that domain's audience. |

***

## Competitor 5: Copernicus Interactive Climate Atlas (C3S Atlas)

**URL:** atlas.climate.copernicus.eu

### What they do exceptionally well

Launched in February 2024, the C3S Atlas operationalized the IPCC AR6 Interactive Atlas into a production-grade public tool. It is the most technically rigorous public climate visualization tool in existence.

**UX strengths:**
- **Past + future in one interface**: toggles between observed historical data and climate projections across multiple warming scenarios (SSP1 to SSP5) within the same UI context
- **IPCC-quality standards**: datasets meet IPCC compatibility and quality requirements — citations are institutional-grade
- **Regional vs global toggle**: users can zoom to regional detail (IPCC reference regions) from the global view, maintaining data resolution across zoom levels
- **Multi-variable selector**: 30 climate variables and derived indices accessible through a clean dropdown
- **Integrated with CDS**: visualizations link directly to the downloadable dataset in the Copernicus Data Store for power users

**UX weaknesses:**
- Designed for scientific professionals; nearly inaccessible for general users without training
- No narrative context; raw maps without explanatory text
- No news integration, alerts, or personalization
- Interface performance is heavy; slow on lower-bandwidth connections

### Implementation recommendations for climatefacts.ai

| C3S Atlas Pattern | climatefacts.ai Adaptation |
|---|---|
| Historical ↔ Projection toggle | Every chart offers a timeline toggle: "Observed (historical)" vs "Projected (SSP2-4.5 / SSP5-8.5)". This is what makes a climate fact platform distinct from a weather platform. |
| Warming scenario switcher | For projection charts, expose a scenario switcher: 1.5°C / 2°C / 3°C warming. Show divergence between scenarios visually. |
| IPCC regional granularity | Align regional views with official IPCC reference regions rather than arbitrary administrative boundaries. This ensures scientific comparability. |
| Projection range uncertainty bands | When displaying future projections, show uncertainty ranges as shaded bands rather than single lines. This is critical for scientific honesty. |

***

## Competitor 6: Climate TRACE

**URL:** climatetrace.org

### What they do exceptionally well

Climate TRACE is the most sophisticated facility-level emissions tracking platform, tracking 744 million+ emitting assets with AI-satellite pipelines. It won a UX Design Award in 2025 for a related delta-climate platform.

**UX strengths:**
- **Facility-level drill-down**: users can zoom from global → country → state → city → individual facility (power plant, factory, mine). The zoom level maps directly to the data granularity
- **Bold visual identity**: strong color palette and typography give the platform an immediately distinctive look — the result of treating it as a brand experience, not just a data portal
- **Open without signup**: all data is freely downloadable with no registration gate — critical for trust and adoption in the scientific community
- **Coalition credibility**: the "who built this" story (Al Gore, Google, NGO coalition) is woven into the product identity — provenance as brand
- **Award-winning delta-climate UX**: the lesson from the delta-climate design process was to reduce colors, return to black/white wireframes when overwhelmed, then reintroduce color only for emphasis

**UX weaknesses:**
- Very sector-specific; not easily adaptable for general climate facts
- No personalization or news integration
- Facility-level focus can overwhelm users looking for country-level summaries

### Implementation recommendations for climatefacts.ai

| Climate TRACE Pattern | climatefacts.ai Adaptation |
|---|---|
| Zoom-level granularity matching data depth | Design map zoom levels to progressively reveal more data: global → continent → country → city → local station. Coarser data (ERA5) at low zoom; station-level at high zoom. |
| Bold brand design language | Invest in a strong visual identity for climatefacts.ai. Avoid the generic "SaaS blue + data portal gray" aesthetic. The brand signal is part of the credibility signal. |
| No-signup data access | Core data views should require no account. Accounts unlock: personalization, saved views, alerts, comparison exports. The free baseline must be fully useful. |
| Provenance as brand | Make the "how we know this" story prominent. A "Data Sources" page and per-chart source badge reinforce the "climate truth" positioning. |

***

## Competitor 7: IQAir (AirVisual)

**URL:** iqair.com / airvisual.com

### What they do exceptionally well

IQAir AirVisual is the best consumer-grade global environmental monitoring app — covering 500,000+ locations across 100+ countries with AI-calibrated sensor validation. It represents the highest standard for consumer UX applied to environmental data.

**UX strengths:**
- **2D and 3D world pollution maps**: users can switch between a 2D choropleth heatmap and a 3D "AirVisual Earth" globe modelization — two representations of the same real-time data
- **Health recommendations system**: AQI numbers are immediately translated into plain-language health recommendations for sensitive groups — bridging the gap between index and human meaning
- **Month-long historical view**: enhanced 30-day historical view for any location — not just real-time, but recent-past trending
- **Wildfire and smoke alerts**: wildfire events appear as interactive map overlays with real-time data, historical context, and forecast — a multi-layered event presentation
- **Pollen + weather integration**: air quality is presented alongside pollen, UV, humidity, and weather — a holistic health environment view rather than single-metric focus
- **Strong mobile-first execution**: the app is rated as one of the most polished environmental data experiences on mobile

**UX weaknesses:**
- Limited climate data (not historical climate, just real-time/forecast air quality)
- No projection or future-state visualization
- No country policy or news integration

### Implementation recommendations for climatefacts.ai

| IQAir Pattern | climatefacts.ai Adaptation |
|---|---|
| 2D/3D map toggle | Implement a 3D globe view (Mapbox globe projection or Three.js/deck.gl) as a premium visualization mode for global data overview. Default to 2D; toggle to 3D for exploration. |
| Plain-language translation | Every data point should have a plain-language interpretation layer: "This means your region has experienced 3× more extreme heat days than in 1990." Science metric → human sentence. |
| Event overlays with multi-state | Extreme weather events (floods, fires, droughts) should appear as map overlays with a mini-timeline: historical → current → forecast. |
| Holistic co-variable view | For any location, surface related co-variables contextually: temperature anomaly + air quality + precipitation deficit together, not in isolation. |

***

## Competitor 8: Probable Futures

**URL:** probablefutures.org

### What they do exceptionally well

Probable Futures is the best example of **accessible climate projection design** for non-expert audiences — translating CORDEX-CORE climate model output into intuitive maps and narratives.

**UX strengths:**
- **Warming level framing**: maps are organized by global warming level (1°C, 1.5°C, 2°C, 3°C) rather than year or scenario — this framing is intuitively understandable for non-scientists
- **Scrollytelling narrative chapters**: data is embedded in narrative chapters ("Stability", "Risk", "Complexity") that provide context before presenting maps — stories come before data
- **Pro tool for overlaying custom data**: Probable Futures Pro lets users upload their own datasets and overlay them on climate maps — climate risk × business data in one view
- **Non-technical audience design**: UX team explicitly removed complexity for non-technical users, keeping only the functionality that served their less-expert audience
- **Design easter egg — tilted UI**: page elements are subtly rotated 1°, 1.5°, or 2° to visually embody the temperature change milestones — a memorable design touch that makes abstract numbers tangible

**UX weaknesses:**
- Limited to climate projections; no historical observations or real-time data
- No country profiles, news, or alerts
- Relatively narrow variable coverage (heat, precipitation, humidity)

### Implementation recommendations for climatefacts.ai

| Probable Futures Pattern | climatefacts.ai Adaptation |
|---|---|
| Warming level as primary navigation | Offer a "warming world explorer": select 1.5°C / 2°C / 3°C and see what changes for a selected country — maps, affected indicators, key facts. Ties future data to familiar narrative. |
| Scrollytelling entry experience | Design a guided introduction for first-time users: a scrollable story that shows a striking climate signal, then invites exploration. Not a traditional "welcome" modal. |
| Data × user data overlay (Pro) | Future-state feature: allow users or organizations to upload their own data (crop yields, asset locations, population data) and overlay with climatefacts.ai variables. High-value enterprise use case. |
| Tilted/tangible design moments | Include at least one design moment that embodies climate data rather than just displays it. For example: a temperature anomaly bar that subtly changes the background color temperature as values increase. |

***

## Cross-Competitor UX Pattern Matrix

| Feature Pattern | OWID | Climate Watch | GFW | C3S Atlas | Climate TRACE | IQAir | Probable Futures | climatefacts.ai (target) |
|---|---|---|---|---|---|---|---|---|
| Country profiles | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | **Must-have** |
| Multi-view chart/map/table | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **Must-have** |
| URL-persistent state | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | **Must-have** |
| Projection / warming scenarios | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ | **Must-have** |
| AOI alerts / subscriptions | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | **Must-have** |
| News integration | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **Differentiator** |
| 3D globe view | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | **Nice-to-have** |
| Plain-language interpretation | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | **Differentiator** |
| Data provenance overlay | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | **Must-have** |
| Scrollytelling narrative | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | **Nice-to-have** |
| Open / no-signup access | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | **Must-have** |
| Embed/share charts | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **Must-have** |
| Media export (print-ready) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **Differentiator** |

***

## Section-by-Section Implementation Roadmap

### 1. Global Map (Core Experience)

**Best practice source:** GFW's layer architecture, IQAir's 2D/3D toggle, OWID's URL persistence

The central map should function as a **layer compositor**, not a choropleth selector. Each variable is a layer that can be added or removed. Performance is critical: use **deck.gl** over **Mapbox GL** for large climate datasets — deck.gl handles GPU-accelerated rendering of millions of data points with composable layers. Temporal animation should encode data into tile batches rather than downloading per frame, following GFW's approach.

Key technical choices:
- **Mapbox Globe projection** for low-zoom world view; switch to Mercator at country zoom level
- **deck.gl HexagonLayer or GridLayer** for density data (station coverage, data quality)
- **deck.gl BitmapLayer** for raster climate variables (ERA5 temperature, precipitation)
- **Animated temporal slider** encoding multi-decade data as a scrub-able timeline
- **Equal-area map projection** (not Mercator) for choropleth country-level maps — standard best practice to avoid area distortion

### 2. Country Climate Passport

**Best practice source:** Climate Watch's country profiles, World Bank CCKP's risk profiles, Climate-ADAPT's EU country pages

Each country page should be a **modular, tabbed profile** — the "Climate Passport" — structured as:

1. **Headline KPIs**: temperature anomaly trend, precipitation change %, extreme event frequency, data quality score
2. **Observed data tab**: interactive time series charts (temperature, precipitation, sea level if coastal). Historical baseline + recent anomaly.
3. **Projections tab**: warming scenario cards (1.5 / 2 / 3°C) with key projected changes. Uncertainty bands displayed as shaded areas.
4. **Extreme events tab**: recent and historical extreme events with event cards (similar to IQAir's wildfire overlays)
5. **Emissions & policy tab**: link to Climate Watch / Climate TRACE data for that country
6. **News feed tab**: curated news items for that country from the news pipeline described in the previous session
7. **Data quality badge**: transparent indicator of source tier (reanalysis / station-validated / sparse) per the architecture framework

WHO's Data Design Principles are an excellent reference here: data presentation should be "straightforward, on-point, realistic, internationalized, accessible, and responsive".

### 3. Data Visualization System

**Best practice source:** OWID's Grapher, Carbon Brief's chart guidelines, WHO data design principles

Climate data visualization has specific requirements that deviate from standard dashboard design:

- **Uncertainty must be shown**: climate projections are ranges, not lines. Always show min/median/max as shaded confidence bands.
- **Anomaly over absolute values**: relative change (vs 1850–1900 baseline) is more communicable than absolute temperature. Follow IPCC convention.
- **Sequential vs diverging color scales**: temperature anomaly maps use **diverging** scales (blue for below baseline, red for above). Precipitation and trend maps use **sequential**. Never use rainbow/jet color scales — they are perceptually misleading.
- **Consistent color assignments**: the same variable always uses the same color across all charts on the platform
- **Draw the eye**: use contrast, size, and motion to direct visual attention to the most important part of each graphic
- **Annotations over complexity**: annotations (labeled events, milestones, threshold lines) add insight without adding clutter
- **F-pattern hierarchy**: most important data in the top-left, less important toward bottom-right

**Recommended chart library stack:**

| Use case | Recommended library |
|---|---|
| Line, bar, area charts | Vega-Lite or Observable Plot (both open source, declarative) |
| Country choropleth maps | Datawrapper-style SVG maps OR deck.gl GeoJsonLayer |
| 3D globe / large-scale raster | deck.gl + Mapbox Globe |
| Animated transitions | Svelte transitions or Framer Motion (React) |
| Climate-specific chart types | Custom SVG using D3.js for stripe charts, beeswarms |

**Climate-specific chart types to implement:**
- **Warming stripes** (Ed Hawkins design): annual temperature anomaly encoded as color hue — visually powerful, immediately communicable
- **Joy plots / ridge charts**: distribution of daily temperatures over decades — excellent for showing distribution shift
- **Small multiples**: same variable across 9–20 countries in a grid — powerful for "how does my country compare?" questions
- **Beeswarm/unit charts**: individual extreme events as dots — makes frequency tangible

### 4. Personalization and Alerts

**Best practice source:** GFW's AOI alerts, IQAir's location-based notifications, OWID's "My Climate Watch"

The personalization layer is the biggest UX differentiator in the competitive landscape — **no competitor does it well**. This is the whitespace climatefacts.ai should own.

Recommended architecture:

**Tier 1: Anonymous (no account)**
- IP-geolocation defaults map to user's country on first visit
- localStorage-backed followed countries/topics (survives session, but not cross-device)
- One-click topic subscribe (e.g., "Follow: Temperature anomaly in Finland")

**Tier 2: Signed-in user**
- Persistent country + topic watchlist synced across devices
- Weekly digest email: "Climate signal in your followed countries this week" — structured similarly to Climate Central's Climate Matters
- Threshold alerts: "Notify me when [country] exceeds [variable] [threshold]" (e.g., "Finland 7-day mean temperature anomaly > 3°C")
- Custom comparison saves: save a multi-country chart configuration as a persistent view

Alert design must follow tiered urgency patterns:
- **Passive info** (weekly digest) → email
- **Context notification** (new data published) → in-app banner, not modal
- **Threshold alert** (extreme event crossed) → push notification + email, with high visual salience
- **Critical event** (ongoing extreme event) → persistent in-app banner until resolved

### 5. Data Storytelling and Narrative Layer

**Best practice source:** Probable Futures' scrollytelling, Climate Central's narrative architecture, SEI's humanizing-data approach

The gap between "data portal" and "platform people return to" is filled by narrative. Climate Central proved this with their redesign: organizing content by story rather than data category increased user engagement and clarity significantly.

**Scrollytelling implementation** for key onboarding and feature stories:
- Use **Scrollama.js** (lightweight, well-maintained) for scroll-triggered chart transitions
- Pattern: prose section → "animate in" a chart visualization → prose continues → chart transforms → reader is now inside the data
- Apply to: first-visit onboarding, annual climate recap, country deep-dives, extreme event explainers

**Onboarding flow design** (best from Appcues/Stonly analysis):
1. First-visit: show striking animated visualization with "The planet this week" headline
2. Soft prompt: "Which country do you care about most?" → immediate personalization with no friction
3. Guided tour: 3-step highlight overlay for map layers, country profiles, alerts
4. Value moment: surface one insight specific to their chosen country within 60 seconds of first visit

**"Plain language" layer** (following IQAir and Probable Futures):
Every metric should have a plain-language companion sentence generated or templated from the data:
- Temperature anomaly: `"Finland's last decade was 2.1°C warmer than the 20th-century average — the warmest on record."`
- Precipitation change: `"Kenya received 18% less rainfall in 2024 than the 1981–2010 average, the third driest year since measurements began."`

This pattern, applied systematically, transforms a data platform into a "climate truth" platform.

***

## Priority Feature Implementation Summary

### MVP (Phase 1) — Foundation
- Global choropleth map with ERA5 temperature + precipitation anomaly + one air quality variable
- URL-persistent state for all chart configurations
- Country profile pages with KPI cards, one time series chart, source provenance badge
- Data quality scoring badge per country/variable
- Multi-view toggle (chart / map / table) on every data panel
- Open, no-signup access baseline

### Differentiation (Phase 2) — Engagement
- Personalized watchlist (anonymous localStorage → account sync)
- Weekly climate digest email for followed countries
- Threshold alert system (in-app + email)
- Plain-language interpretation layer for KPIs
- News feed integrated into country profiles (from GDELT + Event Registry pipeline)
- Embeddable / shareable chart configurations

### Advanced (Phase 3) — Depth
- Projection scenarios (1.5°C / 2°C / 3°C warming level explorer)
- Scrollytelling entry experience
- Temporal animation of historical climate trends
- 3D globe view (deck.gl)
- Media-ready export (high-res PNG with source attribution)
- Custom data overlay (Pro tier) — user datasets × climate variables