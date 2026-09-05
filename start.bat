@echo off
REM Start the Career Support Voice Agent (Windows). Run setup.bat once before first use.
setlocal
cd /d "%~dp0"

if not exist "livekit-voice-agent\.venv" (
  echo The app is not set up yet. Run setup.bat first - you only need to do that once.
  pause & exit /b 1
)
if not exist "livekit-voice-agent\.env.local" (
  echo Missing settings file. Run setup.bat first - you only need to do that once.
  pause & exit /b 1
)

findstr /R "^LIVEKIT_URL=wss://your-project" "livekit-voice-agent\.env.local" >nul 2>nul
if not errorlevel 1 (
  echo Your LiveKit keys are missing.
  echo Open livekit-voice-agent\.env.local in Notepad and paste your keys - get them free at https://cloud.livekit.io
  pause & exit /b 1
)

echo Starting the voice agent...
start "Career Coach - Voice Agent" cmd /c "cd livekit-voice-agent && uv run python agent.py start"

echo Starting the web app...
if exist "agent-starter-react\.next" (
  start "Career Coach - Web App" cmd /c "cd agent-starter-react && pnpm start --port 3000"
) else (
  start "Career Coach - Web App" cmd /c "cd agent-starter-react && pnpm dev --port 3000"
)

echo Waiting for everything to be ready...
timeout /t 12 /nobreak >nul
start http://localhost:3000

echo.
echo Career Coach is running at http://localhost:3000
echo To stop it, close the two "Career Coach" windows that opened.
pause
