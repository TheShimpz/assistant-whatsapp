from __future__ import annotations

import pytest

from lib.interactives import build_choice_message, build_commerce_message, build_flow_message
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


def test_builds_product_product_list_and_catalog_messages() -> None:
    assert build_commerce_message(
        {
            "commerce_type": "product",
            "catalog_id": "367025965434465",
            "product_retailer_id": "sku-1",
            "body": "Produto recomendado",
            "footer": "Example Store",
        }
    ) == {
        "type": "product",
        "body": {"text": "Produto recomendado"},
        "footer": {"text": "Example Store"},
        "action": {"catalog_id": "367025965434465", "product_retailer_id": "sku-1"},
    }

    product_list = build_commerce_message(
        {
            "commerce_type": "product_list",
            "catalog_id": "367025965434465",
            "header": "Ofertas",
            "body": "Escolha os produtos",
            "footer": "Example Store",
            "sections": [
                {
                    "title": "Destaques",
                    "product_items": [
                        {"product_retailer_id": "sku-1"},
                        {"product_retailer_id": "sku-2"},
                    ],
                }
            ],
        }
    )
    assert product_list["type"] == "product_list"
    assert product_list["action"] == {
        "catalog_id": "367025965434465",
        "sections": [
            {
                "title": "Destaques",
                "product_items": [
                    {"product_retailer_id": "sku-1"},
                    {"product_retailer_id": "sku-2"},
                ],
            }
        ],
    }

    assert build_commerce_message(
        {
            "commerce_type": "catalog",
            "body": "Conheça nosso catálogo",
            "thumbnail_product_retailer_id": "sku-1",
        }
    ) == {
        "type": "catalog_message",
        "body": {"text": "Conheça nosso catálogo"},
        "action": {
            "name": "catalog_message",
            "parameters": {"thumbnail_product_retailer_id": "sku-1"},
        },
    }


@pytest.mark.parametrize(
    "message",
    [
        {"commerce_type": "product", "product_retailer_id": "sku-1"},
        {
            "commerce_type": "product",
            "catalog_id": "367025965434465",
            "product_retailer_id": "sku-1",
            "sections": [],
        },
        {
            "commerce_type": "product_list",
            "catalog_id": "367025965434465",
            "header": "Products",
            "body": "Choose",
            "sections": [
                {
                    "title": "One",
                    "product_items": [
                        {"product_retailer_id": "duplicate"},
                        {"product_retailer_id": "duplicate"},
                    ],
                }
            ],
        },
        {"commerce_type": "catalog", "catalog_id": "367025965434465", "body": "Catalog"},
        {"commerce_type": "catalog"},
    ],
)
def test_rejects_invalid_commerce_messages(message: dict[str, object]) -> None:
    with pytest.raises(WhatsAppApiError):
        build_commerce_message(message)


def test_builds_published_flow_by_id_or_name() -> None:
    by_id = build_flow_message(
        {
            "flow_id": "987654321",
            "flow_token": "appointment-42",
            "flow_cta": "Agendar",
            "flow_action": "navigate",
            "screen": "APPOINTMENT",
            "data": [{"key": "customer_id", "value": "42"}],
            "header": {"header_type": "text", "text": "Agendamento"},
            "body": "Escolha um horário",
            "footer": "Example Clinic",
        }
    )
    assert by_id == {
        "type": "flow",
        "header": {"type": "text", "text": "Agendamento"},
        "body": {"text": "Escolha um horário"},
        "footer": {"text": "Example Clinic"},
        "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_action": "navigate",
                "flow_token": "appointment-42",
                "flow_id": "987654321",
                "flow_cta": "Agendar",
                "flow_action_payload": {"screen": "APPOINTMENT", "data": {"customer_id": "42"}},
            },
        },
    }

    by_name = build_flow_message(
        {
            "flow_name": "support_intake",
            "flow_token": "support-43",
            "flow_cta": "Começar",
            "flow_action": "data_exchange",
            "data": [{"key": "ticket_id", "value": "43"}],
            "body": "Conte o que aconteceu",
        }
    )
    assert by_name["action"]["parameters"]["flow_name"] == "support_intake"
    assert by_name["action"]["parameters"]["flow_action"] == "data_exchange"


@pytest.mark.parametrize(
    "message",
    [
        {
            "flow_token": "token",
            "flow_cta": "Open",
            "flow_action": "navigate",
            "screen": "START",
            "body": "Body",
        },
        {
            "flow_id": "1",
            "flow_name": "duplicate",
            "flow_token": "token",
            "flow_cta": "Open",
            "flow_action": "navigate",
            "screen": "START",
            "body": "Body",
        },
        {
            "flow_id": "1",
            "flow_token": "token",
            "flow_cta": "Open",
            "flow_action": "navigate",
            "body": "Body",
        },
        {
            "flow_id": "1",
            "flow_token": "token",
            "flow_cta": "Open",
            "flow_action": "data_exchange",
            "screen": "NOT_ALLOWED",
            "body": "Body",
        },
        {
            "flow_id": "1",
            "flow_token": "token",
            "flow_cta": "Open",
            "flow_action": "data_exchange",
            "data": [{"key": "duplicate", "value": "1"}, {"key": "duplicate", "value": "2"}],
            "body": "Body",
        },
    ],
)
def test_rejects_invalid_flow_messages(message: dict[str, object]) -> None:
    with pytest.raises(WhatsAppApiError):
        build_flow_message(message)
