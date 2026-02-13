# Backend Reference (JobScout)

## Lifespan / startup behavior (important)

In `backend/app/main.py`:

- Postgres mode:
  - connect asyncpg pool
  - run `init_schema(conn)` best-effort
- SQLite mode:
  - no pool; storage handled separately
- Scheduler:
  - runs when `JOBSCOUT_DEBUG=false`
  - uses APScheduler interval job calling `run_scheduled_scrape()`

Implication: schema init must be safe on restart and safe when partially upgraded.

## CORS model

- Allowlist from `settings.cors_origins`
- Plus an allow-regex for `chrome-extension://...` origins (browser extension support)
- Exception handlers manually add CORS headers (don’t remove casually)

## Auth model

### Admin token

- `Authorization: Bearer <JOBSCOUT_ADMIN_TOKEN>`
- Used for `/api/v1/admin/run`, embeddings backfill, etc.

### User token (Supabase)

- `Authorization: Bearer <supabase_access_token>`
- Backend validates via Supabase `/auth/v1/user` (stateless; no JWT lib)

## Apply Workspace endpoints (what makes them fragile)

- Many endpoints are authenticated and rate-limited.
- File upload endpoints depend on `python-multipart`; the router guards import-time failure so the API can still boot.

## DB/migrations model

- Postgres adapter runs:
  - base schema init for JobScout tables
  - Apply Workspace schema (`apply_schema.sql`)
  - ordered list of idempotent migrations
  - optional pgvector migration (best-effort)
  - analytics tables/view (best-effort)
