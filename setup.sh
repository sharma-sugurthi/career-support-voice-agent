#!/usr/bin/env bash
# One-time setup for the Career Support Voice Agent.
# Run this once after downloading the project:   ./setup.sh
# After that, start the app any time with:       ./start.sh
set -u

cd "$(dirname "$0")"
ROOT="$(pwd)"
AGENT_DIR="$ROOT/livekit-voice-agent"
WEB_DIR="$ROOT/agent-starter-react"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m[!]\033[0m %s\n' "$*"; }
fail()  { printf '\n\033[31mSetup stopped:\033[0m %s\n' "$*"; exit 1; }

bold "Career Support Voice Agent - one-time setup"
echo "This will take a few minutes. You only ever run this once."
echo

# ── 1. Python package manager (uv) ───────────────────────────────────────────
bold "Step 1/6: Checking Python tools"
if ! command -v uv >/dev/null 2>&1; then
  echo "  Installing uv (the Python package manager this project uses)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail "Could not install uv. Check your internet connection and run ./setup.sh again."
  # Make uv available in this shell right away
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || fail "uv is installed but not found. Close this terminal, open a new one, and run ./setup.sh again."
ok "uv is ready"

# ── 2. Node.js + pnpm ─────────────────────────────────────────────────────────
bold "Step 2/6: Checking Node.js"
if ! command -v node >/dev/null 2>&1; then
  fail "Node.js is not installed. Download it from https://nodejs.org (choose the LTS version), install it, then run ./setup.sh again."
fi
NODE_MAJOR="$(node -v | sed 's/v\([0-9]*\).*/\1/')"
[ "$NODE_MAJOR" -ge 18 ] || fail "Your Node.js is too old (v$NODE_MAJOR). Install the LTS version from https://nodejs.org and run ./setup.sh again."
if ! command -v pnpm >/dev/null 2>&1; then
  echo "  Installing pnpm..."
  (corepack enable >/dev/null 2>&1 && corepack prepare pnpm@latest --activate >/dev/null 2>&1) || npm install -g pnpm >/dev/null 2>&1 || fail "Could not install pnpm. Run: npm install -g pnpm   and then ./setup.sh again."
fi
ok "Node.js and pnpm are ready"

# ── 3. Install the voice agent ────────────────────────────────────────────────
bold "Step 3/6: Installing the voice agent (Python)"
(cd "$AGENT_DIR" && uv sync) || fail "Python installation failed. Check your internet connection and run ./setup.sh again."
echo "  Downloading speech models (voice detection, turn taking)..."
(cd "$AGENT_DIR" && uv run python agent.py download-files) || warn "Model download failed - it will retry on first start."
ok "Voice agent installed"

# ── 4. Install and build the web app ──────────────────────────────────────────
bold "Step 4/6: Installing the web app"
(cd "$WEB_DIR" && pnpm install --silent) || fail "Web app installation failed. Check your internet connection and run ./setup.sh again."
echo "  Building the web app (makes daily startup fast)..."
(cd "$WEB_DIR" && pnpm build) || fail "Web app build failed. Run ./setup.sh again; if it keeps failing, please open an issue on GitHub."
ok "Web app ready"

# ── 5. Your keys ──────────────────────────────────────────────────────────────
bold "Step 5/6: Your service keys"
echo "  The app needs 3 free accounts (the AI brain itself runs on YOUR computer, no key needed):"
echo "    1. LiveKit Cloud  https://cloud.livekit.io   (connects your mic to the agent)"
echo "    2. AssemblyAI     https://www.assemblyai.com (turns your speech into text)"
echo "    3. Cartesia       https://play.cartesia.ai   (gives the agent its voice)"
echo

AGENT_ENV="$AGENT_DIR/.env.local"
WEB_ENV="$WEB_DIR/.env.local"
[ -f "$AGENT_ENV" ] || cp "$AGENT_DIR/.env.example" "$AGENT_ENV"
[ -f "$WEB_ENV" ]   || cp "$WEB_DIR/.env.example" "$WEB_ENV"

# set_key FILE KEY VALUE - replace or append KEY=VALUE in FILE
set_key() {
  local file="$1" key="$2" value="$3"
  if grep -q "^#*\s*${key}=" "$file"; then
    sed -i.bak "s|^#*\s*${key}=.*|${key}=${value}|" "$file" && rm -f "$file.bak"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$file"
  fi
}

# has_real_value FILE KEY - true if KEY has a non-placeholder value
has_real_value() {
  local v
  v="$(grep "^${key_prefix:-}${2}=" "$1" 2>/dev/null | head -1 | cut -d= -f2-)"
  [ -n "$v" ] && ! printf '%s' "$v" | grep -qiE 'xxxx|your-project'
}

ask_key() {
  local key="$1" label="$2"
  if has_real_value "$AGENT_ENV" "$key"; then
    ok "$label already set"
    return
  fi
  printf '  Paste your %s (or press Enter to add it later): ' "$label"
  read -r value
  if [ -n "$value" ]; then
    set_key "$AGENT_ENV" "$key" "$value"
    case "$key" in LIVEKIT_*) set_key "$WEB_ENV" "$key" "$value" ;; esac
    ok "$label saved"
  else
    warn "$label skipped - add it to livekit-voice-agent/.env.local before starting"
  fi
}

ask_key "LIVEKIT_URL"        "LiveKit URL (starts with wss://)"
ask_key "LIVEKIT_API_KEY"    "LiveKit API key"
ask_key "LIVEKIT_API_SECRET" "LiveKit API secret"
ask_key "ASSEMBLYAI_API_KEY" "AssemblyAI key"
ask_key "CARTESIA_API_KEY"   "Cartesia key"

# ── 6. The AI brain (Ollama, runs on your computer) ───────────────────────────
bold "Step 6/6: The AI brain"
LLM_PROVIDER="$(grep '^LLM_PROVIDER=' "$AGENT_ENV" 2>/dev/null | head -1 | cut -d= -f2)"
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ]; then
  if command -v ollama >/dev/null 2>&1; then
    MODEL="$(grep '^LLM_MODEL=' "$AGENT_ENV" 2>/dev/null | head -1 | cut -d= -f2)"
    MODEL="${MODEL:-llama3.1:8b}"
    echo "  Downloading the AI model ($MODEL) - this is the big one-time download..."
    ollama pull "$MODEL" || warn "Model download failed - run: ollama pull $MODEL"
    ok "AI brain ready ($MODEL, running privately on your computer)"
  else
    warn "Ollama is not installed. It is the free AI brain that runs on your computer."
    echo "     Install it from https://ollama.com/download then run:  ollama pull llama3.1:8b"
    echo "     (Or use a cloud AI instead: set LLM_PROVIDER in livekit-voice-agent/.env.local)"
  fi
else
  ok "You chose the '$LLM_PROVIDER' cloud AI - make sure its API key is in livekit-voice-agent/.env.local"
fi

# Desktop launcher for Linux (absolute path required by .desktop format)
if [ "$(uname -s)" = "Linux" ]; then
  cat > "$ROOT/Start Career Coach.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Career Coach
Comment=Start the Career Support Voice Agent
Exec=bash -c 'cd "$ROOT" && ./start.sh'
Terminal=true
DESKTOP
  chmod +x "$ROOT/Start Career Coach.desktop" 2>/dev/null || true
fi

echo
bold "Setup complete!"
echo "  Start the app any time with:   ./start.sh"
echo "  (macOS: you can also double-click 'Start Career Coach.command')"
