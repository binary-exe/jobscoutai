-- Migration: Trust Report community feedback loop (idempotent)
-- Run this after apply_schema.sql

CREATE TABLE IF NOT EXISTS trust_report_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_target_id UUID NOT NULL REFERENCES job_targets(job_target_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    feedback_kind TEXT NOT NULL CHECK (feedback_kind IN ('report', 'accuracy')),
    dimension TEXT NOT NULL DEFAULT 'overall' CHECK (dimension IN ('overall', 'scam', 'ghost', 'staleness', 'link')),
    value TEXT, -- accuracy: 'accurate'|'inaccurate' ; report: free-form category (e.g. 'scam', 'ghost', 'expired', 'other')
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trust_report_feedback_job_target_id ON trust_report_feedback(job_target_id);
CREATE INDEX IF NOT EXISTS idx_trust_report_feedback_user_id ON trust_report_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_trust_report_feedback_kind ON trust_report_feedback(feedback_kind);
CREATE INDEX IF NOT EXISTS idx_trust_report_feedback_created_at ON trust_report_feedback(created_at DESC);

-- Helpful rollup view for UI + heuristics (cheap read)
CREATE OR REPLACE VIEW trust_report_feedback_summary AS
SELECT
    job_target_id,
    COUNT(*) FILTER (WHERE feedback_kind = 'report') AS reports_total,
    COUNT(*) FILTER (WHERE feedback_kind = 'accuracy' AND value = 'accurate') AS accurate_total,
    COUNT(*) FILTER (WHERE feedback_kind = 'accuracy' AND value = 'inaccurate') AS inaccurate_total,
    COUNT(*) FILTER (WHERE feedback_kind = 'report' AND value = 'scam') AS reports_scam,
    COUNT(*) FILTER (WHERE feedback_kind = 'report' AND value = 'ghost') AS reports_ghost,
    COUNT(*) FILTER (WHERE feedback_kind = 'report' AND value = 'expired') AS reports_expired
FROM trust_report_feedback
GROUP BY job_target_id;

