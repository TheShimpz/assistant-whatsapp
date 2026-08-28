from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from shimpz import Context, InputRequest
from shimpz._human import HumanRequestSuspension

from actions.send_text_message import run as send_text_message
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
        assert title == "Send this WhatsApp message"
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
