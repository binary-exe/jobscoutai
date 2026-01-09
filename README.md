# JobScout

**AI-powered job aggregator for remote work.** Find automation, engineering, and tech jobs from dozens of sources, ranked by relevance using GPT-4.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/yourusername/jobscout)

---

## ✨ Features

- **Multi-source aggregation**: Scrapes Remotive, RemoteOK, WeWorkRemotely, Greenhouse, Lever, Ashby, Recruitee, and more
- **Intelligent discovery**: Auto-discovers company job boards via search
- **AI ranking**: GPT-4 scores jobs by relevance to your search
- **Smart deduplication**: Multi-layer fuzzy matching with LLM arbitration
- **Rich extraction**: Company info, salaries, tech stacks, and contact emails
- **Beautiful UI**: Notion/Apple-inspired minimal design
- **Shareable URLs**: Filter state encoded in URL for bookmarking
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
git clone https://github.com/yourusername/jobscout.git
cd jobscout

# Backend
cd backend
pip install -r requirements.txt
cp env.sample .env  # Edit with your settings
uvicorn backend.app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
cp env.sample .env.local  # Edit with API URL
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

1. **Database**: Create free Supabase project, run schema SQL
2. **Backend**: Deploy to Fly.io with `fly deploy`
3. **Frontend**: Deploy to Vercel with `npx vercel --prod`
4. **Scrapes**: Set up GitHub Actions cron or use built-in scheduler

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
├── providers/             # Job source providers
├── fetchers/              # HTTP/browser fetching
├── extract/               # HTML/JSON extraction
├── llm/                   # AI agents
├── storage/               # SQLite adapter
│
├── cli.py                 # Command-line interface
├── orchestrator.py        # Main scrape pipeline
├── models.py              # Data models
└── dedupe.py              # Deduplication engine
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
| `JOBSCOUT_DATABASE_URL` | Postgres connection string | - |
| `JOBSCOUT_USE_SQLITE` | Use SQLite instead | `false` |
| `JOBSCOUT_ADMIN_TOKEN` | Token for `/admin/run` | - |
| `JOBSCOUT_OPENAI_API_KEY` | OpenAI API key | - |
| `JOBSCOUT_AI_ENABLED` | Enable AI features | `false` |
| `JOBSCOUT_AI_MAX_JOBS` | Max jobs for AI | `50` |
| `JOBSCOUT_SCRAPE_INTERVAL_HOURS` | Auto-scrape interval | `6` |

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
curl "https://api.example.com/api/v1/jobs?q=python&remote=remote&page=1"

# Get stats
curl "https://api.example.com/api/v1/admin/stats"

# Trigger scrape (requires admin token)
curl -X POST "https://api.example.com/api/v1/admin/run" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "automation engineer", "use_ai": true}'
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

| Source | Type | Notes |
|--------|------|-------|
| Remotive | API | No auth required |
| RemoteOK | API | No auth required |
| Arbeitnow | API | No auth required |
| WeWorkRemotely | RSS | No auth required |
| Greenhouse | API | Discovered via search |
| Lever | API | Discovered via search |
| Ashby | API | Discovered via search |
| Recruitee | API | Discovered via search |
| Schema.org | Scraping | Generic job sites |

---

## 🔒 Privacy

- No user accounts or tracking
- Jobs are public data from company sites
- AI processing sends job text to OpenAI (when enabled)
- No personal data collected

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

Found a bug? [Open an issue](https://github.com/yourusername/jobscout/issues).

---

Built with ❤️ for remote workers everywhere.
