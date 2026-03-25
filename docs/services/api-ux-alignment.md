# API & UX Alignment

## Backend (/api/v2)
- GET /articles, /articles/{id}, /tags, /stats, /videos/{id}/status
- Responses include: trust_score, nutrition_label, compliance flags, CTA source URL, summary_type, video_url (when ready), hitl_status.

## Frontend Requirements
- Show trust badge + nutrition label near headline.
- Teaser summary (non-substitutive) + prominent “Read original” CTA.
- Display video preview card when available; show HITL/pending state if not published.
- Respect locale/date formatting; ensure accessibility for badges/labels.

## Validation
- Reject content without CTA/source.
- Hide or label content awaiting HITL approval.

