# JobScout

**AI-powered job aggregator for remote work.** Find automation, engineering, and tech jobs from dozens of sources, ranked by relevance using GPT-4.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/binary-exe/jobscoutai)

---

## ✨ Features

- **Multi-source aggregation**: 25+ built-in providers (Remotive, RemoteOK, WeWorkRemotely, Jobicy, DevITjobs UK, SerpAPI Google Jobs, TheMuse, Findwork, Reed, Adzuna, USAJobs, and more), plus discovery for Greenhouse, Lever, Ashby, Recruitee
- **Intelligent discovery**: Auto-discovers company job boards via search (optional)
- **AI ranking**: GPT-4 scores jobs by relevance to your search
- **Smart deduplication**: Multi-layer fuzzy matching with LLM arbitration
- **Rich extraction**: Company info, salaries, tech stacks, and contact emails
- **Apply Workspace**: AI-tailored cover letters, trust reports, and application tracking (auth via Supabase)
- **Beautiful UI**: Notion/Apple-inspired minimal design
- **Shareable URLs**: Filter state encoded in URL for bookmarking
- **Scheduled scrapes**: Rotation over 60–120 job titles, configurable queries per run
- **Cost-optimized**: Caching, batching, and configurable limits

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                    (Next.js + Tailwind)                      │
│                      Vercel (Free)                           │
└──────────────────────────┬───────────────────────────────────┘
                           │ API
┌──────────────────────────▼───────────────────────────────────┐
│                         Backend                              │
│                    (FastAPI + APScheduler)                   │
│                    Fly.io (~$0-5/mo)                         │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│    Supabase     │ │   OpenAI    │ │   Job Sources   │
│    Postgres     │ │  (Optional) │ │   (APIs/Sites)  │
│    (Free)       │ │ gpt-4o-mini │ │                 │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

---

## 🚀 Quick Start

### Local Development

```bash
# Clone the repo
git clone https://github.com/binary-exe/jobscoutai.git
cd jobscoutai

# Backend (from repo root)
cd backend
pip install -r requirements.txt
pip install -e ../   # Install jobscout package in dev mode
cp env.sample .env   # Edit with your settings
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd frontend
npm install
cp env.sample .env.local  # Set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm run dev
```

Visit `http://localhost:3000` for the UI, `http://localhost:8000/docs` for API docs.

### Run a Scrape (CLI)

```bash
# Basic scrape
python -m jobscout "automation engineer" --remote-only

# With AI features
python -m jobscout "automation engineer" --ai --ai-model gpt-4o-mini

# Full options
python -m jobscout "data engineer" \
  --location "Remote" \
  --remote-only \
  --max-results 100 \
  --ai \
  --ai-max-jobs 50 \
  --output jobs.xlsx \
  --verbose
```

---

## 🌐 Deployment

See [DEPLOY.md](./DEPLOY.md) for full deployment instructions.

**Quick deploy:**

1. **Database**: Create free Supabase project, run schema SQL (use **Session pooler** connection string)
2. **Backend**: From repo root, `fly deploy -a jobscout-api`; set secrets (e.g. `JOBSCOUT_DATABASE_URL`, `JOBSCOUT_ADMIN_TOKEN`, provider API keys) via `fly secrets set`
3. **Frontend**: From **repo root**, `npx vercel --prod` (Vercel config is at root). Production: [jobiqueue.com](https://jobiqueue.com)
4. **Scrapes**: APScheduler on Fly.io runs scheduled scrapes (preset `tech_plus_120` or `tech_core_60`; rotation over 60–120 titles every 6 hours by default)

**Estimated cost: $0-5/month**

---

## 📁 Project Structure

```
jobscout/
├── frontend/               # Next.js web app
│   ├── app/               # Pages and layouts
│   ├── components/        # React components
│   └── lib/               # API client, utilities
│
├── backend/               # FastAPI service
│   └── app/
│       ├── api/           # REST endpoints
│       ├── core/          # Config, database
│       ├── storage/       # Postgres adapter
│       └── worker.py      # Scrape runner
│
├── jobscout/              # Core scraping library
│   ├── providers/         # Job source providers
│   ├── fetchers/          # HTTP/browser fetching
│   ├── extract/           # HTML/JSON extraction
│   ├── llm/               # AI agents
│   ├── storage/           # SQLite adapter
│   ├── cli.py             # Command-line interface
│   ├── orchestrator.py    # Main scrape pipeline
│   ├── models.py          # Data models
│   └── dedupe.py          # Deduplication engine
│
├── pyproject.toml         # Python package config
├── README.md
├── DEPLOY.md
└── AGENTS.md              # Development guide for AI agents
```

---

## 🤖 AI Features

When enabled (`--ai` flag or `JOBSCOUT_AI_ENABLED=true`), the AI pipeline:

1. **Classification**: Infers remote type, employment type, seniority
2. **Company Research**: Extracts company domain and summary
3. **Enrichment**: Generates job summary, requirements, tech stack
4. **Ranking**: Scores jobs 0-100 based on search relevance
5. **Alerts**: Flags suspicious postings (vague salary, crypto scams, etc.)
6. **Dedupe Arbitration**: Resolves ambiguous duplicate pairs

**Cost controls:**

- Default model: `gpt-4o-mini` (~$0.15/1M tokens)
- `ai_max_jobs`: Process top N jobs only
- Response caching in SQLite
- Batched API calls

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JOBSCOUT_DATABASE_URL` | Postgres connection string (use Supabase Session pooler) | - |
| `JOBSCOUT_USE_SQLITE` | Use SQLite instead of Postgres | `false` |
| `JOBSCOUT_ADMIN_TOKEN` | Token for `POST /admin/run` | - |
| `JOBSCOUT_ENABLED_PROVIDERS` | Comma-separated allowlist; omit for all 25 providers | (all) |
| `JOBSCOUT_OPENAI_API_KEY` | OpenAI API key (optional, for AI ranking/enrichment) | - |
| `JOBSCOUT_AI_ENABLED` | Enable AI features | `true` |
| `JOBSCOUT_AI_MAX_JOBS` | Max jobs for AI pipeline | `50` |
| `JOBSCOUT_SCRAPE_INTERVAL_HOURS` | Scheduled scrape interval | `6` |
| `JOBSCOUT_SCHEDULED_QUERIES_PRESET` | Preset: `tech_core_60` or `tech_plus_120` | `tech_plus_120` |
| `JOBSCOUT_PUBLIC_SCRAPE_ENABLED` | Allow public `POST /scrape` (rate-limited) | `false` |

Full list and provider-specific keys (SerpAPI, Adzuna, Findwork, USAJobs, Reed, etc.) are in `backend/env.sample`.

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/jobs` | List jobs with filters |
| `GET` | `/api/v1/jobs/{id}` | Get job details |
| `GET` | `/api/v1/admin/stats` | System statistics |
| `POST` | `/api/v1/admin/run` | Trigger scrape (auth required) |

**Example:**

```bash
# Search jobs
curl "https://jobscout-api.fly.dev/api/v1/jobs?q=python&remote=remote&page=1"

# Get stats
curl "https://jobscout-api.fly.dev/api/v1/admin/stats"

# Trigger on-demand scrape (public endpoint, rate-limited)
curl -X POST "https://jobscout-api.fly.dev/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -d '{"query": "automation engineer", "location": "Remote", "use_ai": false}'

# Trigger admin scrape (requires admin token)
curl -X POST "https://jobscout-api.fly.dev/api/v1/admin/run" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "automation engineer", "location": "Remote", "use_ai": true}'
```

---

## 🎨 Frontend

The UI is built with:

- **Next.js 14** (App Router, Server Components)
- **Tailwind CSS** with custom design system
- **Lucide icons**
- **Radix UI primitives**

Features:

- Server-side rendering for SEO
- URL-encoded filters for sharing
- Dark mode support
- Responsive design
- Skeleton loading states

---

## 📈 Data Sources

**No API key required** (work out of the box):

| Source | Type |
|--------|------|
| Remotive, RemoteOK, Arbeitnow, WeWorkRemotely, WorkingNomads | API / RSS |
| Remoteco, JustRemote, Jobicy, DevITjobs UK | RSS / feeds |
| Wellfound, Stack Overflow, Indeed, FlexJobs | RSS (some may 403 from server IPs) |
| TheMuse | API (optional key for richer results) |
| Greenhouse, Lever, Ashby, Recruitee, Schema.org | Discovery or scraping |

**API key (or app id/key) required** — set in Fly secrets or `.env`; see `backend/env.sample`:

| Provider | Env vars |
|----------|----------|
| SerpAPI Google Jobs | `JOBSCOUT_SERPAPI_API_KEY` |
| Careerjet | `JOBSCOUT_CAREERJET_API_KEY` |
| Adzuna | `JOBSCOUT_ADZUNA_APP_ID`, `JOBSCOUT_ADZUNA_APP_KEY` |
| Findwork | `JOBSCOUT_FINDWORK_API_KEY` |
| USAJobs | `JOBSCOUT_USAJOBS_API_KEY`, `JOBSCOUT_USAJOBS_USER_AGENT` |
| Reed | `JOBSCOUT_REED_API_KEY` |
| Jobs2Careers, WhatJobs, Juju | Respective `JOBSCOUT_*_API_KEY` |
| Arbeitsamt | `JOBSCOUT_ARBEITSAMT_CLIENT_ID`, `JOBSCOUT_ARBEITSAMT_CLIENT_SECRET` |

Default: all built-in providers are enabled; those without keys simply return 0 jobs until configured.

---

## 🔒 Privacy

- **Public job browse**: No account required; jobs are public data from company sites. No personal data is collected for browsing.
- **Apply Workspace and Second Brain (KB)**: Require sign-in (Supabase). Resumes, job targets, apply packs, and KB documents are stored in Supabase Postgres and scoped to your account. AI processing (when enabled) may send job or document text to OpenAI for ranking, cover letters, or KB answers.

---

## 📄 License

MIT License. See [LICENSE](./LICENSE) for details.

---

## 🙏 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

For major changes, open an issue first to discuss.

---

## 🐛 Issues

Found a bug? [Open an issue](https://github.com/binary-exe/jobscoutai/issues).

---

Built with ❤️ for remote workers everywhere.
