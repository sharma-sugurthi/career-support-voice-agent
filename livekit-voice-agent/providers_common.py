"""Shared helpers for provider auto-selection.

The rule of the whole project: a real API key means the user wants the
commercial service, an absent key means that piece runs locally for free.
"""
import os
import re

# values copied from .env.example placeholders don't count as real keys
_PLACEHOLDER = re.compile(r"xxxx|your-project", re.IGNORECASE)


def has_key(env_var: str) -> bool:
    """True only when the env var holds what looks like a real value."""
    value = os.environ.get(env_var, "").strip()
    return bool(value) and not _PLACEHOLDER.search(value)
