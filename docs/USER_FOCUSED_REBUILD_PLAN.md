# Climate News Platform - User-Focused Rebuild Plan

**Date**: 2025-12-26
**Focus**: REAL user needs, not just backend fixes

---

## 🎯 **Core User Problems** (REVISED)

### Primary Problem
**Users face climate misinformation** and need a tool to:
1. Verify trustworthiness of climate news
2. Dig deeper into specific claims
3. Understand climate concepts mentioned in articles
4. Compare sources and find evidence
5. Discover vetted news by topic/region

### User Persona
- **Climate-concerned citizen** who reads news
- Wants to separate fact from fiction
- Needs educational context for technical terms
- Wants to explore news by location/topic
- Needs visual, easy-to-understand trust indicators

---

## 🚨 **Current State Reality Check**

### What Actually Works ❌
- ✅ Articles can be ingested
- ✅ Claims are extracted
- ❌ **Verification shows "unverified"** (not actually finding evidence!)
- ❌ **No user-facing filtering**
- ❌ **No discovery features**
- ❌ **No educational content**
- ❌ **No interactive analysis**
- ❌ **No visual trust indicators**

### What Users See ❌
- List of articles (boring)
- Text that says "3 claims verified" but they're all "unverified"
- No way to filter or discover
- No map view
- No explanations
- No interactive features

**Bottom Line**: It's a static list, not a "lens" to climate news.

---

## 🎯 **Priority 1: Core "Lens" Features**

### 1. Visual Trust Indicators
**Goal**: Users should SEE trustworthiness at a glance

**Features**:
- [ ] Confidence score gauges (0-100)
- [ ] Color-coded verification badges
- [ ] Visual evidence strength indicators
- [ ] Source credibility charts
- [ ] Trust score breakdown diagrams

**Implementation**:
- Use recharts or victory for visualizations
- Add gauge components for scores
- Color system: Green (verified), Yellow (partial), Red (disputed)

---

### 2. Discovery by Topic/Region
**Goal**: Users can request fresh news on specific topics/regions

**Features**:
- [ ] Topic selector (Arctic, Forests, Oceans, Policy, etc.)
- [ ] Region/Country selector
- [ ] "Fetch Fresh News" button that triggers API to find new articles
- [ ] Save preferences (localStorage)
- [ ] Show loading state while fetching

**API Endpoint**:
```
POST /api/discover
{
  "topic": "arctic climate",
  "region": "scandinavia",
  "max_articles": 10
}
```

**Implementation**:
- Create discovery service that searches Google/Perplexity
- Filter by topic keywords + region
- Ingest and process automatically
- Return curated results

---

### 3. World Map Visualization
**Goal**: Users see WHERE news is coming from geographically

**Features**:
- [ ] Interactive world map (Leaflet or Mapbox)
- [ ] Markers for each article location
- [ ] Click marker to see article details
- [ ] Filter map by topic
- [ ] Show claim density by region

**Implementation**:
- Use react-leaflet
- Geocode article locations (store lat/long)
- Cluster markers for readability
- Color-code by verification status

---

### 4. Interactive Claim Analysis Chat
**Goal**: Users can ask questions about claims and get AI explanations

**Features**:
- [ ] Chat widget on article pages
- [ ] Ask: "What does this mean?"
- [ ] Ask: "Find evidence for this claim"
- [ ] Ask: "Compare with other sources"
- [ ] Ask: "Explain [technical term]"
- [ ] Get AI-generated responses with citations

**Implementation**:
- Use Claude API for chat
- Context: article + claims + fact-checks
- Provide sources and links
- Store conversation history

---

### 5. About/Methodology/Data Sources Pages
**Goal**: Build trust through transparency

**Pages**:
- [ ] **/about** - Mission, team, why we exist
- [ ] **/methodology** - How fact-checking works
- [ ] **/data-sources** - List of trusted sources we use
- [ ] **/how-it-works** - Visual explanation of the pipeline

**Content**:
- Explain AI models used
- Show verification process step-by-step
- List scientific databases (NASA, NOAA, etc.)
- Transparency about limitations

---

## 🎯 **Priority 2: Enhanced UX**

### 6. Advanced Filtering
**Goal**: Users can slice and dice articles

**Filters**:
- [ ] By verification status (verified, partial, disputed)
- [ ] By date range
- [ ] By source credibility
- [ ] By topic tags
- [ ] By region
- [ ] By claim count
- [ ] By confidence score

**Implementation**:
- Filter UI component
- Update API to accept filter params
- Real-time filtering

---

### 7. Educational Tooltips
**Goal**: Explain climate concepts inline

**Features**:
- [ ] Hover on technical terms → tooltip with definition
- [ ] Link to full explanations
- [ ] "Learn more" buttons
- [ ] Glossary page

**Implementation**:
- Identify technical terms in text
- Match against climate glossary
- Add tooltip components
- Wikipedia/NASA links

---

### 8. Evidence Drill-Down
**Goal**: Show HOW we verified each claim

**Features**:
- [ ] "See Evidence" button on each claim
- [ ] List of sources consulted
- [ ] Excerpts from sources
- [ ] Confidence calculation explanation
- [ ] Links to original sources

**Implementation**:
- Expand fact_check data in UI
- Show evidence array
- Link to external sources
- Explain confidence scoring

---

## 🎯 **Priority 3: Fix Verification**

### 9. Actually Verify Claims
**Goal**: Stop showing "unverified" for everything

**Current Issue**:
- Evidence retriever returns empty array
- Verdict is always "unverified"
- Confidence always 0.3

**Fix**:
- [ ] Implement real evidence retrieval (Google Fact Check API, scientific DBs)
- [ ] Add claim-specific search queries
- [ ] Use Perplexity for evidence
- [ ] Store actual sources
- [ ] Calculate real confidence scores

---

## 📊 **Implementation Priority Matrix**

| Feature | User Impact | Complexity | Priority |
|---------|-------------|------------|----------|
| Fix verification | HIGH | MEDIUM | **P0** |
| About/Methodology pages | HIGH | LOW | **P0** |
| Visual confidence scores | HIGH | MEDIUM | **P1** |
| Interactive chat | HIGH | HIGH | **P1** |
| Discovery feature | HIGH | MEDIUM | **P1** |
| World map | MEDIUM | MEDIUM | **P2** |
| Advanced filtering | MEDIUM | LOW | **P2** |
| Educational tooltips | MEDIUM | MEDIUM | **P3** |

---

## 🚀 **Week 1 Roadmap**

### Day 1-2: Fix Core Issues
- [ ] Fix claim verification to find real evidence
- [ ] Create About/Methodology/Data Sources pages
- [ ] Add visual confidence score gauges

### Day 3-4: Discovery & Filtering
- [ ] Build topic/region discovery feature
- [ ] Implement filtering system
- [ ] Test with real user scenarios

### Day 5-7: Interactive Features
- [ ] Build claim analysis chat
- [ ] Add educational tooltips
- [ ] Create world map visualization

---

## 🎨 **Design Principles**

1. **Visual First** - Show, don't tell (gauges, charts, maps)
2. **Interactive** - Let users explore and ask questions
3. **Educational** - Explain concepts and methodology
4. **Transparent** - Show sources and confidence reasoning
5. **Actionable** - Help users make informed decisions

---

## 📝 **Success Metrics**

### User Engagement
- Time spent on article pages
- Chat interactions per session
- Filter usage rate
- Map interactions

### Trust Building
- About page views
- Methodology page views
- Evidence drill-down clicks
- Source link clicks

### Discovery
- Discovery feature usage
- New topics explored
- Geographic diversity

---

## 🎯 **The "Lens" Vision**

The platform should feel like:
- **A Magnifying Glass** - Zoom into claims and see evidence
- **A Filter** - Separate signal from noise
- **A Teacher** - Learn while you read
- **An Explorer** - Discover news by topic/region
- **A Trusted Guide** - Transparent, visual, interactive

NOT just:
- ❌ A list of articles
- ❌ Backend infrastructure showcase
- ❌ Static text-based results

---

**Next Action**: Start with P0 items (Fix verification + About pages)
