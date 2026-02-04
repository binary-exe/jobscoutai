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
