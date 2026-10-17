"""Compile the documents-only chat: retrieve once, then answer once.

Built per turn and never cached: compiling two plain nodes is cheaper than the
main agent's cache lookup, and nothing in it depends on the thread.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat.shared.context import SurfSenseContextSchema

from .answer import build_answer_node
from .retrieve import build_retrieve_node
from .state import DocumentsOnlyState


def build_documents_only_agent(
    *, llm: Any, workspace_id: int, checkpointer: Any
) -> Any:
    graph = StateGraph(DocumentsOnlyState, context_schema=SurfSenseContextSchema)
    graph.add_node("retrieve", build_retrieve_node(workspace_id))
    graph.add_node("answer", build_answer_node(llm))
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_documents_only_agent"]
