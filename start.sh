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

check_key() {
  local key="$1" label="$2" where="$3"
  local v
  v="$(grep "^${key}=" "$AGENT_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
  if [ -z "$v" ] || printf '%s' "$v" | grep -qiE 'xxxx|your-project'; then
    fail "Your $label is missing. Open the file livekit-voice-agent/.env.local and paste it after ${key}=  (get one free at $where). Or run ./setup.sh again to be asked for it."
  fi
}
check_key "LIVEKIT_URL"        "LiveKit URL"     "https://cloud.livekit.io"
check_key "LIVEKIT_API_KEY"    "LiveKit API key" "https://cloud.livekit.io"
check_key "LIVEKIT_API_SECRET" "LiveKit secret"  "https://cloud.livekit.io"
check_key "ASSEMBLYAI_API_KEY" "AssemblyAI key"  "https://www.assemblyai.com"
check_key "CARTESIA_API_KEY"   "Cartesia key"    "https://play.cartesia.ai"

LLM_PROVIDER="$(grep '^LLM_PROVIDER=' "$AGENT_ENV" 2>/dev/null | head -1 | cut -d= -f2)"
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ] && command -v ollama >/dev/null 2>&1; then
  # Make sure the local AI brain is awake
  if ! curl -s --max-time 2 "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "Waking up the AI brain (Ollama)..."
    (ollama serve >/dev/null 2>&1 &)
    sleep 2
  fi
fi

# ── Start both services, stop both on Ctrl+C ─────────────────────────────────
PIDS=()
cleanup() {
  echo
  echo "Stopping Career Coach..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
  wait 2>/dev/null
  exit 0
}
trap cleanup INT TERM

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
