"""Extend each match to the end of its section, so a heading brings its body.

Chunking separates a heading ("the 5 moments are:") from the table or list
under it, and the body rarely repeats the words the user searched for. With a
single search per turn there is no second chance to fetch it, so the chunks
after a match are added in document order until the next markdown heading.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.retrieval.models import (
    ChunkHit,
    DocumentHit,
)
from app.db import Chunk

# Sentence-sized chunks put a short section's table 10 chunks after its
# heading (the SIGMN01 hand-hygiene case), so look that far and a bit more.
_LOOKAHEAD_CHUNKS = 15
# Per section and per turn, in characters: one long table fits, and the whole
# prompt stays a few thousand tokens for a local model.
_SECTION_CHARS = 3_000
_TURN_CHARS = 9_000


async def with_section_tails(
    session: AsyncSession, hits: list[DocumentHit]
) -> list[DocumentHit]:
    have = {(hit.document_id, chunk.position) for hit in hits for chunk in hit.chunks}
    following = await _following_chunks(session, hits, exclude=have)

    added: dict[int, list[ChunkHit]] = {}
    budget = _TURN_CHARS
    for document_id, chunk in _matches_best_first(hits):
        for extra in _section_tail(following, document_id, chunk.position):
            if budget <= 0:
                break
            if (document_id, extra.position) in have:
                continue
            have.add((document_id, extra.position))
            added.setdefault(document_id, []).append(extra)
            budget -= len(extra.content)

    return [
        replace(
            hit,
            chunks=sorted(
                [*hit.chunks, *added.get(hit.document_id, [])],
                key=lambda chunk: chunk.position,
            ),
        )
        for hit in hits
    ]


def _matches_best_first(hits: list[DocumentHit]) -> list[tuple[int, ChunkHit]]:
    matches = [(hit.document_id, chunk) for hit in hits for chunk in hit.chunks]
    return sorted(matches, key=lambda match: match[1].score, reverse=True)


def _section_tail(
    following: dict[tuple[int, int], ChunkHit], document_id: int, position: int
) -> list[ChunkHit]:
    tail: list[ChunkHit] = []
    size = 0
    for offset in range(1, _LOOKAHEAD_CHUNKS + 1):
        chunk = following.get((document_id, position + offset))
        if chunk is None:
            # Already a match (or past the document end): its own tail covers it.
            break
        if chunk.content.lstrip().startswith("#"):
            break
        tail.append(chunk)
        size += len(chunk.content)
        if size >= _SECTION_CHARS:
            break
    return tail


async def _following_chunks(
    session: AsyncSession,
    hits: list[DocumentHit],
    *,
    exclude: set[tuple[int, int]],
) -> dict[tuple[int, int], ChunkHit]:
    wanted = {
        (hit.document_id, chunk.position + offset)
        for hit in hits
        for chunk in hit.chunks
        for offset in range(1, _LOOKAHEAD_CHUNKS + 1)
    } - exclude
    if not wanted:
        return {}

    rows = await session.execute(
        select(Chunk.id, Chunk.content, Chunk.position, Chunk.document_id).where(
            tuple_(Chunk.document_id, Chunk.position).in_(sorted(wanted))
        )
    )
    # Scored below every match so a reranker never prefers context over the
    # passage that was actually found.
    return {
        (document_id, position): ChunkHit(
            chunk_id=chunk_id, content=content, position=position, score=0.0
        )
        for chunk_id, content, position, document_id in rows
    }


__all__ = ["with_section_tails"]
