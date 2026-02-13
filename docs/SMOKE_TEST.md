# Smoke test checklist (post-deploy)

Run through this after deploying backend + frontend + extension to confirm the upgrade (Trust v2, Tracker, Extension, Premium AI).

## Prerequisites

- Backend: `https://jobscout-api.fly.dev` (or your API URL)
- Frontend: logged-in user (magic link or OAuth)
- Extension: loaded unpacked from `extension/`, **Connect** done once with app tab open

---

## 1. Apply Workspace

- [ ] Open **Apply** in the app.
- [ ] **Resume**: Upload a PDF/DOCX or paste text; confirm it appears.
- [ ] **Job**: Paste a job URL or description → **Parse**. Parsed job shows title, company, description.
- [ ] **Trust Report**: Click **Generate Trust Report**. Within a few seconds you see:
  - Overall trust score, confidence, “Last verified …”
  - Scam / Ghost / Staleness sections with “Why we flagged this” reasons where applicable.
  - **Next steps** section with actionable items.
  - Community block with “This was accurate” / “Inaccurate” / “Report scam” / “Report ghost” (submit once to confirm).
- [ ] **Apply Pack**: With resume + job, click **Generate Apply Pack**. Tailored summary, bullets, cover note (if any), ATS checklist appear.
- [ ] **Interview Coach**: In “Interview Coach”, click **Generate interview prep**. Questions + rubric appear (or “quota/not enabled” message if Premium AI off).
- [ ] **Tone & templates**: Choose type (Cover letter / Follow-up email) and tone → **Generate**. Content appears; **Copy** works.
- [ ] **Start Tracking**: From Apply Pack, click **Start Tracking**. You are taken or linked to Application History.

---

## 2. Application History (Tracker)

- [ ] Open **Apply → History** (or link from Apply Pack).
- [ ] **Kanban**: Columns show Saved / Applied / Interview / Offer / Rejected. At least one Apply Pack appears under Saved or Applied.
- [ ] **Card**: Open a tracked application card. Change **status** (e.g. Applied → Interview); change saves.
- [ ] **Reminder**: Set **Reminder** date/time; blur to save. Click **ICS** and confirm download.
- [ ] **Notes**: Type in **Notes**, blur; confirm “Saving…” then persistence after refresh.
- [ ] **Contact**: Fill **Contact** (email, LinkedIn URL, phone); blur; confirm save.
- [ ] **Feedback**: Click **Feedback**, choose type (e.g. Rejection), add text and reasons, submit. Card shows feedback summary.
- [ ] **Insights**: If you have feedback, “Outcomes” and “Most common rejection reasons” cards appear above the Kanban.

---

## 3. Extension

- [ ] On a **job detail page** (e.g. LinkedIn job, Indeed listing), open extension popup.
- [ ] Click **Save job**. Message: “Saved. Open Apply Workspace …”.
- [ ] Click **Open Apply Workspace →**. New tab opens Apply with `?job_target_id=...`; job loads and Trust Report runs (or starts).
- [ ] In extension **Settings**, API base = `https://jobscout-api.fly.dev/api/v1` (or your API), App base = your frontend URL.

---

## 4. Public API (no auth)

- [ ] `GET /api/v1/jobs?page_size=1` returns `{ "jobs": [...], "total": N }`.
- [ ] `GET /api/v1/runs/latest` returns a run object or empty.
- [ ] Optional: run `scripts/smoke_api.sh` or `python scripts/smoke_api.py` with `API_BASE=https://jobscout-api.fly.dev/api/v1` (see `scripts/README.md`). Backend must be running.

---

## 5. Metrics (backend)

- [ ] If analytics are enabled, events are stored in `analytics_events`. Run `scripts/metrics_query.sql` in Supabase SQL Editor to see daily rollups (activation, trust, tracker events). See script header for details.

---

## Pass criteria

- No console errors on Apply and History pages during the above.
- Trust Report and Apply Pack generate without 5xx.
- Extension save and “Open Apply Workspace” work; Apply page shows the job and Trust Report.
- Tracker status/notes/contact/reminder/ICS and feedback persist and display correctly.
