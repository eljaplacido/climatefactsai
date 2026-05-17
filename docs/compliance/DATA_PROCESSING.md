# Data Processing Inventory

**Effective date:** 2026-05-17
**Last reviewed:** 2026-05-17
**Document version:** 1.0

This document is the authoritative list of every sub-processor that
touches user personal data, what data each receives, and the contractual
basis for the transfer. It is referenced by `PRIVACY_POLICY.md`,
`GDPR_DPIA.md`, and any DPA we sign with enterprise customers.

---

## 1. Sub-processors

| # | Sub-processor | Purpose | Personal data received | Storage location | Transfer mechanism |
|---|---|---|---|---|---|
| 1 | **Google LLC** | OAuth (`/api/auth/oauth/callback?provider=google`) | Email, name, avatar URL — only at sign-in time | US (Google datacentres) | Standard Contractual Clauses + Adequacy decisions where they exist |
| 2 | **Microsoft Corporation** | OAuth (`/api/auth/oauth/callback?provider=microsoft`) | Email, display name — only at sign-in time | US/EU (Microsoft Cloud) | SCCs |
| 3 | **Anthropic, PBC** | Multi-LLM cross-verification (claim extraction); deep-search synthesis (when ANTHROPIC_API_KEY is set) | URL text content; user query text; never email/name/IP | US | SCCs; data not used to train Anthropic models per their API terms |
| 4 | **DeepSeek** | Primary claim extraction; chat synthesis; URL credibility scoring | URL text content; user query text; never email/name/IP | China (mainland) — see §3 below | Contractual data-processing terms; cross-border transfer notice in `PRIVACY_POLICY.md` |
| 5 | **Perplexity** (optional) | External research lookups during deep-search | User query text; no PII | US | SCCs |
| 6 | **OpenAI** (optional, for vector embeddings) | Article text → embedding vector for pgvector | Article text excerpts; no user PII | US | SCCs; per-API-call billing |
| 7 | **SendGrid (Twilio)** | Transactional email (email-verification, password-reset, alerts) | Email address + transactional content | US | SCCs |
| 8 | **Stripe** | Subscription billing | Email + billing details (Stripe holds card data, we do not) | US | SCCs + PCI-DSS Level 1 |
| 9 | **Google Cloud Platform** | Infrastructure (Cloud Run, Cloud SQL, GCS, Memorystore, Cloud Scheduler) — *target deployment location `europe-west4`* | All hosted data | EU `europe-west4` (planned) | Adequacy decision (EU/Eire) once region cutover happens; SCCs in the interim |
| 10 | **Climate TRACE, OWID, Climate Action Tracker, UNFCCC NDC Registry, IRENA, World Bank CCKP, Global Carbon Project** | Public-data source-of-truth for sustainability indicators | **None** (we pull their public data via HTTPS) | Various | N/A — no personal data is sent |
| 11 | **Anthropic Claude (this assistant)** | Pair-programming during platform development | No production user data; only code + docs | Anthropic API | Internal use; not used at runtime |

The platform's **public-facing endpoints** (`/api/methodology/*`,
`/api/drift/source-mix`, etc.) expose no personal data — they expose
the platform's own prompts (by fingerprint only, not raw template),
formulas, indicators, and aggregated calibration metrics.

---

## 2. Data category × sub-processor matrix

| Category | Google OAuth | MS OAuth | Anthropic | DeepSeek | Perplexity | OpenAI | SendGrid | Stripe | GCP |
|---|---|---|---|---|---|---|---|---|---|
| Email | ✓ at sign-in | ✓ at sign-in | — | — | — | — | ✓ for emails | ✓ for billing | ✓ at rest |
| Name | ✓ at sign-in | ✓ at sign-in | — | — | — | — | ✓ in templates | ✓ for billing | ✓ at rest |
| Password hash | — | — | — | — | — | — | — | — | ✓ at rest |
| IP address | — | — | — | — | — | — | — | — | ✓ in logs |
| User-Agent | — | — | — | — | — | — | — | — | ✓ in sessions |
| URL content submitted | — | — | ✓ when multi-LLM enabled | ✓ | — | ✓ embeddings | — | — | ✓ at rest |
| User query text | — | — | ✓ when multi-LLM enabled | ✓ | ✓ when configured | — | — | — | ✓ at rest |
| Bookmarks + history | — | — | — | — | — | — | — | — | ✓ at rest |
| Source suggestions | — | — | — | — | — | — | — | — | ✓ at rest |
| Calibration labels | — | — | — | — | — | — | — | — | ✓ at rest |
| Payment details | — | — | — | — | — | — | — | ✓ | — (we never store card data) |

---

## 3. Cross-border transfer notes

### 3.1 DeepSeek (China)

DeepSeek is a Chinese AI provider. We use it as the primary LLM for
claim extraction because of its strong climate-science benchmark
performance + cost ratio. Risk mitigations:

- The data sent is **URL content** (which is publicly accessible on the
  source website) plus the user's **query text** (which is the user's
  own input). No personal identifiers, no email, no IP, no session
  data is included in the API call.
- The DeepSeek API call is initiated server-side by Climatefacts.ai; the
  user's browser does not connect directly to DeepSeek.
- Per DeepSeek's API terms (as of 2026-05), customer-submitted data is
  not used to train their models.
- Users uncomfortable with this transfer can:
  - Set `CLILENS_MULTI_LLM_VERIFY=1` to force Anthropic as a secondary
    verifier (which adds an US-based check)
  - Self-host the platform with a different LLM provider configured
    via env variables
  - Request manual deletion of any URL submissions

This is a residual risk acknowledged in `GDPR_DPIA.md §3.2`.

### 3.2 US-based sub-processors

Google, Microsoft, Anthropic, OpenAI, Stripe, SendGrid, and Perplexity
are US-based. We rely on Standard Contractual Clauses (SCCs) for each.
The Data Protection Contact maintains copies of each executed DPA on
file at the platform legal address; available on request.

---

## 4. Retention table

Same as `PRIVACY_POLICY.md §6`. Reproduced here for the
sub-processor view:

| Sub-processor | Data retention at sub-processor |
|---|---|
| Google OAuth | We don't store Google tokens — only the resulting account row + provider ID |
| Microsoft OAuth | Same |
| Anthropic | Per Anthropic's privacy policy; we don't pin retention beyond API call |
| DeepSeek | Per DeepSeek's terms; we don't pin retention beyond API call |
| Perplexity | Per Perplexity's policy |
| OpenAI | Per OpenAI's API data-use policy (30-day call retention for abuse monitoring; not used for training) |
| SendGrid | Per SendGrid's retention (we delete on request) |
| Stripe | Per Stripe's PCI obligations + their privacy policy |
| GCP | Same as our retention (data is hosted, not "sub-processed" in the legal sense beyond GCP's standard processor role) |

---

## 5. How to update this document

1. Open a PR that:
   - Adds the new sub-processor row to §1
   - Adds the column to §2's matrix
   - Documents any cross-border transfer in §3
   - Updates retention in §4
2. Have the Data Protection Contact review
3. Update `PRIVACY_POLICY.md §4.1` to match
4. Bump the document version in the header

Material changes (new sub-processor, new jurisdiction, new data
category) trigger a user notification per `PRIVACY_POLICY.md §10`.
