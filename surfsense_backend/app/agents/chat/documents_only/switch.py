"""Whether chat turns use the documents-only graph instead of the main agent."""

from __future__ import annotations

import os

from app.agents.chat.retrieval_scope import RetrievalScope

_ENV = "SURFSENSE_DOCUMENTS_ONLY_CHAT"


def documents_only_enabled(retrieval_scope: RetrievalScope) -> bool:
    """Read per call so flipping the env var needs a restart, not a rebuild.

    A turn the user scoped to the web still goes to the main agent: this graph
    can only read documents.
    """
    raw = os.environ.get(_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"} and retrieval_scope.allows_documents


__all__ = ["documents_only_enabled"]
