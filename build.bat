@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\build.ps1" -Clean
if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b 1
)
echo.
echo Build succeeded: dist\TimeKeeper.exe
