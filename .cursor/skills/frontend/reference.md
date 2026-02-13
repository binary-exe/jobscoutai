# Frontend Reference (JobScout)

## Canonical modules to follow

- Public API client: `frontend/lib/api.ts`
- Authenticated API client: `frontend/lib/apply-api.ts`
- Supabase client (build-safe): `frontend/lib/supabase.ts`
- Analytics: `frontend/lib/analytics.ts`
- Auth callback flow: `frontend/app/auth/callback/page.tsx`

## Environment variables (rules)

- Anything used in the browser must be `NEXT_PUBLIC_*`.
- Add new env vars to `frontend/env.sample`.
- Code paths that run during build/SSR must not assume env vars exist.

## Auth flows (what exists)

- Users sign in via Supabase; callback page exchanges `code` for session:
  - `supabase.auth.exchangeCodeForSession(code)`
- Some flows may not include `code`; callback page falls back to `supabase.auth.getSession()`.
- After login, frontend may call backend endpoints using bearer token (example: referral apply).

## API calling conventions

### Public endpoints

- Use `frontend/lib/api.ts` and typed interfaces.
- Keep errors user-friendly (“Failed to fetch …”) and don’t leak raw stack traces to UI.

### Auth-required endpoints (Apply Workspace)

- Use `frontend/lib/apply-api.ts`:
  - it fetches the token via `supabase.auth.getSession()`
  - it attaches `Authorization: Bearer <token>`
  - it throws “Authentication required…” if missing token

## Common Next.js pitfalls (avoid)

- Using `window`, `document`, `localStorage` in server components.
- Importing client-only modules into server components (moves crash to build time).
- Throwing hard errors when optional services (Supabase/PostHog) aren’t configured.
