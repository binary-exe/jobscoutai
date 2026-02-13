# PR Check Reference

## What “green” means in this repo

- **Frontend**: `npm run lint` and `npm run build` both succeed.
- **Python**: `python -m compileall backend jobscout` succeeds.
- **Manual smoke**: for endpoint changes, `/docs` loads and the affected endpoints can be called successfully.

## Common failure buckets

### Next.js build fails

Typical causes:

- using browser-only APIs in a server component (missing `"use client"`)
- accessing env vars directly in code paths that run during build/SSR without guards
- importing a module that assumes Supabase is configured (must remain build-safe)

### Auth failures

- Frontend requests missing `Authorization: Bearer <token>` for authenticated endpoints.
- Backend missing `JOBSCOUT_SUPABASE_URL` / `JOBSCOUT_SUPABASE_ANON_KEY` (500 “not configured”).

### DB migration failures

- non-idempotent SQL (fails on second run)
- migration not wired into `init_schema()` execution (works locally but not in deploy/startup)

## “No surprises” PR checklist

- any new env vars are added to `env.sample`
- any new endpoint is included in `backend/app/main.py`
- any SQL migration is additive + idempotent
- public scrape keeps cost/abuse guardrails intact
