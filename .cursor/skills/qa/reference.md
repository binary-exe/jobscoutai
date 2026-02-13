# QA Reference (JobScout)

## Quick smoke commands

- Frontend: `cd frontend && npm run lint && npm run build`
- Python: `python -m compileall backend jobscout`

## Manual smoke endpoints

- Backend:
  - `/health`
  - `/docs`
- Core API:
  - `GET /api/v1/jobs?q=test`
  - `GET /api/v1/jobs/{id}` (pick an id from list)
- Runs:
  - `POST /api/v1/admin/run` (auth required)
  - `GET /api/v1/runs/{run_id}`

## QA notes for “best-effort” behaviors

- Schema init and optional migrations are best-effort; verify failures don’t crash the service.
- Public scrape endpoint is guarded and may be disabled by config; verify the intended behavior (404 vs queued).
