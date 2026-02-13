---
name: authentication
description: Authentication patterns for JobScout (Supabase magic link/OAuth on frontend, backend session validation via Supabase /auth/v1/user, admin token usage). Use when implementing login/logout, protecting routes, attaching Authorization headers, or debugging auth/session issues.
---

# Authentication (Supabase + backend validation)

## What exists in this repo (authoritative)

- **Frontend**: Supabase JS client in `frontend/lib/supabase.ts` (lazy init; safe defaults when env vars missing).
- **Frontend login**: email magic link (`signInWithOtp`) in `frontend/app/login/page.tsx`.
- **Frontend callback**: exchanges `code` for session in `frontend/app/auth/callback/page.tsx`.
- **Backend user auth**: validates session by calling Supabase `GET /auth/v1/user` with the bearer token (see `backend/app/core/auth.py`).
- **Backend admin auth**: `JOBSCOUT_ADMIN_TOKEN` via `Authorization: Bearer ...` (see `backend/app/api/admin.py`).

## End-to-end flow (don’t improvise)

1. **Login page** sends a magic link:
   - `supabase.auth.signInWithOtp({ email, options: { emailRedirectTo } })`
   - `emailRedirectTo` points to `/auth/callback?next=...` (and may include `ref=...`)
2. **Callback page** establishes session:
   - if `code` exists: `supabase.auth.exchangeCodeForSession(code)`
   - else: `supabase.auth.getSession()` must return a session
3. **Authenticated API calls**:
   - frontend gets token via `supabase.auth.getSession()`
   - backend request includes `Authorization: Bearer <access_token>`
4. **Backend validates** by calling Supabase `/auth/v1/user` (stateless).

## Frontend rules (build-safe + consistent)

- Never hardcode keys; use:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- If Supabase is not configured:
  - UI must not crash (SSR/build safe)
  - show a helpful message for login flows (see login page behavior)
- For authenticated backend endpoints, prefer `frontend/lib/apply-api.ts` so bearer tokens are always attached.

## Backend rules (explicit contracts)

- To require a user session on an endpoint, add a dependency:
  - `user = Depends(get_current_user)`
- To make auth optional (personalization), use:
  - `user = Depends(get_optional_user)`
- Always pass auth to the backend as:
  - `Authorization: Bearer <access_token>`

## Common “gotchas” (call these out early)

- Some pages treat “Supabase not configured” as a special dev/demo mode; don’t rely on that for real security—backend still enforces auth.
- Redirect URLs must be configured in Supabase to include `/auth/callback`.
- Backend needs Supabase settings (`JOBSCOUT_SUPABASE_URL`, `JOBSCOUT_SUPABASE_ANON_KEY`) or it will 500.

## Common auth debugging checklist

- Frontend env vars present in `.env.local` and Vercel env
- Supabase redirect URLs include `/auth/callback`
- Backend has `JOBSCOUT_SUPABASE_URL` and `JOBSCOUT_SUPABASE_ANON_KEY`
- Requests include the `Authorization: Bearer ...` header

## Additional resources

- Deep auth notes: [reference.md](reference.md)
- Copy/paste headers & flows: [examples.md](examples.md)
