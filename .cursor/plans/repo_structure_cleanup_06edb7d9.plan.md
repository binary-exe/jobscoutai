---
name: Repo structure cleanup
overview: Convert the current repo into a proper Python package layout (so `jobscout.*` imports always work), fix the frontend’s missing Next.js TS bootstrap file, and clean up committed build artifacts like `node_modules`.
todos:
  - id: pkg-move
    content: Create `jobscout/` package directory and move core Python modules + subpackages (`providers/`, `fetchers/`, `extract/`, `storage/`, `llm/`) under it.
    status: completed
  - id: pyproject
    content: Add root `pyproject.toml` for installable package + `jobscout` console script entrypoint.
    status: completed
  - id: backend-imports
    content: Remove `sys.path` hack in `backend/app/worker.py` and update backend/Dockerfile to install and import the `jobscout` package.
    status: completed
  - id: frontend-nextenv
    content: Add `frontend/next-env.d.ts` and ensure TS config works.
    status: completed
  - id: repo-hygiene
    content: Remove committed `frontend/node_modules/` and add `.gitignore` for node/python artifacts and local env/db/cache files.
    status: completed
---

# Update JobScout file structure

## Why change

- The repo currently has Python modules at the repo root (e.g. `models.py`, `orchestrator.py`) but code imports them as `jobscout.*`. That only works if the **parent** of the repo is on `PYTHONPATH`, which is fragile for local dev, Docker, and CI.
- The frontend is missing `next-env.d.ts` (standard Next.js + TypeScript bootstrap).
- `frontend/node_modules/` appears committed, which should be removed and ignored.

## Target structure (after)

```text
jobscout/
  jobscout/
    __init__.py
    __main__.py
    cli.py
    models.py
    orchestrator.py
    dedupe.py
    providers/
    fetchers/
    extract/
    storage/
    llm/
  backend/
    app/
    ...
  frontend/
    app/
    ...
  pyproject.toml
  README.md
  DEPLOY.md
  .gitignore
```

## Implementation steps

- **Create real package dir**: add `jobscout/` folder at repo root and move all core Python modules into it:
  - Move root files into `jobscout/`: `__init__.py`, `__main__.py`, `cli.py`, `models.py`, `orchestrator.py`, `dedupe.py`.
  - Move directories into `jobscout/`: `providers/`, `fetchers/`, `extract/`, `storage/`, `llm/`.
- **Packaging**: add root `pyproject.toml` so `pip install -e .` works and `python -m jobscout` works from the repo root.
  - Define an entrypoint script (`jobscout`) that maps to `jobscout.cli:main`.
- **Backend import cleanup**: remove the `sys.path.insert(...)` hack in [`backend/app/worker.py`](backend/app/worker.py) and rely on the installed `jobscout` package.
- **Dockerfile update**: update [`backend/Dockerfile`](backend/Dockerfile) to copy/install the `jobscout/` package (e.g. `pip install .` or `pip install -e .`) instead of copying individual root modules.
- **Frontend fix**: add `frontend/next-env.d.ts` (generated standard Next.js content).
- **Repository hygiene**:
  - Remove committed `frontend/node_modules/`.
  - Add root `.gitignore` to ignore `frontend/node_modules/`, `.next/`, Python caches, `.jobscout_cache/`, `*.db`, and local env files.

## Files most impacted

- Core package moves: `models.py`, `orchestrator.py`, `dedupe.py`, `providers/`, `fetchers/`, `extract/`, `storage/`, `llm/` → all under `jobscout/`
- Backend adjustments: [`backend/app/worker.py`](backend/app/worker.py), [`backend/Dockerfile`](backend/Dockerfile)
- Frontend: `frontend/next-env.d.ts`
- Root: `pyproject.toml`, `.gitignore`

## Validation (manual)

- From repo root:
  - `python -m jobscout --help`
  - Backend starts: `uvicorn backend.app.main:app --reload`
  - Frontend starts: `npm run dev` inside `frontend/`