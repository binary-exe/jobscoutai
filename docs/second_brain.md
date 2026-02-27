# Second Brain (KB) RAG

The Second Brain is an optional, authenticated feature that lets users index their own documents (notes, resumes, job text, etc.) and query them with natural language. Answers are grounded in stored content and returned with citations.

- **Requires**: `JOBSCOUT_KB_ENABLED=true`, pgvector extension, and OpenAI API key.
- **Deploy & test**: See [second_brain_deploy_and_test.md](second_brain_deploy_and_test.md) for step-by-step setup and real-time testing.
- **Auth**: All KB endpoints require a valid Supabase session (Bearer token). Data is scoped per user.
- **RLS**: Row-Level Security on `kb_documents` and `kb_chunks` uses the session variable `app.current_user_id`, set per transaction by the backend.

---

## Enabling the feature

1. **Set the env var**  
   In your backend `.env` (or Fly.io secrets), set:
   ```bash
   JOBSCOUT_KB_ENABLED=true
   ```
   (See `backend/env.sample`.)

2. **Ensure pgvector is available**  
   - **Supabase**: The vector extension is available. Use the **Session** pooler connection string (not Direct) so `SET LOCAL` works.
   - On backend startup, `init_schema()` runs `pgvector_migration_second_brain.sql` (best-effort), which runs `CREATE EXTENSION IF NOT EXISTS vector` and creates the `kb_documents` and `kb_chunks` tables and indexes. No manual SQL is required unless you use a different Postgres host that doesn’t have the extension yet.

3. **OpenAI**  
   Set `JOBSCOUT_OPENAI_API_KEY`; it is used for embeddings and for generating answers.

---

## Schema and RLS

Tables are created by the best-effort migration `backend/app/storage/pgvector_migration_second_brain.sql` (run automatically on backend startup if the file is present).

- **kb_documents**: One row per indexed artifact (`user_id`, `source_type`, `source_table`, `source_id`, `title`, `metadata`, `created_at`).
- **kb_chunks**: One row per text chunk with embedding (`user_id`, `document_id`, `chunk_index`, `page`, `text`, `embedding vector(1536)`).

Indexes:

- B-tree: `kb_documents(user_id)`, `kb_documents(source_type)`, `kb_chunks(user_id)`, `kb_chunks(document_id)`.
- HNSW: `kb_chunks(embedding vector_cosine_ops)` for similarity search.

RLS policies:

- `kb_documents_user_policy`: `USING (user_id = (current_setting('app.current_user_id', true)::uuid))`
- `kb_chunks_user_policy`: same for `kb_chunks`.

The backend sets `app.current_user_id` at the start of each transaction for KB operations (e.g. `SET LOCAL app.current_user_id = '<uuid>'`), so all inserts and selects are automatically scoped to that user.

---

## pgvector and Supabase

- Enable the **vector** extension (the migration runs `CREATE EXTENSION IF NOT EXISTS vector`).
- Use the **Session** pooler connection string (not Direct) so that `SET LOCAL` is valid for the session/transaction.

---

## API Endpoints

Base path: `/api/v1/kb`.

### POST /kb/index

Index a document: chunk text, generate embeddings, and store document + chunks.

**Auth**: Required (Bearer token).

**Request body**:

```json
{
  "source_type": "note",
  "source_table": null,
  "source_id": null,
  "title": "My meeting notes",
  "metadata": {},
  "text": "Full text of the document to index..."
}
```

**Response**:

```json
{
  "document_id": "uuid",
  "chunks_indexed": 5
}
```

**Example (curl)**:

```bash
curl -X POST "https://your-api.fly.dev/api/v1/kb/index" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_ACCESS_TOKEN" \
  -d '{"source_type":"note","title":"Test","text":"Your long text here..."}'
```

---

### POST /kb/query

Query the knowledge base: embed the question, run similarity search, and return an answer plus citations.

**Auth**: Required (Bearer token).

**Request body**:

```json
{
  "question": "What did I note about project X?",
  "source_type": null,
  "source_table": null,
  "source_id": null,
  "max_chunks": 10
}
```

**Response**:

```json
{
  "answer": "Based on your notes, project X is...",
  "citations": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "source_type": "note",
      "source_id": "",
      "page": null,
      "score": 0.85,
      "snippet": "First 500 chars of the chunk..."
    }
  ]
}
```

**Example (curl)**:

```bash
curl -X POST "https://your-api.fly.dev/api/v1/kb/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_ACCESS_TOKEN" \
  -d '{"question":"What did I note about project X?","max_chunks":10}'
```

---

## Why `app.current_user_id` per transaction?

The backend does not rely on the database role to identify the user; it uses the Supabase JWT to resolve the user and then sets `app.current_user_id` inside a transaction. This keeps a single connection pool while still enforcing per-user isolation via RLS. All KB reads and writes in that transaction see only rows where `user_id = current_setting('app.current_user_id', true)::uuid`.
