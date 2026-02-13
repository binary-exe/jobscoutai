---
name: jobscoutai-dev
description: Repository-specific development workflow for JobScout (Next.js frontend, FastAPI backend, jobscout Python package). Use when making changes in this repo, setting up local dev, adding endpoints/providers, modifying env vars/schema, or when asked “how we build here”.
---

# JobScoutAI Dev (“how we build here”)

## When to use this skill

Use this whenever you’re developing JobScout in this repo and want the “how we build here” workflow that prevents breakage.

## Non‑negotiables (mistake-proof guardrails)

- **Backwards compatibility**:
  - never remove/rename existing API endpoints
  - never drop/rename existing DB columns
  - prefer additive changes (new nullable columns, new tables/indexes)
- **No secrets in code**: never commit API keys/tokens; only update `env.sample` templates.
- **No platform switches** (Fly/Vercel/Supabase) unless explicitly asked.
- **Cost controls by default**: AI/enrichment stays off unless explicitly enabled and capped.
- **If you add config, you must add docs**:
  - backend config lives in `backend/app/core/config.py` (`JOBSCOUT_*`)
  - templates live in `backend/env.sample` and `frontend/env.sample`

## Repo map (what lives where)

- `frontend/`: Next.js 14 (App Router) + Tailwind + Supabase auth client
- `backend/`: FastAPI API + storage + background worker
- `jobscout/`: scraping library + providers + CLI orchestration

## Local dev commands (canonical)

### Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
pip install -e ../
cp env.sample .env
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)

```bash
cd frontend
npm install
cp env.sample .env.local
npm run dev
```

### Core library / CLI (optional sanity check)

```bash
pip install -e ".[all]"
python -m jobscout "automation engineer" --remote-only --verbose
```

## Decision tree (pick the right layer first)

- UI/UX and pages → `frontend/`
- API behavior, auth enforcement, rate limits, storage → `backend/`
- provider behavior, dedupe, enrichment, AI pipeline → `jobscout/`
- schema/migrations → `backend/app/storage/*.sql` (keep `backend/app/storage/postgres.py` consistent)

## “If you changed X, you must do Y” gates

- **Touched `frontend/`**
  - must run: `cd frontend && npm run lint`
  - must run: `cd frontend && npm run build`
- **Touched Python (`backend/` or `jobscout/`)**
  - must run: `python -m compileall backend jobscout`
  - must smoke-test affected endpoints in `/docs` if you touched API code
- **Added/changed env vars**
  - must update: `backend/env.sample` and/or `frontend/env.sample`
  - must keep runtime/build safe defaults (no crashes when env vars are missing)
- **Added/changed DB schema**
  - must keep it additive + idempotent
  - must add/adjust migration SQL under `backend/app/storage/`
  - must ensure startup schema init is best-effort and won’t brick the app

## Common playbooks (do these exactly)

### Add a backend endpoint

- Create/extend a router in `backend/app/api/`.
- Use explicit Pydantic models for request/response.
- Include the router in `backend/app/main.py` with `prefix=settings.api_prefix`.
- Add auth if needed:
  - admin-only: `verify_admin_token` pattern
  - logged-in user: `get_current_user` / `get_optional_user` dependencies

### Add a DB change (Supabase Postgres)

- Write an **idempotent** migration SQL file (`IF NOT EXISTS`, safe re-runs).
- Ensure it is executed by `backend/app/storage/postgres.py:init_schema()` (or is already in its migration list).
- Do not require manual ordering; idempotency is the safety net.

### Add/modify an Apply Workspace endpoint (authenticated)

- Frontend calls must send `Authorization: Bearer <supabase_access_token>` (see `frontend/lib/apply-api.ts`).
- Backend endpoints must enforce user auth via `get_current_user` and consider per-user rate limits (`backend/app/core/rate_limit.py`).

### Add/modify a scraping provider

- Implement under `jobscout/providers/`.
- Be resilient: timeouts/partial failures shouldn’t crash the whole run.
- Ensure allowlist behavior via `enabled_providers` stays intact.

## “Done” output format (always)

When finishing a task in this repo, report:

- **What changed**: 2–5 bullets, user-facing impact first
- **Key files**: list of touched paths
- **How verified**: commands run + manual checks
- **Notes/risks**: migrations, rollout, compatibility

## Additional resources

- Deep runbooks: [reference.md](reference.md)
- Ready-to-copy snippets: [examples.md](examples.md)
