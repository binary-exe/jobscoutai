# QA Examples

## Bug report template

```markdown
### Repro
1. ...
2. ...

### Expected
...

### Actual
...

### Scope
Frontend / Backend / Both

### Root cause
...

### Fix
...

### Verification
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `python -m compileall backend jobscout`
- Manual: ...
```

## PR verification note (short)

```text
Verified:
- frontend lint/build
- python compileall
- manual smoke: /docs + affected flows
```
