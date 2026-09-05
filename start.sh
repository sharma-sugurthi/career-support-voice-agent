#!/usr/bin/env bash
# Start the Career Support Voice Agent. Run ./setup.sh once before first use.
set -u

cd "$(dirname "$0")"
ROOT="$(pwd)"
AGENT_DIR="$ROOT/livekit-voice-agent"
WEB_DIR="$ROOT/agent-starter-react"
AGENT_ENV="$AGENT_DIR/.env.local"

fail() { printf '\n\033[31m%s\033[0m\n' "$*"; exit 1; }

command -v uv >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$PATH"

# ── Friendly pre-flight checks (no tracebacks for missing config) ─────────────
[ -d "$AGENT_DIR/.venv" ] || fail "The app is not set up yet. Run ./setup.sh first (you only need to do that once)."
[ -f "$AGENT_ENV" ] || fail "Missing settings file. Run ./setup.sh first (you only need to do that once)."

env_value() {
  grep "^${1}=" "$AGENT_ENV" 2>/dev/null | head -1 | cut -d= -f2-
}

check_key() {
  local key="$1" label="$2" where="$3"
  local v
  v="$(env_value "$key")"
  if [ -z "$v" ] || printf '%s' "$v" | grep -qiE 'xxxx|your-project'; then
    fail "Your $label is missing. Open the file livekit-voice-agent/.env.local and paste it after ${key}=  (get one free at $where). Or run ./setup.sh again."
  fi
}

# LiveKit: local server (no account) or cloud (keys required).
# AssemblyAI/Cartesia/AI keys are optional - missing ones fall back to
# local speech, voice, and brain automatically.
LIVEKIT_URL_VALUE="$(env_value LIVEKIT_URL)"
LOCAL_LIVEKIT=""
case "$LIVEKIT_URL_VALUE" in
  *localhost*|*127.0.0.1*)
    LOCAL_LIVEKIT="1"
    [ -x "$ROOT/bin/livekit-server" ] || fail "Local LiveKit server not found. Run ./setup.sh once - it downloads it for you (or add LiveKit Cloud keys to livekit-voice-agent/.env.local)."
    ;;
  *)
    check_key "LIVEKIT_URL"        "LiveKit URL"     "https://cloud.livekit.io"
    check_key "LIVEKIT_API_KEY"    "LiveKit API key" "https://cloud.livekit.io"
    check_key "LIVEKIT_API_SECRET" "LiveKit secret"  "https://cloud.livekit.io"
    ;;
esac

if command -v ollama >/dev/null 2>&1; then
  # Make sure the local AI brain is awake (harmless if a cloud key is used)
  if ! curl -s --max-time 2 "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "Waking up the AI brain (Ollama)..."
    (ollama serve >/dev/null 2>&1 &)
    sleep 2
  fi
fi

# Show which mode each piece runs in (local vs cloud)
(cd "$AGENT_DIR" && uv run python show_mode.py) || true

# ── Start the services, stop them all on Ctrl+C ──────────────────────────────
PIDS=()
cleanup() {
  echo
  echo "Stopping Career Coach..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
  wait 2>/dev/null
  exit 0
}
trap cleanup INT TERM

if [ -n "$LOCAL_LIVEKIT" ]; then
  echo "Starting the local LiveKit server..."
  (exec "$ROOT/bin/livekit-server" --dev >/dev/null 2>&1) &
  PIDS+=($!)
  for _ in $(seq 1 20); do
    curl -s --max-time 1 "http://localhost:7880" >/dev/null 2>&1 && break
    sleep 1
  done
fi

echo "Starting the voice agent..."
(cd "$AGENT_DIR" && exec uv run python agent.py start) &
PIDS+=($!)

echo "Starting the web app..."
if [ -d "$WEB_DIR/.next" ]; then
  (cd "$WEB_DIR" && exec pnpm start --port 3000) &
else
  # Not built yet (setup was interrupted) - dev mode still works, just slower
  (cd "$WEB_DIR" && exec pnpm dev --port 3000) &
fi
PIDS+=($!)

# ── Wait for the web app, then open the browser ──────────────────────────────
echo "Waiting for everything to be ready..."
for _ in $(seq 1 60); do
  if curl -s --max-time 1 "http://localhost:3000" >/dev/null 2>&1; then
    echo
    echo "Career Coach is ready: http://localhost:3000"
    echo "Press Ctrl+C in this window to stop it."
    case "$(uname -s)" in
      Darwin) open "http://localhost:3000" 2>/dev/null || true ;;
      Linux)  xdg-open "http://localhost:3000" >/dev/null 2>&1 || true ;;
    esac
    break
  fi
  sleep 1
done

wait
