-- Migration: Add pack_topups table for one-time pack purchases
-- Run this after apply_schema.sql

-- Pack top-ups table (one-time purchases that add to monthly quota)
CREATE TABLE IF NOT EXISTS pack_topups (
    topup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    pack_count INTEGER NOT NULL DEFAULT 25,
    payment_id VARCHAR(255),  -- Paddle transaction ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ  -- NULL means never expires
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_pack_topups_user_id ON pack_topups(user_id);

-- Add plan column values for new tiers (if not exists)
-- The plan column already exists and accepts any string, so no schema change needed
-- Valid values: 'free', 'pro', 'pro_plus', 'annual', 'paid' (legacy)

COMMENT ON TABLE pack_topups IS 'One-time pack purchases (+25 packs for €5)';
COMMENT ON COLUMN pack_topups.pack_count IS 'Number of packs added (default 25)';
COMMENT ON COLUMN pack_topups.payment_id IS 'Paddle transaction ID for payment verification';
COMMENT ON COLUMN pack_topups.expires_at IS 'NULL means never expires';
