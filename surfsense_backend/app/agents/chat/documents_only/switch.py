"""Whether chat turns use the documents-only graph instead of the main agent."""

from __future__ import annotations

import os

_ENV = "SURFSENSE_DOCUMENTS_ONLY_CHAT"
_SMALL_MODEL_ENV = "SURFSENSE_DOCUMENTS_ONLY_SMALL_MODEL"


def documents_only_enabled() -> bool:
    """Read per call so flipping the env var needs a restart, not a rebuild.

    While it is on, every turn goes to this graph whatever scope the composer
    sent, so web search, connectors and tools stay off until it is turned off.
    """
    raw = os.environ.get(_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def small_model_name() -> str:
    """Model id for greetings and thanks, e.g. ``qwen2.5:1.5b``; empty keeps them on the chat model."""
    return os.environ.get(_SMALL_MODEL_ENV, "").strip()


__all__ = ["documents_only_enabled", "small_model_name"]
