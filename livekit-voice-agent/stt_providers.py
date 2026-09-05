"""Speech-to-text provider selection.

    STT_PROVIDER=auto            (default) ASSEMBLYAI_API_KEY present -> the
                                 cloud service; no key -> whisper-local
    STT_PROVIDER=assemblyai      cloud streaming, free signup credits
    STT_PROVIDER=whisper-local   Whisper on YOUR computer via faster-whisper -
                                 no API key, no account, fully offline
    STT_PROVIDER=openai-compatible  any server speaking the OpenAI audio API
                                 (e.g. Speaches) via STT_BASE_URL

STT_MODEL overrides the model (whisper-local default: "small" - a good
CPU accuracy/speed balance; use "base" on weak machines, "medium" on strong).

The local provider is non-streaming; livekit-agents automatically wraps it
with the session's Silero VAD, so turn-taking still works the same.
"""
import asyncio
import io
import logging
import os
import wave

from livekit.agents import stt
from livekit.agents.types import NOT_GIVEN
from livekit.agents.utils.audio import merge_frames

from providers_common import has_key

logger = logging.getLogger("career-agent.stt")

DEFAULT_PROVIDER = "auto"
SUPPORTED_PROVIDERS = ("auto", "assemblyai", "whisper-local", "openai-compatible")

DEFAULT_MODELS = {
    "assemblyai": "",  # plugin default
    "whisper-local": "small",
    "openai-compatible": "whisper-1",
}


def resolve_stt_provider() -> str:
    provider = os.environ.get("STT_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown STT_PROVIDER '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if provider == "auto":
        return "assemblyai" if has_key("ASSEMBLYAI_API_KEY") else "whisper-local"
    return provider


class WhisperLocalSTT(stt.STT):
    """Offline Whisper via faster-whisper. Non-streaming: the framework's VAD
    StreamAdapter feeds it one utterance at a time."""

    def __init__(self, model: str = "small") -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._model_name = model
        self._model = None
        self._load_lock = asyncio.Lock()

    async def _ensure_model(self):
        if self._model is None:
            async with self._load_lock:
                if self._model is None:
                    def _load():
                        from faster_whisper import WhisperModel

                        # int8 keeps CPU memory/latency sane; first call
                        # downloads the model to the local HF cache
                        return WhisperModel(self._model_name, device="auto", compute_type="int8")

                    logger.info("loading local whisper model '%s'...", self._model_name)
                    self._model = await asyncio.to_thread(_load)
        return self._model

    async def _recognize_impl(self, buffer, *, language=NOT_GIVEN, conn_options) -> stt.SpeechEvent:
        model = await self._ensure_model()
        frame = merge_frames(buffer)

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as w:
            w.setnchannels(frame.num_channels)
            w.setsampwidth(2)  # int16
            w.setframerate(frame.sample_rate)
            w.writeframes(frame.data)
        wav_io.seek(0)

        lang = language if isinstance(language, str) and language else None

        def _transcribe() -> str:
            segments, _info = model.transcribe(wav_io, language=lang, beam_size=1)
            return " ".join(s.text.strip() for s in segments).strip()

        text = await asyncio.to_thread(_transcribe)
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language=lang or "en", text=text)],
        )


def create_stt():
    """Build the STT for the configured provider. Called inside the job
    subprocess, same as create_llm."""
    provider = resolve_stt_provider()
    model = os.environ.get("STT_MODEL") or DEFAULT_MODELS[provider]
    logger.info("STT: %s%s", provider, f" ({model})" if model else "")

    if provider == "assemblyai":
        from livekit.plugins import assemblyai

        return assemblyai.STT()

    if provider == "whisper-local":
        return WhisperLocalSTT(model=model)

    if provider == "openai-compatible":
        from livekit.plugins import openai as lk_openai

        base_url = os.environ.get("STT_BASE_URL")
        if not base_url:
            raise ValueError(
                "STT_PROVIDER=openai-compatible requires STT_BASE_URL "
                "(e.g. http://localhost:8000/v1 for a Speaches server)"
            )
        return lk_openai.STT(
            model=model,
            base_url=base_url,
            api_key=os.environ.get("STT_API_KEY", "not-needed"),
        )

    raise ValueError(f"Unhandled STT provider: {provider}")  # pragma: no cover
