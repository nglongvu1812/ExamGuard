param(
    [string]$Version = "0.1.0-beta.1"
)

$ErrorActionPreference = "Stop"

function Assert-Ok($StepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED at: $StepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PyInstallerExe = Join-Path $RepoRoot "backend\.venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $PyInstallerExe)) {
    throw "PyInstaller not found at $PyInstallerExe. Run: backend\.venv\Scripts\pip.exe install pyinstaller"
}

Write-Host "=== 1. Build Offline Frontend SPA ===" -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run build
    Assert-Ok "frontend npm run build"
} finally {
    Pop-Location
}

Write-Host "=== 2. Build Portable Onedir EXE (PyInstaller) ===" -ForegroundColor Cyan
$DistDir = Join-Path $RepoRoot "dist"
$BuildDir = Join-Path $RepoRoot "build\pyinstaller"
$ReleaseDir = Join-Path $DistDir "release"
New-Item -ItemType Directory -Force -Path $DistDir, $BuildDir, $ReleaseDir | Out-Null

Push-Location $RepoRoot
try {
    & $PyInstallerExe --noconfirm --clean --distpath $DistDir --workpath $BuildDir (Join-Path $RepoRoot "desktop\examguard.spec")
    Assert-Ok "pyinstaller examguard.spec"
} finally {
    Pop-Location
}

$BundleDir = Join-Path $DistDir "ExamGuard"
$ExePath = Join-Path $BundleDir "ExamGuard.exe"
if (-not (Test-Path $ExePath)) {
    throw "Executable missing after build: $ExePath"
}

Write-Host "=== 3. Smoke Check Built EXE Version ===" -ForegroundColor Cyan
$VerOut = & $ExePath --version
Assert-Ok "ExamGuard.exe --version"
Write-Host "Version check: $VerOut" -ForegroundColor Green

Write-Host "=== 4. Bundle Offline Guides & Release Archive ===" -ForegroundColor Cyan
$DocsTarget = Join-Path $BundleDir "docs"
New-Item -ItemType Directory -Force -Path $DocsTarget | Out-Null
foreach ($DocName in @("LAN_AP_GUIDE.md", "TEACHER_QUICKSTART.md", "STUDENT_QUICKSTART.md", "RELEASE_CHECKLIST.md")) {
    $SrcDoc = Join-Path $RepoRoot "docs\$DocName"
    if (Test-Path $SrcDoc) {
        Copy-Item -Force $SrcDoc (Join-Path $DocsTarget $DocName)
    }
}
if (Test-Path (Join-Path $RepoRoot "CHANGELOG.md")) {
    Copy-Item -Force (Join-Path $RepoRoot "CHANGELOG.md") (Join-Path $BundleDir "CHANGELOG.md")
}

$ZipName = "ExamGuard-v$Version-win64-portable.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}

Compress-Archive -Path "$BundleDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal
$HashObj = Get-FileHash -Path $ZipPath -Algorithm SHA256
$ShaLine = "$($HashObj.Hash.ToLowerInvariant())  $ZipName"
$ShaPath = "$ZipPath.sha256"
Set-Content -Path $ShaPath -Value $ShaLine -Encoding utf8

Write-Host "=== Portable Release Built Cleanly ===" -ForegroundColor Green
Write-Host "Bundle dir : $BundleDir"
Write-Host "Archive    : $ZipPath"
Write-Host "SHA-256    : $ShaLine"
