@echo off
REM One-time setup for the Career Support Voice Agent (Windows).
REM Run this once after downloading the project. After that, use start.bat.
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo Career Support Voice Agent - one-time setup
echo This will take a few minutes. You only ever run this once.
echo.

REM ── 1. uv (Python package manager) ──
where uv >nul 2>nul
if errorlevel 1 (
  echo Installing uv, the Python package manager this project uses...
  powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 (
  echo.
  echo Setup stopped: uv was installed but is not found yet.
  echo Close this window, open a new one, and run setup.bat again.
  pause & exit /b 1
)
echo [ok] uv is ready

REM ── 2. Node.js + pnpm ──
where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo Setup stopped: Node.js is not installed.
  echo Download the LTS version from https://nodejs.org , install it, then run setup.bat again.
  pause & exit /b 1
)
where pnpm >nul 2>nul
if errorlevel 1 (
  echo Installing pnpm...
  call npm install -g pnpm >nul 2>nul
)
where pnpm >nul 2>nul
if errorlevel 1 (
  echo Setup stopped: could not install pnpm. Run:  npm install -g pnpm   then setup.bat again.
  pause & exit /b 1
)
echo [ok] Node.js and pnpm are ready

REM ── 3. Voice agent (Python) ──
echo Installing the voice agent...
cd livekit-voice-agent
call uv sync
if errorlevel 1 (
  echo Setup stopped: Python installation failed. Check your internet and run setup.bat again.
  pause & exit /b 1
)
echo Downloading speech models...
call uv run python agent.py download-files
cd ..
echo [ok] Voice agent installed

REM ── 4. Web app ──
echo Installing the web app...
cd agent-starter-react
call pnpm install
if errorlevel 1 (
  echo Setup stopped: web app installation failed. Check your internet and run setup.bat again.
  pause & exit /b 1
)
echo Building the web app - makes daily startup fast...
call pnpm build
cd ..
echo [ok] Web app ready

REM ── 5. Settings files ──
if not exist "livekit-voice-agent\.env.local" copy "livekit-voice-agent\.env.example" "livekit-voice-agent\.env.local" >nul
if not exist "agent-starter-react\.env.local" copy "agent-starter-react\.env.example" "agent-starter-react\.env.local" >nul

echo.
echo The app needs 3 free accounts. The AI brain itself runs on YOUR computer, no key needed:
echo   1. LiveKit Cloud  https://cloud.livekit.io    (connects your mic to the agent)
echo   2. AssemblyAI     https://www.assemblyai.com  (turns your speech into text)
echo   3. Cartesia       https://play.cartesia.ai    (gives the agent its voice)
echo.
echo Now opening the settings file - paste your keys after the = signs and save:
echo   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, ASSEMBLYAI_API_KEY, CARTESIA_API_KEY
echo (Put the same three LIVEKIT lines into agent-starter-react\.env.local too.)
start notepad "livekit-voice-agent\.env.local"

REM ── 6. AI brain ──
where ollama >nul 2>nul
if errorlevel 1 (
  echo.
  echo [!] Ollama is not installed. It is the free AI brain that runs on your computer.
  echo     Install it from https://ollama.com/download then run:  ollama pull llama3.1:8b
) else (
  echo Downloading the AI model - this is the big one-time download...
  ollama pull llama3.1:8b
  echo [ok] AI brain ready, running privately on your computer
)

echo.
echo Setup complete! Start the app any time by double-clicking start.bat
pause
