-- Trust + Applications MVP migration (idempotent)
-- Safe to run multiple times in Supabase SQL editor.

-- 1) Trust reports: add new columns (CREATE TABLE IF NOT EXISTS won't add columns if table already exists)
ALTER TABLE trust_reports
  ADD COLUMN IF NOT EXISTS scam_score INTEGER;

ALTER TABLE trust_reports
  ADD COLUMN IF NOT EXISTS ghost_score INTEGER;

ALTER TABLE trust_reports
  ADD COLUMN IF NOT EXISTS domain_consistency_reasons TEXT[];

ALTER TABLE trust_reports
  ADD COLUMN IF NOT EXISTS trust_score INTEGER;

CREATE INDEX IF NOT EXISTS idx_trust_reports_trust_score ON trust_reports(trust_score DESC);

-- 2) Job targets: add html column used by storage/service layer
ALTER TABLE job_targets
  ADD COLUMN IF NOT EXISTS html TEXT;

-- 3) Application feedback table (new)
CREATE TABLE IF NOT EXISTS application_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('rejection', 'shortlisted', 'offer', 'no_response', 'withdrawn')),
    raw_text TEXT,
    parsed_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_application_feedback_application_id ON application_feedback(application_id);
CREATE INDEX IF NOT EXISTS idx_application_feedback_type ON application_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_application_feedback_created_at ON application_feedback(created_at DESC);

