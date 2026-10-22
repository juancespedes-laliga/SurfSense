"""Pick which model handles a turn, by fixed rules rather than a model call.

Asking a model to choose would add one more call per turn, which is the load
this routing exists to avoid on a single local GPU.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from langchain_core.messages import HumanMessage

# Every word of a small-talk message must be in this list. Kept to greetings,
# thanks and acknowledgements: anything that could be a question about the
# documents goes to the main model.
_SMALL_TALK_WORDS = frozenset(
    {
        "hola",
        "buenas",
        "buenos",
        "buen",
        "dia",
        "dias",
        "tardes",
        "noches",
        "saludos",
        "hey",
        "hi",
        "hello",
        "gracias",
        "muchas",
        "mil",
        "thanks",
        "thank",
        "you",
        "ok",
        "okay",
        "vale",
        "listo",
        "dale",
        "claro",
        "perfecto",
        "entendido",
        "genial",
        "excelente",
        "super",
        "bien",
        "muy",
        "si",
        "no",
        "de",
        "nada",
        "chao",
        "adios",
        "hasta",
        "luego",
        "pronto",
        "bye",
    }
)
_SMALL_TALK_MAX_WORDS = 6
_WORD = re.compile(r"[a-z]+")


def _normalized_words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    return _WORD.findall(folded.encode("ascii", "ignore").decode())


def is_small_talk(text: str) -> bool:
    words = _normalized_words(text)
    return 0 < len(words) <= _SMALL_TALK_MAX_WORDS and all(
        word in _SMALL_TALK_WORDS for word in words
    )


def latest_images(messages: list[Any]) -> list[dict[str, Any]]:
    """Image parts of the latest user message, as the chat input builder sent them."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message.content
            if not isinstance(content, list):
                return []
            return [
                part
                for part in content
                if isinstance(part, dict) and part.get("type") == "image_url"
            ]
    return []


__all__ = ["is_small_talk", "latest_images"]
