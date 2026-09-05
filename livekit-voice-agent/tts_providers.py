"""Text-to-speech provider selection.

    TTS_PROVIDER=auto            (default) CARTESIA_API_KEY present -> the
                                 cloud service; no key -> piper-local
    TTS_PROVIDER=cartesia        cloud, free monthly allowance
    TTS_PROVIDER=piper-local     Piper voices on YOUR computer - no API key,
                                 no account, fully offline, CPU real-time
    TTS_PROVIDER=openai-compatible  any server speaking the OpenAI speech API
                                 (e.g. a local Kokoro server) via TTS_BASE_URL

TTS_VOICE overrides the voice (piper-local default: en_US-lessac-medium,
~60MB, auto-downloaded on first start to livekit-voice-agent/models/).
Browse voices at https://rhasspy.github.io/piper-samples/
"""
import asyncio
import logging
import os
from pathlib import Path

from livekit.agents import tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

from providers_common import has_key

logger = logging.getLogger("career-agent.tts")

DEFAULT_PROVIDER = "auto"
SUPPORTED_PROVIDERS = ("auto", "cartesia", "piper-local", "openai-compatible")

DEFAULT_VOICES = {
    "cartesia": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    "piper-local": "en_US-lessac-medium",
    "openai-compatible": "alloy",
}

MODELS_DIR = Path(__file__).parent / "models"


def resolve_tts_provider() -> str:
    provider = os.environ.get("TTS_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown TTS_PROVIDER '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if provider == "auto":
        return "cartesia" if has_key("CARTESIA_API_KEY") else "piper-local"
    return provider


class PiperLocalTTS(tts.TTS):
    """Offline TTS via Piper. Loads (and if needed downloads) the voice
    lazily on first synthesis, off the event loop."""

    def __init__(self, voice: str = "en_US-lessac-medium") -> None:
        # sample_rate here is a placeholder until the voice config is loaded;
        # each synthesis initializes the emitter with the voice's real rate.
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=22050,
            num_channels=1,
        )
        self._voice_name = voice
        self._voice = None
        self._load_lock = asyncio.Lock()

    async def _ensure_voice(self):
        if self._voice is None:
            async with self._load_lock:
                if self._voice is None:
                    def _load():
                        from piper import PiperVoice
                        from piper.download_voices import download_voice

                        MODELS_DIR.mkdir(parents=True, exist_ok=True)
                        model_path = MODELS_DIR / f"{self._voice_name}.onnx"
                        if not model_path.exists():
                            logger.info(
                                "downloading piper voice '%s' (one time, ~60MB)...",
                                self._voice_name,
                            )
                            download_voice(self._voice_name, MODELS_DIR)
                        return PiperVoice.load(model_path)

                    self._voice = await asyncio.to_thread(_load)
        return self._voice

    def synthesize(self, text: str, *, conn_options=DEFAULT_API_CONNECT_OPTIONS) -> "tts.ChunkedStream":
        return _PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _PiperChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: PiperLocalTTS, input_text: str, conn_options) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._piper_tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        voice = await self._piper_tts._ensure_voice()

        def _synthesize() -> tuple[int, list[bytes]]:
            chunks = [c.audio_int16_bytes for c in voice.synthesize(self.input_text)]
            return voice.config.sample_rate, chunks

        sample_rate, chunks = await asyncio.to_thread(_synthesize)
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        for chunk in chunks:
            output_emitter.push(chunk)
        output_emitter.flush()


def create_tts():
    """Build the TTS for the configured provider. Called inside the job
    subprocess, same as create_llm."""
    provider = resolve_tts_provider()
    voice = os.environ.get("TTS_VOICE") or DEFAULT_VOICES[provider]
    logger.info("TTS: %s (%s)", provider, voice)

    if provider == "cartesia":
        from livekit.plugins import cartesia

        return cartesia.TTS(model="sonic-2", voice=voice)

    if provider == "piper-local":
        return PiperLocalTTS(voice=voice)

    if provider == "openai-compatible":
        from livekit.plugins import openai as lk_openai

        base_url = os.environ.get("TTS_BASE_URL")
        if not base_url:
            raise ValueError(
                "TTS_PROVIDER=openai-compatible requires TTS_BASE_URL "
                "(e.g. http://localhost:8880/v1 for a local Kokoro server)"
            )
        return lk_openai.TTS(
            model=os.environ.get("TTS_MODEL", "tts-1"),
            voice=voice,
            base_url=base_url,
            api_key=os.environ.get("TTS_API_KEY", "not-needed"),
        )

    raise ValueError(f"Unhandled TTS provider: {provider}")  # pragma: no cover
