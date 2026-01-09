# JobScout Development Guide for AI Agents

This document provides comprehensive context for AI agents (like Codex CLI) to continue development on JobScout.

**⚠️ CRITICAL: Read this entire document before making any changes. This file is re-read every session.**

## 📋 Table of Contents

1. [Quick Start & Commands](#quick-start--commands) ⚡ **START HERE**
2. [Repository Map](#repository-map)
3. [Definition of Done](#definition-of-done)
4. [Development Constraints](#development-constraints)
5. [Project Overview](#project-overview)
6. [Architecture](#architecture)
7. [Directory Structure](#directory-structure)
8. [Key Components](#key-components)
9. [API Endpoints](#api-endpoints)
10. [Database Schema](#database-schema)
11. [Environment Variables](#environment-variables)
12. [Development Workflow](#development-workflow)
13. [Common Tasks](#common-tasks)
14. [Deployment](#deployment)
15. [Known Issues & TODOs](#known-issues--todos)

---

## Quick Start & Commands

### Repository Map

```
jobscout/                          # Root monorepo
├── frontend/                      # Next.js 14 app (Vercel)
│   ├── app/                      # Pages (App Router)
│   ├── components/               # React components
│   ├── lib/                      # API client, utils
│   └── package.json              # npm scripts
│
├── backend/                       # FastAPI app (Fly.io)
│   ├── app/                      # FastAPI application
│   │   ├── api/                  # REST endpoints
│   │   ├── core/                 # Config, database
│   │   ├── storage/              # Postgres adapter
│   │   └── worker.py             # Background tasks
│   ├── Dockerfile                # Fly.io deployment
│   └── requirements.txt          # Python deps
│
└── jobscout/                     # Core scraping library (Python package)
    ├── providers/                # Job source providers
    ├── fetchers/                 # HTTP/browser fetching
    ├── extract/                  # HTML/JSON extraction
    ├── llm/                      # AI features
    └── storage/                  # SQLite adapter
```

### Exact Commands

#### Development

**Backend (FastAPI):**
```bash
cd backend
pip install -r requirements.txt
pip install -e ../  # Install jobscout package in dev mode
cp env.sample .env
# Edit .env with your settings
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```
- Runs at: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

**Frontend (Next.js):**
```bash
cd frontend
npm install
cp env.sample .env.local
# Edit .env.local: NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm run dev
```
- Runs at: `http://localhost:3000`

**Core Library (CLI):**
```bash
# Install in dev mode
pip install -e ".[all]"

# Run scrape
python -m jobscout "automation engineer" --remote-only --verbose
```

#### Testing

**Backend:**
```bash
cd backend
# No formal test suite yet - test via Swagger UI at /docs
# Or manual API calls:
curl http://localhost:8000/api/v1/jobs?q=test
```

**Frontend:**
```bash
cd frontend
npm run lint        # TypeScript/ESLint checks
npm run build       # Production build test
```

**Core Library:**
```bash
# Manual testing via CLI
python -m jobscout "test query" --verbose
```

#### Build

**Backend:**
```bash
cd backend
# Build happens in Dockerfile for Fly.io
# Local build test:
docker build -f Dockerfile -t jobscout-api .
```

**Frontend:**
```bash
cd frontend
npm run build       # Production build
npm run start       # Test production build locally
```

#### Deploy

**Backend (Fly.io):**
```bash
# From repo root
fly deploy -a jobscout-api

# Check logs
fly logs -a jobscout-api

# Set secrets (if needed)
fly secrets set JOBSCOUT_DATABASE_URL="..." -a jobscout-api
```

**Frontend (Vercel):**
```bash
# Auto-deploys on push to main branch
# Manual deploy:
cd frontend
npx vercel --prod

# Or via GitHub integration (automatic)
```

**Database (Supabase):**
- Schema changes: Run SQL in Supabase SQL Editor
- Connection: Use Session pooler connection string (not Direct)

---

## Definition of Done

Before considering any task complete, verify:

### ✅ Code Quality
- [ ] **Linting**: No lint errors
  - Backend: Python code follows PEP 8 (no formal linter yet, but check manually)
  - Frontend: `npm run lint` passes
- [ ] **Type Safety**: TypeScript types are correct (frontend)
- [ ] **No Console Errors**: Check browser console and server logs

### ✅ Functionality
- [ ] **Local Testing**: Feature works in local dev environment
  - Backend: Test via Swagger UI (`/docs`) or curl
  - Frontend: Test in browser at `http://localhost:3000`
- [ ] **API Compatibility**: Changes don't break existing API contracts
- [ ] **Database**: Schema changes (if any) are backward compatible

### ✅ Deployment Check
- [ ] **Build Success**: 
  - Frontend: `npm run build` succeeds
  - Backend: Docker build succeeds (or would succeed)
- [ ] **Environment Variables**: All required env vars documented in `env.sample`
- [ ] **Documentation**: Updated `AGENTS.md` if architecture/commands changed

### ✅ Git Hygiene
- [ ] **Commits**: Clear, descriptive commit messages
- [ ] **No Secrets**: No API keys, tokens, or passwords in code
- [ ] **No Large Files**: No binary files or large data files committed

**Note**: Formal unit tests are not yet implemented. Manual testing via Swagger UI and browser is acceptable for now.

---

## Development Constraints

### 🚫 DO NOT

1. **Infrastructure Changes**
   - ❌ Do NOT change deployment platforms (Fly.io, Vercel, Supabase)
   - ❌ Do NOT modify `fly.toml` structure without explicit request
   - ❌ Do NOT change Dockerfile base image or major dependencies
   - ❌ Do NOT add new infrastructure services (Redis, queues, etc.) without approval

2. **Dependency Management**
   - ❌ Do NOT add new Python packages to `backend/requirements.txt` without checking if they're in `pyproject.toml`
   - ❌ Do NOT add new npm packages to `frontend/package.json` without justification
   - ❌ Do NOT upgrade major versions (e.g., Next.js 14 → 15, Python 3.11 → 3.12) without approval
   - ✅ Prefer using existing dependencies from `pyproject.toml` optional groups

3. **Database Schema**
   - ❌ Do NOT drop or rename existing columns (breaking changes)
   - ❌ Do NOT change column types without migration plan
   - ✅ Add new columns as nullable when possible
   - ✅ Always update both `backend/app/storage/postgres.py` schema AND `AGENTS.md` documentation

4. **API Contracts**
   - ❌ Do NOT remove or rename existing API endpoints
   - ❌ Do NOT change request/response schemas without versioning
   - ✅ Add new endpoints as `/api/v1/new-endpoint`
   - ✅ Maintain backward compatibility

5. **Environment Variables**
   - ❌ Do NOT remove existing env vars
   - ❌ Do NOT change env var names without migration path
   - ✅ Always update `env.sample` files when adding new vars
   - ✅ Document new vars in `AGENTS.md`

6. **File Structure**
   - ❌ Do NOT move files between `frontend/` and `backend/` without explicit request
   - ❌ Do NOT restructure the `jobscout/` package without approval
   - ✅ Follow existing patterns and conventions

### ✅ DO

1. **Follow Existing Patterns**
   - Use existing component patterns in `frontend/components/`
   - Follow API endpoint structure in `backend/app/api/`
   - Match provider implementation style in `jobscout/providers/`

2. **Error Handling**
   - Always handle errors gracefully
   - Log errors with context
   - Return appropriate HTTP status codes

3. **Documentation**
   - Update `AGENTS.md` if you add new commands, endpoints, or patterns
   - Add comments for complex logic
   - Update `env.sample` files for new configuration

4. **Testing**
   - Test locally before committing
   - Verify API endpoints via Swagger UI
   - Check frontend in browser

5. **Cost Awareness**
   - Be mindful of API costs (OpenAI, external APIs)
   - Use caching where appropriate
   - Respect rate limits

---

## Project Overview

**JobScout** is an AI-powered job aggregator that:
- Scrapes jobs from multiple sources (RemoteOK, WeWorkRemotely, Remotive, Arbeitnow, etc.)
- Provides on-demand scraping via web UI
- Uses AI (OpenAI GPT-4o-mini) for ranking, classification, and enrichment (optional)
- Stores jobs in PostgreSQL (Supabase) or SQLite (local dev)
- Serves a beautiful Next.js frontend with real-time search

**Tech Stack:**
- **Backend**: FastAPI (Python 3.11), asyncpg, APScheduler
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS
- **Database**: PostgreSQL (Supabase) / SQLite (dev)
- **Deployment**: Fly.io (backend), Vercel (frontend)
- **AI**: OpenAI API (gpt-4o-mini, optional)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                         │
│              Vercel: jobscoutai.vercel.app                    │
│  - Server-side rendering                                      │
│  - On-demand scraping via POST /api/v1/scrape                │
│  - Real-time job search with filters                          │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼───────────────────────────────────┐
│                  Backend (FastAPI)                            │
│            Fly.io: jobscout-api.fly.dev                       │
│  - REST API (/api/v1/jobs, /api/v1/scrape, /api/v1/runs)     │
│  - Background scraping (async, writes to Postgres)            │
│  - Scheduled scrapes (APScheduler, every 6h)                  │
│  - Rate limiting & concurrency caps                           │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│   Supabase      │ │   OpenAI    │ │  Job Sources    │
│   PostgreSQL    │ │  (Optional) │ │  (APIs/RSS)     │
│   - jobs table  │ │ gpt-4o-mini │ │  - RemoteOK     │
│   - runs table  │ │             │ │  - WeWorkRemotely│
│   - llm_cache   │ │             │ │  - Remotive     │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

**Data Flow:**
1. User enters search query → Frontend triggers `POST /api/v1/scrape`
2. Backend enqueues scrape run → Returns `run_id` immediately
3. Background worker scrapes from multiple providers → Writes to Postgres
4. Frontend polls `GET /api/v1/runs/{run_id}` → Shows progress
5. When complete, frontend refreshes job list from `GET /api/v1/jobs`

---

## Directory Structure

```
jobscout/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/                # API endpoints
│   │   │   ├── jobs.py         # GET /jobs, GET /jobs/{id}
│   │   │   ├── scrape.py       # POST /scrape (public, rate-limited)
│   │   │   ├── runs.py          # GET /runs/{id}, GET /runs/latest
│   │   │   └── admin.py        # POST /admin/run (admin-only)
│   │   ├── core/
│   │   │   ├── config.py       # Settings (Pydantic)
│   │   │   └── database.py     # asyncpg connection pool
│   │   ├── storage/
│   │   │   └── postgres.py     # Postgres adapter (upsert_job, start_run, etc.)
│   │   ├── worker.py           # Background scraping logic
│   │   └── main.py             # FastAPI app entry point
│   ├── Dockerfile              # Fly.io deployment
│   ├── requirements.txt        # Python dependencies
│   └── env.sample              # Environment variable template
│
├── frontend/                   # Next.js frontend
│   ├── app/
│   │   ├── page.tsx            # Home page (job list + search)
│   │   ├── job/[id]/page.tsx   # Job detail page
│   │   └── layout.tsx          # Root layout
│   ├── components/
│   │   ├── SearchBar.tsx       # Search input + scrape trigger
│   │   ├── JobCard.tsx         # Job list item
│   │   ├── Filters.tsx         # Sidebar filters
│   │   ├── FormattedDescription.tsx  # Formats job descriptions
│   │   └── ...
│   ├── lib/
│   │   ├── api.ts              # API client functions
│   │   └── utils.ts            # Utility functions
│   └── package.json
│
├── jobscout/                   # Core scraping library
│   ├── orchestrator.py         # Main scrape orchestration
│   ├── models.py              # Criteria, NormalizedJob, enums
│   ├── dedupe.py              # Multi-layer deduplication
│   ├── providers/             # Job source providers
│   │   ├── remoteok.py
│   │   ├── weworkremotely.py
│   │   ├── remotive.py
│   │   ├── arbeitnow.py
│   │   ├── discovery.py        # Auto-discovers ATS job boards
│   │   └── ...
│   ├── fetchers/              # HTTP/Browser fetching
│   │   ├── http.py            # aiohttp with retries/throttling
│   │   └── browser.py         # Playwright (optional)
│   ├── extract/               # Data extraction
│   │   ├── html.py            # HTML stripping/parsing
│   │   ├── jsonld.py          # Schema.org JobPosting parsing
│   │   └── enrich.py          # Company page enrichment
│   ├── llm/                   # AI features (optional)
│   │   ├── provider.py        # Abstract LLM client
│   │   ├── openai_client.py   # OpenAI implementation
│   │   ├── rank.py            # Job ranking
│   │   ├── classify.py        # Remote type, employment type
│   │   ├── enrich_llm.py      # Summary, requirements, tech stack
│   │   ├── company_agent.py   # Company research
│   │   ├── alerts.py          # Quality/safety flags
│   │   └── cache.py           # SQLite LLM response cache
│   └── storage/
│       └── sqlite.py          # SQLite adapter (local dev)
│
├── pyproject.toml             # Python package config
├── README.md
├── DEPLOY.md
└── AGENTS.md                  # This file
```

---

## Key Components

### Backend

#### `backend/app/worker.py`
- `enqueue_scrape_run()`: Creates run record, triggers background scrape
- `trigger_scrape_run()`: Synchronous scrape (used by admin endpoint)
- `run_scheduled_scrape()`: Scheduled scrape runner

#### `backend/app/api/scrape.py`
- `POST /api/v1/scrape`: Public endpoint for on-demand scraping
  - Rate limiting: 6 requests/hour per IP
  - Concurrency cap: 1 active scrape
  - Returns `{status: "queued", run_id: N}` immediately

#### `backend/app/api/runs.py`
- `GET /api/v1/runs/{run_id}`: Get run status and stats
- `GET /api/v1/runs/latest`: Get most recent run

#### `backend/app/storage/postgres.py`
- `upsert_job_from_dict()`: Insert/update job (handles timestamps)
- `start_run()`: Create run record
- `finish_run()`: Update run with final stats

### Frontend

#### `frontend/components/SearchBar.tsx`
- Search input with Enter key handler
- Triggers `POST /api/v1/scrape` on submit
- Polls run status, shows "Scraping..." indicator
- Auto-refreshes results when scrape completes
- AI toggle (sparkles icon, default off)

#### `frontend/components/FormattedDescription.tsx`
- Formats plain text job descriptions
- Detects headings, bullet points, paragraphs
- Renders with proper spacing and structure

#### `frontend/lib/api.ts`
- `getJobs()`: Fetch jobs with filters
- `getJob(id)`: Fetch single job details
- `scrapeNow()`: Trigger on-demand scrape
- `getRunStatus(id)`: Poll run status

### Core Library

#### `jobscout/orchestrator.py`
- `run_scrape()`: Main orchestration function
  - Discovery (optional)
  - Provider collection (parallel)
  - Filtering
  - Deduplication
  - Enrichment
  - AI pipeline (optional)
  - Storage

#### `jobscout/providers/base.py`
- `Provider` abstract base class
- `ProviderStats` for tracking errors/collected jobs

#### `jobscout/dedupe.py`
- `DedupeEngine`: Multi-layer deduplication
  - Provider ID matching
  - URL canonicalization
  - Fuzzy matching (title + company)
  - LLM arbitration for uncertain pairs (optional)

---

## API Endpoints

### Public Endpoints

#### `GET /api/v1/jobs`
Query parameters:
- `q`: Search query (title, company, description)
- `location`: Location filter
- `remote`: `remote`, `hybrid`, `onsite`
- `employment`: `full_time`, `contract`, etc.
- `source`: Source filter
- `posted_since`: Days ago
- `min_score`: Minimum AI score (0-100)
- `sort`: `ai_score`, `posted_at`, `first_seen_at`
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 50)

Response:
```json
{
  "jobs": [...],
  "total": 188,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

#### `GET /api/v1/jobs/{job_id}`
Returns full job details including full description text.

#### `POST /api/v1/scrape`
Request body:
```json
{
  "query": "automation engineer",
  "location": "Remote",
  "use_ai": false
}
```

Response:
```json
{
  "status": "queued",
  "run_id": 2,
  "message": "Scrape queued"
}
```

Rate limits:
- 6 requests/hour per IP
- 1 concurrent scrape max

#### `GET /api/v1/runs/{run_id}`
Response:
```json
{
  "run_id": 2,
  "started_at": "2026-01-09T10:43:06Z",
  "finished_at": null,
  "jobs_collected": 192,
  "jobs_new": 19,
  "jobs_updated": 75,
  "jobs_filtered": 23,
  "errors": 0,
  "sources": "remotive, remoteok, arbeitnow, weworkremotely",
  "criteria": {...}
}
```

#### `GET /api/v1/runs/latest`
Returns the most recent run.

#### `GET /api/v1/admin/stats`
Public stats endpoint (no auth required).

### Admin Endpoints

#### `POST /api/v1/admin/run`
Requires `Authorization: Bearer {admin_token}` header.

Request body:
```json
{
  "query": "automation engineer",
  "location": "Remote",
  "use_ai": false
}
```

---

## Database Schema

### `jobs` table (PostgreSQL)

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,              -- MD5 hash of provider_id + source
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
    remote_type TEXT DEFAULT 'unknown',   -- 'remote', 'hybrid', 'onsite', 'unknown'
    employment_types TEXT[] DEFAULT '{}', -- ['full_time', 'contract', ...]
    
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
    
    -- AI fields (nullable)
    ai_score REAL,                        -- 0-100 relevance score
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

CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_company ON jobs(company_normalized);
CREATE INDEX idx_jobs_remote_type ON jobs(remote_type);
CREATE INDEX idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX idx_jobs_first_seen ON jobs(first_seen_at DESC);
CREATE INDEX idx_jobs_ai_score ON jobs(ai_score DESC NULLS LAST);
CREATE INDEX idx_jobs_search ON jobs USING gin(to_tsvector('english', title || ' ' || company || ' ' || COALESCE(description_text, '')));
```

### `runs` table

```sql
CREATE TABLE runs (
    run_id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    criteria JSONB,                       -- Search criteria used
    jobs_collected INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    jobs_filtered INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    sources TEXT,                         -- Comma-separated list
    error_summary TEXT
);

CREATE INDEX idx_runs_started_at ON runs(started_at DESC);
```

### `llm_cache` table (SQLite only, for LLM response caching)

```sql
CREATE TABLE llm_cache (
    key TEXT PRIMARY KEY,                 -- Hash of prompt
    response TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

## Environment Variables

### Backend (`backend/.env` or Fly.io secrets)

```bash
# Database
JOBSCOUT_DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
JOBSCOUT_USE_SQLITE=false
JOBSCOUT_SQLITE_PATH=jobs.db

# CORS (JSON array string)
JOBSCOUT_CORS_ORIGINS='["https://jobscoutai.vercel.app","http://localhost:3000"]'

# Admin
JOBSCOUT_ADMIN_TOKEN=your-long-random-token-here

# Scraper defaults
JOBSCOUT_DEFAULT_SEARCH_QUERY=automation engineer
JOBSCOUT_DEFAULT_LOCATION=Remote
JOBSCOUT_SCRAPE_INTERVAL_HOURS=6

# AI (optional)
JOBSCOUT_OPENAI_API_KEY=sk-...
JOBSCOUT_OPENAI_MODEL=gpt-4o-mini
JOBSCOUT_AI_ENABLED=false
JOBSCOUT_AI_MAX_JOBS=50

# Public scrape guardrails
JOBSCOUT_PUBLIC_SCRAPE_ENABLED=true
JOBSCOUT_PUBLIC_SCRAPE_MAX_CONCURRENT=1
JOBSCOUT_PUBLIC_SCRAPE_RATE_LIMIT_PER_HOUR=6
JOBSCOUT_PUBLIC_SCRAPE_MAX_RESULTS_PER_SOURCE=200
```

### Frontend (`frontend/.env.local` or Vercel env vars)

```bash
NEXT_PUBLIC_API_URL=https://jobscout-api.fly.dev/api/v1
```

---

## Development Workflow

> **Note**: See [Quick Start & Commands](#quick-start--commands) for exact commands.

### Local Setup

See [Quick Start & Commands](#quick-start--commands) section above for step-by-step setup instructions.

**Key points:**
- Backend runs on `http://localhost:8000`
- Frontend runs on `http://localhost:3000`
- For local dev, use SQLite: set `JOBSCOUT_USE_SQLITE=true` in backend `.env`
- SQLite DB created at `JOBSCOUT_SQLITE_PATH` (default: `jobs.db`)

### Testing Changes

1. **Backend API:**
   - Visit `http://localhost:8000/docs` for Swagger UI
   - Test endpoints interactively
   - Check logs for errors

2. **Frontend:**
   - Visit `http://localhost:3000`
   - Test in browser with DevTools open
   - Run `npm run lint` before committing
   - Run `npm run build` to verify production build

3. **CLI (core library):**
   ```bash
   python -m jobscout "test query" --verbose
   ```

### Code Style

- **Python**: Follow PEP 8, use type hints, max line length 100
- **TypeScript**: Use strict mode, prefer functional components
- **Formatting**: No enforced formatter (yet), but be consistent
- **Imports**: Group imports (stdlib, third-party, local)

---

## Common Tasks

### Adding a New Job Provider

1. Create `jobscout/providers/{name}.py`:
   ```python
   from jobscout.providers.base import Provider
   from jobscout.models import NormalizedJob, Criteria
   
   class MyProvider(Provider):
       name = "myprovider"
       
       async def collect(self, fetcher, criteria):
           # Fetch jobs from API/RSS/scraping
           # Return List[NormalizedJob]
           pass
   ```

2. Register in `jobscout/providers/__init__.py`

3. Add to `jobscout/orchestrator.py` provider list

### Fixing Provider Errors

- Check `provider.stats.error_messages` in logs
- Common issues:
  - API endpoint changed
  - HTML structure changed
  - Rate limiting
  - Network timeouts

### Adding a New API Endpoint

1. Create/update `backend/app/api/{name}.py`
2. Add router to `backend/app/main.py`:
   ```python
   from backend.app.api import {name}
   app.include_router({name}.router, prefix=settings.api_prefix)
   ```

### Updating Frontend Components

- Components are in `frontend/components/`
- Use Tailwind CSS for styling
- Follow existing patterns (minimal, clean design)

### Debugging Scrape Issues

1. Check Fly.io logs: `fly logs -a jobscout-api`
2. Check run status: `GET /api/v1/runs/{run_id}`
3. Check provider stats in orchestrator logs
4. Test provider individually in CLI

---

## Deployment

> **Note**: See [Quick Start & Commands](#quick-start--commands) for exact deploy commands.

### Backend (Fly.io)

**Deploy:**
```bash
fly deploy -a jobscout-api
```

**Set secrets (if needed):**
```bash
fly secrets set JOBSCOUT_DATABASE_URL="..." -a jobscout-api
fly secrets set JOBSCOUT_CORS_ORIGINS='["https://jobscoutai.vercel.app"]' -a jobscout-api
fly secrets set JOBSCOUT_ADMIN_TOKEN="..." -a jobscout-api
```

**Check logs:**
```bash
fly logs -a jobscout-api
```

**Important**: 
- Uses `backend/Dockerfile` for build
- Auto-scales based on traffic
- Scheduled scrapes run via APScheduler

### Frontend (Vercel)

**Auto-deploy**: Pushes to `main` branch automatically trigger deployment

**Manual deploy:**
```bash
cd frontend
npx vercel --prod
```

**Environment variables**: Set in Vercel dashboard
- `NEXT_PUBLIC_API_URL=https://jobscout-api.fly.dev/api/v1`

### Database (Supabase)

1. Create project at supabase.com
2. Run SQL schema (see `DEPLOY.md` or `backend/app/storage/postgres.py`)
3. Get connection string from Settings → Database
4. **Use Session pooler connection string** (not Direct) for Fly.io compatibility

---

## Known Issues & TODOs

### Current Issues

1. **Job descriptions formatting**: ✅ Fixed with `FormattedDescription` component
2. **Provider errors**: Some providers (Arbeitnow) may have parsing issues - check logs
3. **CORS**: Ensure all frontend domains are in `JOBSCOUT_CORS_ORIGINS`

### Future Enhancements

1. **Better description parsing**: Use `extract_text_structured()` instead of `strip_html()` to preserve more structure
2. **Email notifications**: Alert users when new jobs match their saved searches
3. **User accounts**: Save favorite jobs, search history
4. **More providers**: Add more job boards (Indeed, LinkedIn, etc.)
5. **Better AI prompts**: Fine-tune ranking/classification prompts
6. **Export features**: CSV/Excel export from UI
7. **Job alerts**: Email/Slack notifications for new matches

### Technical Debt

1. **Error handling**: More graceful degradation when providers fail
2. **Caching**: Add Redis for job list caching
3. **Testing**: Add unit tests for providers, deduplication
4. **Monitoring**: Add Sentry/error tracking
5. **Rate limiting**: More sophisticated rate limiting (per-user, per-query)

---

## Quick Reference

### Key Files to Modify

- **Add provider**: `jobscout/providers/{name}.py`
- **Change API**: `backend/app/api/{name}.py`
- **Update UI**: `frontend/components/{Component}.tsx`
- **Fix scraping**: `jobscout/orchestrator.py`
- **Database changes**: `backend/app/storage/postgres.py`

### Important Functions

- `run_scrape()`: Main orchestration (`jobscout/orchestrator.py`)
- `enqueue_scrape_run()`: Background scrape trigger (`backend/app/worker.py`)
- `upsert_job_from_dict()`: Save job to DB (`backend/app/storage/postgres.py`)
- `DedupeEngine.dedupe()`: Remove duplicates (`jobscout/dedupe.py`)

### Common Commands

```bash
# Backend logs
fly logs -a jobscout-api

# Test API
curl https://jobscout-api.fly.dev/api/v1/jobs?q=engineer

# Trigger scrape
curl -X POST https://jobscout-api.fly.dev/api/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"query":"engineer","location":"Remote"}'

# Local CLI scrape
python -m jobscout "engineer" --verbose
```

---

## Contact & Resources

- **Repository**: https://github.com/binary-exe/jobscoutai
- **Backend API**: https://jobscout-api.fly.dev/docs
- **Frontend**: https://jobscoutai.vercel.app
- **Deployment Guide**: See `DEPLOY.md`

---

**Last Updated**: 2026-01-09
**Version**: 1.0.0
