@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installing GLM Coding Helper backend environment...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup_backend.ps1" -Target cpu
pause
