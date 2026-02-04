-- Migration: Add referrals table for referral program
-- Run this after apply_schema.sql

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    referral_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referee_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    referral_code VARCHAR(32) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending, completed, expired
    packs_awarded_referrer INTEGER DEFAULT 0,
    packs_awarded_referee INTEGER DEFAULT 0,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referee_id ON referrals(referee_id);
CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code);

-- Add referral_code column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(32);
ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by UUID REFERENCES users(user_id);

-- Create unique index on user referral codes
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code) WHERE referral_code IS NOT NULL;

COMMENT ON TABLE referrals IS 'Referral tracking for "Give 10 packs, Get 10 packs" program';
COMMENT ON COLUMN referrals.status IS 'pending = invited, completed = referee created first pack, expired = not used within time limit';
COMMENT ON COLUMN referrals.packs_awarded_referrer IS 'Number of packs awarded to referrer (10)';
COMMENT ON COLUMN referrals.packs_awarded_referee IS 'Number of packs awarded to referee (10)';
