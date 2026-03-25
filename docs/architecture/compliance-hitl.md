# Compliance & HITL Protocol

## Ingestion Gate
- Check robots.txt and X-Robots-Tag for noai/noimageai; on opt-out → SKIP + log.
- Domain allow/deny lists; default-deny on parsing errors.
- Record compliance decision in DB (publisher/article level).

## Non-Substitutive Summaries
- Prompt: 3-sentence teaser; omit outcomes/details; encourage click-through to source.
- Enforce CTA link in API and UI.

## LangGraph HITL
- Interrupt when trust_score < threshold or sensitive keywords.
- Queue item in moderation dashboard; resume graph on approval; mark rejected on deny.
- Persist checkpoints and audit logs; include reviewer and rationale.

## Audit & Transparency
- Surface trust_score, nutrition_label, compliance flags, and CTA in API responses.
- Log skip reasons for opt-outs; expose to observability.

