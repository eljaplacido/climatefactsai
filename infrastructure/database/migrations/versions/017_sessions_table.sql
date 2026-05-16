-- =============================================================================
-- 017_sessions_table.sql — Stateful refresh-token sessions with replay detection
-- =============================================================================
-- Closes audit finding S2 (2026-05-16): the JWT refresh-token was stateless,
-- non-rotating, valid for 30 days, with no revocation on password change or
-- logout. A stolen refresh + access pair yielded one month of persistent
-- access; the audit flagged this as a P0 that compounds with the OAuth
-- email-match takeover (S1) and the localStorage XSS surface (S5).
--
-- This migration:
--   1. Creates the `sessions` table keyed by JWT `jti` claim.
--   2. Every issued refresh token now corresponds to a row here.
--   3. /refresh rotates: old `jti` is marked revoked, a new `jti` is issued.
--   4. /logout, password change, password reset all revoke sessions server-side.
--   5. Replay detection: if a revoked `jti` is presented at /refresh,
--      ALL active sessions for that user are cascaded-revoked (the standard
--      response to suspected token theft).
--
-- Backward-compat note: refresh tokens issued before this migration will not
-- have a `jti` claim. Those tokens stop working after deploy — all signed-in
-- users will be forced to re-login once. This is intentional and acceptable
-- for a security upgrade.
-- =============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    jti UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    issued_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP NULL,
    revoke_reason TEXT NULL,
    user_agent TEXT NULL,
    ip_address INET NULL
);

-- Hot path: look up a session by jti (signature already validated, so jti is
-- trustworthy). Active sessions only.
CREATE INDEX IF NOT EXISTS idx_sessions_jti_active
    ON sessions(jti)
    WHERE revoked_at IS NULL;

-- For revoke-all-user-sessions on password change / reset / suspected theft.
CREATE INDEX IF NOT EXISTS idx_sessions_user_id_active
    ON sessions(user_id)
    WHERE revoked_at IS NULL;

-- For periodic cleanup of expired-and-already-revoked rows.
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
    ON sessions(expires_at);

COMMENT ON TABLE  sessions IS 'Stateful refresh-token sessions. One row per refresh token issued. Rotated on /refresh; revoked on /logout, password change, password reset, and replay detection.';
COMMENT ON COLUMN sessions.jti           IS 'JWT ID claim from the refresh token. Primary key.';
COMMENT ON COLUMN sessions.revoked_at    IS 'NULL while active. Set on rotation, /logout, password change/reset, or detected replay.';
COMMENT ON COLUMN sessions.revoke_reason IS 'One of: rotated | logout | password_change | password_reset | replay_detected | admin_revoked.';
