"""Graph state for the documents-only chat.

Keys and reducers match the main agent's, so a thread can switch between the
two graphs without losing history or citation numbering.
"""

from __future__ import annotations

from typing import Annotated, Any, NotRequired

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.state.reducers import (
    _citation_registry_merge_reducer,
)


class DocumentsOnlyState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    citation_registry: NotRequired[
        Annotated[CitationRegistry, _citation_registry_merge_reducer]
    ]
    retrieved_context: NotRequired[str | None]
    # Sent by the chat input builder; accepted so the input is not rejected.
    workspace_id: NotRequired[Any]
    request_id: NotRequired[Any]
    turn_id: NotRequired[Any]


__all__ = ["DocumentsOnlyState"]
