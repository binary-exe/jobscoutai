# Deploy Reference (deep troubleshooting)

## Environment variables: where they live

- Backend settings are `JOBSCOUT_*` in `backend/app/core/config.py`.
- Backend template: `backend/env.sample`.
- Frontend template: `frontend/env.sample` (Vercel env vars mirror this).

## Required “minimum viable production” env

### Backend (Fly secrets)

- `JOBSCOUT_DATABASE_URL` (Supabase session pooler recommended)
- `JOBSCOUT_CORS_ORIGINS` (must include frontend domain)
- `JOBSCOUT_ADMIN_TOKEN` (for `/api/v1/admin/run`, embeddings backfill)

If using auth-protected features:

- `JOBSCOUT_SUPABASE_URL`
- `JOBSCOUT_SUPABASE_ANON_KEY`

If using AI features:

- `JOBSCOUT_AI_ENABLED=true`
- `JOBSCOUT_OPENAI_API_KEY`

### Frontend (Vercel env)

- `NEXT_PUBLIC_API_URL` (backend URL including `/api/v1`)
- If enabling Supabase login:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Rollback playbook

### Fly.io

- Identify failing release via Fly release tooling.
- Roll back to previous working release (preferred) instead of patching production.

### Vercel

- Redeploy the last known good deployment from Vercel dashboard.

## Common production issues

### CORS errors

- Ensure frontend origin is listed in `JOBSCOUT_CORS_ORIGINS` (JSON list or comma-separated).
- Redeploy backend after updating.

### Database connection fails

- Supabase connection string must include password.
- Use `?sslmode=require` when needed.
- Prefer **Session pooler** for Fly compatibility.

### “Supabase auth not configured” (backend)

- Set `JOBSCOUT_SUPABASE_URL` and `JOBSCOUT_SUPABASE_ANON_KEY` in Fly secrets.

### Public scrape disabled (404 on `/api/v1/scrape`)

- This is expected when `JOBSCOUT_PUBLIC_SCRAPE_ENABLED=false`.
- Use `/api/v1/admin/run` with `JOBSCOUT_ADMIN_TOKEN` for manual runs.
