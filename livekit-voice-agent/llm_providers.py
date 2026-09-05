"""LLM provider selection for the voice agent.

Default is "auto": whichever commercial API key you have gets used
(quality order: anthropic > openai > google > groq), and with no keys at
all the LLM runs locally via Ollama for free. Override with LLM_PROVIDER:

    auto        (default) key present -> that provider; no keys -> ollama
    ollama      self-hosted via Ollama, no API key needed
    openai-compatible     any self-hosted OpenAI-compatible server (vLLM,
                          llama.cpp, LM Studio, TGI, ...)
    anthropic             Claude via ANTHROPIC_API_KEY
    openai                GPT via OPENAI_API_KEY
    google                Gemini via GOOGLE_API_KEY
    groq                  Groq cloud via GROQ_API_KEY

Each provider's model can be overridden with LLM_MODEL. Plugin imports are
lazy so you only need the packages for the provider you actually use.
"""
import logging
import os

from providers_common import has_key

logger = logging.getLogger("career-agent.llm")

SUPPORTED_PROVIDERS = (
    "auto",
    "ollama",
    "openai-compatible",
    "anthropic",
    "openai",
    "google",
    "groq",
)

DEFAULT_PROVIDER = "auto"

# auto mode: first provider whose key exists wins, else local
_AUTO_ORDER = (
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("google", "GOOGLE_API_KEY"),
    ("groq", "GROQ_API_KEY"),
)

# Default model per provider, override with LLM_MODEL
DEFAULT_MODELS = {
    "ollama": "llama3.1:8b",
    "openai-compatible": "meta-llama/Llama-3.1-8B-Instruct",
    "anthropic": "claude-opus-5",
    "openai": "gpt-5.1",
    "google": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
}


def resolve_provider() -> str:
    """Read and validate LLM_PROVIDER. In auto mode (the default), a real
    commercial API key selects its provider; with no keys the LLM runs
    locally via Ollama."""
    provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if provider != "auto":
        return provider
    for candidate, env_var in _AUTO_ORDER:
        if has_key(env_var):
            return candidate
    return "ollama"


def resolve_model(provider: str) -> str:
    return os.environ.get("LLM_MODEL") or DEFAULT_MODELS[provider]


def create_llm():
    """Build the LiveKit LLM plugin for the configured provider.

    Must be called inside the agent job process (livekit-agents runs jobs in
    a subprocess, so clients created in the parent process don't survive the
    IPC boundary).
    """
    provider = resolve_provider()
    model = resolve_model(provider)
    logger.info("LLM: %s (%s)", provider, model)

    if provider == "ollama":
        from livekit.plugins import openai as lk_openai

        return lk_openai.LLM.with_ollama(
            model=model,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )

    if provider == "openai-compatible":
        from livekit.plugins import openai as lk_openai

        base_url = os.environ.get("LLM_BASE_URL")
        if not base_url:
            raise ValueError(
                "LLM_PROVIDER=openai-compatible requires LLM_BASE_URL "
                "(e.g. http://localhost:8000/v1 for vLLM)"
            )
        return lk_openai.LLM(
            model=model,
            base_url=base_url,
            api_key=os.environ.get("LLM_API_KEY", "not-needed"),
        )

    if provider == "anthropic":
        from livekit.plugins import anthropic as lk_anthropic

        return lk_anthropic.LLM(model=model)

    if provider == "openai":
        from livekit.plugins import openai as lk_openai

        return lk_openai.LLM(model=model)

    if provider == "google":
        from livekit.plugins import google as lk_google

        return lk_google.LLM(model=model)

    if provider == "groq":
        from livekit.plugins import openai as lk_openai

        # Groq speaks the OpenAI API
        return lk_openai.LLM(
            model=model,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY"),
        )

    raise ValueError(f"Unhandled provider: {provider}")  # pragma: no cover


# ---------------------------------------------------------------------------
# LLM failure classification, so the agent can SAY what went wrong instead of
# going silent when credits run out or a rate limit hits.
# ---------------------------------------------------------------------------

_QUOTA_MARKERS = (
    "insufficient_quota",
    "insufficient credits",
    "credit balance",
    "credits",
    "quota exceeded",
    "exceeded your current quota",
    "billing",
    "payment required",
    "402",
)

_RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "429",
    "too many requests",
    "overloaded",
    "503",
)


def classify_llm_error(error) -> str | None:
    """Classify an LLM error as 'quota' (credits gone), 'rate_limit' (wait
    and retry), or None (something else)."""
    text = str(error).lower()
    if any(marker in text for marker in _QUOTA_MARKERS):
        return "quota"
    if any(marker in text for marker in _RATE_LIMIT_MARKERS):
        return "rate_limit"
    return None


SPOKEN_ERROR_MESSAGES = {
    "quota": (
        "I'm sorry, my language model credits are completed. "
        "Please add credits or switch to the self-hosted model, then try again."
    ),
    "rate_limit": (
        "I've hit a temporary rate limit. "
        "Please wait a moment and ask me again."
    ),
}
