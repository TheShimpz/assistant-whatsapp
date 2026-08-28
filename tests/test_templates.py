from __future__ import annotations

import pytest

from lib.templates import build_template_message
from lib.whatsapp import WhatsAppApiError


def test_builds_plain_and_complete_template_messages() -> None:
    assert build_template_message({"name": "hello_world", "language_code": "en_US"}) == {
        "name": "hello_world",
        "language": {"code": "en_US"},
    }

    template = build_template_message(
        {
            "name": "order_update",
            "language_code": "pt_BR",
            "components": [
                {
                    "component_type": "header",
                    "parameters": [
                        {
                            "parameter_type": "image",
                            "media": {"link": "https://cdn.example.com/order.jpg"},
                        }
                    ],
                },
                {
                    "component_type": "body",
                    "parameters": [
                        {"parameter_type": "text", "text": "Pedido 42"},
                        {
                            "parameter_type": "currency",
                            "currency": {"fallback_value": "R$ 100,99", "code": "BRL", "amount_1000": 100990},
                        },
                        {
                            "parameter_type": "date_time",
                            "date_time": {
                                "fallback_value": "27 de agosto de 2026",
                                "year": 2026,
                                "month": 8,
                                "day_of_month": 27,
                                "calendar": "GREGORIAN",
                            },
                        },
                    ],
                },
                {
                    "component_type": "button",
                    "sub_type": "quick_reply",
                    "index": 0,
                    "parameters": [{"parameter_type": "payload", "payload": "confirm-order-42"}],
                },
                {
                    "component_type": "button",
                    "sub_type": "catalog",
                    "index": 1,
                    "parameters": [
                        {
                            "parameter_type": "action",
                            "action": {"thumbnail_product_retailer_id": "sku-42"},
                        }
                    ],
                },
                {
                    "component_type": "button",
                    "sub_type": "flow",
                    "index": 2,
                    "parameters": [
                        {
                            "parameter_type": "action",
                            "action": {
                                "flow_token": "order-flow-42",
                                "flow_action_data": [{"key": "order_id", "value": "42"}],
                            },
                        }
                    ],
                },
                {
                    "component_type": "button",
                    "sub_type": "copy_code",
                    "index": 3,
                    "parameters": [{"parameter_type": "coupon_code", "coupon_code": "SAVE10"}],
                },
            ],
        }
    )

    assert template["name"] == "order_update"
    assert template["language"] == {"code": "pt_BR"}
    components = template["components"]
    assert components[0] == {
        "type": "header",
        "parameters": [{"type": "image", "image": {"link": "https://cdn.example.com/order.jpg"}}],
    }
    assert components[1]["parameters"][1] == {
        "type": "currency",
        "currency": {"fallback_value": "R$ 100,99", "code": "BRL", "amount_1000": 100990},
    }
    assert components[3]["sub_type"] == "CATALOG"
    assert components[4]["parameters"] == [
        {
            "type": "action",
            "action": {"flow_token": "order-flow-42", "flow_action_data": {"order_id": "42"}},
        }
    ]


@pytest.mark.parametrize(
    "message",
    [
        {"name": "Invalid Name", "language_code": "en_US"},
        {"name": "hello", "language_code": "english"},
        {
            "name": "hello",
            "language_code": "en_US",
            "components": [
                {
                    "component_type": "header",
                    "parameters": [
                        {"parameter_type": "text", "text": "one"},
                        {"parameter_type": "text", "text": "two"},
                    ],
                }
            ],
        },
        {
            "name": "hello",
            "language_code": "en_US",
            "components": [
                {
                    "component_type": "body",
                    "parameters": [{"parameter_type": "payload", "payload": "wrong component"}],
                }
            ],
        },
        {
            "name": "hello",
            "language_code": "en_US",
            "components": [
                {
                    "component_type": "header",
                    "parameters": [
                        {
                            "parameter_type": "image",
                            "media": {
                                "media_id": "123",
                                "link": "https://cdn.example.com/image.jpg",
                            },
                        }
                    ],
                }
            ],
        },
        {
            "name": "hello",
            "language_code": "en_US",
            "components": [
                {
                    "component_type": "body",
                    "parameters": [{"parameter_type": "text", "text": "one"}],
                },
                {
                    "component_type": "body",
                    "parameters": [{"parameter_type": "text", "text": "two"}],
                },
            ],
        },
    ],
)
def test_rejects_invalid_template_shapes(message: dict[str, object]) -> None:
    with pytest.raises(WhatsAppApiError):
        build_template_message(message)
