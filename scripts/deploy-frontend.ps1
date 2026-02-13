# Deploy JobScout frontend to Vercel (production).
# First-time: run from frontend folder: npx vercel link --scope binary-exes-projects
# Then select your existing Vercel project (e.g. jobscoutai). Then run this script again.

$frontendDir = Join-Path (Join-Path $PSScriptRoot "..") "frontend"
$projectJson = Join-Path (Join-Path $frontendDir ".vercel") "project.json"

if (-not (Test-Path $projectJson)) {
    Write-Host "Project not linked. Run this once from a terminal:"
    Write-Host "  cd frontend"
    Write-Host "  npx vercel link --scope binary-exes-projects"
    Write-Host "Then choose your existing Vercel project and run this script again."
    exit 1
}

$project = Get-Content $projectJson | ConvertFrom-Json
$env:VERCEL_ORG_ID = $project.orgId
$env:VERCEL_PROJECT_ID = $project.projectId
Set-Location $frontendDir
npx vercel --prod --yes
exit $LASTEXITCODE
