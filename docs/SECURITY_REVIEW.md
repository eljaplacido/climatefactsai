# Security & Privacy Review — Production Readiness

**Date**: 2026-03-20
**Status**: Review completed, recommendations below

## Authentication & Authorization

| Area | Status | Details |
|------|--------|---------|
| JWT tokens | OK | HS256 with env-based secret, 1h access / 30d refresh |
| Password hashing | OK | bcrypt with auto-generated salt |
| Password policy | OK | Min 8 chars, validated server-side |
| Account lockout | OK | 5 failed attempts = 15min lock |
| Email verification | OK | 24h token expiry |
| Password reset | OK | 1h token, prevents email enumeration |
| Optional auth | OK | `get_optional_user` for public endpoints |
| Tier enforcement | OK | Data source access gated by subscription |

## API Security

| Area | Status | Details |
|------|--------|---------|
| Rate limiting | OK | Per-tier limits on all resource types |
| CORS | OK | Configurable via CORS_ORIGINS env var |
| Input validation | OK | Pydantic models with field constraints |
| SQL injection | OK | All queries use parameterized `:param` binding |
| Request IDs | OK | ObservabilityMiddleware adds X-Request-ID |
| File upload limits | OK | 20MB max, extension whitelist |
| Stripe webhooks | OK | Signature verification |

## Data & Privacy

| Area | Status | Recommendation |
|------|--------|----------------|
| PII storage | REVIEW | User table stores email, name. Consider encryption at rest |
| Data retention | REVIEW | No automatic cleanup of old usage logs. Add retention policy |
| GDPR compliance | REVIEW | Add data export and deletion endpoints for user data |
| API key storage | OK | Keys stored as bcrypt hashes, prefix-only displayed |
| Secrets management | OK | `.env` in `.gitignore`, not tracked in git |
| Logging | REVIEW | Ensure no PII in log output (user IDs OK, emails should be masked) |

## Infrastructure

| Area | Status | Recommendation |
|------|--------|----------------|
| HTTPS | REQUIRED | Must be enforced in production (reverse proxy) |
| Database | OK | Parameterized queries, connection pooling |
| Redis | OK | Used for caching, not for auth state |
| File uploads | OK | In-memory processing, no disk persistence of uploads |
| Dependencies | REVIEW | Run `pip audit` / `npm audit` before deploy |

## OAuth Security

| Area | Status | Details |
|------|--------|---------|
| Google OAuth | REVIEW | Missing PKCE (Proof Key for Code Exchange) |
| State parameter | REVIEW | No CSRF state validation in OAuth callback |
| Redirect URI | REVIEW | Should validate against registered URIs |
| Token handling | OK | Tokens created server-side after OAuth exchange |

## Rate Limiting Architecture

| Area | Status | Details |
|------|--------|---------|
| Per-tier limits | OK | freemium/standard/professional/enterprise defined |
| Implementation | REVIEW | Uses in-memory dict; not distributed-safe. Migrate to Redis for production |
| Response headers | REVIEW | `X-RateLimit-Limit/Remaining/Reset` not yet returned |

## Scoring Pipeline Integrity

| Area | Status | Details |
|------|--------|---------|
| Default scores | REVIEW | Articles with no claims get neutral 60% score rather than explicit "unscored" |
| Failed analysis | OK | `claims_status = 'failed'` with user-facing error explanation |
| Silent fallbacks | REVIEW | LLM unavailable = no insight_summary generated (no user warning) |
| Weather validation | OK | Only applies to weather claims; non-weather articles skip enrichment |

## Security Fixes Applied (2026-03-20)

| Fix | Status | Details |
|-----|--------|---------|
| Security headers (backend) | FIXED | SecurityHeadersMiddleware: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS |
| Security headers (frontend) | FIXED | next.config.js headers(): X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy |
| XSS via dangerouslySetInnerHTML | FIXED | Added sanitizeHtml() to ArticleDetailTabs.tsx — strips script, iframe, event handlers |
| Auth token in API requests | FIXED | api.ts interceptor now attaches Authorization Bearer header from localStorage |
| SSRF protection | FIXED | url_analysis_routes.py now uses ipaddress module for comprehensive private/reserved/link-local/IPv6 checks |

## Recommendations for Production Launch

### CRITICAL (Must fix before launch)
1. **Article ingestion auth** — Add authentication to `POST /api/articles/ingest` (currently unauthenticated, allows arbitrary data injection)
2. **Chat session IDOR** — Add user ownership check to `GET /api/chat/sessions/{id}` (any user can read any session)
3. **OAuth redirect_uri validation** — Validate against server-side allowlist before token exchange
4. **OAuth CSRF state** — Add state parameter generation and validation in OAuth flow

### HIGH Priority (Security)
5. **HTTPS enforcement** — Configure reverse proxy (nginx/Caddy) with TLS
6. **Admin RBAC** — Admin endpoints use `get_optional_user` with no role check; add `is_admin` role verification
7. **Rate limiting to Redis** — Migrate from in-memory dict for distributed safety
8. **Prompt injection mitigation** — Move user input to "user" message role in LLM prompts, add input sanitization
9. **Token invalidation** — Invalidate refresh tokens on password change/reset (add token generation counter to users table)
10. **Premium feature check consistency** — Standardize `check_premium_feature` call sites to pass `subscription_tier` string

### MEDIUM Priority (Compliance)
11. **CORS origins** — Replace `localhost` defaults with actual domain
12. **GDPR endpoints** — Add `/api/user/export-data` and `/api/user/delete-account`
13. **Data retention** — Add scheduled cleanup of usage_logs older than 90 days
14. **Log sanitization** — Mask emails in structured logs (auth_routes.py line 224 logs PII)
15. **Rate limit headers** — Return `X-RateLimit-*` headers in responses
16. **Auth endpoint rate limiting** — Add IP-based limits to `/api/auth/register` and `/api/auth/forgot-password`
17. **Database URL redaction** — Redact password from connection URL in error logs (shared/database.py)
18. **Error detail leakage** — Return generic error messages to clients, log details server-side only

### LOWER Priority (Hardening)
19. **Dependency audit** — `pip audit` + `npm audit` in CI pipeline
20. **Celery pickle** — Remove `pickle` from CELERY_ACCEPT_CONTENT (use json only)
21. **JWT secret validation** — Add startup check that JWT_SECRET_KEY is not the example value and is >= 32 bytes
22. **Secrets rotation** — Document key rotation procedure
23. **Database backups** — Document backup/restore procedures
24. **Scoring transparency** — Show "unscored" instead of default 60% for unanalyzed articles
25. **httpOnly cookies** — Consider moving token storage from localStorage to httpOnly cookies to mitigate XSS token theft
