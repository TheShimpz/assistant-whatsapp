from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from shimpz import Context, InputRequest
from shimpz._human import HumanRequestSuspension

from actions.mark_message_read import run as mark_message_read
from actions.send_catalog_message import run as send_catalog_message
from actions.send_choice_message import run as send_choice_message
from actions.send_contacts_message import run as send_contacts_message
from actions.send_flow_message import run as send_flow_message
from actions.send_location_message import run as send_location_message
from actions.send_media_message import run as send_media_message
from actions.send_template_message import run as send_template_message
from actions.send_text_message import run as send_text_message
from actions.set_message_reaction import run as set_message_reaction
from lib.whatsapp import (
    MAX_RESPONSE_BYTES,
    WhatsAppApiClient,
    WhatsAppApiError,
    WhatsAppTokenRejected,
)

SENDER_ID = "123456789012345"
RECIPIENT = "15555550123"
TOKEN = "opaque-meta-access-token"


class _Content:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self.raw[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class _Response:
    def __init__(self, payload: object, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.raw = payload if isinstance(payload, bytes) else json.dumps(payload, separators=(",", ":")).encode()
        self.status = status
        self.headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(self.raw)),
            **(headers or {}),
        }
        self.content = _Content(self.raw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Session:
    def __init__(self, responses: list[_Response], events: list[str] | None = None) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.events = events

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.requests.append((url, {"method": method, **kwargs}))
        if self.events is not None:
            self.events.append("provider")
        return self.responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _StoredInputRejected(RuntimeError):
    pass


class _ActionContext:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def request_approval(self, *, title: str, description: str) -> None:
        assert "WhatsApp" in title
        assert TOKEN not in description
        self.events.append("approval")

    def request_input(self, request: InputRequest) -> str:
        sdk_context = Context(
            {},
            human_requests=["input:password"],
            stored_input_ids=["whatsapp-token"],
        )
        with pytest.raises(HumanRequestSuspension) as suspended:
            sdk_context.request_input(request)
        frame = suspended.value.request
        assert set(frame) == {
            "kind",
            "ordinal",
            "title",
            "description",
            "label",
            "required",
            "placeholder",
            "min_length",
            "max_length",
            "stored_input",
            "fingerprint",
        }
        assert frame == {
            "kind": "input:password",
            "ordinal": 0,
            "title": "WhatsApp access token",
            "description": "Enter the Meta access token used by this WhatsApp Action.",
            "label": "Meta access token",
            "required": True,
            "placeholder": None,
            "min_length": 1,
            "max_length": 1024,
            "stored_input": "whatsapp-token",
            "fingerprint": frame["fingerprint"],
        }
        assert isinstance(frame["fingerprint"], str)
        assert len(frame["fingerprint"]) == 64
        assert TOKEN not in request.title
        assert TOKEN not in request.description
        self.events.append("stored-input")
        return TOKEN

    def reject_stored_input(self, stored_input: str) -> None:
        assert stored_input == "whatsapp-token"
        self.events.append("rejected")
        raise _StoredInputRejected


def _success() -> dict[str, object]:
    return {
        "messaging_product": "whatsapp",
        "contacts": [{"input": RECIPIENT, "wa_id": RECIPIENT}],
        "messages": [{"id": "wamid.message-id"}],
    }


def test_sends_one_exact_text_message_without_exposing_the_token() -> None:
    session = _Session([_Response(_success())])

    result = asyncio.run(
        WhatsAppApiClient(session, TOKEN).send_text_message(SENDER_ID, f"+{RECIPIENT}", {"body": "Hello"})
    )

    assert result == {"recipient": RECIPIENT, "whatsapp_id": RECIPIENT, "message_id": "wamid.message-id"}
    url, request = session.requests[0]
    assert url == f"https://graph.facebook.com/v23.0/{SENDER_ID}/messages"
    assert request["method"] == "POST"
    assert request["allow_redirects"] is False
    assert request["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request["data"]) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": RECIPIENT,
        "type": "text",
        "text": {"preview_url": False, "body": "Hello"},
    }
    assert TOKEN not in json.dumps(result)


def test_distinguishes_explicit_token_rejection_from_other_provider_failures() -> None:
    for response in (
        _Response({"error": {"code": 190}}, status=400),
        _Response({"error": {"code": 190}}, status=200),
    ):
        with pytest.raises(WhatsAppTokenRejected):
            asyncio.run(
                WhatsAppApiClient(_Session([response]), TOKEN).send_text_message(
                    SENDER_ID, RECIPIENT, {"body": "Hello"}
                )
            )

    for response in (
        _Response({"error": {"code": 1}}, status=401),
        _Response({"error": {"code": 200}}, status=403),
        _Response({"error": {"code": 4}}, status=429),
    ):
        with pytest.raises(WhatsAppApiError) as failure:
            asyncio.run(
                WhatsAppApiClient(_Session([response]), TOKEN).send_text_message(
                    SENDER_ID, RECIPIENT, {"body": "Hello"}
                )
            )
        assert not isinstance(failure.value, WhatsAppTokenRejected)


def test_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)

    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(send_text_message(SENDER_ID, RECIPIENT, {"body": "Hello"}, ctx=_ActionContext(events)))

    assert result["message_id"] == "wamid.message-id"
    assert events == ["approval", "stored-input", "provider"]


def test_action_clears_only_an_explicitly_rejected_token() -> None:
    rejected_events: list[str] = []
    rejected = _Session([_Response({"error": {"code": 190}}, status=400)], rejected_events)
    with (
        patch("lib.runtime.create_http_session", return_value=rejected),
        pytest.raises(_StoredInputRejected),
    ):
        asyncio.run(send_text_message(SENDER_ID, RECIPIENT, {"body": "Hello"}, ctx=_ActionContext(rejected_events)))
    assert rejected_events == ["approval", "stored-input", "provider", "rejected"]

    denied_events: list[str] = []
    denied = _Session([_Response({"error": {"code": 200}}, status=403)], denied_events)
    with (
        patch("lib.runtime.create_http_session", return_value=denied),
        pytest.raises(WhatsAppApiError),
    ):
        asyncio.run(send_text_message(SENDER_ID, RECIPIENT, {"body": "Hello"}, ctx=_ActionContext(denied_events)))
    assert denied_events == ["approval", "stored-input", "provider"]


def test_rejects_ambiguous_or_oversized_provider_results() -> None:
    invalid = [
        _Response({**_success(), "contacts": []}),
        _Response({**_success(), "messages": [{"id": "not-a-whatsapp-id"}]}),
        _Response(_success(), headers={"Content-Encoding": "gzip"}),
        _Response(b"{" + (b"x" * MAX_RESPONSE_BYTES) + b"}"),
    ]
    for response in invalid:
        with pytest.raises(WhatsAppApiError):
            asyncio.run(
                WhatsAppApiClient(_Session([response]), TOKEN).send_text_message(
                    SENDER_ID, RECIPIENT, {"body": "Hello"}
                )
            )


def test_redacts_token_from_unexpected_transport_errors() -> None:
    class _ExplodingSession:
        def request(self, *_args: object, **_kwargs: object) -> _Response:
            raise aiohttp.ClientConnectionError(f"transport accidentally exposed {TOKEN}")

    with pytest.raises(WhatsAppApiError, match="WhatsApp request failed") as failure:
        asyncio.run(
            WhatsAppApiClient(_ExplodingSession(), TOKEN).send_text_message(
                SENDER_ID, RECIPIENT, {"body": "Hello"}
            )
        )

    assert failure.value.__cause__ is None
    assert TOKEN not in str(failure.value)


def test_sends_text_preview_and_reply_context() -> None:
    session = _Session([_Response(_success())])

    asyncio.run(
        WhatsAppApiClient(session, TOKEN).send_text_message(
            SENDER_ID,
            RECIPIENT,
            {"body": "See https://example.com", "preview_url": True, "reply_to_message_id": "wamid.previous"},
        )
    )

    assert json.loads(session.requests[0][1]["data"]) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": RECIPIENT,
        "context": {"message_id": "wamid.previous"},
        "type": "text",
        "text": {"preview_url": True, "body": "See https://example.com"},
    }


def test_sends_media_by_id_and_https_link_with_exact_fields() -> None:
    image_session = _Session([_Response(_success())])
    asyncio.run(
        WhatsAppApiClient(image_session, TOKEN).send_media_message(
            SENDER_ID,
            RECIPIENT,
            {
                "media_type": "image",
                "media_id": "123456789",
                "caption": "Reviewed image",
                "reply_to_message_id": "wamid.previous",
            },
        )
    )
    assert json.loads(image_session.requests[0][1]["data"]) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": RECIPIENT,
        "type": "image",
        "image": {"id": "123456789", "caption": "Reviewed image"},
        "context": {"message_id": "wamid.previous"},
    }

    document_session = _Session([_Response(_success())])
    asyncio.run(
        WhatsAppApiClient(document_session, TOKEN).send_media_message(
            SENDER_ID,
            RECIPIENT,
            {
                "media_type": "document",
                "link": "https://cdn.example.com/report.pdf?version=1",
                "filename": "report.pdf",
            },
        )
    )
    assert json.loads(document_session.requests[0][1]["data"])["document"] == {
        "link": "https://cdn.example.com/report.pdf?version=1",
        "filename": "report.pdf",
    }


@pytest.mark.parametrize(
    "message",
    [
        {"media_type": "image"},
        {"media_type": "image", "media_id": "1", "link": "https://cdn.example.com/a.jpg"},
        {"media_type": "audio", "media_id": "1", "caption": "not supported"},
        {"media_type": "video", "media_id": "1", "filename": "not-supported.mp4"},
        {"media_type": "image", "link": "http://cdn.example.com/a.jpg"},
        {"media_type": "image", "link": "https://user:secret@cdn.example.com/a.jpg"},
        {"media_type": "image", "link": "https://127.0.0.1/a.jpg"},
    ],
)
def test_rejects_invalid_media_combinations_before_provider(message: dict[str, object]) -> None:
    session = _Session([])
    with pytest.raises(WhatsAppApiError):
        asyncio.run(WhatsAppApiClient(session, TOKEN).send_media_message(SENDER_ID, RECIPIENT, message))
    assert session.requests == []


def test_media_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_media_message(
                SENDER_ID,
                RECIPIENT,
                {"media_type": "sticker", "media_id": "123456789"},
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert events == ["approval", "stored-input", "provider"]


def test_sends_location_with_optional_fields_and_reply() -> None:
    session = _Session([_Response(_success())])
    asyncio.run(
        WhatsAppApiClient(session, TOKEN).send_location_message(
            SENDER_ID,
            RECIPIENT,
            {
                "latitude": -23.55052,
                "longitude": -46.633308,
                "name": "Praça da Sé",
                "address": "Sé, São Paulo - SP",
                "reply_to_message_id": "wamid.previous",
            },
        )
    )
    assert json.loads(session.requests[0][1]["data"]) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": RECIPIENT,
        "type": "location",
        "location": {
            "latitude": -23.55052,
            "longitude": -46.633308,
            "name": "Praça da Sé",
            "address": "Sé, São Paulo - SP",
        },
        "context": {"message_id": "wamid.previous"},
    }


@pytest.mark.parametrize(
    "location",
    [
        {"latitude": 91.0, "longitude": 0.0},
        {"latitude": 0.0, "longitude": -181.0},
        {"latitude": True, "longitude": 0.0},
        {"latitude": float("nan"), "longitude": 0.0},
        {"latitude": 0.0, "longitude": 0.0, "unknown": "field"},
    ],
)
def test_rejects_invalid_locations_before_provider(location: dict[str, object]) -> None:
    session = _Session([])
    with pytest.raises(WhatsAppApiError):
        asyncio.run(WhatsAppApiClient(session, TOKEN).send_location_message(SENDER_ID, RECIPIENT, location))
    assert session.requests == []


def test_location_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_location_message(
                SENDER_ID,
                RECIPIENT,
                {"latitude": -23.55052, "longitude": -46.633308},
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert events == ["approval", "stored-input", "provider"]


def _complete_contact() -> dict[str, object]:
    return {
        "name": {"formatted_name": "Ana Silva", "first_name": "Ana", "last_name": "Silva"},
        "addresses": [
            {
                "street": "Avenida Paulista, 1000",
                "city": "São Paulo",
                "state": "SP",
                "zip": "01310-100",
                "country": "Brasil",
                "country_code": "BR",
                "type": "WORK",
            }
        ],
        "birthday": "1990-05-12",
        "emails": [{"email": "ana@example.com", "type": "WORK"}],
        "org": {"company": "Example", "department": "Operations", "title": "Manager"},
        "phones": [{"phone": "+55 11 99999-0000", "wa_id": "5511999990000", "type": "WORK"}],
        "urls": [{"url": "https://example.com/ana", "type": "WORK"}],
    }


def test_sends_complete_contact_cards_and_reply_context() -> None:
    session = _Session([_Response(_success())])
    asyncio.run(
        WhatsAppApiClient(session, TOKEN).send_contacts_message(
            SENDER_ID,
            RECIPIENT,
            {"contacts": [_complete_contact()], "reply_to_message_id": "wamid.previous"},
        )
    )
    payload = json.loads(session.requests[0][1]["data"])
    assert payload["type"] == "contacts"
    assert payload["context"] == {"message_id": "wamid.previous"}
    assert payload["contacts"] == [
        {
            **_complete_contact(),
            "addresses": [{**_complete_contact()["addresses"][0], "country_code": "br"}],
        }
    ]


@pytest.mark.parametrize(
    "message",
    [
        {"contacts": []},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "emails": [{"email": "invalid"}]}]},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "org": {}}]},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "phones": [{"type": "WORK"}]}]},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "birthday": "2023-02-29"}]},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "urls": [{"url": "http://example.com"}]}]},
        {"contacts": [{"name": {"formatted_name": "Ana"}, "unknown": "field"}]},
    ],
)
def test_rejects_invalid_contact_cards_before_provider(message: dict[str, object]) -> None:
    session = _Session([])
    with pytest.raises(WhatsAppApiError):
        asyncio.run(WhatsAppApiClient(session, TOKEN).send_contacts_message(SENDER_ID, RECIPIENT, message))
    assert session.requests == []


def test_contacts_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_contacts_message(
                SENDER_ID,
                RECIPIENT,
                {"contacts": [{"name": {"formatted_name": "Ana Silva"}}]},
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert events == ["approval", "stored-input", "provider"]


@pytest.mark.parametrize("emoji", ["👍🏽", "👩‍💻", "🇧🇷", "1️⃣", ""])
def test_adds_or_removes_one_message_reaction(emoji: str) -> None:
    session = _Session([_Response(_success())])
    asyncio.run(
        WhatsAppApiClient(session, TOKEN).set_message_reaction(
            SENDER_ID,
            RECIPIENT,
            {"message_id": "wamid.target", "emoji": emoji},
        )
    )
    assert json.loads(session.requests[0][1]["data"]) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": RECIPIENT,
        "type": "reaction",
        "reaction": {"message_id": "wamid.target", "emoji": emoji},
    }


@pytest.mark.parametrize("emoji", ["hello", "😀😀", " ", "😀\n"])
def test_rejects_invalid_reactions_before_provider(emoji: str) -> None:
    session = _Session([])
    with pytest.raises(WhatsAppApiError):
        asyncio.run(
            WhatsAppApiClient(session, TOKEN).set_message_reaction(
                SENDER_ID,
                RECIPIENT,
                {"message_id": "wamid.target", "emoji": emoji},
            )
        )
    assert session.requests == []


def test_reaction_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            set_message_reaction(
                SENDER_ID,
                RECIPIENT,
                {"message_id": "wamid.target", "emoji": "✅"},
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert events == ["approval", "stored-input", "provider"]


@pytest.mark.parametrize(
    ("typing_indicator", "method"),
    [(False, "PUT"), (True, "POST")],
)
def test_marks_incoming_message_read_with_optional_typing_indicator(
    typing_indicator: bool,
    method: str,
) -> None:
    session = _Session([_Response({"success": True})])
    result = asyncio.run(
        WhatsAppApiClient(session, TOKEN).mark_message_read(
            SENDER_ID,
            {"message_id": "wamid.incoming", "typing_indicator": typing_indicator},
        )
    )
    assert result == {
        "message_id": "wamid.incoming",
        "read": True,
        "typing_indicator": typing_indicator,
    }
    request = session.requests[0][1]
    assert request["method"] == method
    expected: dict[str, object] = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.incoming",
    }
    if typing_indicator:
        expected["typing_indicator"] = {"type": "text"}
    assert json.loads(request["data"]) == expected


def test_rejects_invalid_read_receipt_results_and_inputs() -> None:
    invalid_result = _Session([_Response({"success": False})])
    with pytest.raises(WhatsAppApiError, match="read receipt result"):
        asyncio.run(
            WhatsAppApiClient(invalid_result, TOKEN).mark_message_read(
                SENDER_ID,
                {"message_id": "wamid.incoming"},
            )
        )

    no_request = _Session([])
    with pytest.raises(WhatsAppApiError, match="typing indicator"):
        asyncio.run(
            WhatsAppApiClient(no_request, TOKEN).mark_message_read(
                SENDER_ID,
                {"message_id": "wamid.incoming", "typing_indicator": "yes"},
            )
        )
    assert no_request.requests == []


def test_read_receipt_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response({"success": True})], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            mark_message_read(
                SENDER_ID,
                {"message_id": "wamid.incoming", "typing_indicator": True},
                ctx=_ActionContext(events),
            )
        )
    assert result["read"] is True
    assert events == ["approval", "stored-input", "provider"]


def test_template_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_template_message(
                SENDER_ID,
                RECIPIENT,
                {"name": "hello_world", "language_code": "en_US"},
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert json.loads(session.requests[0][1]["data"])["template"] == {
        "name": "hello_world",
        "language": {"code": "en_US"},
    }
    assert events == ["approval", "stored-input", "provider"]


def test_choice_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_choice_message(
                SENDER_ID,
                RECIPIENT,
                {
                    "choice_type": "button",
                    "body": "Choose one",
                    "buttons": [{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
                },
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert json.loads(session.requests[0][1]["data"])["interactive"]["type"] == "button"
    assert events == ["approval", "stored-input", "provider"]


def test_catalog_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_catalog_message(
                SENDER_ID,
                RECIPIENT,
                {
                    "commerce_type": "product",
                    "catalog_id": "367025965434465",
                    "product_retailer_id": "sku-1",
                },
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert json.loads(session.requests[0][1]["data"])["interactive"]["type"] == "product"
    assert events == ["approval", "stored-input", "provider"]


def test_flow_action_orders_approval_before_stored_input_and_provider() -> None:
    events: list[str] = []
    session = _Session([_Response(_success())], events)
    with patch("lib.runtime.create_http_session", return_value=session):
        result = asyncio.run(
            send_flow_message(
                SENDER_ID,
                RECIPIENT,
                {
                    "flow_id": "987654321",
                    "flow_token": "appointment-42",
                    "flow_cta": "Schedule",
                    "flow_action": "navigate",
                    "screen": "APPOINTMENT",
                    "body": "Choose a time",
                },
                ctx=_ActionContext(events),
            )
        )
    assert result["message_id"] == "wamid.message-id"
    assert json.loads(session.requests[0][1]["data"])["interactive"]["type"] == "flow"
    assert events == ["approval", "stored-input", "provider"]
