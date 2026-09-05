"""Print which provider each piece of the stack will use - called by the
start scripts so users see their running mode at a glance."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env.local")

import os  # noqa: E402

from llm_providers import resolve_model, resolve_provider  # noqa: E402
from stt_providers import resolve_stt_provider  # noqa: E402
from tts_providers import resolve_tts_provider  # noqa: E402


def main() -> None:
    llm = resolve_provider()
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    livekit_mode = "local" if "localhost" in livekit_url or "127.0.0.1" in livekit_url else "cloud"
    parts = [
        f"LLM={llm} ({resolve_model(llm)})",
        f"STT={resolve_stt_provider()}",
        f"TTS={resolve_tts_provider()}",
        f"LiveKit={livekit_mode}",
    ]
    print("Running with: " + "  ".join(parts))


if __name__ == "__main__":
    main()
