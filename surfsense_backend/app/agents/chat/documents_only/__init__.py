"""Documents-only chat: one knowledge-base search and one model call per turn.

For local models that cannot drive the main agent's tool loop quickly.
"""

from .graph import build_documents_only_agent
from .switch import documents_only_enabled

__all__ = ["build_documents_only_agent", "documents_only_enabled"]
