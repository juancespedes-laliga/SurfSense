"""Compile the documents-only chat: retrieve once, then answer once.

Greetings and thanks skip the search and go to the small model; turns with
images are answered by the vision model. Built per turn and never cached:
compiling a few plain nodes is cheaper than the main agent's cache lookup, and
nothing in it depends on the thread.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat.shared.context import SurfSenseContextSchema

from .answer import build_answer_node, build_small_talk_node
from .retrieve import build_retrieve_node, latest_question
from .routing import is_small_talk, latest_images
from .state import DocumentsOnlyState


def route_turn(state: DocumentsOnlyState) -> str:
    messages = state.get("messages", [])
    if not latest_images(messages) and is_small_talk(latest_question(messages)):
        return "small_talk"
    return "retrieve"


def build_documents_only_agent(
    *, llm: Any, workspace_id: int, checkpointer: Any
) -> Any:
    graph = StateGraph(DocumentsOnlyState, context_schema=SurfSenseContextSchema)
    graph.add_node("retrieve", build_retrieve_node(workspace_id))
    graph.add_node("answer", build_answer_node(llm, workspace_id))
    graph.add_node("small_talk", build_small_talk_node(llm, workspace_id))
    graph.add_conditional_edges(
        START, route_turn, {"retrieve": "retrieve", "small_talk": "small_talk"}
    )
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_edge("small_talk", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_documents_only_agent", "route_turn"]
