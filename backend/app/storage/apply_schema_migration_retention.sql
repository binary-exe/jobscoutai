-- Migration: Add saved searches and job alerts for retention
-- Run this after apply_schema.sql

-- Saved searches table
CREATE TABLE IF NOT EXISTS saved_searches (
    search_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(255),
    query VARCHAR(500),
    filters JSONB DEFAULT '{}',  -- {location, remote, employment, min_score, etc}
    notify_frequency VARCHAR(32) DEFAULT 'weekly',  -- daily, weekly, never
    last_notified_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for saved searches
CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_searches_active ON saved_searches(is_active) WHERE is_active = true;

-- Job alerts table (stores when user was notified about which jobs)
CREATE TABLE IF NOT EXISTS job_alerts_sent (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES saved_searches(search_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    job_ids TEXT[],  -- Array of job_ids included in this alert
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for job alerts
CREATE INDEX IF NOT EXISTS idx_job_alerts_sent_search_id ON job_alerts_sent(search_id);
CREATE INDEX IF NOT EXISTS idx_job_alerts_sent_user_id ON job_alerts_sent(user_id);

-- Email preferences column on users
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_preferences JSONB DEFAULT '{"weekly_digest": true, "job_alerts": true, "marketing": true}';

COMMENT ON TABLE saved_searches IS 'User saved searches for quick filtering and alerts';
COMMENT ON COLUMN saved_searches.notify_frequency IS 'daily, weekly, or never for email notifications';
COMMENT ON COLUMN saved_searches.filters IS 'JSON object with filter parameters: {location, remote, employment, etc}';
COMMENT ON TABLE job_alerts_sent IS 'Tracking which jobs were sent in alerts to avoid duplicates';
