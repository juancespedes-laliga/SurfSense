"""Graph node: one model call that answers from the retrieved excerpts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .models import load_small_llm, load_vision_llm
from .retrieve import latest_question
from .routing import latest_images
from .state import DocumentsOnlyState

_PROMPT = (Path(__file__).with_name("answer_prompt.md")).read_text(encoding="utf-8")
_IMAGE_NOTE = (
    "The user attached images to their latest message. Read and describe them "
    "when the question is about them; those statements need no citation. Keep "
    "using the excerpts, with citations, for anything about the documents."
)
_NO_VISION_NOTE = (
    "The user attached images, but no vision model is set up, so you cannot see "
    "them. Say so in one sentence, then answer from the excerpts."
)
_SMALL_TALK_PROMPT = (
    "You are the assistant of the user's document workspace. The user sent a "
    "greeting, thanks or a short acknowledgement. Reply in one or two friendly "
    "sentences in the language of their message, and offer to answer questions "
    "about their documents. Do not make up any document content."
)
# Earlier turns give follow-ups like "where was it founded?" their subject.
_HISTORY_MESSAGES = 6
_NO_CONTEXT = (
    "<retrieved_context>\nNo matching excerpts were found.\n</retrieved_context>"
)


def _plain_text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
    return str(content or "").strip()


def _history(messages: list[Any]) -> list[Any]:
    """Prior user/assistant text only; tool traffic from the main agent is dropped."""
    prior: list[Any] = []
    for message in messages[:-1]:
        if isinstance(message, HumanMessage):
            text = latest_question([message])
        elif isinstance(message, AIMessage) and not message.tool_calls:
            text = _plain_text(message.content)
        else:
            continue
        if text:
            prior.append(type(message)(content=text))
    return prior[-_HISTORY_MESSAGES:]


def build_answer_node(llm: Any, workspace_id: int):
    async def answer(state: DocumentsOnlyState) -> dict[str, Any]:
        messages = state.get("messages", [])
        context = state.get("retrieved_context") or _NO_CONTEXT
        question = latest_question(messages)
        text = f"{context}\n\n{question}"

        images = latest_images(messages)
        vision_llm = await load_vision_llm(workspace_id) if images else None
        if vision_llm is not None:
            model, system = vision_llm, f"{_PROMPT}\n\n{_IMAGE_NOTE}"
            content: Any = [{"type": "text", "text": text}, *images]
        else:
            model, content = llm, text
            system = f"{_PROMPT}\n\n{_NO_VISION_NOTE}" if images else _PROMPT

        prompt = [
            SystemMessage(content=system),
            *_history(messages),
            HumanMessage(content=content),
        ]
        reply = await model.ainvoke(prompt)
        return {"messages": [reply]}

    return answer


def build_small_talk_node(llm: Any, workspace_id: int):
    """Greetings and thanks: no search, and the small model when one is set."""

    async def small_talk(state: DocumentsOnlyState) -> dict[str, Any]:
        messages = state.get("messages", [])
        model = await load_small_llm(workspace_id) or llm
        prompt = [
            SystemMessage(content=_SMALL_TALK_PROMPT),
            *_history(messages),
            HumanMessage(content=latest_question(messages)),
        ]
        reply = await model.ainvoke(prompt)
        return {"messages": [reply]}

    return small_talk


__all__ = ["build_answer_node", "build_small_talk_node"]
