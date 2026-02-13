# Authentication Examples (copy/paste)

## Authenticated fetch to backend (frontend)

```ts
const { data } = await supabase.auth.getSession();
const token = data.session?.access_token;
if (!token) throw new Error('Not authenticated');

const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/some/auth/endpoint`, {
  headers: { Authorization: `Bearer ${token}` },
});
```

## Backend endpoint requiring a logged-in user

```python
from fastapi import APIRouter, Depends
from backend.app.core.auth import AuthUser, get_current_user

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/me")
async def me(user: AuthUser = Depends(get_current_user)):
    return {"user_id": str(user.user_id), "email": user.email}
```

## Admin token header

```text
Authorization: Bearer <JOBSCOUT_ADMIN_TOKEN>
```
