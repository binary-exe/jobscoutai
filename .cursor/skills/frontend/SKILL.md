---
name: frontend
description: JobScout frontend workflow and conventions (Next.js App Router + Tailwind + Radix, API client usage, auth patterns). Use when changing pages/components in frontend/, fixing Next.js build/lint issues, or implementing UI features.
---

# Frontend (Next.js 14) conventions

## Ground rules (hard constraints)

- **App Router** pages live in `frontend/app/`.
- Prefer **small, composable components** under `frontend/components/`.
- Use **Tailwind** for styling; keep class lists readable (extract components when needed).
- Keep **networking centralized** in `frontend/lib/api.ts` (public) and `frontend/lib/apply-api.ts` (auth-required).
- **Build/SSR safety** is mandatory: code must not crash when env vars (Supabase/analytics) are missing.

## Local workflow

```bash
cd frontend
npm install
npm run dev
```

Before finishing a change:

```bash
npm run lint
npm run build
```

## Server vs client components (don’t guess)

- App Router components are **server components by default**.
- If you use hooks (`useState`, `useEffect`), event handlers, `window`, or `localStorage`, you must add `"use client"` at the top.
- Keep client-only logic in client components; pass data via props.

## Data fetching & caching (match existing patterns)

- Public data calls live in `frontend/lib/api.ts`.
  - `getJobs()` uses `fetch(..., { next: { revalidate: 60 } })`
  - `getRun()` uses `fetch(..., { cache: 'no-store' })` for live polling
- Don’t invent new fetch patterns unless necessary; extend the existing functions/types first.

## Auth (Supabase) — build-safe by design

- Supabase client is provided by `frontend/lib/supabase.ts`.
- The client is **lazy** and returns safe defaults at build time when env vars are missing.
- Any auth UI must handle “Supabase not configured” gracefully (don’t crash SSR/build).
- For authenticated backend endpoints (Apply Workspace), use `frontend/lib/apply-api.ts` so the bearer token is always attached.

## Analytics (PostHog + server-side capture)

- Analytics init must run **client-side only** (see `frontend/lib/analytics.ts`).
- If analytics env vars are missing, analytics must silently disable (no crashes).
- Use `trackEvent(...)` and the existing helpers; don’t scatter ad-hoc analytics calls.

## UX expectations

- Always include:
  - **Loading** states for fetches and long tasks
  - **Empty** states (no results)
  - **Error** states with actionable message
- Accessibility:
  - Buttons/links must be keyboard reachable
  - Inputs need labels (visible or `aria-label`)

## When adding a new page (checklist)

- Confirm if it’s server or client (default: server; add `"use client"` only if needed).
- Wire networking via `frontend/lib/api.ts` / `frontend/lib/apply-api.ts` (don’t duplicate fetch logic).
- If it depends on env vars (Supabase/analytics/API URL), ensure it doesn’t break `npm run build` without them.

## Additional resources

- Deeper patterns + common pitfalls: [reference.md](reference.md)
- Copy/paste snippets: [examples.md](examples.md)
