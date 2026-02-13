# PR Check Examples

## PR description (filled example)

```markdown
## Summary
- Add authenticated Apply Workspace endpoints for trust reports and feedback.
- Improve frontend error states and keep Supabase build-safe behavior.

## Why
- Users need a safer “apply” workflow and feedback loop without breaking public job search.

## Changes
- **Frontend**: Use `frontend/lib/apply-api.ts` for authenticated calls and surface actionable errors.
- **Backend**: Add `/apply/...` endpoints guarded by Supabase JWT; add per-user rate limiting.
- **DB/Storage**: Add idempotent migration for trust feedback tables; executed in `init_schema()`.

## Risk / rollout notes
- Migration is additive and idempotent; safe on restart.
- Auth required: unauthenticated users see a clear login prompt.

## Test plan
- [ ] `frontend`: `npm run lint`
- [ ] `frontend`: `npm run build`
- [ ] `python`: `python -m compileall backend jobscout`
- [ ] Manual: `/docs` → exercised new endpoints with/without bearer token
```

## Debug note (good shape)

```text
Failing command: cd frontend && npm run build
Error: ReferenceError: window is not defined (server component importing client-only code)
Root cause: module imported at build/SSR time used window.
Fix: move code behind "use client" boundary and/or dynamic import; reran build successfully.
```
