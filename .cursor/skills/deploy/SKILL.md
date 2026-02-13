---
name: deploy
description: Deployment workflow for JobScout: Supabase (DB), Fly.io (FastAPI backend), Vercel (Next.js frontend). Use when asked to deploy, cut a release, change env vars/secrets, apply SQL migrations, or troubleshoot production deploy issues.
---

# Deploy (Supabase + Fly.io + Vercel)

## Principles (don’t violate)

- **No infra changes** (platform swaps, major config rewrites) unless explicitly requested.
- **Backwards compatible** DB/API changes only.
- **Secrets never committed**: use Fly/Vercel/Supabase secret managers; keep `env.sample` updated.

## Pre-deploy gates (must be green)

- **Frontend**: `cd frontend && npm run lint && npm run build`
- **Backend**: `python -m compileall backend jobscout`
- **DB**: migrations are additive (new nullable columns, new tables/indexes)
- **Config**: any new env vars are present in `backend/env.sample` or `frontend/env.sample`

## Database (Supabase) migration workflow (safe + repeatable)

1. Put migration SQL in `backend/app/storage/<migration>.sql`.
2. Ensure it is **idempotent** (safe to rerun).
3. Ensure `backend/app/storage/postgres.py:init_schema()` executes it (or it’s explicitly optional/best-effort).
4. Apply the SQL via **Supabase SQL Editor** (or rely on startup execution if that’s how it’s wired).
5. Never drop/rename columns in-place; use additive patterns.

## Backend deploy (Fly.io)

Typical deploy:

```bash
fly deploy -a jobscout-api
```

Common ops:

- **Logs**: `fly logs -a jobscout-api`
- **Set/update secrets** (examples):
  - `JOBSCOUT_DATABASE_URL`
  - `JOBSCOUT_CORS_ORIGINS`
  - `JOBSCOUT_ADMIN_TOKEN`
  - `JOBSCOUT_SUPABASE_URL`, `JOBSCOUT_SUPABASE_ANON_KEY` (auth validation)
  - `JOBSCOUT_AI_ENABLED`, `JOBSCOUT_OPENAI_API_KEY`

Rollback (when needed):

- Prefer rolling back by Fly release tooling (don’t hot-edit code in prod).

## Frontend deploy (Vercel)

- Normal path: merge to `main` (GitHub integration auto-deploys).
- Manual deploy:

```bash
cd frontend
npm install
npx vercel --prod
```

Required env var:

- `NEXT_PUBLIC_API_URL` (points to backend `/api/v1`)

## Post-deploy smoke checks (must do)

- Backend: `GET /health` and `GET /docs`
- Frontend: home page loads, search works, job detail page loads
- Trigger a scrape via admin endpoint (if applicable) and confirm run status updates

## Additional resources

- Deep troubleshooting + rollback notes: [reference.md](reference.md)
- Copy/paste commands: [examples.md](examples.md)
