"""Graph node: search the knowledge base once for the user's latest question."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.shared.citations import load_registry
from app.agents.chat.multi_agent_chat.shared.retrieval import SearchScope, build_context
from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.runtime.references import referenced_document_ids
from app.agents.chat.shared.context import SurfSenseContextSchema
from app.db import shielded_async_session
from app.services.reranker_service import RerankerService

from .section_tail import with_section_tails
from .state import DocumentsOnlyState

# Matches the main agent's search_knowledge_base default; enough for a
# focused answer while keeping the prompt small for local models.
_TOP_K = 5

_USER_QUERY = re.compile(r"<user_query>(.*?)</user_query>", re.DOTALL)
# Mention chips arrive rewritten to `/documents/...` paths; they scope the
# search but are noise inside the query text.
_MENTION_PATH = re.compile(r"`/[^`]*`")
_SPEAKER_PREFIX = re.compile(r"^\*\*\[[^\]]*\]:\*\*\s*")


def latest_question(messages: list[Any]) -> str:
    questions = _questions(messages, limit=1)
    return questions[0] if questions else ""


def _search_query(messages: list[Any]) -> str:
    """Latest question plus the one before it.

    A follow-up like "where was it founded?" names no subject; the previous
    question supplies it, and the extra terms cost a single-pass search little.
    """
    return " ".join(reversed(_questions(messages, limit=2)))


def _questions(messages: list[Any], *, limit: int) -> list[str]:
    found: list[str] = []
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and (
            text := _question_text(message.content)
        ):
            found.append(text)
            if len(found) == limit:
                break
    return found


def _question_text(content: Any) -> str:
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    text = str(content or "")
    if match := _USER_QUERY.search(text):
        text = match.group(1)
    text = _SPEAKER_PREFIX.sub("", text)
    return _MENTION_PATH.sub(" ", text).strip()


def build_retrieve_node(workspace_id: int):
    reranker = RerankerService.get_reranker_instance()

    async def retrieve(
        state: DocumentsOnlyState, runtime: Runtime[SurfSenseContextSchema]
    ) -> dict[str, Any]:
        query = _search_query(state.get("messages", []))
        if not query:
            return {"retrieved_context": None}

        context = runtime.context
        registry = load_registry(state)
        async with shielded_async_session() as session:
            pinned = await referenced_document_ids(
                session,
                workspace_id=workspace_id,
                document_ids=getattr(context, "mentioned_document_ids", None),
                folder_ids=getattr(context, "mentioned_folder_ids", None),
            )
            hits = await search_chunks(
                session,
                workspace_id=workspace_id,
                query=query,
                scope=SearchScope(document_ids=pinned or None),
                top_k=_TOP_K,
            )
            hits = await with_section_tails(session, hits)
        rendered = await asyncio.to_thread(
            build_context, query, hits, registry, reranker=reranker
        )
        return {"retrieved_context": rendered, "citation_registry": registry}

    return retrieve


__all__ = ["build_retrieve_node", "latest_question"]
