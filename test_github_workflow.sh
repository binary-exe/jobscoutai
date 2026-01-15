#!/bin/bash
# Test script to verify the GitHub Actions workflow endpoint
# Usage: ./test_github_workflow.sh <API_URL> <ADMIN_TOKEN>

set -e

API_URL="${1:-https://jobscout-api.fly.dev}"
ADMIN_TOKEN="${2}"

if [ -z "$ADMIN_TOKEN" ]; then
    echo "Usage: $0 <API_URL> <ADMIN_TOKEN>"
    echo "Example: $0 https://jobscout-api.fly.dev your-token-here"
    exit 1
fi

echo "Testing GitHub Actions workflow endpoint..."
echo "API URL: $API_URL"
echo ""

# Test payload (same as workflow)
QUERY="automation engineer"
USE_AI=false
LOCATION="Remote"

# Build JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "query": "$QUERY",
  "location": "$LOCATION",
  "use_ai": $USE_AI
}
EOF
)

echo "Request payload:"
echo "$JSON_PAYLOAD" | jq .
echo ""

# Make request
echo "Making POST request to $API_URL/api/v1/admin/run..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/admin/run" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo ""
echo "Response:"
echo "  HTTP Code: $HTTP_CODE"
echo "  Body: $BODY"
echo ""

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "✅ Test passed! The endpoint is working correctly."
    echo "   The GitHub Actions workflow should work now."
    exit 0
else
    echo "❌ Test failed (HTTP $HTTP_CODE)"
    echo "   Check your API_URL and ADMIN_TOKEN"
    exit 1
fi
