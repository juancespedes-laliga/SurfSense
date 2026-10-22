"""Tests for how the documents-only chat reads the user's questions."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.chat.documents_only.answer import _history
from app.agents.chat.documents_only.retrieve import _search_query, latest_question
from app.agents.chat.documents_only.switch import documents_only_enabled

pytestmark = pytest.mark.unit


def test_latest_question_drops_mention_paths_and_speaker_prefix():
    message = HumanMessage(
        content="**[Ana]:** `/documents/manual.pdf` ¿Cuáles son los módulos?"
    )
    assert latest_question([message]) == "¿Cuáles son los módulos?"


def test_latest_question_reads_wrapped_query_and_text_parts():
    message = HumanMessage(
        content=[
            {"type": "text", "text": "<ctx/>\n\n<user_query>¿Quién?</user_query>"},
            {"type": "image_url", "image_url": {"url": "data:"}},
        ]
    )
    assert latest_question([message]) == "¿Quién?"


def test_search_query_adds_previous_question_for_follow_ups():
    messages = [
        HumanMessage(content="¿Quién fundó Café El Mirador?"),
        AIMessage(content="Laura Restrepo [1]."),
        HumanMessage(content="¿En qué parte?"),
    ]
    assert _search_query(messages) == "¿Quién fundó Café El Mirador? ¿En qué parte?"


def test_history_keeps_only_prior_text_turns():
    messages = [
        HumanMessage(content="`/documents/a.pdf` hola"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="raw", tool_call_id="1"),
        AIMessage(content="respuesta"),
        HumanMessage(content="siguiente"),
    ]
    assert [m.content for m in _history(messages)] == ["hola", "respuesta"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("TRUE", True),
        ("on", True),
        ("false", False),
        ("", False),
    ],
)
def test_switch(monkeypatch, value, expected):
    monkeypatch.setenv("SURFSENSE_DOCUMENTS_ONLY_CHAT", value)
    assert documents_only_enabled() is expected
