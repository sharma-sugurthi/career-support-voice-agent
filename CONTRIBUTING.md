# Contributing

Thanks for your interest! This project aims to be the best open-source voice AI career coach, and contributions of any size are welcome.

## Quick start

1. Fork the repo and clone your fork.
2. Follow the setup in the [README](README.md) (Python agent + Next.js frontend).
3. Create a branch, make your change, and open a pull request against `main`.

## Before you open a PR

- Run the test suite: `cd livekit-voice-agent && uv run --with pytest pytest ../tests/ -v`
- Keep changes focused. One topic per PR is much easier to review.
- If you add an LLM provider, add it to `llm_providers.py`, `.env.example`, the README provider table, and the tests.

## Good first contributions

- New LLM/STT/TTS provider integrations
- Better career-coaching prompts (interview drills, resume review flows)
- Multilingual support
- Docker / deployment guides
- Bug reports with reproduction steps (open an issue!)

## Questions

Open a GitHub issue or discussion. If this project helps you, consider [starring it](https://github.com/sharma-sugurthi/career-support-voice-agent) or [sponsoring](https://github.com/sponsors/sharma-sugurthi).
