---
name: Apply Workspace integration
overview: Add a one-click Job→Apply Workspace import flow, generate a full ATS-friendly tailored resume DOCX plus a highly personalized cover letter, and expose download/copy actions in the Apply Workspace UI.
todos:
  - id: backend-job-import
    content: Add POST /apply/job/import endpoint in backend/app/api/apply.py that creates job_targets directly from JobScout job data (store extras in extracted_json).
    status: completed
  - id: frontend-open-in-apply
    content: Add “Open in Apply Workspace” button on frontend/app/job/[id]/page.tsx linking to /apply?jobId=... and implement Apply page auto-import flow.
    status: completed
  - id: cover-letter-personalization
    content: Enhance backend/app/services/apply_pack_generator.py to generate a longer, more personalized cover letter using job title/company/description and available company summary/website data.
    status: completed
  - id: resume-docx-full
    content: Improve backend/app/services/docx_generator.py so resume export generates a complete ATS-friendly tailored resume DOCX (rebuilt from resume text + tailored content).
    status: completed
  - id: apply-ui-actions
    content: Update frontend/app/apply/page.tsx to add Copy Cover Letter + separate resume/cover DOCX downloads via exportApplyPackDocx.
    status: completed
---

# Apply Workspace: one-click import + tailored resume DOCX + cover letter actions

## Goals

- Add an **“Open in Apply Workspace”** button on each job detail page.
- When entering Apply Workspace from a job, **auto-import all job details** (title/company/location/URLs/description/AI insights) into a `job_target` without re-scraping external URLs.
- Generate an Apply Pack whose outputs include:
  - **Hyper-personalized cover letter** (AI when configured).
  - **Complete ATS-friendly tailored resume DOCX** (rebuilt from extracted resume text + tailored content).
- In Apply Workspace, add user actions:
  - **Download tailored resume DOCX**.
  - **Download cover letter DOCX**.
  - **Copy cover letter**.

## Current state (what we’ll build on)

- Frontend Apply Workspace already exists at `/apply` (`frontend/app/apply/page.tsx`) and uses `frontend/lib/apply-api.ts`.
- Backend Apply API exists under `/api/v1/apply/*` (`backend/app/api/apply.py`), including:
  - `POST /apply/job/parse`
  - `POST /apply/pack/generate`
  - `GET /apply/pack/{id}/export?format=resume|cover|combined` (DOCX)

## Proposed UX / data flow

```mermaid
flowchart TD
  JobDetailPage -->|click OpenInApplyWorkspace| ApplyWorkspacePage
  ApplyWorkspacePage -->|GET /jobs/{jobId}| JobScoutAPI
  ApplyWorkspacePage -->|POST /apply/job/import| ApplyAPI
  ApplyAPI -->|INSERT job_targets| Postgres
  ApplyWorkspacePage -->|upload resume file| ApplyAPI
  ApplyWorkspacePage -->|POST /apply/pack/generate| ApplyAPI
  ApplyAPI -->|AI when configured| LLM
  ApplyWorkspacePage -->|GET /apply/pack/{id}/export?format=resume| ApplyAPI
  ApplyWorkspacePage -->|GET /apply/pack/{id}/export?format=cover| ApplyAPI
```

## Backend changes

### 1) Add an import endpoint that accepts JobScout job data directly

- **Add** `POST /api/v1/apply/job/import` in [`backend/app/api/apply.py`](backend/app/api/apply.py).
- New request model (example fields):
  - `job_id` (JobScout ID, optional but useful for auditing)
  - `job_url`, `apply_url`
  - `title`, `company`, `location_raw`/`location`, `remote_type`, `employment_types`, `salary_min/max/currency`
  - `description_text`
  - optional: `company_website`, `linkedin_url`, `ai_company_summary`, `ai_summary`, `ai_requirements`, `ai_tech_stack`
- Implementation: create a `job_target` via `apply_storage.create_job_target(...)` **without** calling `job_parser.parse_job_url`.
  - Store extra JobScout-only fields into `job_targets.extracted_json` (already JSONB) to avoid schema migrations.

### 2) Improve cover letter generation to be “hyper personalized”

- Update [`backend/app/services/apply_pack_generator.py`](backend/app/services/apply_pack_generator.py):
  - Pass **job title, company name, job description**, plus any `company_website`/`ai_company_summary` found in `job_target.extracted_json`.
  - Replace the current 2–3 sentence cover note prompt with a longer structure (e.g., 3–5 short paragraphs) that explicitly:
    - Mirrors role expectations.
    - References inferred company values/culture.
    - Uses 2–3 relevant achievements from resume bullets.
  - Keep current policy: **use AI if OpenAI key is configured; otherwise fall back**.

### 3) Make resume DOCX export produce a complete “tailored resume”

- Enhance [`backend/app/services/docx_generator.py`](backend/app/services/docx_generator.py) and the existing export endpoint:
  - `format=resume` should generate an ATS-friendly full resume DOCX:
    - Start with tailored summary.
    - Add tailored achievements.
    - Then render the **full resume text** into structured sections (simple heuristics: headings like EXPERIENCE/EDUCATION/SKILLS) instead of dumping “reference paragraphs”.
  - This aligns with your choice: **rebuild_docx** (not preserving original formatting).

## Frontend changes

### 1) Add “Open in Apply Workspace” button on job detail

- Update `[frontend/app/job/[id]/page.tsx](frontend/app/job/[id]/page.tsx)`:
  - Add a secondary button near “Apply Now” to navigate to `/apply?jobId={job.job_id}`.

### 2) Auto-import job into Apply Workspace

- Update [`frontend/app/apply/page.tsx`](frontend/app/apply/page.tsx):
  - On mount, read `jobId` from query params.
  - Fetch job details via JobScout API (reuse [`frontend/lib/api.ts`](frontend/lib/api.ts) or add a small client-safe helper).
  - Call new `importJobFromJobScout(...)` API helper to create a `job_target`.
  - Set `parsedJob` state from the response and auto-trigger trust report.

### 3) Add cover letter copy + separate downloads

- Update [`frontend/app/apply/page.tsx`](frontend/app/apply/page.tsx):
  - Add “Copy Cover Letter” button (uses `navigator.clipboard.writeText(applyPack.cover_note)`).
  - Add separate download buttons calling existing export endpoint:
    - `exportApplyPackDocx(applyPackId, 'resume')`
    - `exportApplyPackDocx(applyPackId, 'cover')`
  - Keep existing combined DOCX export.

### 4) Add API client helper

- Update [`frontend/lib/apply-api.ts`](frontend/lib/apply-api.ts):
  - Add `importJobFromJobScout(job: JobDetail): Promise<ParsedJob>` hitting `POST /apply/job/import`.

## Verification (runtime)

- From a job detail page:
  - Click “Open in Apply Workspace” → Apply page loads with job details populated (no manual paste).
- Upload resume (PDF/DOCX): resume text extracted.
- Generate Apply Pack:
  - Cover letter length/structure reflects role + company alignment.
- Download:
  - Resume DOCX exports as a full resume (not just a short section).
  - Cover letter DOCX exports.
  - Copy cover letter copies full text.

## Notes / constraints

- **PDF download**: per your selection, we’ll ship **DOCX-only** for now (no server PDF generation).
- **No schema migrations initially**: we’ll store JobScout extras in `job_targets.extracted_json`.