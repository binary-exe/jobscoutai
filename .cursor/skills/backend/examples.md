# Backend Examples (copy/paste)

## New authenticated endpoint (user session)

Checklist:

- Add Pydantic request/response models
- Add `user: AuthUser = Depends(get_current_user)`
- Use `HTTPException` with clear `detail`
- Add rate limiting if expensive

## Rate limit guard (per user)

```python
from fastapi import Depends
from backend.app.core.auth import get_current_user, AuthUser
from backend.app.core.rate_limit import check_rate_limit, apply_pack_limiter

@router.post("/something-expensive")
async def expensive(user: AuthUser = Depends(get_current_user)):
    check_rate_limit(user.user_id, apply_pack_limiter)
    ...
```

## Fire-and-forget endpoint shape (204)

- For event capture, return `204` even if payload is missing; don’t block UI flows.
