# JobScoutAI Dev Examples (copy/paste)

## “What changed / verified” completion note

```markdown
What changed
- ...
- ...

Key files
- ...

How verified
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `python -m compileall backend jobscout`
- Manual: `/docs` → exercised ...

Notes / risks
- Schema: additive migration `backend/app/storage/...sql`
- Backwards compatibility: no endpoint removals, no column drops
```

## Add an authenticated Apply Workspace request (frontend)

- Use the helper in `frontend/lib/apply-api.ts` so the bearer token is always attached.

## Add a public API call (frontend)

- Add a typed function in `frontend/lib/api.ts` and keep errors user-actionable.
