# Second Brain: Deploy and Real-Time Test

Step-by-step setup to deploy the Second Brain (KB) feature and test it live.

---

## Prerequisites

- Supabase project (Postgres + Auth)
- Fly.io account (backend)
- Vercel account (frontend)
- OpenAI API key

---

## 1. Database (Supabase)

### 1.1 Connection string

Use the **Session pooler** connection string (required for `SET LOCAL`):

1. Supabase Dashboard → **Settings** → **Database**
2. Under **Connection string**, choose **Session mode** (not Transaction)
3. Copy the URI, e.g.:
   ```
   postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```

### 1.2 Schema

The backend creates KB tables on startup via `pgvector_migration_second_brain.sql`. No manual SQL is needed.

If you want to run it manually first:

1. **SQL Editor** → New query
2. Paste contents of `backend/app/storage/pgvector_migration_second_brain.sql`
3. Run

---

## 2. Backend (Fly.io)

### 2.1 Set secrets

```bash
# Required for KB
fly secrets set JOBSCOUT_KB_ENABLED="true" -a jobscout-api
fly secrets set JOBSCOUT_OPENAI_API_KEY="sk-your-key" -a jobscout-api

# If not already set
fly secrets set JOBSCOUT_DATABASE_URL="postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require" -a jobscout-api
fly secrets set JOBSCOUT_SUPABASE_URL="https://your-project.supabase.co" -a jobscout-api
fly secrets set JOBSCOUT_SUPABASE_ANON_KEY="your-anon-key" -a jobscout-api
fly secrets set JOBSCOUT_CORS_ORIGINS='["https://jobiqueue.com","https://www.jobiqueue.com","http://localhost:3000"]' -a jobscout-api
```

### 2.2 Deploy

```bash
cd c:\Users\abdul\Desktop\jobscout
fly deploy -a jobscout-api
```

### 2.3 Verify startup

```bash
fly logs -a jobscout-api
```

Look for:

- `[DB] Connected to Postgres`
- No errors mentioning `pgvector_migration_second_brain` (best-effort; failures are logged but don’t crash the app)

---

## 3. Frontend (Vercel)

### 3.1 Environment variables

In Vercel → Project → **Settings** → **Environment Variables**:

| Name | Value |
|------|-------|
| `NEXT_PUBLIC_API_URL` | `https://jobscout-api.fly.dev/api/v1` |

### 3.2 Deploy

```bash
cd frontend
npx vercel --prod
```

Or push to `main` if Vercel is connected to GitHub.

---

## 4. Real-Time Test (Browser)

### 4.1 Sign in

1. Open your frontend (e.g. `https://jobiqueue.com`)
2. Click **Sign In** → use magic link or OAuth
3. Complete sign-in

### 4.2 Open Second Brain

1. Click **Second Brain** in the nav (or go to `/kb`)
2. You should see the KB page with Index and Query forms

### 4.3 Index a document

1. **Source type**: `note` (or any label)
2. **Title**: `Test doc`
3. **Text to index**: Paste a few paragraphs, e.g.:
   ```
   Project Alpha is a new initiative to improve our onboarding flow.
   Key goals: reduce time-to-productivity by 30%, add interactive tutorials.
   Timeline: Q2 2025. Owner: Jane from Product.
   ```
4. Click **Index**
5. You should see: `Indexed N chunk(s). Document ID: ...`

### 4.4 Query

1. **Question**: `What is Project Alpha?`
2. Click **Ask**
3. You should see an answer and citations (chunk snippets with scores)

### 4.5 Troubleshooting

| Symptom | Check |
|---------|-------|
| "Knowledge base is not enabled" | `JOBSCOUT_KB_ENABLED=true` in Fly secrets |
| "OpenAI API key not configured" | `JOBSCOUT_OPENAI_API_KEY` set in Fly secrets |
| "Authentication required" | Sign in again; session may have expired |
| 502 / embedding failed | OpenAI key valid; check `fly logs` |
| Empty answer / no citations | Index first; wait a few seconds; try a clearer question |

---

## 5. Optional: API Test (curl)

To test the API directly with a real token:

### 5.1 Get a token

1. Sign in on the frontend
2. Open DevTools → **Application** → **Local Storage**
3. Find the Supabase key that stores the session (e.g. `sb-...-auth-token`)
4. Copy the `access_token` value

Or use the Supabase client in the browser console:

```javascript
const { data } = await window.supabase?.auth.getSession?.();
console.log(data?.session?.access_token);
```

### 5.2 Index

```bash
curl -X POST "https://jobscout-api.fly.dev/api/v1/kb/index" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"source_type":"note","title":"API test","text":"This is a test document for the Second Brain API."}'
```

Expected: `{"document_id":"...","chunks_indexed":1}`

### 5.3 Query

```bash
curl -X POST "https://jobscout-api.fly.dev/api/v1/kb/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"question":"What is this document about?","max_chunks":5}'
```

Expected: `{"answer":"...","citations":[...]}`

---

## 6. Smoke Script

```bash
API_BASE=https://jobscout-api.fly.dev/api/v1 python scripts/smoke_api.py
```

KB endpoints without auth should return 401/422 (auth required). Other checks (jobs, runs, admin) require a fully configured backend.
