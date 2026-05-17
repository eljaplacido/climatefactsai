# CliLens.AI Privacy Policy

**Effective date:** 2026-05-17
**Last reviewed:** 2026-05-17
**Document version:** 1.0

This privacy policy describes what personal data CliLens.AI ("the platform")
collects, how we use it, who we share it with, and the rights you have over
your data. It is written to satisfy the EU General Data Protection
Regulation (GDPR), the UK Data Protection Act 2018, and equivalent
frameworks.

If anything here is unclear or you want to exercise one of your rights,
write to **support@clilens.ai** with the subject "Privacy".

---

## 1. Who we are

CliLens.AI is operated by the entity identified in the Terms of Service.
For data-protection purposes we act as the **data controller** for the
personal data described below. Our processors are listed in
`DATA_PROCESSING.md`.

---

## 2. What personal data we collect

### 2.1 Account data

When you create an account (email/password or via Google/Microsoft OAuth):

- Email address
- Full name (optional)
- Avatar URL (optional, populated automatically from OAuth)
- Password hash (bcrypt; the plaintext is never stored or logged)
- Subscription tier (freemium / basic / professional / enterprise)
- Account creation timestamp
- Last-login timestamp
- Email-verification token (cleared on verification)
- Password-reset token (cleared on use; expires in 1 hour)

### 2.2 Session data

Every refresh token issued (login / signup / OAuth callback) creates a
row in `sessions`:

- JWT `jti` (session identifier)
- User ID (foreign key)
- User-Agent header (first 512 chars)
- IP address (`X-Forwarded-For` leftmost entry when behind a proxy, else
  socket peer)
- Issued / last-used / expires timestamps
- Revocation timestamp + reason (`rotated` / `logout` / `password_change` /
  `password_reset` / `replay_detected`)

### 2.3 Activity data

When you use platform features, we log:

- URL analyses you submit (URL, extracted text, extracted claims,
  fact-check results, hallucination score, multi-LLM agreement)
- Bookmarks, reading history, saved queries (only when logged in)
- Source suggestions you submit
- Calibration labels you provide if you have admin role

URL analyses submitted while logged out are associated with a synthetic
anonymous user ID. They are not linkable back to a real person from
within the platform.

### 2.4 Telemetry

- OpenTelemetry spans for API requests (request path, status code, latency)
- Application logs (structured JSON; do **not** include passwords or
  raw tokens)

---

## 3. How we use your data

| Purpose | Legal basis (GDPR Art. 6) | Data used |
|---|---|---|
| Account creation + login | Contract performance | Account data, session data |
| Email verification + password reset | Legitimate interest in account security | Email, verification/reset token |
| Personalised feed + bookmarks + history | Contract performance | Activity data |
| URL analysis + claim extraction | Contract performance | URL + extracted text |
| Source suggestions review | Legitimate interest in source quality | Source-suggestion submission |
| Audit trail + transparency reporting | Legitimate interest in defensible methodology | Provenance + calibration data |
| Service security (replay detection, rate limit) | Legitimate interest in service integrity | Session data, IP, User-Agent |
| Calibration of platform confidence scores | Legitimate interest in scoring accuracy | Calibration labels (admin-only) |
| Compliance with legal obligations | Legal obligation | Whatever the law requires |

We do **not** use personal data for:
- Automated decision-making with legal effect on you
- Profile-based advertising (we run no ads)
- Selling to third parties

---

## 4. Who we share data with

### 4.1 Sub-processors

Listed in full in `DATA_PROCESSING.md`. Summary:

| Sub-processor | Data shared | Purpose | Jurisdiction |
|---|---|---|---|
| Google (OAuth) | Email + name when you sign in via Google | Authentication | US (Standard Contractual Clauses) |
| Microsoft (OAuth) | Email + name when you sign in via Microsoft | Authentication | US/EU (SCCs) |
| Anthropic | URL content + extracted claims (when multi-LLM verification is enabled) | LLM cross-verification | US (SCCs) |
| DeepSeek | URL content + extracted claims | LLM extraction / chat synthesis | China (consult `DATA_PROCESSING.md` for transfer notes) |
| Perplexity (optional) | Search queries | External research lookups | US (SCCs) |
| Climate TRACE / OWID / Climate Action Tracker | None (we read their public data; we send no personal data) | Source-of-truth indicators | N/A |
| OpenAI (optional, embeddings) | Article text excerpts | Vector embeddings | US (SCCs) |
| SendGrid | Email address + verification link | Transactional email | US (SCCs) |
| Cloud provider (GCP) | All hosted data | Infrastructure | EU `europe-west4` planned (see GCP cloud project memo) |

### 4.2 Public surfaces

The `/api/methodology/*` endpoints expose:
- The prompts the platform uses (names + versions + content-hash fingerprints; the raw template text is **not** exposed publicly)
- The sustainability-score formula + weights
- The indicator catalogue
- The calibration metrics (Brier / ECE / Platt parameters) once labels accumulate

None of these expose personal data.

### 4.3 Legal disclosures

We disclose data when legally required (court order, subpoena, lawful
request from EU/UK/national authorities). We push back where the request
is overbroad and notify you where the law allows.

---

## 5. International transfers

Some sub-processors are outside the EU/UK. Where this happens we rely on:
- Standard Contractual Clauses (SCCs) approved by the EU Commission
- Adequacy decisions where they exist
- Additional safeguards documented in `DATA_PROCESSING.md`

If you have concerns about a specific transfer, write to
**support@clilens.ai** and we'll explain the controls in place.

---

## 6. How long we keep data

| Category | Retention |
|---|---|
| Account data | Until you delete your account, then 30 days for backups |
| Active sessions | Until refresh token expires (30 days) or you log out |
| Revoked sessions | 90 days for audit, then deleted |
| URL analyses (your submissions) | Indefinitely while account active; deleted with account |
| URL analyses (anonymous) | 12 months |
| Bookmarks + reading history | Until you delete them or delete your account |
| Source suggestions | Indefinitely (they're a contribution to the platform) |
| Calibration labels | Indefinitely (they're a contribution to the platform) |
| `claim_provenance` rows | Indefinitely (audit trail) |
| Application logs | 30 days |
| OpenTelemetry traces | 30 days |
| Email-verification + password-reset tokens | Cleared on use; expire in 24h and 1h respectively |

---

## 7. Your rights

Under GDPR (and equivalents) you have the right to:

- **Access**: ask what data we hold on you. We respond within 30 days.
- **Rectification**: ask us to correct inaccurate data.
- **Erasure** ("right to be forgotten"): delete your account; all
  account-linked data is purged within 30 days. `claim_provenance` rows
  for analyses you submitted are anonymised (`user_id` set to NULL).
- **Restriction**: ask us to stop processing specific data while we
  resolve a dispute.
- **Portability**: receive your data in a machine-readable format. We
  provide JSON export via the `/api/export/*` endpoints.
- **Object**: object to processing based on legitimate interest. We
  evaluate each objection on its merits.
- **Withdraw consent**: where processing is based on consent (currently
  only optional marketing emails), withdraw anytime.
- **Lodge a complaint**: with your national data-protection authority.
  EU users: see https://edpb.europa.eu/about-edpb/about-edpb/members_en.
  UK users: https://ico.org.uk.

To exercise any of these, email **support@clilens.ai**. We may ask for
proof of identity before complying.

---

## 8. Security

We protect your data with:

- Passwords hashed with bcrypt (per-user salt, current default cost factor)
- JWT tokens signed with HS256; refresh tokens are stateful (one row per
  active session) and rotated on every refresh; presenting a replayed
  refresh token cascade-revokes all your active sessions
- HTTPS-only transport (HSTS + secure cookies in production)
- OAuth callbacks verify `email_verified=true` from Google before
  associating an account
- URL submissions go through SSRF guards that re-validate every redirect
  hop (no fetching from private IPs / metadata endpoints)
- HTML rendered to your browser is sanitised by DOMPurify with a strict
  allowlist
- Rate-limit middleware fail-closes on Redis outage for anonymous traffic
- Adversarial probe suite runs in CI on every PR

If you find a vulnerability, report it to **security@clilens.ai**. We
will not pursue good-faith research.

---

## 9. Children

CliLens.AI is intended for users 16 and older (the GDPR-Lite age
threshold for several EU member states). We don't knowingly collect data
from children under 16. If you believe we have, write to
**support@clilens.ai** and we will delete it.

---

## 10. Changes to this policy

Material changes will be notified via email at least 30 days before they
take effect. The "Last reviewed" date at the top reflects the most
recent edit. Older versions are kept in version control under
`docs/compliance/` and are reachable through their git SHA.

---

## 11. Contact

Data Protection Contact: **support@clilens.ai**
Security disclosures: **security@clilens.ai**

If you live in the EU/UK you also have the right to contact your
national data-protection authority directly without going through us.
