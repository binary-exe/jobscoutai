-- pgvector migration for personalized ranking (idempotent)
-- Run in Supabase SQL editor.

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding columns to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_embedding_hash TEXT;

-- 3. Add embedding columns to user_profiles table (for profile-based ranking)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_embedding_hash TEXT;

-- 4. Create indexes for similarity search (ivfflat)
-- Note: ivfflat index requires at least 1000 rows to be effective.
-- If you have fewer rows, the index will still work but may not provide speedup.
-- For small tables, pgvector will use sequential scan which is fine.

-- Jobs embedding index (cosine similarity)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_jobs_embedding_cosine'
    ) THEN
        -- Use ivfflat with lists=100 for tables with 1k-100k rows
        CREATE INDEX idx_jobs_embedding_cosine ON jobs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- If index creation fails (e.g., not enough rows), ignore
    RAISE NOTICE 'Could not create ivfflat index on jobs.embedding: %', SQLERRM;
END;
$$;

-- User profiles embedding index
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_profiles_embedding_cosine'
    ) THEN
        CREATE INDEX idx_user_profiles_embedding_cosine ON user_profiles USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not create ivfflat index on user_profiles.embedding: %', SQLERRM;
END;
$$;

-- 5. Create index on job_embedding_hash for cache lookups
CREATE INDEX IF NOT EXISTS idx_jobs_embedding_hash ON jobs(job_embedding_hash);
CREATE INDEX IF NOT EXISTS idx_user_profiles_embedding_hash ON user_profiles(profile_embedding_hash);
