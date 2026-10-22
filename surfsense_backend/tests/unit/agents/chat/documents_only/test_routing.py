"""Rules that send a documents-only turn to the small, vision or chat model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.chat.documents_only.graph import route_turn
from app.agents.chat.documents_only.routing import is_small_talk, latest_images
from app.agents.chat.documents_only.switch import small_model_name

pytestmark = pytest.mark.unit

_IMAGE = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}


@pytest.mark.parametrize(
    "text",
    ["Hola", "¡Muchas gracias!", "ok", "Buenos días", "listo, gracias", "Adiós"],
)
def test_small_talk(text):
    assert is_small_talk(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Hola, ¿cuáles son los 5 momentos de higiene de manos?",
        "gracias, y el protocolo de aislamiento?",
        "¿Qué dice el manual?",
    ],
)
def test_not_small_talk(text):
    assert not is_small_talk(text)


def test_latest_images_reads_only_the_latest_user_message():
    messages = [
        HumanMessage(content=[{"type": "text", "text": "mira"}, _IMAGE]),
        AIMessage(content="ok"),
        HumanMessage(content="y esto?"),
    ]
    assert latest_images(messages) == []
    assert latest_images(messages[:1]) == [_IMAGE]


def test_route_turn():
    assert route_turn({"messages": [HumanMessage(content="gracias")]}) == "small_talk"
    assert (
        route_turn({"messages": [HumanMessage(content="¿Qué es la sepsis?")]})
        == "retrieve"
    )
    image_thanks = HumanMessage(content=[{"type": "text", "text": "gracias"}, _IMAGE])
    assert route_turn({"messages": [image_thanks]}) == "retrieve"


def test_small_model_name(monkeypatch):
    monkeypatch.setenv("SURFSENSE_DOCUMENTS_ONLY_SMALL_MODEL", " qwen2.5:1.5b ")
    assert small_model_name() == "qwen2.5:1.5b"
    monkeypatch.delenv("SURFSENSE_DOCUMENTS_ONLY_SMALL_MODEL")
    assert small_model_name() == ""
