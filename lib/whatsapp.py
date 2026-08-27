"""Bounded WhatsApp Cloud API client."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, TypedDict
from urllib.parse import quote

import aiohttp

GRAPH_API_ORIGIN = "https://graph.facebook.com"
GRAPH_API_VERSION = "v23.0"
MAX_RESPONSE_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 8 * 1024
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=8, connect=3, sock_connect=3, sock_read=5)
_PHONE_NUMBER_ID_PATTERN = r"^[1-9][0-9]{4,31}$"
_RECIPIENT_PATTERN = r"^\+?[1-9][0-9]{7,14}$"
_PHONE_NUMBER_ID = re.compile(_PHONE_NUMBER_ID_PATTERN)
_RECIPIENT = re.compile(_RECIPIENT_PATTERN)

PhoneNumberId = Annotated[
    str,
    "Meta WhatsApp sender phone-number id.",
    {"pattern": _PHONE_NUMBER_ID_PATTERN},
]
Recipient = Annotated[
    str,
    "Recipient number with country code, optionally prefixed by +.",
    {"pattern": _RECIPIENT_PATTERN},
]
MessageText = Annotated[str, "WhatsApp text body.", {"minLength": 1, "maxLength": 4096}]


class SendTextMessageResult(TypedDict):
    recipient: Recipient
    whatsapp_id: Annotated[str, {"pattern": r"^[1-9][0-9]{7,19}$"}]
    message_id: Annotated[str, {"minLength": 1, "maxLength": 512}]


class WhatsAppApiError(RuntimeError):
    """WhatsApp did not satisfy the declared Action contract."""


class WhatsAppTokenRejected(WhatsAppApiError):
    """WhatsApp explicitly rejected the supplied access token."""


class WhatsAppApiClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def send_text_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        message: str,
        access_token: str,
    ) -> SendTextMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destination,
            "type": "text",
            "text": {"preview_url": False, "body": _message(message)},
        }
        encoded = json.dumps(body, allow_nan=False, ensure_ascii=False, separators=(",", ":")).encode()
        if not 1 <= len(encoded) <= MAX_REQUEST_BYTES:
            raise WhatsAppApiError("WhatsApp request size is invalid")
        payload = await self._post(sender, access_token, encoded)
        return _send_result(payload, destination)

    async def _post(self, sender: str, access_token: str, body: bytes) -> dict[str, Any]:
        path = f"/{GRAPH_API_VERSION}/{quote(sender, safe='')}/messages"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                "POST",
                f"{GRAPH_API_ORIGIN}{path}",
                headers=headers,
                data=body,
                allow_redirects=False,
            ) as response:
                raw = await _read_response(response)
                payload = _json_object(raw)
                if response.status == 401 or _error_code(payload) == 190:
                    raise WhatsAppTokenRejected("WhatsApp rejected the access token")
                if response.status != 200:
                    raise WhatsAppApiError("WhatsApp rejected the message")
                return payload
        except WhatsAppApiError:
            raise
        except Exception as exc:
            raise WhatsAppApiError("WhatsApp request failed") from exc


def create_http_session() -> aiohttp.ClientSession:
    session = aiohttp.ClientSession(
        auto_decompress=False,
        timeout=HTTP_TIMEOUT,
        trust_env=True,
        headers={"User-Agent": "assistant-whatsapp/0.1.0"},
    )
    session._retry_connection = False
    return session


async def _read_response(response: Any) -> bytes:
    media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    content_encoding = response.headers.get("Content-Encoding", "").strip()
    raw_length = response.headers.get("Content-Length")
    if media_type != "application/json" or content_encoding:
        raise WhatsAppApiError("WhatsApp response metadata is invalid")
    if raw_length is not None and (
        not raw_length.isascii() or not raw_length.isdigit() or int(raw_length) > MAX_RESPONSE_BYTES
    ):
        raise WhatsAppApiError("WhatsApp response size is invalid")
    raw = bytearray()
    while True:
        chunk = await response.content.read(min(16 * 1024, (MAX_RESPONSE_BYTES + 1) - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise WhatsAppApiError("WhatsApp response size is invalid")
    if not raw:
        raise WhatsAppApiError("WhatsApp response is empty")
    return bytes(raw)


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw, parse_constant=_reject_json_constant, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError) as exc:
        raise WhatsAppApiError("WhatsApp response JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise WhatsAppApiError("WhatsApp response is invalid")
    return payload


def _send_result(payload: dict[str, Any], recipient: str) -> SendTextMessageResult:
    contacts = payload.get("contacts")
    messages = payload.get("messages")
    if (
        payload.get("messaging_product") != "whatsapp"
        or not isinstance(contacts, list)
        or len(contacts) != 1
        or not isinstance(contacts[0], dict)
        or contacts[0].get("input") != recipient
        or not isinstance(messages, list)
        or len(messages) != 1
        or not isinstance(messages[0], dict)
    ):
        raise WhatsAppApiError("WhatsApp message result is invalid")
    whatsapp_id = _whatsapp_id(contacts[0].get("wa_id"))
    message_id = _public_text(messages[0].get("id"), 512)
    if not message_id.startswith("wamid."):
        raise WhatsAppApiError("WhatsApp message result is invalid")
    return {"recipient": recipient, "whatsapp_id": whatsapp_id, "message_id": message_id}


def _phone_number_id(value: object) -> str:
    if not isinstance(value, str) or _PHONE_NUMBER_ID.fullmatch(value) is None:
        raise WhatsAppApiError("WhatsApp sender phone-number id is invalid")
    return value


def _recipient(value: object) -> str:
    if not isinstance(value, str) or _RECIPIENT.fullmatch(value) is None:
        raise WhatsAppApiError("WhatsApp recipient is invalid")
    return value.removeprefix("+")


def _message(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or value != value.strip():
        raise WhatsAppApiError("WhatsApp message is invalid")
    if any((ord(character) < 32 and character not in "\n\t") or ord(character) == 127 for character in value):
        raise WhatsAppApiError("WhatsApp message is invalid")
    return value


def _whatsapp_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]{7,19}", value) is None:
        raise WhatsAppApiError("WhatsApp contact result is invalid")
    return value


def _public_text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise WhatsAppApiError("WhatsApp text result is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise WhatsAppApiError("WhatsApp text result is invalid")
    return value


def _error_code(payload: dict[str, Any]) -> int | None:
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if type(code) is int else None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
