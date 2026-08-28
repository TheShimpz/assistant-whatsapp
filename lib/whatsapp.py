"""Bounded WhatsApp Cloud API client."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from ipaddress import ip_address
from math import isfinite
from typing import Annotated, Any, Literal, NotRequired, TypedDict
from urllib.parse import quote, urlsplit

import aiohttp

GRAPH_API_ORIGIN = "https://graph.facebook.com"
GRAPH_API_VERSION = "v23.0"
MAX_RESPONSE_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 64 * 1024
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
MessageId = Annotated[str, "WhatsApp message id.", {"minLength": 7, "maxLength": 512, "pattern": r"^wamid\..+$"}]
MediaId = Annotated[str, "Meta media object id.", {"minLength": 1, "maxLength": 512}]
MediaLink = Annotated[
    str,
    "Public HTTPS media URL for Meta to fetch.",
    {"minLength": 9, "maxLength": 2048, "pattern": r"^https://"},
]
MediaCaption = Annotated[str, "Media caption.", {"minLength": 1, "maxLength": 1024}]
MediaFilename = Annotated[str, "Document filename.", {"minLength": 1, "maxLength": 240}]
Latitude = Annotated[float, "Location latitude.", {"minimum": -90.0, "maximum": 90.0}]
Longitude = Annotated[float, "Location longitude.", {"minimum": -180.0, "maximum": 180.0}]
LocationText = Annotated[str, "Location name or address.", {"minLength": 1, "maxLength": 1000}]
ContactText = Annotated[str, "Contact field.", {"minLength": 1, "maxLength": 256}]
ContactEmailValue = Annotated[
    str,
    "Contact email address.",
    {"minLength": 3, "maxLength": 254, "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$"},
]
ContactUrlValue = Annotated[
    str,
    "Contact HTTPS URL.",
    {"minLength": 9, "maxLength": 2048, "pattern": r"^https://"},
]


class TextMessage(TypedDict):
    body: MessageText
    preview_url: NotRequired[bool]
    reply_to_message_id: NotRequired[MessageId]


class MediaMessage(TypedDict):
    media_type: Literal["audio", "document", "image", "sticker", "video"]
    media_id: NotRequired[MediaId]
    link: NotRequired[MediaLink]
    caption: NotRequired[MediaCaption]
    filename: NotRequired[MediaFilename]
    reply_to_message_id: NotRequired[MessageId]


class LocationMessage(TypedDict):
    latitude: Latitude
    longitude: Longitude
    name: NotRequired[LocationText]
    address: NotRequired[LocationText]
    reply_to_message_id: NotRequired[MessageId]


class ContactName(TypedDict):
    formatted_name: ContactText
    first_name: NotRequired[ContactText]
    last_name: NotRequired[ContactText]
    middle_name: NotRequired[ContactText]
    suffix: NotRequired[ContactText]
    prefix: NotRequired[ContactText]


class ContactAddress(TypedDict):
    street: NotRequired[ContactText]
    city: NotRequired[ContactText]
    state: NotRequired[ContactText]
    zip: NotRequired[ContactText]
    country: NotRequired[ContactText]
    country_code: NotRequired[Annotated[str, {"minLength": 2, "maxLength": 2, "pattern": r"^[A-Za-z]{2}$"}]]
    type: NotRequired[Literal["HOME", "WORK"]]


class ContactEmail(TypedDict):
    email: ContactEmailValue
    type: NotRequired[Literal["HOME", "WORK"]]


class ContactOrganization(TypedDict):
    company: NotRequired[ContactText]
    department: NotRequired[ContactText]
    title: NotRequired[ContactText]


class ContactPhone(TypedDict):
    phone: NotRequired[Annotated[str, {"minLength": 3, "maxLength": 32}]]
    wa_id: NotRequired[Annotated[str, {"minLength": 8, "maxLength": 20, "pattern": r"^[1-9][0-9]{7,19}$"}]]
    type: NotRequired[Literal["HOME", "WORK"]]


class ContactUrl(TypedDict):
    url: ContactUrlValue
    type: NotRequired[Literal["HOME", "WORK"]]


class Contact(TypedDict):
    name: ContactName
    addresses: NotRequired[Annotated[list[ContactAddress], {"minItems": 1, "maxItems": 3}]]
    birthday: NotRequired[Annotated[str, {"minLength": 10, "maxLength": 10, "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}]]
    emails: NotRequired[Annotated[list[ContactEmail], {"minItems": 1, "maxItems": 3}]]
    org: NotRequired[ContactOrganization]
    phones: NotRequired[Annotated[list[ContactPhone], {"minItems": 1, "maxItems": 5}]]
    urls: NotRequired[Annotated[list[ContactUrl], {"minItems": 1, "maxItems": 3}]]


class ContactsMessage(TypedDict):
    contacts: Annotated[list[Contact], {"minItems": 1, "maxItems": 10}]
    reply_to_message_id: NotRequired[MessageId]


class ReactionMessage(TypedDict):
    message_id: MessageId
    emoji: Annotated[str, "One emoji, or an empty string to remove a reaction.", {"maxLength": 16}]


class ReadReceipt(TypedDict):
    message_id: MessageId
    typing_indicator: NotRequired[bool]


class SendMessageResult(TypedDict):
    recipient: Recipient
    whatsapp_id: Annotated[str, {"pattern": r"^[1-9][0-9]{7,19}$"}]
    message_id: Annotated[str, {"minLength": 1, "maxLength": 512}]


class ReadReceiptResult(TypedDict):
    message_id: MessageId
    read: bool
    typing_indicator: bool


class WhatsAppApiError(RuntimeError):
    """WhatsApp did not satisfy the declared Action contract."""


class WhatsAppTokenRejected(WhatsAppApiError):
    """WhatsApp explicitly rejected the supplied access token."""


class WhatsAppApiClient:
    def __init__(self, session: aiohttp.ClientSession, access_token: str) -> None:
        self._session = session
        self._access_token = _access_token(access_token)

    async def send_text_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        message: TextMessage,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        text = _text_message(message)
        return await self._send_message(
            sender,
            destination,
            "text",
            {"preview_url": text.get("preview_url", False), "body": text["body"]},
            text.get("reply_to_message_id"),
        )

    async def send_media_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        message: MediaMessage,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        media_type, media, reply_to = _media_message(message)
        return await self._send_message(sender, destination, media_type, media, reply_to)

    async def send_location_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        message: LocationMessage,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        location, reply_to = _location_message(message)
        return await self._send_message(sender, destination, "location", location, reply_to)

    async def send_contacts_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        message: ContactsMessage,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        contacts, reply_to = _contacts_message(message)
        return await self._send_message(sender, destination, "contacts", contacts, reply_to)

    async def set_message_reaction(
        self,
        sender_phone_number_id: str,
        recipient: str,
        reaction: ReactionMessage,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        content = _reaction_message(reaction)
        return await self._send_message(sender, destination, "reaction", content, None)

    async def mark_message_read(
        self,
        sender_phone_number_id: str,
        receipt: ReadReceipt,
    ) -> ReadReceiptResult:
        sender = _phone_number_id(sender_phone_number_id)
        message_id, typing_indicator = _read_receipt(receipt)
        body: dict[str, object] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if typing_indicator:
            body["typing_indicator"] = {"type": "text"}
        method = "POST" if typing_indicator else "PUT"
        payload = await self._request(sender, method, _encoded_body(body))
        if payload != {"success": True}:
            raise WhatsAppApiError("WhatsApp read receipt result is invalid")
        return {"message_id": message_id, "read": True, "typing_indicator": typing_indicator}

    async def send_template_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        template: dict[str, object],
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        return await self._send_message(sender, destination, "template", template, None)

    async def send_interactive_message(
        self,
        sender_phone_number_id: str,
        recipient: str,
        interactive: dict[str, object],
        reply_to_message_id: str | None = None,
    ) -> SendMessageResult:
        sender = _phone_number_id(sender_phone_number_id)
        destination = _recipient(recipient)
        return await self._send_message(sender, destination, "interactive", interactive, reply_to_message_id)

    async def _send_message(
        self,
        sender: str,
        destination: str,
        message_type: str,
        content: object,
        reply_to_message_id: str | None,
    ) -> SendMessageResult:
        body: dict[str, object] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destination,
            "type": message_type,
            message_type: content,
        }
        if reply_to_message_id is not None:
            body["context"] = {"message_id": reply_to_message_id}
        payload = await self._request(sender, "POST", _encoded_body(body))
        return _send_result(payload, destination)

    async def _request(self, sender: str, method: str, body: bytes) -> dict[str, Any]:
        path = f"/{GRAPH_API_VERSION}/{quote(sender, safe='')}/messages"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                method,
                f"{GRAPH_API_ORIGIN}{path}",
                headers=headers,
                data=body,
                allow_redirects=False,
            ) as response:
                raw = await _read_response(response)
                payload = _json_object(raw)
                if _error_code(payload) == 190:
                    raise WhatsAppTokenRejected("WhatsApp rejected the access token")
                if response.status != 200:
                    raise WhatsAppApiError("WhatsApp rejected the request")
                return payload
        except WhatsAppApiError:
            raise
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise WhatsAppApiError("WhatsApp request failed") from None


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


def _send_result(payload: dict[str, Any], recipient: str) -> SendMessageResult:
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


def _access_token(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 1024
        or any(not 33 <= ord(character) <= 126 for character in value)
    ):
        raise WhatsAppApiError("WhatsApp access token is invalid")
    return value


def _recipient(value: object) -> str:
    if not isinstance(value, str) or _RECIPIENT.fullmatch(value) is None:
        raise WhatsAppApiError("WhatsApp recipient is invalid")
    return value.removeprefix("+")


def _message_text(value: object) -> str:
    return _bounded_message_text(value, 4096)


def _bounded_message_text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or value != value.strip():
        raise WhatsAppApiError("WhatsApp message is invalid")
    if any((ord(character) < 32 and character not in "\n\t") or ord(character) == 127 for character in value):
        raise WhatsAppApiError("WhatsApp message is invalid")
    return value


def _text_message(value: object) -> TextMessage:
    message = _closed_object(value, required={"body"}, optional={"preview_url", "reply_to_message_id"})
    result: TextMessage = {"body": _message_text(message["body"])}
    if "preview_url" in message:
        preview_url = message["preview_url"]
        if type(preview_url) is not bool:
            raise WhatsAppApiError("WhatsApp text preview option is invalid")
        result["preview_url"] = preview_url
    if "reply_to_message_id" in message:
        result["reply_to_message_id"] = _message_id(message["reply_to_message_id"])
    return result


def _media_message(value: object) -> tuple[str, dict[str, object], str | None]:
    message = _closed_object(
        value,
        required={"media_type"},
        optional={"media_id", "link", "caption", "filename", "reply_to_message_id"},
    )
    media_type = message["media_type"]
    if not isinstance(media_type, str) or media_type not in {"audio", "document", "image", "sticker", "video"}:
        raise WhatsAppApiError("WhatsApp media type is invalid")
    sources = [key for key in ("media_id", "link") if key in message]
    if len(sources) != 1:
        raise WhatsAppApiError("WhatsApp media source is invalid")
    source = sources[0]
    source_value = (
        _public_text(message[source], 512) if source == "media_id" else _https_url(message[source])
    )
    media: dict[str, object] = {"id" if source == "media_id" else "link": source_value}
    if "caption" in message:
        if media_type not in {"document", "image", "video"}:
            raise WhatsAppApiError("WhatsApp media caption is invalid")
        media["caption"] = _bounded_message_text(message["caption"], 1024)
    if "filename" in message:
        if media_type != "document":
            raise WhatsAppApiError("WhatsApp media filename is invalid")
        media["filename"] = _public_text(message["filename"], 240)
    reply_to = _message_id(message["reply_to_message_id"]) if "reply_to_message_id" in message else None
    return media_type, media, reply_to


def media_message_summary(value: object) -> str:
    """Validate one media request and return a bounded approval summary."""
    media_type, media, reply_to = _media_message(value)
    source = "Meta media id" if "id" in media else "public HTTPS link"
    reply = " as a reply" if reply_to is not None else ""
    return f"{media_type} from {source}{reply}"


def _location_message(value: object) -> tuple[dict[str, object], str | None]:
    message = _closed_object(
        value,
        required={"latitude", "longitude"},
        optional={"name", "address", "reply_to_message_id"},
    )
    location: dict[str, object] = {
        "latitude": _coordinate(message["latitude"], minimum=-90.0, maximum=90.0),
        "longitude": _coordinate(message["longitude"], minimum=-180.0, maximum=180.0),
    }
    for field in ("name", "address"):
        if field in message:
            location[field] = _bounded_message_text(message[field], 1000)
    reply_to = _message_id(message["reply_to_message_id"]) if "reply_to_message_id" in message else None
    return location, reply_to


def location_message_summary(value: object) -> str:
    """Validate one location request and return a bounded approval summary."""
    location, reply_to = _location_message(value)
    reply = " as a reply" if reply_to is not None else ""
    return f"location at {location['latitude']}, {location['longitude']}{reply}"


def _coordinate(value: object, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WhatsAppApiError("WhatsApp location coordinate is invalid")
    coordinate = float(value)
    if not isfinite(coordinate) or not minimum <= coordinate <= maximum:
        raise WhatsAppApiError("WhatsApp location coordinate is invalid")
    return coordinate


def _contacts_message(value: object) -> tuple[list[dict[str, object]], str | None]:
    message = _closed_object(value, required={"contacts"}, optional={"reply_to_message_id"})
    contacts = _bounded_list(message["contacts"], minimum=1, maximum=10)
    result = [_contact(item) for item in contacts]
    reply_to = _message_id(message["reply_to_message_id"]) if "reply_to_message_id" in message else None
    return result, reply_to


def contacts_message_summary(value: object) -> str:
    """Validate one contacts request and return a bounded approval summary."""
    contacts, reply_to = _contacts_message(value)
    reply = " as a reply" if reply_to is not None else ""
    noun = "contact" if len(contacts) == 1 else "contacts"
    return f"{len(contacts)} {noun}{reply}"


def _contact(value: object) -> dict[str, object]:
    contact = _closed_object(
        value,
        required={"name"},
        optional={"addresses", "birthday", "emails", "org", "phones", "urls"},
    )
    result: dict[str, object] = {"name": _contact_name(contact["name"])}
    if "addresses" in contact:
        result["addresses"] = [
            _contact_address(item) for item in _bounded_list(contact["addresses"], minimum=1, maximum=3)
        ]
    if "birthday" in contact:
        result["birthday"] = _birthday(contact["birthday"])
    if "emails" in contact:
        result["emails"] = [
            _contact_email(item) for item in _bounded_list(contact["emails"], minimum=1, maximum=3)
        ]
    if "org" in contact:
        result["org"] = _contact_organization(contact["org"])
    if "phones" in contact:
        result["phones"] = [
            _contact_phone(item) for item in _bounded_list(contact["phones"], minimum=1, maximum=5)
        ]
    if "urls" in contact:
        result["urls"] = [
            _contact_url(item) for item in _bounded_list(contact["urls"], minimum=1, maximum=3)
        ]
    return result


def _contact_name(value: object) -> dict[str, object]:
    name = _closed_object(
        value,
        required={"formatted_name"},
        optional={"first_name", "last_name", "middle_name", "suffix", "prefix"},
    )
    return _text_fields(name, maximum=256)


def _contact_address(value: object) -> dict[str, object]:
    address = _closed_object(
        value,
        required=set(),
        optional={"street", "city", "state", "zip", "country", "country_code", "type"},
    )
    if not address or set(address) == {"type"}:
        raise WhatsAppApiError("WhatsApp contact address is invalid")
    result = _text_fields(address, maximum=256, excluded={"type", "country_code"})
    if "country_code" in address:
        country_code = _public_text(address["country_code"], 2)
        if re.fullmatch(r"[A-Za-z]{2}", country_code) is None:
            raise WhatsAppApiError("WhatsApp contact country code is invalid")
        result["country_code"] = country_code.lower()
    _copy_contact_type(address, result)
    return result


def _contact_email(value: object) -> dict[str, object]:
    email = _closed_object(value, required={"email"}, optional={"type"})
    address = _public_text(email["email"], 254)
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", address) is None:
        raise WhatsAppApiError("WhatsApp contact email is invalid")
    result: dict[str, object] = {"email": address}
    _copy_contact_type(email, result)
    return result


def _contact_organization(value: object) -> dict[str, object]:
    organization = _closed_object(value, required=set(), optional={"company", "department", "title"})
    if not organization:
        raise WhatsAppApiError("WhatsApp contact organization is invalid")
    return _text_fields(organization, maximum=256)


def _contact_phone(value: object) -> dict[str, object]:
    phone = _closed_object(value, required=set(), optional={"phone", "wa_id", "type"})
    if not ({"phone", "wa_id"} & set(phone)):
        raise WhatsAppApiError("WhatsApp contact phone is invalid")
    result: dict[str, object] = {}
    if "phone" in phone:
        result["phone"] = _public_text(phone["phone"], 32)
    if "wa_id" in phone:
        result["wa_id"] = _whatsapp_id(phone["wa_id"])
    _copy_contact_type(phone, result)
    return result


def _contact_url(value: object) -> dict[str, object]:
    contact_url = _closed_object(value, required={"url"}, optional={"type"})
    result: dict[str, object] = {"url": _https_url(contact_url["url"])}
    _copy_contact_type(contact_url, result)
    return result


def _copy_contact_type(source: dict[str, object], target: dict[str, object]) -> None:
    if "type" not in source:
        return
    contact_type = source["type"]
    if not isinstance(contact_type, str) or contact_type not in {"HOME", "WORK"}:
        raise WhatsAppApiError("WhatsApp contact field type is invalid")
    target["type"] = contact_type


def _text_fields(
    value: dict[str, object],
    *,
    maximum: int,
    excluded: set[str] | None = None,
) -> dict[str, object]:
    omitted = excluded or set()
    return {key: _bounded_message_text(item, maximum) for key, item in value.items() if key not in omitted}


def _birthday(value: object) -> str:
    birthday = _public_text(value, 10)
    try:
        parsed = date.fromisoformat(birthday)
    except ValueError:
        raise WhatsAppApiError("WhatsApp contact birthday is invalid") from None
    if parsed.isoformat() != birthday:
        raise WhatsAppApiError("WhatsApp contact birthday is invalid")
    return birthday


def _bounded_list(value: object, *, minimum: int, maximum: int) -> list[object]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise WhatsAppApiError("WhatsApp list is invalid")
    return value


def _encoded_body(body: dict[str, object]) -> bytes:
    encoded = json.dumps(body, allow_nan=False, ensure_ascii=False, separators=(",", ":")).encode()
    if not 1 <= len(encoded) <= MAX_REQUEST_BYTES:
        raise WhatsAppApiError("WhatsApp request size is invalid")
    return encoded


def _reaction_message(value: object) -> dict[str, object]:
    reaction = _closed_object(value, required={"message_id", "emoji"}, optional=set())
    emoji = reaction["emoji"]
    if not isinstance(emoji, str) or not _valid_reaction_emoji(emoji):
        raise WhatsAppApiError("WhatsApp reaction emoji is invalid")
    return {"message_id": _message_id(reaction["message_id"]), "emoji": emoji}


def reaction_message_summary(value: object) -> str:
    """Validate one reaction request and return a bounded approval summary."""
    reaction = _reaction_message(value)
    emoji = reaction["emoji"]
    return f"reaction {emoji}" if emoji else "reaction removal"


def _read_receipt(value: object) -> tuple[str, bool]:
    receipt = _closed_object(value, required={"message_id"}, optional={"typing_indicator"})
    typing_indicator = receipt.get("typing_indicator", False)
    if type(typing_indicator) is not bool:
        raise WhatsAppApiError("WhatsApp typing indicator is invalid")
    return _message_id(receipt["message_id"]), typing_indicator


def read_receipt_summary(value: object) -> str:
    """Validate one read receipt and return a bounded approval summary."""
    message_id, typing_indicator = _read_receipt(value)
    typing = " and show a typing indicator" if typing_indicator else ""
    return f"mark message {message_id} as read{typing}"


def _valid_reaction_emoji(value: str) -> bool:
    if value == "":
        return True
    pairs = [(character, unicodedata.category(character)) for character in value]
    if len(value) > 16 or any(
        character.isspace() or (category[0] == "C" and character != "\u200d")
        for character, category in pairs
    ):
        return False
    allowed = all(
        category[0] in {"M", "S"} or character in {"#", "*", "\u200d"} or character.isdecimal()
        for character, category in pairs
    )
    if not allowed:
        return False
    regional = [character for character, _category in pairs if "\U0001f1e6" <= character <= "\U0001f1ff"]
    if regional:
        return len(regional) == 2 and len(regional) == len(value)
    if "\u20e3" in value:
        return value[0] in "#*0123456789" and value.endswith("\u20e3")
    symbols = [category for _character, category in pairs if category.startswith("S") and category != "Sk"]
    return "\u200d" in value or len(symbols) == 1


def _message_id(value: object) -> str:
    message_id = _public_text(value, 512)
    if not message_id.startswith("wamid."):
        raise WhatsAppApiError("WhatsApp message id is invalid")
    return message_id


def _https_url(value: object) -> str:
    url = _public_text(value, 2048)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise WhatsAppApiError("WhatsApp media URL is invalid") from None
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
        or hostname is None
        or not _domain_name(hostname)
    ):
        raise WhatsAppApiError("WhatsApp media URL is invalid")
    return url


def _domain_name(hostname: str) -> bool:
    if not hostname.isascii() or len(hostname) > 253 or "." not in hostname or hostname.endswith("."):
        return False
    try:
        ip_address(hostname)
    except ValueError:
        pass
    else:
        return False
    return all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) is not None
        for label in hostname.split(".")
    )


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


def _closed_object(value: object, *, required: set[str], optional: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise WhatsAppApiError("WhatsApp object is invalid")
    if set(value) - required - optional or not required.issubset(value):
        raise WhatsAppApiError("WhatsApp object is invalid")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
