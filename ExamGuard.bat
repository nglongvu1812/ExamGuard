@echo off
title ExamGuard Local Assessment Server
cd /d "%~dp0"
if exist "dist\ExamGuard\ExamGuard.exe" (
    start "" "dist\ExamGuard\ExamGuard.exe"
) else if exist "ExamGuard.exe" (
    start "" "ExamGuard.exe"
) else (
    echo [LOI] Khong tim thay ExamGuard.exe!
    pause
)
