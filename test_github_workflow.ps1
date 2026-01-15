# Test script to verify the GitHub Actions workflow endpoint
# Usage: .\test_github_workflow.ps1 <API_URL> <ADMIN_TOKEN>

param(
    [string]$ApiUrl = "https://jobscout-api.fly.dev",
    [string]$AdminToken
)

if (-not $AdminToken) {
    Write-Host "Usage: .\test_github_workflow.ps1 -ApiUrl <URL> -AdminToken <TOKEN>" -ForegroundColor Yellow
    Write-Host "Example: .\test_github_workflow.ps1 -ApiUrl https://jobscout-api.fly.dev -AdminToken your-token-here" -ForegroundColor Yellow
    exit 1
}

Write-Host "Testing GitHub Actions workflow endpoint..." -ForegroundColor Cyan
Write-Host "API URL: $ApiUrl" -ForegroundColor Gray
Write-Host ""

# Test payload (same as workflow)
$query = "automation engineer"
$useAi = $false
$location = "Remote"

# Build JSON payload
$jsonPayload = @{
    query = $query
    location = $location
    use_ai = $useAi
} | ConvertTo-Json

Write-Host "Request payload:" -ForegroundColor Cyan
Write-Host $jsonPayload -ForegroundColor Gray
Write-Host ""

# Make request
Write-Host "Making POST request to $ApiUrl/api/v1/admin/run..." -ForegroundColor Cyan

try {
    $headers = @{
        "Authorization" = "Bearer $AdminToken"
        "Content-Type" = "application/json"
    }
    
    $response = Invoke-RestMethod -Uri "$ApiUrl/api/v1/admin/run" `
        -Method Post `
        -Headers $headers `
        -Body $jsonPayload `
        -ErrorAction Stop
    
    Write-Host ""
    Write-Host "✅ Test passed! The endpoint is working correctly." -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10
    Write-Host ""
    Write-Host "The GitHub Actions workflow should work now." -ForegroundColor Green
    exit 0
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $errorBody = $_.ErrorDetails.Message
    
    Write-Host ""
    Write-Host "❌ Test failed (HTTP $statusCode)" -ForegroundColor Red
    Write-Host "Error: $errorBody" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check your API_URL and ADMIN_TOKEN" -ForegroundColor Yellow
    exit 1
}
