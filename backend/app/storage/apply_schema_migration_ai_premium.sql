-- Migration: Premium AI features (cache + guardrails) (idempotent)
-- Run this after apply_schema.sql

CREATE TABLE IF NOT EXISTS ai_generation_cache (
    cache_key TEXT PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    feature TEXT NOT NULL, -- interview_coach | template | ...
    model TEXT,
    request_hash TEXT,
    request_json JSONB,
    response_json JSONB,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ai_generation_cache_user_feature_created
ON ai_generation_cache(user_id, feature, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_generation_cache_expires_at
ON ai_generation_cache(expires_at);

