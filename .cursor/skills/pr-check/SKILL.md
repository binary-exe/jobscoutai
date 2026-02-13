---
name: pr-check
description: Runs a PR readiness workflow (git diff review + lint/typecheck/build checks) and writes a PR summary with a test plan. Use when preparing a pull request, responding to “run checks”, “before we merge”, CI failures, or when asked to draft a PR description.
---

# PR Check (run checks + write PR summary)

## Output contract (don’t skip)

This skill produces:

1. **Check results**: what ran, pass/fail, and what was fixed
2. **PR description**: summary + risks + test plan (copy/paste ready)

Do **not** write the PR summary until the relevant checks are green (or you’ve explicitly documented why a check can’t run).

## Step 1: Snapshot the change (scope correctly)

Run and skim:

- `git status`
- `git diff`
- `git log -10 --oneline`

Then classify the PR scope:

- **Frontend scope**: anything under `frontend/`
- **Backend scope**: anything under `backend/`
- **Core scope**: anything under `jobscout/`
- **DB scope**: `backend/app/storage/*.sql` or schema-related changes
- **Config scope**: `backend/app/core/config.py`, `backend/env.sample`, `frontend/env.sample`, deployment config

## Step 2: Run the check matrix (only what applies)

### Always (any PR)

- Confirm you didn’t accidentally include secrets (`.env`, keys, tokens).
- Ensure changes are backwards compatible (no endpoint removals, no column drops).

### Frontend checks (when `frontend/` changed)

```bash
cd frontend
npm ci || npm install
npm run lint
npm run build
```

**Gate**: if `npm run build` fails, fix build issues before anything else.

### Python checks (when `backend/` or `jobscout/` changed)

```bash
python -m compileall backend jobscout
```

If API code changed, also smoke-test locally:

- start backend
- open `/docs`
- exercise affected endpoints

### DB/schema checks (when SQL/storage changed)

- Confirm migrations are **idempotent** (`IF NOT EXISTS`, safe re-runs).
- Confirm schema changes are **additive** (no drop/rename/type changes without plan).
- Confirm `backend/app/storage/postgres.py:init_schema()` will execute the migration (or it’s explicitly optional/best-effort).

## Step 3: If checks fail (tight feedback loop)

- Fix the issue.
- Rerun the **smallest** set of failing checks (don’t rerun everything blindly).
- If you introduced new config or changed env var requirements:
  - update `backend/env.sample` and/or `frontend/env.sample`

## Step 4: Write the PR summary (copy/paste template)

Use this shape:

```markdown
## Summary
- ...
- ...

## Why
- ...

## Changes
- **Frontend**: ...
- **Backend**: ...
- **Core (`jobscout/`)**: ...
- **DB/Storage**: ...

## Risk / rollout notes
- ...

## Test plan
- [ ] `frontend`: `npm run lint` (if frontend changed)
- [ ] `frontend`: `npm run build` (if frontend changed)
- [ ] `python`: `python -m compileall backend jobscout` (if python changed)
- [ ] Manual: `/docs` exercised: ...
```

## Debug notes format (when something fails)

When a check fails, capture:

- command that failed
- the **first** relevant error line(s)
- root cause (1–2 sentences)
- fix (what changed)
