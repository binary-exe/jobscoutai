# Scripts

## smoke_api.sh / smoke_api.py

Smoke test for **public** API endpoints (no auth): `/health`, `/api/v1/jobs`, `/api/v1/runs/latest`, `/api/v1/admin/stats`.

**Bash** (Linux/macOS/Git Bash):
```bash
API_BASE=https://jobscout-api.fly.dev/api/v1 ./scripts/smoke_api.sh
./scripts/smoke_api.sh   # defaults to http://localhost:8000/api/v1
```

**Python** (any OS, no extra deps):
```bash
API_BASE=https://jobscout-api.fly.dev/api/v1 python scripts/smoke_api.py
python scripts/smoke_api.py
```

Exits with code 1 if any required endpoint returns non-200.

## deploy-frontend.ps1

Deploy the frontend to Vercel (production). Requires the project to be linked first.

**First time:** From a terminal (interactive), run:
```powershell
cd frontend
npx vercel link --scope binary-exes-projects
```
Choose your existing Vercel project (e.g. jobscoutai).

**Then deploy:**
```powershell
# From repo root
powershell -ExecutionPolicy Bypass -File scripts/deploy-frontend.ps1
```

**Alternative (from repo root):** If your Vercel project has **Root Directory** set to `frontend`, you can deploy from the repo root: `npx vercel --prod --yes` (with `VERCEL_ORG_ID` set if using a team).

## metrics_query.sql

SQL to run in **Supabase SQL Editor** (or any Postgres client) to inspect product analytics:

- Daily rollup of all event types (`analytics_daily_events`)
- Activation: `first_apply_pack_created` counts
- Trust: `trust_report_generated` counts
- Tracker: `application_tracked` counts

Backend must have created `analytics_events` and the view (done automatically on first request after deploy).
