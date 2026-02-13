---
name: qa
description: QA workflow for JobScout (manual regression checklist for Next.js + FastAPI, API contract safety, deploy smoke tests). Use when verifying changes, triaging bugs, writing test plans, or validating a PR before merge/deploy.
---

# QA (manual-first, high signal)

## Expectations

- There is **no formal automated test suite**; QA is primarily:
  - `npm run lint`, `npm run build`
  - backend smoke tests via `/docs` and targeted curls
  - UI regression checks in the browser

## Core regression checklist (must run for most PRs)

### Frontend

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- Home page loads, search works, results render
- Job detail page loads and description renders
- Auth flows don’t crash when Supabase is not configured (build/SSR safe)

### Backend

- `python -m compileall backend jobscout`
- `/health` returns 200
- `/docs` loads
- For changed endpoints: validate request/response shape stays compatible

### Scrape/run flow (when affected)

- Trigger a run (admin/public depending on settings)
- Check run status endpoint updates and completes
- Confirm jobs list updates / filters still work

## Regression matrix (run what matches the change)

### Public browse (always if frontend changed)

- Search query updates URL params (no full reload required)
- Filters change results and pagination behaves
- Empty state renders when no jobs found

### Job detail page (if `frontend/app/job/[id]` or job API changed)

- Page renders with structured data script and no runtime warnings
- “Apply Now” opens external link
- “Open in Apply Workspace” routes to `/apply?jobId=...`

### Auth flows (if auth or Apply Workspace changed)

- Login page:
  - sending magic link shows “check your email” state
  - helpful error when Supabase isn’t configured
- Callback page:
  - handles both `code` and “no code but session exists” flows
- Logged-in nav:
  - Header shows email and dropdown; logout works

### Apply Workspace (if `frontend/app/apply` or `/apply` backend changed)

- Auth guard redirects to `/login?next=...` when logged out
- Import-from-JobScout by `jobId` happens at most once (no infinite loops)
- Parse job by URL and by pasted text
- Generate trust report and submit trust feedback
- Generate apply pack (rate limited behavior is clear)

### Payments / upgrade (if Paddle endpoints or account page changed)

- Account page loads quota
- Upgrade flow requests checkout URL and navigates to Paddle

### Analytics (if metrics/analytics changed)

- Client-side tracking doesn’t crash when PostHog env vars are missing
- Server-side capture endpoint returns 204 and doesn’t block UI

## Bug triage format

When reporting or fixing a bug, capture:

- **Repro steps** (minimal)
- **Expected vs actual**
- **Scope** (frontend/backend/both)
- **Root cause** (one paragraph)
- **Fix** (what changed, why safe)

## Additional resources

- Deeper QA runbooks: [reference.md](reference.md)
- Copy/paste bug template + verification note: [examples.md](examples.md)
