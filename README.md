# Career Support Voice Agent

[![CI](https://github.com/sharma-sugurthi/career-support-voice-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/sharma-sugurthi/career-support-voice-agent/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/sharma-sugurthi/career-support-voice-agent?style=flat)](https://github.com/sharma-sugurthi/career-support-voice-agent/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/sharma-sugurthi/career-support-voice-agent?style=flat)](https://github.com/sharma-sugurthi/career-support-voice-agent/fork)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-%E2%9D%A4-ff69b4?logo=githubsponsors)](https://github.com/sponsors/sharma-sugurthi)

An open-source, voice-first AI career coach - actually a whole team of them. Open a browser, click start, and talk about resumes, mock interviews, LinkedIn, higher studies in India or abroad, acing one company or one exam (UPSC, SSC, banking, CAT, GATE), study schedules, and portfolio projects. It listens, thinks, talks back in under two seconds, and remembers you next time.

Built for everyone, not just engineers: a UPSC aspirant, a marketer, a designer, and a CS student all get a coach that speaks their language.

**Keys optional, always.** Every piece of the stack follows one rule: paste an API key and it automatically uses the best commercial service; leave it empty and that piece automatically runs on your own computer, free forever. No keys at all? The whole thing - brain (Ollama), ears (Whisper), voice (Piper), even the LiveKit connection (local server) - runs on one laptop with zero accounts.

> This project started as a career support agent for my university, RGUKT. It's now a general-purpose voice career coach that anyone can run, extend, and deploy. If it helps you, a ⭐ star keeps it going, and [sponsoring](https://github.com/sponsors/sharma-sugurthi) helps me spend more time on it.

## How it works

Two services talk to each other through a LiveKit room. The browser handles the mic and speaker; the Python agent handles everything else.

```
Browser (Next.js) --- LiveKit (cloud or local) --- Python Agent
                                      STT:  AssemblyAI, or local Whisper
                                      LLM:  your key's provider, or local Ollama
                                      TTS:  Cartesia, or local Piper
                                      VAD:  Silero (always local)
                                      Turn detection: Multilingual ONNX (always local)
```

Which side of each "or" runs is decided automatically by whether its key exists - `./start.sh` prints the chosen mode every time.

## Meet the team

One conversation, eight coaches. The main coach understands what you need and hands you to the right specialist mid-call - it feels like one continuous conversation.

```
                     ┌─ ResumeCoach          resume/CV/portfolio, any field
                     ├─ InterviewCoach       mock interviews + honest scored verdicts
CareerCoach ─────────├─ LinkedInCoach        profile building from your own text
 (routes, plans)     ├─ HigherStudiesPlanner India + abroad, asks your budget FIRST
                     ├─ TargetPrep           ace one company or one exam (UPSC/SSC/CAT/GATE)
                     ├─ StudyPlanner         week-by-week schedules that fit your life
                     └─ ProjectMentor        proof-of-work + live hackathon listings
```

Every specialist shares your memory and can research with real tools: keyless web search, page reading (robots.txt respected), currency conversion at official ECB rates, and exact budget math done in Python, never in the model's head.

## It remembers you

Close the tab, come back next week, and the coach picks up where you left off. Everything lives in one local SQLite file (`livekit-voice-agent/data/career.db`) created automatically - **nothing is hosted anywhere**, no database to set up, no account to create. Your identity is an anonymous ID in your browser; your career data never leaves your machine (delete that one file to wipe it). At the end of each session the agent writes itself a short memory note; during conversation it saves durable facts you tell it, each tagged with where it came from.

## How it avoids making things up

Honest framing: no AI system can guarantee zero hallucinations. This project is engineered to make them rare, and caught when they matter:

1. **Grounding contract in every prompt**: any fact with a number or date attached - fees, deadlines, cutoffs, salaries - must come from a tool result in the conversation, or the agent says "let me look that up" / "I don't know". Saying "I don't know" is explicitly rewarded.
2. **Spoken citations**: facts come with their source named out loud ("according to the official GATE website...").
3. **Deterministic math**: currency and budget totals are computed in Python tools.
4. **Provenance in memory**: every remembered fact records whether the user said it, the web sourced it, or it was inferred - and inferred facts are never presented back as truth.
5. **A verification gate on plans**: before any plan containing money or dates is saved, a second LLM pass checks each claim against the tool evidence actually gathered in the conversation. Unsupported claims block the save and are named, so the agent re-researches instead of persisting fiction.
6. **Grounding evals**: `RUN_EVALS=1 uv run --with pytest pytest ../tests/evals/ -v` tests the real configured model against the contract (must not invent a fee, must admit uncertainty, verifier must catch a fabricated number). Run it after changing prompts or models.

Small local models hallucinate more than big ones. For fact-heavy work (higher studies costs, target research), prefer at least a 14B model or a hosted provider - the eval suite tells you where your model stands.

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

### Keys upgrade you, no keys costs you nothing

There is nothing to configure. Every piece checks for its key and decides by itself:

| Piece | Key present → | Key absent → |
|---|---|---|
| Brain (LLM) | `ANTHROPIC_API_KEY` → Claude, `OPENAI_API_KEY` → GPT, `GOOGLE_API_KEY` → Gemini, `GROQ_API_KEY` → Groq (in that priority) | local Ollama |
| Ears (STT) | `ASSEMBLYAI_API_KEY` → AssemblyAI streaming | local Whisper |
| Voice (TTS) | `CARTESIA_API_KEY` → Cartesia sonic-2 | local Piper ([voice samples](https://rhasspy.github.io/piper-samples/)) |
| Connection | LiveKit Cloud keys → their free tier | a local `livekit-server` that `setup.sh` downloads - no account at all |

Paste a key into `livekit-voice-agent/.env.local` any time and that one piece upgrades on next start; delete it and the piece falls back to local. Force a specific provider with `LLM_PROVIDER` / `STT_PROVIDER` / `TTS_PROVIDER` when you want to override the automatics (both speech pieces also accept `openai-compatible` with a `*_BASE_URL` for local servers like Speaches or Kokoro).

Honest tradeoffs of all-local: Piper sounds more robotic than Cartesia, local Whisper adds a beat of pause after you stop talking (per-utterance, not streaming - `STT_MODEL=base` on weak machines, `medium` with a GPU), and the local LiveKit server is for using it yourself on your own machine or network. The moment you want to put your agent on the internet for other people, that's what the LiveKit Cloud free tier is for.

### When credits run out

If a hosted provider fails, the agent tells you out loud instead of going silent:

- **Credits/quota exhausted** → "My language model credits are completed. Please add credits or switch to the self-hosted model, then try again."
- **Temporary rate limit** → "I've hit a temporary rate limit. Please wait a moment and ask me again."

## What's in this repo

```
career-support-voice-agent/
    setup.sh / setup.bat        one-time setup for non-technical users
    start.sh / start.bat        one-step start (agent + web app + browser)
    livekit-voice-agent/        Python agent
        agent.py                session wiring, memory hooks, error speech
        llm_providers.py        LLM provider selection + failure classification
        agents_team/            the coach + seven specialists
        prompts/                composed instructions (base + grounding + specialty)
        tools/                  search, page reading, finance, claim verifier
        memory/                 SQLite store + session summarizer
    agent-starter-react/        Next.js 15 frontend
    tests/                      96 tests, no live credentials needed
        evals/                  opt-in grounding evals against your real LLM
    .github/workflows/ci.yml    tests on every push and PR
```

## Easy setup (for everyone)

You don't need to be a programmer. Set up once, then start with one step every time.

**One-time setup:**

1. Install [Node.js](https://nodejs.org) (LTS version) and [Ollama](https://ollama.com/download) - both are normal installers, click Next until done.
2. Download this project (green "Code" button above → Download ZIP → unzip), or `git clone` it.
3. Open a terminal in the project folder and run:
   - Mac/Linux: `./setup.sh`
   - Windows: double-click `setup.bat`
4. The setup asks for your API keys - **every one is optional**. Press Enter to skip any of them and that piece runs on your own computer instead, free forever. No accounts needed at all.

**Starting it (every time after):**

- Mac: double-click `Start Career Coach.command` (or run `./start.sh`)
- Windows: double-click `start.bat`
- Linux: run `./start.sh`

Your browser opens at http://localhost:3000 - hit Start call and talk. Press Ctrl+C in the terminal (or close the windows on Windows) to stop.

## Manual setup (for developers)

You need Python 3.10+, [uv](https://astral.sh/uv), Node.js 18+, and pnpm.

API keys - all optional (missing ones fall back to local automatically):

- **LiveKit Cloud** at https://cloud.livekit.io - project Settings → URL, API key, secret (skip = local `livekit-server`)
- **AssemblyAI** at https://www.assemblyai.com - speech to text (skip = local Whisper)
- **Cartesia** at https://play.cartesia.ai - text to speech (skip = local Piper)
- **Anthropic / OpenAI / Google / Groq** - the brain (skip = local Ollama)

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

Tests cover env setup, the agent team and its handoff graph, prompt composition, memory round-trips with provenance, tool allowlists, the claim verifier, LLM provider selection, and credit-exhaustion classification. No live API keys needed. The opt-in grounding evals (`RUN_EVALS=1`) additionally exercise your real configured LLM.

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
