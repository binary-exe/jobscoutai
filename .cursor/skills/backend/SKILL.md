---
name: backend
description: JobScout backend workflow and conventions (FastAPI routers, Settings/env vars, storage via asyncpg, rate limits/guardrails). Use when editing backend/app/*, adding endpoints, changing config, or troubleshooting API behavior.
---

# Backend (FastAPI) conventions

## Local workflow

```bash
cd backend
pip install -r requirements.txt
pip install -e ../
cp env.sample .env
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Key URLs:

- API docs: `/docs`
- Health: `/health`

## Hard rules (mistake-proof)

- **Never** remove/rename existing endpoints; add new ones under `/api/v1/...`.
- **Never** break startup:
  - DB schema init (`init_schema`) must be idempotent/best-effort
  - optional dependencies must not crash at import time (guard them like Apply upload does)
- **Always** keep new env vars documented in `backend/env.sample` and defined in `backend/app/core/config.py`.

## Adding/changing endpoints (router conventions)

- Routers live under `backend/app/api/`.
- Routers are included in `backend/app/main.py` with `prefix=settings.api_prefix` (default `/api/v1`).
- Return helpful HTTP errors (`HTTPException`) with a clear `detail`.
- For frontend “fire-and-forget” endpoints, it’s OK to return 204 (see `metrics/event`).

## Config / env vars

- Settings are defined in `backend/app/core/config.py` and use env prefix `JOBSCOUT_`.
- If you add a setting:
  - add it to `Settings`
  - document it in `backend/env.sample`

## Auth patterns (don’t improvise)

- **Admin auth**: `backend/app/api/admin.py:verify_admin_token` checks `Authorization: Bearer <token>`.
- **User auth**: `backend/app/core/auth.py` validates Supabase JWT via `/auth/v1/user`.
  - Require auth: `user: AuthUser = Depends(get_current_user)`
  - Optional auth: `user: Optional[AuthUser] = Depends(get_optional_user)`

## Rate limiting (Apply Workspace + expensive endpoints)

- Use per-user in-memory rate limiters from `backend/app/core/rate_limit.py`.
- The limiter is a guardrail, not a billing system; keep it strict and predictable.

## Storage / DB safety (how this backend actually boots)

- DB pool: `backend/app/core/database.py` (asyncpg pool).
- Startup:
  - `backend/app/main.py` connects to Postgres (unless SQLite)
  - runs `backend/app/storage/postgres.py:init_schema()` **best-effort**
  - schema init must be **idempotent** and must not brick the service on partial failure
- Storage + migrations:
  - SQL lives in `backend/app/storage/*.sql`
  - `init_schema()` executes base schema + a list of migrations (idempotent; safe if already applied)

## Public scrape guardrails (do not weaken accidentally)

- `POST /api/v1/scrape` is intentionally guarded in-memory:
  - concurrency cap
  - per-IP rate limit
  - forces `use_ai=False` for public scrapes (AI reserved for admin/trusted flows)

## Minimal verification

```bash
python -m compileall backend
```

Then smoke-test affected endpoints in `/docs`.

## Additional resources

- Deeper backend runbooks: [reference.md](reference.md)
- Copy/paste snippets: [examples.md](examples.md)
