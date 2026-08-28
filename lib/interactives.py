"""Typed WhatsApp interactive-message request builders."""

from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from lib.whatsapp import (
    MessageId,
    WhatsAppApiError,
    _bounded_list,
    _bounded_message_text,
    _closed_object,
    _https_url,
    _message_id,
    _public_text,
)

BodyText = Annotated[str, "Interactive message body.", {"minLength": 1, "maxLength": 1024}]
HeaderText = Annotated[str, "Interactive message header.", {"minLength": 1, "maxLength": 60}]
FooterText = Annotated[str, "Interactive message footer.", {"minLength": 1, "maxLength": 60}]
OpaqueId = Annotated[str, "Stable reply identifier.", {"minLength": 1, "maxLength": 256}]


class InteractiveHeader(TypedDict):
    header_type: Literal["text", "image", "video", "document"]
    text: NotRequired[HeaderText]
    media_id: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 512}]]
    link: NotRequired[Annotated[str, {"minLength": 9, "maxLength": 2048, "pattern": r"^https://"}]]
    filename: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 240}]]


class ReplyButton(TypedDict):
    id: OpaqueId
    title: Annotated[str, {"minLength": 1, "maxLength": 20}]


class ListRow(TypedDict):
    id: OpaqueId
    title: Annotated[str, {"minLength": 1, "maxLength": 24}]
    description: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 72}]]


class ListSection(TypedDict):
    title: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 24}]]
    rows: Annotated[list[ListRow], {"minItems": 1, "maxItems": 10}]


class ChoiceMessage(TypedDict):
    choice_type: Literal["button", "list"]
    body: BodyText
    header: NotRequired[InteractiveHeader]
    footer: NotRequired[FooterText]
    buttons: NotRequired[Annotated[list[ReplyButton], {"minItems": 1, "maxItems": 3}]]
    list_button: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 20}]]
    sections: NotRequired[Annotated[list[ListSection], {"minItems": 1, "maxItems": 10}]]
    reply_to_message_id: NotRequired[MessageId]


class ProductItem(TypedDict):
    product_retailer_id: Annotated[str, {"minLength": 1, "maxLength": 256}]


class ProductSection(TypedDict):
    title: Annotated[str, {"minLength": 1, "maxLength": 24}]
    product_items: Annotated[list[ProductItem], {"minItems": 1, "maxItems": 30}]


class CommerceMessage(TypedDict):
    commerce_type: Literal["product", "product_list", "catalog"]
    catalog_id: NotRequired[Annotated[str, {"minLength": 5, "maxLength": 32, "pattern": r"^[1-9][0-9]+$"}]]
    product_retailer_id: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 256}]]
    header: NotRequired[HeaderText]
    body: NotRequired[BodyText]
    footer: NotRequired[FooterText]
    sections: NotRequired[Annotated[list[ProductSection], {"minItems": 1, "maxItems": 10}]]
    thumbnail_product_retailer_id: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 256}]]


def build_choice_message(value: object) -> tuple[dict[str, object], str | None]:
    """Build a reply-button or list interactive object and optional reply context."""
    message = _closed_object(
        value,
        required={"choice_type", "body"},
        optional={"header", "footer", "buttons", "list_button", "sections", "reply_to_message_id"},
    )
    choice_type = message["choice_type"]
    if not isinstance(choice_type, str) or choice_type not in {"button", "list"}:
        raise WhatsAppApiError("WhatsApp choice type is invalid")
    result: dict[str, object] = {
        "type": choice_type,
        "body": {"text": _bounded_message_text(message["body"], 1024)},
    }
    if "header" in message:
        result["header"] = _interactive_header(message["header"], allow_media=choice_type == "button")
    if "footer" in message:
        result["footer"] = {"text": _bounded_message_text(message["footer"], 60)}
    if choice_type == "button":
        result["action"] = _reply_button_action(message)
    else:
        result["action"] = _list_action(message)
    reply_to = _message_id(message["reply_to_message_id"]) if "reply_to_message_id" in message else None
    return result, reply_to


def choice_message_summary(interactive: dict[str, object], reply_to: str | None) -> str:
    """Return a bounded approval summary for one built choice message."""
    action = interactive["action"]
    count = len(action["buttons"]) if interactive["type"] == "button" else sum(
        len(section["rows"]) for section in action["sections"]
    )
    reply = " as a reply" if reply_to is not None else ""
    return f"{interactive['type']} choice with {count} options{reply}"


def build_commerce_message(value: object) -> dict[str, object]:
    """Build a single-product, multi-product, or catalog interactive object."""
    message = _closed_object(
        value,
        required={"commerce_type"},
        optional={
            "catalog_id",
            "product_retailer_id",
            "header",
            "body",
            "footer",
            "sections",
            "thumbnail_product_retailer_id",
        },
    )
    commerce_type = message["commerce_type"]
    if not isinstance(commerce_type, str) or commerce_type not in {"product", "product_list", "catalog"}:
        raise WhatsAppApiError("WhatsApp commerce type is invalid")
    if commerce_type == "product":
        return _single_product(message)
    if commerce_type == "product_list":
        return _product_list(message)
    return _catalog(message)


def commerce_message_summary(interactive: dict[str, object]) -> str:
    """Return a bounded approval summary for one built commerce message."""
    if interactive["type"] == "product_list":
        count = sum(len(section["product_items"]) for section in interactive["action"]["sections"])
        return f"product list with {count} products"
    return str(interactive["type"]).replace("_", " ")


def _single_product(message: dict[str, object]) -> dict[str, object]:
    required = {"commerce_type", "catalog_id", "product_retailer_id"}
    if set(message) - required - {"body", "footer"} or not required.issubset(message):
        raise WhatsAppApiError("WhatsApp single-product message is invalid")
    result: dict[str, object] = {
        "type": "product",
        "action": {
            "catalog_id": _catalog_id(message["catalog_id"]),
            "product_retailer_id": _public_text(message["product_retailer_id"], 256),
        },
    }
    _copy_body_footer(message, result)
    return result


def _product_list(message: dict[str, object]) -> dict[str, object]:
    required = {"commerce_type", "catalog_id", "header", "body", "sections"}
    if set(message) - required - {"footer"} or not required.issubset(message):
        raise WhatsAppApiError("WhatsApp product-list message is invalid")
    sections = [
        _product_section(item) for item in _bounded_list(message["sections"], minimum=1, maximum=10)
    ]
    product_ids = [item["product_retailer_id"] for section in sections for item in section["product_items"]]
    if not 1 <= len(product_ids) <= 30 or len(product_ids) != len(set(product_ids)):
        raise WhatsAppApiError("WhatsApp product-list items are invalid")
    result: dict[str, object] = {
        "type": "product_list",
        "header": {"type": "text", "text": _bounded_message_text(message["header"], 60)},
        "body": {"text": _bounded_message_text(message["body"], 1024)},
        "action": {"catalog_id": _catalog_id(message["catalog_id"]), "sections": sections},
    }
    if "footer" in message:
        result["footer"] = {"text": _bounded_message_text(message["footer"], 60)}
    return result


def _product_section(value: object) -> dict[str, object]:
    section = _closed_object(value, required={"title", "product_items"}, optional=set())
    return {
        "title": _bounded_message_text(section["title"], 24),
        "product_items": [
            _product_item(item) for item in _bounded_list(section["product_items"], minimum=1, maximum=30)
        ],
    }


def _product_item(value: object) -> dict[str, object]:
    item = _closed_object(value, required={"product_retailer_id"}, optional=set())
    return {"product_retailer_id": _public_text(item["product_retailer_id"], 256)}


def _catalog(message: dict[str, object]) -> dict[str, object]:
    required = {"commerce_type", "body"}
    if set(message) - required - {"footer", "thumbnail_product_retailer_id"} or not required.issubset(message):
        raise WhatsAppApiError("WhatsApp catalog message is invalid")
    action: dict[str, object] = {"name": "catalog_message"}
    if "thumbnail_product_retailer_id" in message:
        action["parameters"] = {
            "thumbnail_product_retailer_id": _public_text(message["thumbnail_product_retailer_id"], 256)
        }
    result: dict[str, object] = {"type": "catalog_message", "action": action}
    _copy_body_footer(message, result)
    return result


def _copy_body_footer(source: dict[str, object], target: dict[str, object]) -> None:
    if "body" in source:
        target["body"] = {"text": _bounded_message_text(source["body"], 1024)}
    if "footer" in source:
        target["footer"] = {"text": _bounded_message_text(source["footer"], 60)}


def _catalog_id(value: object) -> str:
    catalog_id = _public_text(value, 32)
    if len(catalog_id) < 5 or not catalog_id.isascii() or not catalog_id.isdigit() or catalog_id.startswith("0"):
        raise WhatsAppApiError("WhatsApp catalog id is invalid")
    return catalog_id


def _reply_button_action(message: dict[str, object]) -> dict[str, object]:
    if "list_button" in message or "sections" in message or "buttons" not in message:
        raise WhatsAppApiError("WhatsApp reply buttons are invalid")
    buttons = _bounded_list(message["buttons"], minimum=1, maximum=3)
    result = [_reply_button(item) for item in buttons]
    ids = [button["reply"]["id"] for button in result]
    if len(ids) != len(set(ids)):
        raise WhatsAppApiError("WhatsApp reply button ids are duplicated")
    return {"buttons": result}


def _reply_button(value: object) -> dict[str, object]:
    button = _closed_object(value, required={"id", "title"}, optional=set())
    return {
        "type": "reply",
        "reply": {"id": _public_text(button["id"], 256), "title": _bounded_message_text(button["title"], 20)},
    }


def _list_action(message: dict[str, object]) -> dict[str, object]:
    if "buttons" in message or "list_button" not in message or "sections" not in message:
        raise WhatsAppApiError("WhatsApp list message is invalid")
    sections = [_list_section(item) for item in _bounded_list(message["sections"], minimum=1, maximum=10)]
    rows = [row for section in sections for row in section["rows"]]
    if not 1 <= len(rows) <= 10:
        raise WhatsAppApiError("WhatsApp list rows are invalid")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise WhatsAppApiError("WhatsApp list row ids are duplicated")
    return {"button": _bounded_message_text(message["list_button"], 20), "sections": sections}


def _list_section(value: object) -> dict[str, object]:
    section = _closed_object(value, required={"rows"}, optional={"title"})
    result: dict[str, object] = {
        "rows": [_list_row(item) for item in _bounded_list(section["rows"], minimum=1, maximum=10)]
    }
    if "title" in section:
        result["title"] = _bounded_message_text(section["title"], 24)
    return result


def _list_row(value: object) -> dict[str, object]:
    row = _closed_object(value, required={"id", "title"}, optional={"description"})
    result: dict[str, object] = {
        "id": _public_text(row["id"], 256),
        "title": _bounded_message_text(row["title"], 24),
    }
    if "description" in row:
        result["description"] = _bounded_message_text(row["description"], 72)
    return result


def _interactive_header(value: object, *, allow_media: bool) -> dict[str, object]:
    header = _closed_object(
        value,
        required={"header_type"},
        optional={"text", "media_id", "link", "filename"},
    )
    header_type = header["header_type"]
    if not isinstance(header_type, str) or header_type not in {"text", "image", "video", "document"}:
        raise WhatsAppApiError("WhatsApp interactive header type is invalid")
    if header_type == "text":
        if set(header) != {"header_type", "text"}:
            raise WhatsAppApiError("WhatsApp interactive text header is invalid")
        return {"type": "text", "text": _bounded_message_text(header["text"], 60)}
    if not allow_media:
        raise WhatsAppApiError("WhatsApp list header must be text")
    sources = [field for field in ("media_id", "link") if field in header]
    if len(sources) != 1 or "text" in header or ("filename" in header and header_type != "document"):
        raise WhatsAppApiError("WhatsApp interactive media header is invalid")
    source = sources[0]
    media: dict[str, object] = {
        "id" if source == "media_id" else "link": (
            _public_text(header[source], 512) if source == "media_id" else _https_url(header[source])
        )
    }
    if "filename" in header:
        media["filename"] = _public_text(header["filename"], 240)
    return {"type": header_type, header_type: media}
