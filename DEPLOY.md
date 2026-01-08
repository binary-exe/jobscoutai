# JobScout Deployment Guide

Deploy JobScout for **free or near-free** using Vercel (frontend), Supabase (database), and Fly.io or Render (backend).

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Vercel        │────▶│   Fly.io/       │────▶│   Supabase      │
│   (Frontend)    │     │   Render        │     │   (Postgres)    │
│   FREE          │     │   (Backend)     │     │   FREE          │
│                 │     │   ~$0-5/mo      │     │                 │
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_remote_type ON jobs(remote_type);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_ai_score ON jobs(ai_score DESC NULLS LAST);

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
    criteria JSONB
);
```

### 1.3 Get Connection String
1. Go to **Settings > Database**
2. Copy the **Connection string (URI)** - looks like:
   `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

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
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[env]
  JOBSCOUT_USE_SQLITE = "false"
  JOBSCOUT_DEBUG = "false"
```

### 2.5 Deploy
```bash
fly deploy
```

Your API will be at: `https://jobscout-api.fly.dev`

---

## Step 2 (Alternative): Backend (Render)

### 2.1 Create Web Service
1. Go to [render.com](https://render.com) and sign up
2. **New > Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (spins down after 15 min inactivity)

### 2.2 Add Environment Variables
In Render dashboard, add:
- `JOBSCOUT_DATABASE_URL`
- `JOBSCOUT_ADMIN_TOKEN`
- `JOBSCOUT_CORS_ORIGINS`
- `JOBSCOUT_OPENAI_API_KEY` (optional)
- `JOBSCOUT_AI_ENABLED`

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
| **Render** | 750 hours/month, spins down | Free but cold starts |
| **OpenAI** | Pay-as-you-go | ~$0.15/1M input tokens with gpt-4o-mini |

**Estimated total: $0-5/month** depending on usage.

---

## Cron / Scheduled Scrapes

The backend has a built-in scheduler, but if using Render (which spins down), use an external cron:

### Option A: GitHub Actions (Free)
Create `.github/workflows/scrape.yml`:

```yaml
name: Scheduled Scrape
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger scrape
        run: |
          curl -X POST ${{ secrets.API_URL }}/admin/run \
            -H "Authorization: Bearer ${{ secrets.ADMIN_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{"query": "automation engineer", "use_ai": true}'
```

Add secrets in GitHub repo settings.

### Option B: cron-job.org (Free)
1. Go to [cron-job.org](https://cron-job.org)
2. Create job hitting your `/admin/run` endpoint
3. Set schedule (e.g., every 6 hours)

---

## Monitoring

- **Fly.io**: `fly logs`
- **Render**: Dashboard > Logs
- **Vercel**: Dashboard > Deployments > Functions

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
- [ ] Deploy backend to Fly.io/Render
- [ ] Run initial scrape
- [ ] Test all pages load correctly
- [ ] Test job detail pages
- [ ] Verify search/filters work
- [ ] Add OpenGraph image to `/frontend/public/og.png`
- [ ] Update meta tags in `layout.tsx`
- [ ] Prepare demo video
- [ ] Write launch tagline
- [ ] Schedule for Tuesday/Wednesday 12:01 AM PST
