-- Migration: Add credit ledger for unified usage-based billing
-- Run this after apply_schema.sql

CREATE TABLE IF NOT EXISTS credit_ledger (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    delta_credits INTEGER NOT NULL,
    reason TEXT NOT NULL, -- plan_grant | topup | spend | refund
    feature TEXT, -- apply_pack | ai_interview_coach | ai_template | apply_pack_review | ...
    idempotency_key TEXT,
    metadata JSONB,
    available_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_id ON credit_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_created_at ON credit_ledger(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_available_at ON credit_ledger(available_at);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_expires_at ON credit_ledger(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_idempotency_key
ON credit_ledger(idempotency_key) WHERE idempotency_key IS NOT NULL;
