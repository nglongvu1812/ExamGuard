$ErrorActionPreference = "Stop"

function Assert-Ok($StepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED at: $StepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "=== 1. Backend Lint (ruff) ===" -ForegroundColor Cyan
& "$PSScriptRoot\..\backend\.venv\Scripts\ruff.exe" check "$PSScriptRoot\..\backend\app" "$PSScriptRoot\..\backend\tests"
Assert-Ok "ruff"

Write-Host "=== 2. Backend Typecheck (mypy) ===" -ForegroundColor Cyan
& "$PSScriptRoot\..\backend\.venv\Scripts\mypy.exe" --config-file "$PSScriptRoot\..\backend\pyproject.toml" "$PSScriptRoot\..\backend\app"
Assert-Ok "mypy"

Write-Host "=== 3. Backend Tests (pytest) ===" -ForegroundColor Cyan
Push-Location "$PSScriptRoot\..\backend"
try {
    & "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" -m pytest -v
    Assert-Ok "pytest"
} finally {
    Pop-Location
}

Write-Host "=== 4. Frontend Lint, Typecheck, Tests & Build ===" -ForegroundColor Cyan
Push-Location "$PSScriptRoot\..\frontend"
try {
    npm run lint
    Assert-Ok "frontend lint"
    npm run typecheck
    Assert-Ok "frontend typecheck"
    npm test
    Assert-Ok "frontend vitest"
    npm run build
    Assert-Ok "frontend build"
} finally {
    Pop-Location
}

Write-Host "ALL CHECKS PASSED!" -ForegroundColor Green
