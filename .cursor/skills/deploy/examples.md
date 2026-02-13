# Deploy Examples (copy/paste)

## Fly: set core secrets

```bash
fly secrets set JOBSCOUT_DATABASE_URL="postgresql://..." -a jobscout-api
fly secrets set JOBSCOUT_CORS_ORIGINS='["https://your-app.vercel.app"]' -a jobscout-api
fly secrets set JOBSCOUT_ADMIN_TOKEN="..." -a jobscout-api
```

## Fly: deploy + watch logs

```bash
fly deploy -a jobscout-api
fly logs -a jobscout-api
```

## Trigger an admin scrape run

```bash
curl -X POST https://jobscout-api.fly.dev/api/v1/admin/run ^
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"automation engineer\",\"location\":\"Remote\",\"use_ai\":false}"
```

## Vercel: manual deploy

```bash
cd frontend
npx vercel --prod
```
