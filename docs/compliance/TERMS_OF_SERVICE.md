# CliLens.AI Terms of Service

**Effective date:** 2026-05-17
**Last reviewed:** 2026-05-17
**Document version:** 1.0

By using CliLens.AI ("the platform", "we") you agree to these Terms of
Service. If you don't agree, please don't use the platform.

---

## 1. What CliLens.AI is

CliLens.AI is an AI-powered climate news verification and intelligence
platform. It:

- Aggregates climate news from public sources
- Extracts claims and runs fact-checking pipelines
- Surfaces per-country climate / sustainability indicators (Climate
  TRACE, OWID, Climate Action Tracker, and more)
- Provides a chat interface for querying climate data
- Lets you submit URLs for independent analysis

The platform's analytical outputs are **assistive, not authoritative**.
Every score we display is paired with methodology documentation
(`/api/methodology`) and an audit trail
(`/api/methodology/audit-trail/*`). Treat our outputs as a starting
point for further research, not as a final verdict.

---

## 2. Accounts

To use most features you create an account (email/password or via
Google/Microsoft OAuth). You agree to:

- Provide accurate information
- Keep your password (and any API keys) confidential
- Notify us at **support@clilens.ai** if you suspect your account is
  compromised
- Be 16 years or older

We may suspend or terminate accounts that:

- Violate these terms
- Are used to attack the platform (rate-limit abuse, scraping,
  injection attempts)
- Have been inactive for 24+ months (we notify before disabling)

---

## 3. Subscription tiers

We offer four tiers:

| Tier | Cost | Limits |
|---|---|---|
| Freemium | $0 | 5 articles/day, basic search, map view |
| Basic | $9.99/mo | 50 articles/day, deep search, bookmarks, email digests |
| Professional | $29.99/mo | Unlimited articles, API access (1000/day), priority analysis |
| Enterprise | $99.99/mo | Team features, dedicated SLA, custom integrations |

Billing is handled by Stripe (see `DATA_PROCESSING.md`). Cancel any
time; charges are not pro-rated for partial months but we honour the
remainder of the paid period.

---

## 4. Acceptable use

You may **not**:

- Use the platform to harass, defame, or harm anyone
- Submit URLs that link to illegal content (CSAM, terrorism material,
  etc.)
- Scrape the platform aggressively, evade rate limits, or attempt to
  reverse-engineer our prompts (the methodology endpoint exposes
  prompt fingerprints — that's the supported surface)
- Use the platform to train competing AI models without written
  permission
- Resell platform output as if it were your own analysis without
  attribution

We monitor for abuse via the rate limiter and the drift detector. Abuse
detection is not personal — it's pattern-based.

---

## 5. Intellectual property

- **Your content**: text, URLs, source suggestions, calibration labels
  you submit remain yours. You grant us a worldwide, royalty-free
  licence to process them for the purposes described in the Privacy
  Policy.
- **Platform IP**: the platform code (FastAPI + Next.js), prompts,
  scoring formulas, and aggregated indicator data are ours. The
  underlying source data we ingest (RSS feeds, public datasets) is
  governed by each source's licence — we cite + link to original
  sources for every piece of content we display.
- **Open-source**: parts of the platform are open-sourced under their
  respective licences (see `LICENSE` and `docs/licenses/`).

---

## 6. Disclaimer

**The platform produces probabilistic outputs.** Climate science is
itself probabilistic, and our LLM-derived signals (extracted claims,
agreement scores, hallucination grounding) all carry uncertainty bands
that we surface alongside the score. The methodology drawer shows you
exactly which model + prompt fingerprint + retrieval strategy produced
a given output.

We provide the platform **AS IS**. To the maximum extent permitted by
law, we exclude warranties of merchantability, fitness for a particular
purpose, and non-infringement.

For the avoidance of doubt: **don't make legally-binding or
safety-critical decisions based solely on a CliLens.AI score**.
Cross-reference with primary sources (linked from every analysis).

---

## 7. Limitation of liability

To the maximum extent permitted by law, our aggregate liability for any
claim arising from or related to the platform is limited to the greater
of:

- Amounts you paid us in the 12 months preceding the claim, OR
- USD 100

We are not liable for indirect, incidental, consequential, or punitive
damages.

These limitations apply regardless of legal theory (contract, tort,
strict liability, etc.). Some jurisdictions don't allow these
exclusions; in those jurisdictions our liability is the minimum
permitted by law.

---

## 8. Indemnity

You agree to indemnify CliLens.AI against third-party claims arising
from your misuse of the platform, your violation of these Terms, or
your violation of someone else's rights.

---

## 9. Termination

Either party can terminate at any time:

- **You**: delete your account via `/dashboard/settings` or by emailing
  **support@clilens.ai**. We purge personal data per the Privacy
  Policy.
- **Us**: with 30 days notice for any reason, or immediately for
  violations of these Terms or applicable law.

Sections that should survive termination (IP, indemnity, limitation of
liability, disclaimer, dispute resolution, definitions) do.

---

## 10. Governing law + disputes

These Terms are governed by the laws of the jurisdiction stated in the
"Contact" section below. Disputes go to the courts of that
jurisdiction. EU/UK users keep their statutory consumer-protection
rights regardless.

---

## 11. Changes to these Terms

Material changes will be notified at least 30 days before they take
effect, via email and an in-app banner. Continued use of the platform
after the change date constitutes acceptance.

Older versions remain in version control under `docs/compliance/` and
are reachable by git SHA.

---

## 12. Contact

- General inquiries: **support@clilens.ai**
- Security disclosures: **security@clilens.ai**
- Legal notices: as posted at the entity address in the platform
  footer
