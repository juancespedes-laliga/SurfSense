"""Tests for extending a match to the end of its section."""

from __future__ import annotations

import pytest

from app.agents.chat.documents_only import section_tail
from app.agents.chat.multi_agent_chat.shared.retrieval.models import ChunkHit

pytestmark = pytest.mark.unit


def _chunk(position: int, content: str) -> ChunkHit:
    return ChunkHit(chunk_id=position, content=content, position=position, score=0.0)


def _following(*chunks: ChunkHit) -> dict[tuple[int, int], ChunkHit]:
    return {(1, chunk.position): chunk for chunk in chunks}


def test_tail_runs_to_the_table_and_stops_at_the_next_heading():
    following = _following(
        _chunk(11, "intro"),
        _chunk(12, "Los 5 momentos se resumen así:"),
        _chunk(13, "| OPORTUNIDAD | POR QUÉ |"),
        _chunk(14, "## Recomendaciones"),
    )
    tail = section_tail._section_tail(following, 1, 10)
    assert [chunk.position for chunk in tail] == [11, 12, 13]


def test_tail_stops_before_another_match():
    following = _following(_chunk(11, "a"), _chunk(13, "c"))
    tail = section_tail._section_tail(following, 1, 10)
    assert [chunk.position for chunk in tail] == [11]


def test_tail_keeps_the_chunk_that_crosses_the_section_budget(monkeypatch):
    monkeypatch.setattr(section_tail, "_SECTION_CHARS", 5)
    following = _following(_chunk(11, "abc"), _chunk(12, "defgh"), _chunk(13, "i"))
    tail = section_tail._section_tail(following, 1, 10)
    assert [chunk.position for chunk in tail] == [11, 12]
