# RGUKT Career Support Voice Agent

This is a voice AI project I built during my final year at RGUKT (Rajiv Gandhi University of Knowledge Technologies). Students open a browser, click start, and talk to an AI that helps with career questions - resumes, placements, interview prep, higher studies, that sort of thing. The agent listens, thinks, and talks back. End to end it takes under two seconds on a normal connection.

Two separate services work together through a LiveKit room. The browser handles the mic and speaker. The Python agent handles everything else.

```
Browser (Next.js) --- LiveKit Cloud --- Python Agent
                                            STT: AssemblyAI
                                            LLM: Groq (compound-mini)
                                            TTS: Cartesia sonic-2
                                            VAD: Silero
                                            Turn detection: Multilingual ONNX
```

## What's in this repo

```
career-support-voice-agent/
    livekit-voice-agent/      Python agent
        agent.py              everything starts here
        pyproject.toml
        uv.lock
        .env.example
    agent-starter-react/      Next.js 15 frontend
        app/
        components/
        .env.example
    tests/
        agent/
            test_agent.py     16 tests, no live credentials needed
    .gitignore
    README.md
```

## What you need installed

- Python 3.10 or newer
- [uv](https://astral.sh/uv) for Python package management (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 18 or newer
- pnpm (`npm install -g pnpm`)

## API keys you need

Four services, all free tiers are enough for development and demos.

- **LiveKit Cloud** at https://cloud.livekit.io - create a project, go to Settings, grab the URL, API key, and secret
- **AssemblyAI** at https://www.assemblyai.com - just sign up and copy the API key from the dashboard
- **Groq** at https://console.groq.com - no billing required, just create an API key
- **Cartesia** at https://play.cartesia.ai - sign up and get an API key from your account

## Setting up

Start with the Python agent:

```bash
cd livekit-voice-agent
uv sync
python agent.py download-files
cp .env.example .env.local
# fill in your keys in .env.local
```

Then the frontend:

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
source .venv/bin/activate
python agent.py dev
```

```bash
# terminal 2
cd agent-starter-react
pnpm dev
```

Go to http://localhost:3000, hit Start call, and talk.

## Running the tests

```bash
source livekit-voice-agent/.venv/bin/activate
pytest tests/ -v
```

Tests cover env setup, imports, the Assistant class, and pyproject.toml. They don't need any live API keys to run.

## Why these specific tools

**Groq for the LLM** - their LPU chips are genuinely faster than GPU-based inference at this price point. For voice, if your LLM is slow the whole thing feels broken even if STT and TTS are fast. `groq/compound-mini` is free and has enough quota for a demo.

**AssemblyAI for speech to text** - the streaming model handles Indian English better than most Whisper-based options I tested. It also sends partial transcripts, so the agent can start thinking before you finish speaking.

**Cartesia for text to speech** - `sonic-2` generates audio faster than real-time, which means the agent starts speaking within about 200ms of the first token from the LLM. ElevenLabs sounds slightly better but the free tier latency is noticeably worse.

**The subprocess thing** - LiveKit agents 1.3.x runs the LLM in a separate OS process via IPC. This means if you create an OpenAI client object in the main process and try to pass it to the session, it gets dropped because Python can't serialize it across the process boundary. The fix is to create the Groq client inside `my_agent()` so it gets created fresh in the right process.

## Known issues

Groq's free tier has a token per minute limit on compound-mini. In normal conversation you won't hit it. If you're testing rapidly by connecting and disconnecting many times in a row, you'll get a rate limit error and the call will fail. Just wait a minute and try again.

This setup runs one session at a time. If you need more concurrent users, run multiple agent processes.

The ONNX turn-detector model runs on CPU. Works fine on an i3. Don't try running a local LLM on the same machine, it won't work without a GPU.

## License

Apache 2.0
