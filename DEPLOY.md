# JobScout Deployment Guide

Deploy JobScout for **free or near-free** using Vercel (frontend), Supabase (database), and Fly.io (backend).

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Vercel        │────▶│   Fly.io        │────▶│   Supabase      │
│   (Frontend)    │     │   (Backend)     │     │   (Postgres)    │
│   FREE          │     │   ~$0-5/mo      │     │   FREE          │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Step 1: Database (Supabase)

### 1.1 Create Supabase Project
1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project (free tier)
3. Wait for it to provision (~2 min)

### 1.2 Initialize Schema
1. Go to **SQL Editor** in Supabase Dashboard
2. Run this SQL (copy from `backend/app/storage/postgres.py` or use):

```sql
-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    provider_id TEXT,
    source TEXT NOT NULL,
    source_url TEXT,
    
    title TEXT NOT NULL,
    title_normalized TEXT,
    company TEXT NOT NULL,
    company_normalized TEXT,
    
    location_raw TEXT,
    country TEXT,
    city TEXT,
    remote_type TEXT DEFAULT 'unknown',
    
    employment_types TEXT[] DEFAULT '{}',
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    
    job_url TEXT,
    job_url_canonical TEXT,
    apply_url TEXT,
    
    description_text TEXT,
    
    emails TEXT[] DEFAULT '{}',
    company_website TEXT,
    linkedin_url TEXT,
    twitter_url TEXT,
    facebook_url TEXT,
    instagram_url TEXT,
    youtube_url TEXT,
    other_urls TEXT[] DEFAULT '{}',
    
    tags TEXT[] DEFAULT '{}',
    founder TEXT,
    
    posted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- AI fields
    ai_score REAL,
    ai_reasons TEXT,
    ai_remote_type TEXT,
    ai_employment_types TEXT[] DEFAULT '{}',
    ai_seniority TEXT,
    ai_confidence REAL,
    ai_summary TEXT,
    ai_requirements TEXT,
    ai_tech_stack TEXT,
    ai_company_domain TEXT,
    ai_company_summary TEXT,
    ai_flags TEXT[] DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_normalized);
CREATE INDEX IF NOT EXISTS idx_jobs_remote_type ON jobs(remote_type);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_ai_score ON jobs(ai_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_search ON jobs USING gin(to_tsvector('english', title || ' ' || company || ' ' || COALESCE(description_text, '')));

-- Runs table
CREATE TABLE IF NOT EXISTS runs (
    run_id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    jobs_collected INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    jobs_filtered INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    sources TEXT,
    criteria JSONB,
    error_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);
```

**No manual SQL required:** The backend runs `init_schema()` on startup and applies everything below. You only need to run the SQL above (or in `postgres.py` / `apply_schema.sql`) if you want the schema in place before the first deploy. Once the Fly app has started at least once with a valid `JOBSCOUT_DATABASE_URL`, it will create/update:

- **Core:** `jobs`, `runs` (from `postgres.py`)
- **Apply Workspace:** `apply_schema.sql` → `users`, `resume_versions`, `user_profiles`, `job_targets`, `trust_reports`, `apply_packs`, `applications`, `application_feedback`, `usage_ledger`, `entitlements`
- **Migrations (in order):** `apply_schema_migration_trust_applications_mvp.sql`, `apply_schema_migration_html.sql`, `apply_schema_migration_profiles.sql`, `apply_schema_migration_pack_topups.sql`, `apply_schema_migration_referrals.sql`, `apply_schema_migration_retention.sql`, `apply_schema_migration_trust_feedback.sql`, `apply_schema_migration_ai_premium.sql`, `apply_schema_migration_contacts.sql`
- **Optional:** `pgvector_migration_personalization.sql` (best-effort), `analytics_events` table and `analytics_daily_events` view

If something failed on a previous deploy, you can run the same SQL files in that order in the Supabase SQL Editor.

### 1.2b (Recommended) Enable personalization with pgvector
If you want **personalized job ranking** and **semantic matching**, run this SQL next:

```sql
-- Copy/paste from:
-- backend/app/storage/pgvector_migration_personalization.sql
```

### 1.3 Get Connection String
1. Go to **Settings > Database**
2. **Important**: Use the **Session pooler** connection string (not Direct connection)
   - Click on "Connection string" tab
   - Select "Session mode" (not Transaction mode)
   - Copy the connection string - looks like:
     `postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require`
   - Or the URI format: `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres?sslmode=require`
   
**Note**: The Session pooler is recommended for better compatibility with Fly.io and connection pooling.

---

## Step 2: Backend (Fly.io - Recommended)

### 2.1 Install Fly CLI
```bash
# macOS
brew install flyctl

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

# Linux
curl -L https://fly.io/install.sh | sh
```

### 2.2 Login & Create App
```bash
cd backend
fly auth login
fly launch --name jobscout-api --no-deploy
```

### 2.3 Set Secrets
```bash
fly secrets set JOBSCOUT_DATABASE_URL="postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"
fly secrets set JOBSCOUT_ADMIN_TOKEN="your-secure-token"
fly secrets set JOBSCOUT_CORS_ORIGINS='["https://your-app.vercel.app"]'
fly secrets set JOBSCOUT_AI_ENABLED="true"
fly secrets set JOBSCOUT_OPENAI_API_KEY="sk-..."
```

### 2.4 Create fly.toml
```toml
app = "jobscout-api"
primary_region = "iad"

[build]
  dockerfile = "backend/Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

[env]
  JOBSCOUT_USE_SQLITE = "false"
  JOBSCOUT_DEBUG = "false"
  JOBSCOUT_SCRAPE_INTERVAL_HOURS = "6"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

### 2.5 Deploy
```bash
fly deploy
```

Your API will be at: `https://jobscout-api.fly.dev`

**Note:** Fly.io is the recommended backend platform. It provides better performance, automatic scaling, and built-in scheduled tasks. The backend uses APScheduler for scheduled scrapes, which works seamlessly with Fly.io's always-on machines.

---

## Step 3: Frontend (Vercel)

### 3.1 Deploy to Vercel
```bash
cd frontend
npm install
npx vercel --prod
```

**If login fails**, see [Vercel CLI login troubleshooting](#vercel-cli-login-troubleshooting) below.

Or connect GitHub:
1. Go to [vercel.com](https://vercel.com)
2. **New Project > Import Git Repository**
3. Select your repo
4. Set **Root Directory**: `frontend`

### 3.2 Set Environment Variables
In Vercel dashboard > Settings > Environment Variables:
- `NEXT_PUBLIC_API_URL` = `https://jobscout-api.fly.dev/api/v1`

### 3.3 Redeploy
```bash
npx vercel --prod
```

**Script (after linking):** From repo root, `powershell -ExecutionPolicy Bypass -File scripts/deploy-frontend.ps1`. See `scripts/README.md`.

**From repo root:** If the Vercel project has **Root Directory** = `frontend`, you can run `npx vercel --prod --yes` from the repo root (where `vercel.json` lives). Ensure you're logged in and, for teams, set `VERCEL_ORG_ID` to your team id if needed.

### Vercel CLI login troubleshooting

If `vercel login` or `npx vercel --prod` fails or keeps asking you to log in:

1. **Run login in a real terminal (interactive)**  
   In PowerShell or Command Prompt (not through an automated script), run:
   ```bash
   cd frontend
   npx vercel login
   ```
   The CLI will show a **one-time code** and open your browser. Complete the sign-in in the browser; the token is saved locally.

2. **Token expired**  
   Vercel tokens expire after **10 days** of no use. If you see `The specified token is not valid`, run `npx vercel login` again to get a new token.

3. **Use a scope if you have a team**  
   If you use a team (e.g. "binary-exes-projects"), link the project once so later deploys work without `--scope`:
   ```bash
   cd frontend
   npx vercel link --scope binary-exes-projects
   ```
   When prompted, choose the existing Vercel project or create one. Then:
   ```bash
   npx vercel --prod
   ```

4. **Alternative: deploy without CLI**  
   - Push your code to GitHub and connect the repo in [Vercel Dashboard](https://vercel.com) → **Add New Project**. Set **Root Directory** to `frontend`.  
   - Every push to `main` will auto-deploy. No `vercel login` needed.

5. **CI/CD: use a token from the dashboard**  
   For scripts or CI, create a token at [vercel.com/account/tokens](https://vercel.com/account/tokens) and run:
   ```bash
   vercel --prod --token YOUR_TOKEN
   ```

---

## Step 4: Initial Data Load

Trigger your first scrape:

```bash
curl -X POST https://jobscout-api.fly.dev/api/v1/admin/run \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "automation engineer", "location": "Remote", "use_ai": true}'
```

---

## Cost Summary

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **Vercel** | 100GB bandwidth, unlimited deploys | Perfect for frontend |
| **Supabase** | 500MB database, 2GB bandwidth | Plenty for ~50k jobs |
| **Fly.io** | 3 shared VMs, 160GB bandwidth | May need $5/mo for always-on |
| **OpenAI** | Pay-as-you-go | ~$0.15/1M input tokens with gpt-4o-mini |

**Estimated total: $0-5/month** depending on usage.

---

## Scheduled Scrapes

The backend uses **APScheduler** for automatic scheduled scrapes. This is configured in `backend/app/main.py` and runs every 6 hours by default (configurable via `JOBSCOUT_SCRAPE_INTERVAL_HOURS`).

Since Fly.io keeps machines running, scheduled scrapes work automatically without any external cron setup.

**To change the schedule:**
1. Set `JOBSCOUT_SCRAPE_INTERVAL_HOURS` in Fly.io secrets
2. Redeploy: `fly deploy -a jobscout-api`

---

## Monitoring

- **Fly.io**: `fly logs -a jobscout-api` or dashboard at fly.io
- **Vercel**: Dashboard > Deployments > Functions
- **Supabase**: Dashboard > Logs

---

## Troubleshooting

### Database connection fails
- Check Supabase connection string includes password
- Ensure `?sslmode=require` if needed
- Whitelist IP in Supabase if using VPN

### CORS errors
- Add your frontend URL to `JOBSCOUT_CORS_ORIGINS`
- Redeploy backend after changing

### AI not working
- Verify `JOBSCOUT_OPENAI_API_KEY` is set
- Check `JOBSCOUT_AI_ENABLED=true`
- Monitor OpenAI usage at platform.openai.com

---

---

## Post-upgrade deploy checklist (Apply Workspace, Extension, Premium AI)

After implementing the upgrade plan (Trust v2, Tracker, Extension, Premium AI), use this checklist to deploy and verify.

### 1. Backend (Fly.io)

```bash
# From repo root
fly deploy -a jobscout-api
```

- **Migrations**: Backend runs `init_schema()` on startup; it applies `apply_schema_migration_contacts.sql`, `apply_schema_migration_trust_feedback.sql`, and creates `analytics_events` + `analytics_daily_events` if missing. No manual SQL needed for existing Supabase projects (migrations are additive and idempotent).
- **Secrets to set** (if not already):
  ```bash
  fly secrets set JOBSCOUT_DATABASE_URL="postgresql://..." -a jobscout-api
  fly secrets set JOBSCOUT_CORS_ORIGINS='["https://jobscoutai.vercel.app","http://localhost:3000"]' -a jobscout-api
  fly secrets set JOBSCOUT_SUPABASE_URL="https://YOUR_PROJECT.supabase.co" -a jobscout-api
  fly secrets set JOBSCOUT_SUPABASE_ANON_KEY="..." -a jobscout-api
  fly secrets set JOBSCOUT_ADMIN_TOKEN="..." -a jobscout-api
  ```
- **Premium AI** (Interview Coach + Templates): Set to enable quota-gated features.
  ```bash
  fly secrets set JOBSCOUT_PREMIUM_AI_ENABLED="true" -a jobscout-api
  fly secrets set JOBSCOUT_OPENAI_API_KEY="sk-..." -a jobscout-api
  ```
- **CORS**: Chrome/Edge extension origins are allowed automatically via regex (`chrome-extension://*`). No need to add extension IDs to `JOBSCOUT_CORS_ORIGINS`.

**Verify**: `curl -s https://jobscout-api.fly.dev/api/v1/jobs?page_size=1` returns JSON. Or run `scripts/smoke_api.sh` / `scripts/smoke_api.py` with `API_BASE=https://jobscout-api.fly.dev/api/v1` (see `scripts/README.md`).

### 2. Frontend (Vercel)

- **Option A – Git**: Push to `main`; Vercel auto-deploys if connected.
- **Option B – CLI**:
  ```bash
  cd frontend
  npx vercel --prod
  ```
- **Env**: In Vercel dashboard, set `NEXT_PUBLIC_API_URL=https://jobscout-api.fly.dev/api/v1` (and `NEXT_PUBLIC_SUPABASE_*`, `NEXT_PUBLIC_POSTHOG_*` if used).

**Verify**: Open the app URL, go to Apply Workspace, parse a job, generate Trust Report and Apply Pack.

### 3. Extension (Chrome/Edge)

- **Load unpacked**: Chrome → Extensions → Developer mode → Load unpacked → select the `extension/` folder.
- **Connect**: Open JobScoutAI in a tab, log in, then in the extension popup click **Connect**.
- **Save job**: On a job detail page (e.g. LinkedIn/Indeed), click **Save job** in the extension, then **Open Apply Workspace →** to deep-link and generate Trust Report.

See `extension/README.md` for full steps.

### 4. Config summary

| Item | Where | Notes |
|------|--------|--------|
| Premium AI | Fly secrets | `JOBSCOUT_PREMIUM_AI_ENABLED=true`, `JOBSCOUT_OPENAI_API_KEY` |
| CORS | Fly secrets | `JOBSCOUT_CORS_ORIGINS`; extension allowed by regex |
| Apply schema | Auto on startup | Backend runs migrations in `postgres.py` |

---

## Product Hunt Launch Checklist

- [ ] Deploy frontend to Vercel
- [ ] Deploy backend to Fly.io
- [ ] Run initial scrape
- [ ] Test all pages load correctly
- [ ] Test job detail pages
- [ ] Verify search/filters work
- [ ] Add OpenGraph image to `/frontend/public/og.png`
- [ ] Update meta tags in `layout.tsx`
- [ ] Prepare demo video
- [ ] Write launch tagline
- [ ] Schedule for Tuesday/Wednesday 12:01 AM PST
