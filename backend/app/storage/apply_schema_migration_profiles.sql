-- Profile system migration (idempotent)
-- Run in Supabase SQL editor.

-- User profiles (1:1 with users)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,

    headline TEXT,
    location TEXT,
    desired_roles TEXT[] DEFAULT '{}',
    work_authorization TEXT,
    remote_preferences TEXT,
    salary_expectations JSONB,

    skills TEXT[] DEFAULT '{}',
    education JSONB,
    certifications TEXT[] DEFAULT '{}',
    projects JSONB,
    interests TEXT[] DEFAULT '{}',
    links JSONB,

    primary_resume_id UUID REFERENCES resume_versions(resume_id) ON DELETE SET NULL,

    profile_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_updated_at ON user_profiles(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_primary_resume_id ON user_profiles(primary_resume_id);

