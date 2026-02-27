-- pgvector migration for Second Brain (KB) RAG (idempotent)
-- Run via init_schema() or Supabase SQL editor.
-- Requires Session pooler / Session mode in Supabase for SET LOCAL.

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. KB documents (one per indexed artifact)
CREATE TABLE IF NOT EXISTS kb_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_table TEXT,
    source_id TEXT,
    title TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_user_id ON kb_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_kb_documents_source_type ON kb_documents(source_type);

-- 3. KB chunks (text + embedding per chunk)
CREATE TABLE IF NOT EXISTS kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    page INT,
    token_count INT,
    text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_user_id ON kb_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_document_id ON kb_chunks(document_id);

-- 4. HNSW index for cosine similarity search
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'kb_chunks_embedding_hnsw'
    ) THEN
        CREATE INDEX kb_chunks_embedding_hnsw ON kb_chunks USING hnsw (embedding vector_cosine_ops);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not create HNSW index on kb_chunks.embedding: %', SQLERRM;
END;
$$;

-- 5. Row-Level Security (session-variable pattern)
ALTER TABLE kb_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_chunks ENABLE ROW LEVEL SECURITY;

-- Policies: only rows where user_id matches app.current_user_id
-- USING: SELECT/UPDATE/DELETE; WITH CHECK: INSERT/UPDATE (ensures new rows have correct user_id)
DROP POLICY IF EXISTS kb_documents_user_policy ON kb_documents;
CREATE POLICY kb_documents_user_policy ON kb_documents
    USING (user_id = (current_setting('app.current_user_id', true)::uuid))
    WITH CHECK (user_id = (current_setting('app.current_user_id', true)::uuid));

DROP POLICY IF EXISTS kb_chunks_user_policy ON kb_chunks;
CREATE POLICY kb_chunks_user_policy ON kb_chunks
    USING (user_id = (current_setting('app.current_user_id', true)::uuid))
    WITH CHECK (user_id = (current_setting('app.current_user_id', true)::uuid));
