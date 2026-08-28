from __future__ import annotations

import pytest

from lib.interactives import build_choice_message
from lib.whatsapp import WhatsAppApiError


def test_builds_reply_buttons_and_list_messages() -> None:
    buttons, reply_to = build_choice_message(
        {
            "choice_type": "button",
            "body": "Escolha uma opção",
            "header": {"header_type": "image", "media_id": "123456789"},
            "footer": "Atendimento Example",
            "buttons": [
                {"id": "confirm", "title": "Confirmar"},
                {"id": "cancel", "title": "Cancelar"},
            ],
            "reply_to_message_id": "wamid.previous",
        }
    )
    assert reply_to == "wamid.previous"
    assert buttons == {
        "type": "button",
        "header": {"type": "image", "image": {"id": "123456789"}},
        "body": {"text": "Escolha uma opção"},
        "footer": {"text": "Atendimento Example"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "confirm", "title": "Confirmar"}},
                {"type": "reply", "reply": {"id": "cancel", "title": "Cancelar"}},
            ]
        },
    }

    list_message, reply_to = build_choice_message(
        {
            "choice_type": "list",
            "header": {"header_type": "text", "text": "Catálogo"},
            "body": "Selecione um item",
            "list_button": "Ver opções",
            "sections": [
                {
                    "title": "Produtos",
                    "rows": [
                        {"id": "sku-1", "title": "Produto 1", "description": "Primeira opção"},
                        {"id": "sku-2", "title": "Produto 2"},
                    ],
                }
            ],
        }
    )
    assert reply_to is None
    assert list_message["type"] == "list"
    assert list_message["action"] == {
        "button": "Ver opções",
        "sections": [
            {
                "title": "Produtos",
                "rows": [
                    {"id": "sku-1", "title": "Produto 1", "description": "Primeira opção"},
                    {"id": "sku-2", "title": "Produto 2"},
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "message",
    [
        {"choice_type": "button", "body": "Choose", "sections": []},
        {
            "choice_type": "button",
            "body": "Choose",
            "buttons": [{"id": "same", "title": "One"}, {"id": "same", "title": "Two"}],
        },
        {
            "choice_type": "list",
            "body": "Choose",
            "header": {"header_type": "image", "media_id": "123"},
            "list_button": "Options",
            "sections": [{"rows": [{"id": "one", "title": "One"}]}],
        },
        {
            "choice_type": "list",
            "body": "Choose",
            "list_button": "Options",
            "sections": [
                {"rows": [{"id": "same", "title": "One"}]},
                {"rows": [{"id": "same", "title": "Two"}]},
            ],
        },
    ],
)
def test_rejects_invalid_choice_messages(message: dict[str, object]) -> None:
    with pytest.raises(WhatsAppApiError):
        build_choice_message(message)
