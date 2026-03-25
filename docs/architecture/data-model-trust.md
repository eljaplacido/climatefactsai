# Data Model Changes (Trust & Compliance)

## Tables
- publishers:
  - domain (unique), name, tdm_opt_out (bool), trust_score (int), nutrition_label JSONB, created_at/updated_at
- articles:
  - publisher_id FK, original_url (unique), headline, summary_text, summary_type (AI_GENERATED/HUMAN_EDITED), video_url, published_at, ingested_at, compliance_check_passed (bool), provenance JSONB, trust_score_cache
- Optional:
  - moderation_queue: article_id, status (PENDING/APPROVED/REJECTED), reviewer, notes, timestamps
  - video_jobs: article_id, status, render_provider (remotion), cost_cents, duration_ms, output_url

## Notes
- Indexes: publishers.domain, publishers.trust_score, articles.publisher_id + published_at.
- Provenance should store summary prompt version, model, and HITL reviewer when applicable.
- CTA/source link must be stored and returned in API responses.

