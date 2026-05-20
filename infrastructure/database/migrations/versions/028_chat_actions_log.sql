-- Migration 028: chat_actions_log — telemetry for agentic chat actions
--
-- Every action suggested by the chat LLM is recorded so:
--   1. The platform knows which answers users actually act on
--      (feeds calibration_label priority).
--   2. Action-suggestion accuracy can be measured over time.
--   3. Misbehaving action suggestions can be audited per session.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS chat_actions_log (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL,
    message_id      UUID NOT NULL,
    action_type     VARCHAR(64) NOT NULL CHECK (action_type IN (
                        'navigate', 'analyze_url', 'apply_search_filters',
                        'apply_map_filters', 'open_methodology_section',
                        'open_country', 'start_deep_search',
                        'bookmark_article', 'start_calibration_label'
                    )),
    params          JSONB NOT NULL DEFAULT '{}',
    suggested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    was_clicked     BOOLEAN NOT NULL DEFAULT FALSE,
    clicked_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chat_actions_log_session
    ON chat_actions_log (session_id);

CREATE INDEX IF NOT EXISTS idx_chat_actions_log_type_clicked
    ON chat_actions_log (action_type, was_clicked)
    WHERE was_clicked = TRUE;

COMMENT ON TABLE chat_actions_log IS
'Telemetry for agentic chat actions. Each row records a suggested action
 from the chat LLM; was_clicked goes TRUE when a user confirms the action.
 Used to rank which answers are most actionable — feeds calibration label
 prioritisation.';
