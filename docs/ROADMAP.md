# Climatefacts.ai — Feature Roadmap

**Last Updated:** 2026-05-20
**Status Tracking:** DONE / IN PROGRESS / PLANNED

---

## Phase 1: Core Platform (DONE)
- FastAPI backend with PostgreSQL + pgvector
- Next.js 14 frontend with Tailwind CSS
- Article ingestion from Perplexity + RSS feeds
- Multi-country RSS feed registry (194 countries)
- JWT authentication (register, login, token refresh)
- URL analysis endpoint with claim extraction
- Celery + Redis for background task processing
- OpenTelemetry tracing with Jaeger
- Docker Compose deployment

## Phase 2: Architecture (DONE)
- Kafka → Celery + Redis refactor
- Domain-Driven Design (Content, Intelligence, Trust)
- 7 containers (down from 17)

## Phase 3: EU Expansion + Global Coverage (DONE)
- 194 countries with RSS feeds (193 UN member states + Kosovo)
- DeepL + DeepSeek translation integration
- Staggered Celery Beat scheduling
- 6 indicator adapters (Climate TRACE, OWID, CAT, UNFCCC NDCs, IRENA, ND-GAIN)

## Phase 4: Intelligence Pipeline (DONE)
- Automated fact-checking pipeline with Celery chains
- Advanced analytics dashboard
- DeepSeek-Only LLM migration
- Re-run Analysis & failure transparency
- URL Analysis / submit article fixes
- Transparency report visual fixes
- World map data gap resolution

## Phase 5: User Features (DONE)
- Auth & profiles (JWT, register, login, token refresh)
- Bookmarks + saved queries + reading history
- Stripe subscription billing (4 tiers: Freemium, Standard, Professional, Enterprise)
- API key management
- OAuth (Google, Microsoft)

## Phase 6: Trust Infrastructure (DONE)
- claim_provenance audit trail (model, prompt version, SHA-256 fingerprint, hallucination score)
- Versioned prompt registry with SHA-256 fingerprints
- Multi-LLM cross-verification (DeepSeek + Anthropic)
- Hallucination detection (spaCy NER + statistic check + LLM grounding)
- Platt scaling calibration (Brier, ECE, reliability diagrams)
- KL-divergence drift detection (source mix + prompt fingerprints)
- EU AI Act Article 50 labelling (`data-ai-generated`, JSON-LD)
- Source credibility tier database (27 seed rows, Scimago Q1-Q3)

## Phase 7: Agentic Platform (DONE)
- Agentic chat actions protocol (9 action types)
- chat_actions_log telemetry
- chatActionDispatcher.ts frontend controller
- AI transparency badge on all AI surfaces

## Phase 8: Corporate Claim Verification (DONE)
- `/companies` index and `/companies/[ticker]` detail pages
- 3 public adapters (CDP, SBTi, Net Zero Tracker)
- ECGT-aware claim verification (offset flagging, SBTi validation cross-ref)
- `company_climate_disclosures` schema with Scope 1/2/3 + assurance tracking

## Phase 9: Metrology & Trust Signals (DONE)
- Audit trail UUID → title/URL denormalization
- Decomposed confidence gauge (radar chart on CredibilityGauge)
- Self-audit gap published on /methodology (4.78 vs 3.6)
- Learned drift thresholds (Gaussian 2σ/3σ/4σ)
- Per-indicator uncertainty propagation in sustainability composite
- Per-country claim ledger endpoint
- Analysis reproducibility engine

## Phase 10: Long Horizon (PLANNED)
- Cross-language hallucination detection (per-language embeddings + claim clustering)
- FAIR metadata + immutable audit ledger (Hyperledger Fabric)
- Nature/TNFD biodiversity module
- Embed widget + QR fact-check cards
- Scenario engine + financial translation layer
- Mobile PWA

---

**Note:** This roadmap tracks shipped features. See `docs/reports/Implementation-Plan-2026-05-20.md` for the upcoming 12-week implementation plan.
