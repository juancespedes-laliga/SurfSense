"""Load the extra models the documents-only chat routes to.

Each loader returns ``None`` when its model is not set up, and the caller then
falls back to the workspace's chat model.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.chat.runtime.llm_config import SanitizedChatLiteLLM
from app.db import Model, Workspace, shielded_async_session
from app.services.llm_service import get_vision_llm
from app.services.model_resolver import to_litellm

from .switch import small_model_name

logger = logging.getLogger(__name__)


async def load_small_llm(workspace_id: int) -> Any | None:
    """The model named by the small-model env var, on one of the workspace's connections.

    It need not be enabled in the model list: enabling it there would also
    offer it in the chat model picker.
    """
    name = small_model_name()
    if not name:
        return None
    async with shielded_async_session() as session:
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            return None
        result = await session.execute(
            select(Model)
            .options(selectinload(Model.connection))
            .where(Model.model_id == name)
        )
        for model in result.scalars():
            conn = model.connection
            if not conn or not conn.enabled:
                continue
            if conn.workspace_id is not None and conn.workspace_id != workspace.id:
                continue
            if conn.user_id is not None and conn.user_id != workspace.user_id:
                continue
            model_string, kwargs = to_litellm(conn, model.model_id)
            return SanitizedChatLiteLLM(
                model=model_string, **{**kwargs, "streaming": True}
            )
    logger.warning("Documents-only small model %r not found on any connection", name)
    return None


async def load_vision_llm(workspace_id: int) -> Any | None:
    """The workspace's vision model, set under Model Roles in the settings."""
    async with shielded_async_session() as session:
        llm = await get_vision_llm(session, workspace_id)
    if llm is None:
        return None
    # Built for document extraction, which does not stream; the chat does.
    if "streaming" in type(llm).model_fields:
        llm = llm.model_copy(update={"streaming": True})
    return llm


__all__ = ["load_small_llm", "load_vision_llm"]
