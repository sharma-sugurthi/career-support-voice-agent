# RGUKT Career Support Voice Agent

A real-time voice AI system built for RGUKT (Rajiv Gandhi University of Knowledge Technologies). Students speak into a browser, the agent transcribes, reasons, and responds - end-to-end latency under two seconds on a decent connection.

The system is split into two independent services that communicate through a LiveKit room:

```
Browser (Next.js)  ──WebRTC──  LiveKit Cloud  ──── Python Agent
                                                       ├─ STT: AssemblyAI
                                                       ├─ LLM: Groq (compound-mini)
                                                       ├─ TTS: Cartesia sonic-2
                                                       ├─ VAD: Silero
                                                       └─ Turn detection: Multilingual ONNX
```

---

## Structure

```
career-support-voice-agent/
├── livekit-voice-agent/      # Python agent (uv)
│   ├── agent.py              # Entry point - all agent logic lives here
│   ├── pyproject.toml        # Dependencies
│   ├── uv.lock               # Locked dependency graph
│   └── .env.example          # Template for required secrets
├── agent-starter-react/      # Next.js 15 frontend (pnpm)
│   ├── app/                  # App router pages and API routes
│   ├── components/           # React components (livekit + app-level)
│   ├── lib/utils.ts          # Shared utilities
│   └── .env.example          # Template for required secrets
├── tests/
│   └── agent/
│       └── test_agent.py     # Pytest suite - runs without live credentials
└── .gitignore
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.10 | System package or pyenv |
| uv | any | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 18 | System package or nvm |
| pnpm | ≥ 9 | `npm install -g pnpm` |

---

## API Keys

You need accounts at four services. All have free tiers that cover development and demo loads:

| Service | Purpose | Where to get it |
|---------|---------|-----------------|
| [LiveKit Cloud](https://cloud.livekit.io) | WebRTC room infrastructure | Project → Settings → Keys |
| [AssemblyAI](https://www.assemblyai.com) | Speech-to-text (streaming) | Dashboard → API Keys |
| [Groq](https://console.groq.com) | LLM inference (free, no billing) | API Keys → Create Key |
| [Cartesia](https://play.cartesia.ai) | Text-to-speech | Account → API Keys |

---

## Setup

### Python Agent

```bash
cd livekit-voice-agent

# Install dependencies into an isolated venv
uv sync

# Download the turn-detector ONNX model (~400MB, one-time)
python agent.py download-files

# Copy and fill in credentials
cp .env.example .env.local
# edit .env.local with your keys
```

### Frontend

```bash
cd agent-starter-react

# Install dependencies
pnpm install

# Copy and fill in credentials
cp .env.example .env.local
# edit .env.local - only three LiveKit keys needed here
```

---

## Running

Start both services in separate terminals. Order doesn't matter.

```bash
# Terminal 1 - Python agent (hot-reloads on file changes)
cd livekit-voice-agent
source .venv/bin/activate
python agent.py dev
```

```bash
# Terminal 2 - Next.js frontend
cd agent-starter-react
pnpm dev
```

Open `http://localhost:3000`, click **Start call**, and speak.

---

## Tests

```bash
# From the project root, with the agent venv active
source livekit-voice-agent/.venv/bin/activate
pytest tests/ -v
```

The test suite covers environment setup, agent imports, class hierarchy, and dependency declarations. It does not require live API credentials or a running LiveKit room.

---

## Architecture Notes

**Why Groq instead of OpenAI?**  
Groq's LPU hardware delivers inference latency that OpenAI can't match at comparable price points. For voice, every 100ms matters - a slow LLM makes the whole pipeline feel broken regardless of how fast your STT and TTS are. `groq/compound-mini` runs on-demand with a generous free tier.

**Why AssemblyAI for STT?**  
The `universal-streaming` model handles Indian English accent variance better than Whisper-based alternatives in benchmarks that matter here. LiveKit's AssemblyAI plugin streams partial transcripts, so the LLM starts forming a response before the user finishes speaking.

**Why Cartesia for TTS?**  
`sonic-2` generates audio faster than real-time on their servers, which means the agent can begin speaking within ~200ms of LLM first-token. The alternative (ElevenLabs) has higher quality but meaningfully higher latency at the free tier.

**Why the inference subprocess architecture?**  
LiveKit agents 1.3.x runs LLM, VAD, and turn-detector in separate OS processes via IPC. VAD and turn-detection run in the inference subprocess (shared across calls), while the job subprocess handles each individual session. The practical implication is that objects created in the main process - like an `AsyncOpenAI` client - cannot be pickled across the IPC boundary. That is why `OPENAI_BASE_URL` and the Groq client are configured inside `my_agent()` rather than at module level.

---

## Limitations

- **Rate limits**: Groq's free tier caps at ~8000 tokens/minute for compound-mini. Normal conversations stay well under this; back-to-back rapid testing will hit it. The agent recovers automatically on the next call.
- **Hardware**: The ONNX turn-detector model runs on CPU. An i3 handles it fine. Do not attempt to run local LLM inference on this hardware.
- **Concurrency**: This setup handles one concurrent session. LiveKit Cloud dispatches jobs to available workers; if you need multiple simultaneous users, run multiple agent processes.

---

## License

MIT
