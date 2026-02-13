# JobScoutAI Dev Reference (deep runbooks)

Keep `SKILL.md` short; use this file for the details that prevent “auto-agent drift”.

## Canonical entry points (high signal)

- **Backend app**: `backend/app/main.py`
- **Settings/env**: `backend/app/core/config.py` + `backend/env.sample`
- **Backend auth**: `backend/app/core/auth.py` (Supabase `/auth/v1/user`)
- **Public scrape guardrails**: `backend/app/api/scrape.py`
- **Admin endpoints**: `backend/app/api/admin.py`
- **DB init + migrations execution**: `backend/app/storage/postgres.py:init_schema()`
- **Frontend API client**: `frontend/lib/api.ts`
- **Apply Workspace API client (auth-required)**: `frontend/lib/apply-api.ts`
- **Supabase client (build-safe)**: `frontend/lib/supabase.ts`
- **Scraping orchestration**: `jobscout/orchestrator.py`

## Hard rules (copy/paste into your mental model)

### API safety rules

- Add endpoints; don’t rename/remove existing ones.
- Keep response keys stable; add fields as optional.
- Prefer clear, explicit Pydantic models to avoid accidental shape changes.

### DB safety rules

- Add columns as nullable (or with safe defaults).
- Use **idempotent SQL** (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` where possible).
- If a migration can fail on already-upgraded DBs, it must fail safely (best-effort) and not brick startup.
- `init_schema()` runs at startup; treat it as “must not crash”.

### Auth safety rules

- Frontend must not crash build/SSR when Supabase env vars are missing.
- Backend “logged-in user” is defined by successfully calling Supabase `/auth/v1/user` using:
  - `Authorization: Bearer <token>`
  - `apikey: <supabase_anon_key>`

### Cost/abuse guardrails

- Public scrape endpoint is intentionally guarded and forces `use_ai=False` for cost control (`backend/app/api/scrape.py`).
- Use per-user rate limiting for expensive authenticated endpoints (`backend/app/core/rate_limit.py`).

## Playbooks

### Add a new backend router

1. Create `backend/app/api/<feature>.py` with:
   - `router = APIRouter(prefix="/<feature>", tags=[...])`
   - request/response models
2. Include in `backend/app/main.py` with `app.include_router(..., prefix=settings.api_prefix)`
3. If authenticated:
   - use `Depends(get_current_user)` from `backend/app/core/auth.py`
4. Smoke test in `/docs` locally.

### Add a DB migration file

1. Add SQL file under `backend/app/storage/` with **idempotent** statements.
2. Ensure `backend/app/storage/postgres.py:init_schema()` executes it (migration list).
3. If it’s optional (pgvector, premium features), make it best-effort and safe to skip.

### Add a frontend API call

- Prefer adding functions in `frontend/lib/api.ts` (public endpoints) or `frontend/lib/apply-api.ts` (authenticated endpoints).
- Keep errors actionable: include server `detail` when available.

## Minimal verification matrix

- **Frontend touched**: `npm run lint`, `npm run build`
- **Backend/core touched**: `python -m compileall backend jobscout`
- **API touched**: open `/docs`, exercise the endpoint(s)
- **Auth touched**: verify behavior with and without Supabase env vars (build-safe)
