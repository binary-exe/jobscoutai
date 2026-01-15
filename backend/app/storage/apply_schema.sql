-- Apply Workspace V1 Database Schema
-- Run this in Supabase SQL Editor or via migration

-- Users table (if not exists)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'paid')),
    subscription_id TEXT, -- Paddle subscription ID
    paddle_customer_id TEXT, -- Paddle customer ID
    subscription_status TEXT, -- active, cancelled, past_due, etc.
    subscription_ends_at TIMESTAMPTZ -- When subscription expires
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_subscription_id ON users(subscription_id);

-- Resume versions
CREATE TABLE IF NOT EXISTS resume_versions (
    resume_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    resume_text TEXT NOT NULL,
    resume_hash TEXT NOT NULL, -- SHA256 hash for caching
    proof_points TEXT, -- JSON array of quantified achievements
    extracted_skills JSONB, -- Structured skills extraction
    extracted_seniority TEXT,
    extracted_bullets JSONB, -- Evidence bullets
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resume_versions_user_id ON resume_versions(user_id);
CREATE INDEX IF NOT EXISTS idx_resume_versions_hash ON resume_versions(resume_hash);

-- Job targets (parsed job descriptions)
CREATE TABLE IF NOT EXISTS job_targets (
    job_target_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    job_url TEXT,
    job_text TEXT, -- Raw JD text if pasted
    job_hash TEXT NOT NULL, -- SHA256 hash for caching
    extracted_json JSONB, -- JSON-LD JobPosting or parsed structure
    title TEXT,
    company TEXT,
    location TEXT,
    remote_type TEXT,
    employment_type TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    description_text TEXT,
    requirements TEXT[],
    keywords TEXT[],
    must_haves TEXT[],
    role_rubric TEXT, -- LLM-generated rubric
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_targets_user_id ON job_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_job_targets_hash ON job_targets(job_hash);
CREATE INDEX IF NOT EXISTS idx_job_targets_url ON job_targets(job_url);

-- Trust reports
CREATE TABLE IF NOT EXISTS trust_reports (
    trust_report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_target_id UUID NOT NULL REFERENCES job_targets(job_target_id) ON DELETE CASCADE,
    scam_risk TEXT NOT NULL CHECK (scam_risk IN ('low', 'medium', 'high')),
    scam_reasons TEXT[], -- Array of reasons
    ghost_likelihood TEXT NOT NULL CHECK (ghost_likelihood IN ('low', 'medium', 'high')),
    ghost_reasons TEXT[],
    staleness_score INTEGER, -- 0-100
    staleness_reasons TEXT[],
    domain TEXT,
    extracted_emails TEXT[],
    extracted_phones TEXT[],
    apply_link_status TEXT, -- valid, broken, missing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trust_reports_job_target_id ON trust_reports(job_target_id);

-- Apply packs (generated tailored content)
CREATE TABLE IF NOT EXISTS apply_packs (
    apply_pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES resume_versions(resume_id) ON DELETE CASCADE,
    job_target_id UUID NOT NULL REFERENCES job_targets(job_target_id) ON DELETE CASCADE,
    pack_hash TEXT NOT NULL, -- resume_hash + job_target_hash for caching
    tailored_summary TEXT,
    tailored_bullets JSONB, -- Array of tailored bullet points
    cover_note TEXT,
    ats_checklist JSONB, -- Keyword coverage, missing skills, etc.
    keyword_coverage REAL, -- 0-100
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_apply_packs_user_id ON apply_packs(user_id);
CREATE INDEX IF NOT EXISTS idx_apply_packs_hash ON apply_packs(pack_hash);
CREATE INDEX IF NOT EXISTS idx_apply_packs_created_at ON apply_packs(created_at DESC);

-- Applications (tracker)
CREATE TABLE IF NOT EXISTS applications (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    apply_pack_id UUID REFERENCES apply_packs(apply_pack_id) ON DELETE SET NULL,
    job_target_id UUID REFERENCES job_targets(job_target_id) ON DELETE SET NULL,
    status TEXT DEFAULT 'applied' CHECK (status IN ('applied', 'interview', 'offer', 'rejected', 'withdrawn')),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interview_at TIMESTAMPTZ,
    offer_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    notes TEXT,
    reminder_at TIMESTAMPTZ, -- For follow-up reminders
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_reminder_at ON applications(reminder_at) WHERE reminder_at IS NOT NULL;

-- Usage ledger (for quota tracking)
CREATE TABLE IF NOT EXISTS usage_ledger (
    usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN ('apply_pack', 'docx_export', 'trust_report')),
    apply_pack_id UUID REFERENCES apply_packs(apply_pack_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_id ON usage_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_ledger_created_at ON usage_ledger(created_at DESC);
-- Note: Monthly aggregation is handled in queries, not via index (date_trunc is not IMMUTABLE)

-- Entitlements (plan features - can be stored on users table, but this allows for future flexibility)
CREATE TABLE IF NOT EXISTS entitlements (
    entitlement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    feature TEXT NOT NULL, -- 'apply_packs', 'docx_export', 'unlimited_tracker'
    limit_value INTEGER, -- NULL = unlimited
    period TEXT DEFAULT 'month' CHECK (period IN ('month', 'year', 'lifetime')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_entitlements_user_id ON entitlements(user_id);
CREATE INDEX IF NOT EXISTS idx_entitlements_feature ON entitlements(feature);
