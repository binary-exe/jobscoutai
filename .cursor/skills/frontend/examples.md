# Frontend Examples

## Add a new public API client function

Checklist:

- Add a typed interface for the response
- Build a `URLSearchParams` from optional params
- Use `fetch` with `next: { revalidate: ... }` for cacheable data

## Add an authenticated Apply Workspace call

Checklist:

- Add a function in `frontend/lib/apply-api.ts`
- Use `apiRequest<T>(...)` helper so the bearer token is always attached
- On UI side: show error message from thrown Error (don’t swallow silently)

## Client component boundary reminder

If you add:

- `useState`, `useEffect`, `useRouter`, click handlers, `window`

Then add:

```ts
'use client';
```
