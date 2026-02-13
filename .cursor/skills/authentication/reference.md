# Authentication Reference (JobScout)

## Frontend files (canonical)

- Supabase client: `frontend/lib/supabase.ts`
- Login (magic link): `frontend/app/login/page.tsx`
- Callback (session exchange): `frontend/app/auth/callback/page.tsx`
- Header session display + logout: `frontend/components/Header.tsx`

## Backend files (canonical)

- Supabase validation deps: `backend/app/core/auth.py`
- Admin token auth: `backend/app/api/admin.py`
- Example auth-required endpoints: `backend/app/api/profile.py`, `backend/app/api/apply.py`, `backend/app/api/referrals.py`

## Exact backend validation contract

Backend calls:

- URL: `${JOBSCOUT_SUPABASE_URL}/auth/v1/user`
- Headers:
  - `Authorization: Bearer <token from frontend>`
  - `apikey: <JOBSCOUT_SUPABASE_ANON_KEY>`

If Supabase config is missing, backend returns 500 (“Supabase auth not configured”).

## Referral flow (what exists)

- Login and callback may carry `ref=<referral_code>`.
- Callback attempts to apply referral by calling backend `POST /api/v1/referrals/apply` with bearer token.
- Referral endpoints are auth-required (`get_current_user`).

## Security note (important)

Frontend “auth gating” is UX only. The backend must enforce:

- auth required for Apply Workspace/profile/referrals
- admin token required for admin endpoints
