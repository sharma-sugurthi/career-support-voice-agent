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

REM Local LiveKit server or cloud?
set "LOCAL_LIVEKIT="
findstr /C:"LIVEKIT_URL=ws://localhost" "livekit-voice-agent\.env.local" >nul 2>nul
if not errorlevel 1 set "LOCAL_LIVEKIT=1"

if not defined LOCAL_LIVEKIT (
  findstr /R "^LIVEKIT_URL=wss://your-project" "livekit-voice-agent\.env.local" >nul 2>nul
  if not errorlevel 1 (
    echo Your LiveKit settings are missing. Run setup.bat again - it configures a
    echo free local server, or paste LiveKit Cloud keys in livekit-voice-agent\.env.local
    pause & exit /b 1
  )
)

if defined LOCAL_LIVEKIT (
  if not exist "bin\livekit-server.exe" (
    echo Local LiveKit server not found. Run setup.bat once - it downloads it for you.
    pause & exit /b 1
  )
  echo Starting the local LiveKit server...
  start "Career Coach - LiveKit" cmd /c "bin\livekit-server.exe --dev"
  timeout /t 3 /nobreak >nul
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
echo To stop it, close the "Career Coach" windows that opened.
pause
