# Climatefacts.ai Compliance Documentation

This directory contains the platform's legal + data-protection docs.

| Document | Purpose | Audience |
|---|---|---|
| [PRIVACY_POLICY.md](PRIVACY_POLICY.md) | What personal data we collect, how we use it, who we share it with, and your rights | Users, regulators |
| [TERMS_OF_SERVICE.md](TERMS_OF_SERVICE.md) | Contract between the platform and the user | Users |
| [GDPR_DPIA.md](GDPR_DPIA.md) | Data Protection Impact Assessment under GDPR Art. 35 | DPO, supervisory authorities |
| [DATA_PROCESSING.md](DATA_PROCESSING.md) | Sub-processor inventory + data-category matrix + cross-border transfer notes | DPO, enterprise customers, supervisory authorities |

## Operating principles

- **Material changes** to any of these docs trigger user notification
  per `PRIVACY_POLICY.md §10` (30-day notice via email + in-app banner).
- **Older versions** remain in version control under this directory and
  are reachable by git SHA. The `Document version:` header is bumped on
  every meaningful change.
- **Review cadence**: every 12 months minimum, or immediately upon any
  of the trigger events in `GDPR_DPIA.md §6`.

## How these docs connect to the platform

The platform's behaviour is described in terms of specific code paths so
these docs stay accurate even as features ship:

- Sub-processor list (`DATA_PROCESSING.md §1`) matches the active
  integrations in `requirements.txt` + `src/frontend/package.json`.
- Security mitigations (`PRIVACY_POLICY.md §8`, `GDPR_DPIA.md §3 + §5`)
  reference specific commits + migrations (e.g. S2 = migration 017 +
  stateful sessions; S6 = `_validate_safe_url`).
- Data-rights endpoints (`GDPR_DPIA.md §4`) list the live API surfaces
  that already satisfy each right.

When you ship a feature that touches personal data:

1. Update `DATA_PROCESSING.md` if a new sub-processor is involved.
2. Update `PRIVACY_POLICY.md §2` if a new data category is collected.
3. If the change is material, update `GDPR_DPIA.md §3` (risk register).
4. Update the `Last reviewed` date on every modified doc.

## Contact

- General privacy enquiries: **support@clilens.ai**
- Security disclosures: **security@clilens.ai**
- Enterprise DPA / customer data-protection enquiries: same address,
  subject line "DPA".
