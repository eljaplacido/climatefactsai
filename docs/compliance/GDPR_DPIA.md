# Data Protection Impact Assessment (DPIA)

**Subject:** CliLens.AI platform — climate news verification + intelligence.
**Date completed:** 2026-05-17
**Reviewer:** Platform Engineering, Data Protection Contact (`support@clilens.ai`)
**Next review:** Annually, or on any change to processing purposes / sub-processors / data flows.
**Document version:** 1.0

This DPIA is conducted under GDPR Article 35. It describes how the platform
processes personal data, identifies risks, and documents the mitigations
already in place. It is intended to be readable by your DPO and by
EU/UK supervisory authorities.

---

## 1. Description of processing operations

### 1.1 What we do

CliLens.AI ingests climate news from ~230 public RSS sources, runs
claim extraction via DeepSeek (with optional Anthropic cross-verification),
indexes content with pgvector for hybrid search, and surfaces per-country
indicators from Climate TRACE, OWID, Climate Action Tracker, and (soon)
UNFCCC NDC / IRENA / WB CCKP. Users can submit URLs for independent
analysis; logged-in users can save searches, bookmark articles, suggest
new sources, and (for admin reviewers) record calibration labels.

### 1.2 Personal data categories

| Category | Data points | Notes |
|---|---|---|
| Account | Email, full name, password hash, OAuth provider IDs, subscription tier | Bcrypt for passwords; OAuth tokens stored as session refs only |
| Session | JWT jti, IP, User-Agent, timestamps | Used for replay detection (S2) |
| User-submitted content | URLs analysed, source suggestions, calibration labels | Linked to user_id |
| Activity | Bookmarks, reading history, saved queries | Logged-in only |
| Telemetry | Span data (request path, latency, status) | No content body |
| Application logs | Structured JSON | Passwords / raw tokens never logged |

### 1.3 Special-category data

The platform does **not** intentionally collect special-category data
(GDPR Art. 9 — race, politics, health, etc.). Climate news content may
incidentally reference health (climate-health linkages) or political
opinions (climate policy debates), but the platform processes article
text as factual content, not as a profile of any individual.

User-submitted URLs may, in rare cases, contain personal data about
third parties (e.g., a quote from a public figure). We do not extract
such data into structured fields; it remains in the `extracted_text`
column. Users are responsible for not submitting URLs containing
sensitive personal data about non-public individuals.

### 1.4 Data flows

```
   ┌──────────┐
   │  User    │
   └────┬─────┘
        │ HTTPS
        ▼
   ┌──────────────────────────────────────┐
   │  CliLens.AI API (FastAPI)            │
   │  - Auth: bcrypt + JWT sessions       │
   │  - Routes: /api/* (37+ routers)      │
   └─────┬───────────┬──────────┬─────────┘
         │           │          │
         ▼           ▼          ▼
   ┌─────────┐  ┌─────────┐  ┌─────────────────┐
   │Postgres │  │ Redis   │  │ Sub-processors  │
   │ (RLS    │  │ (rate   │  │ (LLMs, email,   │
   │ ready)  │  │ limit)  │  │  OAuth, billing)│
   └─────────┘  └─────────┘  └─────────────────┘
```

Sub-processors receive only the minimum data necessary for their
function (see `DATA_PROCESSING.md`).

---

## 2. Necessity and proportionality

### 2.1 Lawful basis

| Processing | Basis (GDPR Art. 6) |
|---|---|
| Account creation, login, password reset | Contract performance (6(1)(b)) |
| Email verification, replay detection, abuse prevention | Legitimate interests (6(1)(f)) |
| Personalised feed, bookmarks, history | Contract performance (6(1)(b)) |
| URL analysis | Contract performance (6(1)(b)) |
| Audit trail (claim_provenance) | Legitimate interests in defensible methodology (6(1)(f)) |
| Calibration labels | Legitimate interests in scoring accuracy (6(1)(f)) |
| Service security telemetry | Legitimate interests (6(1)(f)) |
| Marketing emails | Consent (6(1)(a)); withdrawable anytime |

### 2.2 Data minimisation

- We collect the minimum data required for each purpose (email + name
  for accounts; no postal address, no phone number, no date of birth).
- IP address is stored in `sessions.ip_address` for replay-detection
  purposes; not joined to URL analysis content.
- Anonymous URL analyses use a synthetic UUID so the row's `user_id`
  isn't linkable to a real person.
- LLM calls receive the URL content + claim text; they don't receive
  the user's identity, email, or session info.

### 2.3 Purpose limitation

Personal data collected for one purpose is not used for another without
a new legal basis. For example, account email is used for login + email
verification + password reset + transactional emails (security
alerts), not for marketing without separate consent.

---

## 3. Risks and mitigations

### 3.1 Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Credential theft via XSS** | Low (DOMPurify allowlist, no eval, CSP planned) | High | DOMPurify (S4), CSP headers (in `main.py:191-200`), planned httpOnly cookie migration (S5) for refresh tokens |
| **Refresh-token replay** | Low (stateful sessions) | High | One row per session in `sessions`; rotation on every `/refresh`; replay → cascade-revoke (S2) |
| **OAuth account takeover via email-match** | Low (closed) | High | `_exchange_google_code` requires `email_verified=true` (S1) |
| **SSRF via redirect** | Low (closed) | Medium | `_validate_safe_url` re-runs on every redirect target (S6) |
| **Unauthorized read of URL analyses** | Low (closed) | Medium | Signed job-tokens required for anonymous GETs (S7) |
| **LLM data exfiltration** | Low | Medium | LLM calls send URL content only, not personal data; sub-processors under SCCs |
| **Calibration label tampering** | Low (admin-secret gated) | Medium | `X-Admin-Secret` env-gated; rows immutable post-insert |
| **Source supply-chain compromise** | Low (drift detector) | Medium | KL-divergence on source mix flags unexpected publisher shifts (Phase 6) |
| **Hallucinated claim mislabels real person** | Medium | High | HallucinationDetector runs on every URL analysis; flagged segments surface in audit trail |
| **Sub-processor outage** | Medium | Low | Adapters are best-effort; URL analysis falls back to single-LLM mode; OAuth alternatives (email/password) always available |
| **Data export to EU-non-adequate jurisdictions** | Medium (DeepSeek/China) | Medium | SCCs where available; users can disable multi-LLM (uses only DeepSeek) |
| **Operator misuses admin secret** | Low | High | `X-Admin-Secret` rotated regularly; logged calls in audit trail (planned) |

### 3.2 High-residual-risk items requiring DPO/supervisory review

- **DeepSeek as LLM provider (China-based)**: significant cross-border
  data transfer. Mitigation: only URL/article content is sent (no PII).
  Risk acceptable for the platform's purposes; documented in
  `DATA_PROCESSING.md`.

No other high-residual-risk items.

---

## 4. Rights of data subjects

Implemented:

- **Access**: `GET /api/user/profile`, `GET /api/user/activity`,
  `GET /api/user/bookmarks` etc. expose what we hold.
- **Rectification**: `PUT /api/auth/me` updates name + avatar.
- **Erasure**: `DELETE /api/user/account` purges all account-linked
  data within 30 days. `claim_provenance` rows are anonymised (user_id
  → NULL) rather than deleted because they're audit data.
- **Portability**: `GET /api/export/article/{id}/pdf`,
  `GET /api/export/search/csv`, `GET /api/export/history` provide
  machine-readable exports.
- **Restriction / objection**: handled manually via
  **support@clilens.ai** within 30 days.
- **Withdraw consent**: marketing prefs in
  `/api/user/preferences`; effective immediately.

Plan: an in-app data-rights dashboard (Phase 6 follow-up) that surfaces
all of the above in one page.

---

## 5. Security measures

Documented in `PRIVACY_POLICY.md` §8 and `docs/SECURITY_REVIEW.md`.
Key controls:

- TLS-only transport with HSTS in production
- Bcrypt password hashing with per-user salt
- Stateful JWT sessions with rotation + replay detection
- OAuth `email_verified` check
- DOMPurify HTML sanitisation
- SSRF guards with per-redirect-hop re-validation
- Signed job-tokens for anonymous URL analysis reads
- Rate-limit middleware (Redis-backed; fail-closed for anonymous)
- Adversarial probe suite runs in CI on every PR (Phase 6 wave 3)
- HallucinationDetector on every URL analysis (Phase 6 wave 2)
- Multi-LLM cross-verification gate (Phase 5 waves 1-6)
- KL-divergence drift detection on source mix (Phase 6 wave 1)
- Per-claim audit trail (`claim_provenance`) with model + prompt
  fingerprint + retrieval strategy + source articles + hallucination
  score (Phase 4 waves 3 + 4)

Roadmap items relevant to data protection:

- S5: migrate JWTs from `localStorage` to `httpOnly; Secure;
  SameSite=Lax` cookies + CSRF token (closes the XSS-to-takeover
  chain). Tracked as Phase 1 closure.

---

## 6. Consultation

This DPIA was prepared by the platform engineering lead in consultation
with the Data Protection Contact. No external consultation with a DPO
or supervisory authority has been required, because no high-risk
residual processing remains after the mitigations above. We will
consult external advisors if:

- A new sub-processor is added that significantly changes data flows
- We add processing of special-category data
- A supervisory authority requests review

---

## 7. Approval

This DPIA is approved by the platform engineering lead. The next review
is scheduled for **2027-05-17** or immediately upon any of the trigger
events above.

For supervisory-authority enquiries, contact **support@clilens.ai**
with the subject line "DPIA enquiry".
