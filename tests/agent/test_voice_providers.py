"""Tests for STT/TTS provider selection and the local engines' plumbing.
Engines are mocked - no model downloads, no network."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from stt_providers import (  # noqa: E402
    WhisperLocalSTT,
    create_stt,
    resolve_stt_provider,
)
from tts_providers import (  # noqa: E402
    PiperLocalTTS,
    create_tts,
    resolve_tts_provider,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestProviderSelection:
    def test_auto_uses_cloud_when_keys_exist(self):
        with patch.dict(
            os.environ,
            {"ASSEMBLYAI_API_KEY": "real-key-123", "CARTESIA_API_KEY": "sk_car_real"},
        ):
            os.environ.pop("STT_PROVIDER", None)
            os.environ.pop("TTS_PROVIDER", None)
            assert resolve_stt_provider() == "assemblyai"
            assert resolve_tts_provider() == "cartesia"

    def test_auto_falls_back_to_local_without_keys(self):
        with patch.dict(os.environ, {}, clear=False):
            for var in ("STT_PROVIDER", "TTS_PROVIDER", "ASSEMBLYAI_API_KEY", "CARTESIA_API_KEY"):
                os.environ.pop(var, None)
            assert resolve_stt_provider() == "whisper-local"
            assert resolve_tts_provider() == "piper-local"

    def test_free_mode_providers_resolve(self):
        with patch.dict(
            os.environ, {"STT_PROVIDER": "whisper-local", "TTS_PROVIDER": "piper-local"}
        ):
            assert resolve_stt_provider() == "whisper-local"
            assert resolve_tts_provider() == "piper-local"

    def test_unknown_providers_raise(self):
        with patch.dict(os.environ, {"STT_PROVIDER": "nope"}):
            with pytest.raises(ValueError, match="Unknown STT_PROVIDER"):
                resolve_stt_provider()
        with patch.dict(os.environ, {"TTS_PROVIDER": "nope"}):
            with pytest.raises(ValueError, match="Unknown TTS_PROVIDER"):
                resolve_tts_provider()

    def test_create_local_engines_without_loading_models(self):
        """Construction must be instant - models load lazily on first use."""
        with patch.dict(
            os.environ, {"STT_PROVIDER": "whisper-local", "TTS_PROVIDER": "piper-local"}
        ):
            s = create_stt()
            t = create_tts()
        assert isinstance(s, WhisperLocalSTT) and s._model is None
        assert isinstance(t, PiperLocalTTS) and t._voice is None

    def test_openai_compatible_requires_base_url(self):
        with patch.dict(os.environ, {"STT_PROVIDER": "openai-compatible"}, clear=False):
            os.environ.pop("STT_BASE_URL", None)
            with pytest.raises(ValueError, match="STT_BASE_URL"):
                create_stt()
        with patch.dict(os.environ, {"TTS_PROVIDER": "openai-compatible"}, clear=False):
            os.environ.pop("TTS_BASE_URL", None)
            with pytest.raises(ValueError, match="TTS_BASE_URL"):
                create_tts()

    def test_local_stt_is_nonstreaming_so_vad_wraps_it(self):
        """livekit-agents auto-wraps non-streaming STT with the session VAD -
        that only happens if capabilities.streaming is False."""
        assert WhisperLocalSTT().capabilities.streaming is False


class TestWhisperLocalTranscription:
    def test_recognize_assembles_segment_texts(self):
        from livekit import rtc

        stt_engine = WhisperLocalSTT()
        seg1, seg2 = MagicMock(text=" I want a "), MagicMock(text="mock interview. ")
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (iter([seg1, seg2]), MagicMock())

        async def fake_ensure():
            return fake_model

        stt_engine._ensure_model = fake_ensure
        # 0.5s of silence @16kHz mono int16
        frame = rtc.AudioFrame(
            data=b"\x00\x00" * 8000, sample_rate=16000, num_channels=1, samples_per_channel=8000
        )
        event = _run(stt_engine.recognize(buffer=frame))
        assert event.alternatives[0].text == "I want a mock interview."


class TestPiperLocalSynthesis:
    def test_chunked_stream_pushes_pcm(self):
        tts_engine = PiperLocalTTS()
        chunk = MagicMock(audio_int16_bytes=b"\x01\x02" * 100)
        fake_voice = MagicMock()
        fake_voice.synthesize.return_value = iter([chunk, chunk])
        fake_voice.config.sample_rate = 22050

        async def fake_ensure():
            return fake_voice

        tts_engine._ensure_voice = fake_ensure

        async def scenario():
            # ChunkedStream starts internal tasks, so it needs a running loop
            stream = tts_engine.synthesize("hello there")
            emitter = MagicMock()
            try:
                await stream._run(emitter)
            finally:
                await stream.aclose()
            return emitter

        emitter = _run(scenario())

        emitter.initialize.assert_called_once()
        kwargs = emitter.initialize.call_args.kwargs
        assert kwargs["sample_rate"] == 22050
        assert kwargs["mime_type"] == "audio/pcm"
        assert emitter.push.call_count == 2
        emitter.flush.assert_called_once()
