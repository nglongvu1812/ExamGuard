@echo off
setlocal
cd /d "%~dp0.."
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" desktop\launcher.py %*
) else (
    python desktop\launcher.py %*
)
