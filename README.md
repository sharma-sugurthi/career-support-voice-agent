# Career Support Voice Agent

[![CI](https://github.com/sharma-sugurthi/career-support-voice-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/sharma-sugurthi/career-support-voice-agent/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/sharma-sugurthi/career-support-voice-agent?style=flat)](https://github.com/sharma-sugurthi/career-support-voice-agent/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/sharma-sugurthi/career-support-voice-agent?style=flat)](https://github.com/sharma-sugurthi/career-support-voice-agent/fork)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-%E2%9D%A4-ff69b4?logo=githubsponsors)](https://github.com/sponsors/sharma-sugurthi)

An open-source, voice-first AI career coach. Open a browser, click start, and talk to an AI about resumes, interview prep, job search strategy, salary negotiation, career switches, higher studies, and skill development. It listens, thinks, and talks back in under two seconds on a normal connection.

**Self-hosted by default.** Out of the box the agent runs on your own machine with a local LLM through Ollama - no LLM API key, no per-token cost, and your conversations never leave your hardware. If you prefer a hosted model, switch to Claude, GPT, Gemini, or Groq with one env var.

> This project started as a career support agent for my university, RGUKT. It's now a general-purpose voice career coach that anyone can run, extend, and deploy. If it helps you, a ⭐ star keeps it going, and [sponsoring](https://github.com/sponsors/sharma-sugurthi) helps me spend more time on it.

## How it works

Two services talk to each other through a LiveKit room. The browser handles the mic and speaker; the Python agent handles everything else.

```
Browser (Next.js) --- LiveKit --- Python Agent
                                      STT:  AssemblyAI streaming
                                      LLM:  YOUR CHOICE (self-hosted default)
                                      TTS:  Cartesia sonic-2
                                      VAD:  Silero
                                      Turn detection: Multilingual ONNX
```

## Choose your LLM

Set `LLM_PROVIDER` in `livekit-voice-agent/.env.local`. Override the model with `LLM_MODEL`.

| Provider | `LLM_PROVIDER` | Default model | Needs |
|---|---|---|---|
| **Ollama (self-hosted, default)** | `ollama` | `llama3.1:8b` | [Ollama](https://ollama.com) running locally |
| Any OpenAI-compatible server (vLLM, llama.cpp, LM Studio, TGI) | `openai-compatible` | `meta-llama/Llama-3.1-8B-Instruct` | `LLM_BASE_URL` |
| Anthropic Claude | `anthropic` | `claude-opus-5` | `ANTHROPIC_API_KEY` |
| OpenAI GPT | `openai` | `gpt-5.1` | `OPENAI_API_KEY` |
| Google Gemini | `google` | `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Groq (fast + free tier) | `groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |

### Self-hosting the LLM

Install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.1:8b
ollama serve   # usually already running as a service
```

That's it - the agent's default config finds it at `http://localhost:11434/v1`. Pick a model for your hardware:

| Hardware | Suggested `LLM_MODEL` | Notes |
|---|---|---|
| 8 GB RAM, no GPU | `llama3.1:8b` | The default. Fine for short voice replies |
| 16 GB RAM / mid GPU | `qwen2.5:14b` or `gpt-oss:20b` | Noticeably smarter answers |
| 24 GB+ VRAM | `qwen2.5:32b` | Great quality, still responsive |
| Serious GPU (48 GB+) | `llama3.3:70b` | Best self-hosted quality |

Voice feels broken when the LLM is slow, so prefer the largest model that still streams tokens quickly on your machine. For production-grade serving, run [vLLM](https://docs.vllm.ai) and use `LLM_PROVIDER=openai-compatible` with `LLM_BASE_URL=http://your-server:8000/v1`.

### When credits run out

If a hosted provider fails, the agent tells you out loud instead of going silent:

- **Credits/quota exhausted** → "My language model credits are completed. Please add credits or switch to the self-hosted model, then try again."
- **Temporary rate limit** → "I've hit a temporary rate limit. Please wait a moment and ask me again."

## What's in this repo

```
career-support-voice-agent/
    livekit-voice-agent/      Python agent
        agent.py              session wiring, error handling
        llm_providers.py      provider selection + failure classification
        pyproject.toml
        .env.example
    agent-starter-react/      Next.js 15 frontend
    tests/agent/              runs without any live credentials
    .github/workflows/ci.yml  tests on every push and PR
```

## Setup

You need Python 3.10+, [uv](https://astral.sh/uv), Node.js 18+, and pnpm.

API keys (all have free tiers; none needed for the LLM if you self-host):

- **LiveKit Cloud** at https://cloud.livekit.io - project Settings → URL, API key, secret
- **AssemblyAI** at https://www.assemblyai.com - speech to text
- **Cartesia** at https://play.cartesia.ai - text to speech

Python agent:

```bash
cd livekit-voice-agent
uv sync
uv run python agent.py download-files
cp .env.example .env.local
# fill in your keys and pick your LLM_PROVIDER in .env.local
```

Frontend:

```bash
cd agent-starter-react
pnpm install
cp .env.example .env.local
# only the three LiveKit keys go here
```

## Running it

Open two terminals.

```bash
# terminal 1
cd livekit-voice-agent
uv run python agent.py dev
```

```bash
# terminal 2
cd agent-starter-react
pnpm dev
```

Go to http://localhost:3000, hit Start call, and talk.

## Running the tests

```bash
cd livekit-voice-agent
uv run --with pytest pytest ../tests/ -v
```

Tests cover env setup, imports, the Assistant class, LLM provider selection, and the credit-exhaustion error classification. No live API keys needed.

## Why these specific tools

**Self-hosted LLM by default** - a career conversation is personal. Running the model locally means zero per-token cost and full privacy. The provider layer is one file (`llm_providers.py`), so swapping in a hosted model is a single env var when you want more brainpower.

**AssemblyAI for speech to text** - the streaming model handles accented English better than most Whisper-based options I tested, and partial transcripts let the agent start thinking before you finish speaking.

**Cartesia for text to speech** - `sonic-2` generates audio faster than real-time, so the agent starts speaking within about 200ms of the first LLM token.

**The subprocess thing** - LiveKit agents runs each job in a separate OS process. Client objects created in the main process don't survive the IPC boundary, so the LLM client is created inside the session entrypoint (`create_llm()` is called there, not at import time).

## Known limits

One agent process handles one conversation at a time; run more processes for more concurrent users. The ONNX turn-detector runs fine on CPU, but don't run the local LLM and the agent on a machine with no headroom - if token streaming is slow, the whole conversation feels slow.

## Support this project

If this repo helped you land an interview, build your own voice agent, or learn LiveKit:

- ⭐ [Star the repo](https://github.com/sharma-sugurthi/career-support-voice-agent) - it genuinely helps others find it
- 🍴 [Fork it](https://github.com/sharma-sugurthi/career-support-voice-agent/fork) and build your own agent on top
- ❤️ [Sponsor on GitHub](https://github.com/sponsors/sharma-sugurthi) - sponsorship funds the time to add new providers, languages, and deployment guides
- 🐛 [Open issues](https://github.com/sharma-sugurthi/career-support-voice-agent/issues) and PRs - see [CONTRIBUTING.md](CONTRIBUTING.md)

## License

Apache 2.0
