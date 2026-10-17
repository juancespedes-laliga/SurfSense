"""Graph node: one model call that answers from the retrieved excerpts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .retrieve import latest_question
from .state import DocumentsOnlyState

_PROMPT = (Path(__file__).with_name("answer_prompt.md")).read_text(encoding="utf-8")
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


def build_answer_node(llm: Any):
    async def answer(state: DocumentsOnlyState) -> dict[str, Any]:
        messages = state.get("messages", [])
        context = state.get("retrieved_context") or _NO_CONTEXT
        question = latest_question(messages)
        prompt = [
            SystemMessage(content=_PROMPT),
            *_history(messages),
            HumanMessage(content=f"{context}\n\n{question}"),
        ]
        reply = await llm.ainvoke(prompt)
        return {"messages": [reply]}

    return answer


__all__ = ["build_answer_node"]
