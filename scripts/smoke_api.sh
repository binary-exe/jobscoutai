#!/usr/bin/env sh
# Smoke test for public JobScout API endpoints (no auth).
# Usage: API_BASE=https://jobscout-api.fly.dev/api/v1 ./scripts/smoke_api.sh
# Or:   ./scripts/smoke_api.sh  (defaults to localhost)

set -e
BASE="${API_BASE:-http://localhost:8000/api/v1}"

echo "Smoke testing API at $BASE"
ROOT="${BASE%/api/v1*}"

# Health
echo "  GET /health ..."
resp=$(curl -s -o /dev/null -w "%{http_code}" "$ROOT/health" 2>/dev/null || true)
if [ "$resp" = "200" ]; then echo "  OK"; else echo "  WARN: /health returned $resp"; fi

# GET /jobs
echo "  GET /jobs ..."
resp=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/jobs?page_size=1")
if [ "$resp" != "200" ]; then
  echo "  FAIL: GET /jobs returned $resp"
  exit 1
fi
echo "  OK"

# GET /runs/latest
echo "  GET /runs/latest ..."
resp=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/runs/latest")
if [ "$resp" != "200" ]; then
  echo "  FAIL: GET /runs/latest returned $resp"
  exit 1
fi
echo "  OK"

# GET /admin/stats (public stats)
echo "  GET /admin/stats ..."
resp=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/admin/stats")
if [ "$resp" != "200" ]; then
  echo "  FAIL: GET /admin/stats returned $resp"
  exit 1
fi
echo "  OK"

echo "All smoke checks passed."
