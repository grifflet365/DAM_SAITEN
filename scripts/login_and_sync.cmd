@echo off
rem DAM_SAITEN: log in to DAM-tomo yourself in a Chrome window, then fetch, save and push the scoring data.
rem Since 2026-10-26 the DAM-tomo login checks an invisible reCAPTCHA, so the fetch can no longer log in by itself.
rem The login state is kept in %LOCALAPPDATA%\DAM_SAITEN (outside this public repository).
cd /d "%~dp0.."
python scripts\dam_session.py login
if errorlevel 1 (
  echo.
  echo Login was not confirmed. Nothing was fetched.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_and_push.ps1"
echo.
pause
