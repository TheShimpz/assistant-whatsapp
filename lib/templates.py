"""Typed WhatsApp message-template request builders."""

import re
from typing import Annotated, Literal, NotRequired, TypedDict

from lib.whatsapp import (
    WhatsAppApiError,
    _bounded_list,
    _bounded_message_text,
    _closed_object,
    _https_url,
    _public_text,
)

TemplateName = Annotated[
    str,
    "Approved WhatsApp template name.",
    {"minLength": 1, "maxLength": 512, "pattern": r"^[a-z0-9_]+$"},
]
LanguageCode = Annotated[
    str,
    "Template language and optional locale code.",
    {"minLength": 2, "maxLength": 6, "pattern": r"^[a-z]{2,3}(?:_[A-Z]{2})?$"},
]
TemplateValue = Annotated[str, "Template parameter value.", {"minLength": 1, "maxLength": 1024}]
TemplateMediaId = Annotated[str, "Meta media object id.", {"minLength": 1, "maxLength": 512}]
TemplateMediaLink = Annotated[
    str,
    "Public HTTPS media URL for Meta to fetch.",
    {"minLength": 9, "maxLength": 2048, "pattern": r"^https://"},
]


class TemplateMedia(TypedDict):
    media_id: NotRequired[TemplateMediaId]
    link: NotRequired[TemplateMediaLink]
    filename: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 240}]]


class TemplateCurrency(TypedDict):
    fallback_value: Annotated[str, {"minLength": 1, "maxLength": 100}]
    code: Annotated[str, {"minLength": 3, "maxLength": 3, "pattern": r"^[A-Z]{3}$"}]
    amount_1000: Annotated[int, {"minimum": 0, "maximum": 9_000_000_000_000_000}]


class TemplateDateTime(TypedDict):
    fallback_value: Annotated[str, {"minLength": 1, "maxLength": 100}]
    day_of_week: NotRequired[Annotated[int, {"minimum": 1, "maximum": 7}]]
    year: NotRequired[Annotated[int, {"minimum": 1970, "maximum": 2100}]]
    month: NotRequired[Annotated[int, {"minimum": 1, "maximum": 12}]]
    day_of_month: NotRequired[Annotated[int, {"minimum": 1, "maximum": 31}]]
    hour: NotRequired[Annotated[int, {"minimum": 0, "maximum": 23}]]
    minute: NotRequired[Annotated[int, {"minimum": 0, "maximum": 59}]]
    calendar: NotRequired[Literal["GREGORIAN"]]


class FlowDataEntry(TypedDict):
    key: Annotated[str, {"minLength": 1, "maxLength": 64, "pattern": r"^[A-Za-z][A-Za-z0-9_]*$"}]
    value: Annotated[str, {"maxLength": 1024}]


class TemplateAction(TypedDict):
    thumbnail_product_retailer_id: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 256}]]
    flow_token: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 1024}]]
    flow_action_data: NotRequired[Annotated[list[FlowDataEntry], {"minItems": 1, "maxItems": 20}]]


class TemplateParameter(TypedDict):
    parameter_type: Literal[
        "text",
        "currency",
        "date_time",
        "image",
        "document",
        "video",
        "payload",
        "action",
        "coupon_code",
    ]
    text: NotRequired[TemplateValue]
    currency: NotRequired[TemplateCurrency]
    date_time: NotRequired[TemplateDateTime]
    media: NotRequired[TemplateMedia]
    payload: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 256}]]
    action: NotRequired[TemplateAction]
    coupon_code: NotRequired[Annotated[str, {"minLength": 1, "maxLength": 128}]]


class TemplateComponent(TypedDict):
    component_type: Literal["header", "body", "button"]
    sub_type: NotRequired[Literal["quick_reply", "url", "catalog", "flow", "copy_code"]]
    index: NotRequired[Annotated[int, {"minimum": 0, "maximum": 9}]]
    parameters: Annotated[list[TemplateParameter], {"minItems": 1, "maxItems": 20}]


class TemplateMessage(TypedDict):
    name: TemplateName
    language_code: LanguageCode
    components: NotRequired[Annotated[list[TemplateComponent], {"minItems": 1, "maxItems": 12}]]


def build_template_message(value: object) -> dict[str, object]:
    """Build one closed template object accepted by the messages endpoint."""
    message = _closed_object(value, required={"name", "language_code"}, optional={"components"})
    name = _public_text(message["name"], 512)
    if re.fullmatch(r"[a-z0-9_]+", name) is None:
        raise WhatsAppApiError("WhatsApp template name is invalid")
    language_code = _public_text(message["language_code"], 6)
    if re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", language_code) is None:
        raise WhatsAppApiError("WhatsApp template language is invalid")
    result: dict[str, object] = {"name": name, "language": {"code": language_code}}
    if "components" in message:
        components = [
            _template_component(item)
            for item in _bounded_list(message["components"], minimum=1, maximum=12)
        ]
        _validate_component_uniqueness(components)
        result["components"] = components
    return result


def _template_component(value: object) -> dict[str, object]:
    component = _closed_object(
        value,
        required={"component_type", "parameters"},
        optional={"sub_type", "index"},
    )
    component_type = component["component_type"]
    if not isinstance(component_type, str) or component_type not in {"header", "body", "button"}:
        raise WhatsAppApiError("WhatsApp template component type is invalid")
    if component_type == "button":
        return _template_button(component)
    if "sub_type" in component or "index" in component:
        raise WhatsAppApiError("WhatsApp template component is invalid")
    parameters = _bounded_list(component["parameters"], minimum=1, maximum=20)
    allowed = {"text", "image", "document", "video"} if component_type == "header" else {
        "text",
        "currency",
        "date_time",
    }
    if component_type == "header" and len(parameters) != 1:
        raise WhatsAppApiError("WhatsApp template header is invalid")
    return {
        "type": component_type,
        "parameters": [_template_parameter(item, allowed=allowed) for item in parameters],
    }


def _template_button(component: dict[str, object]) -> dict[str, object]:
    sub_type = component.get("sub_type")
    index = component.get("index")
    if (
        not isinstance(sub_type, str)
        or sub_type not in {"quick_reply", "url", "catalog", "flow", "copy_code"}
        or isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index <= 9
    ):
        raise WhatsAppApiError("WhatsApp template button is invalid")
    parameters = _bounded_list(component["parameters"], minimum=1, maximum=1)
    allowed_by_subtype = {
        "quick_reply": {"payload"},
        "url": {"text"},
        "catalog": {"action"},
        "flow": {"action"},
        "copy_code": {"coupon_code"},
    }
    output_subtype = "CATALOG" if sub_type == "catalog" else sub_type
    return {
        "type": "button",
        "sub_type": output_subtype,
        "index": str(index),
        "parameters": [
            _template_parameter(parameters[0], allowed=allowed_by_subtype[sub_type], button_subtype=sub_type)
        ],
    }


def _template_parameter(
    value: object,
    *,
    allowed: set[str],
    button_subtype: str | None = None,
) -> dict[str, object]:
    parameter = _closed_object(
        value,
        required={"parameter_type"},
        optional={"text", "currency", "date_time", "media", "payload", "action", "coupon_code"},
    )
    parameter_type = parameter["parameter_type"]
    if not isinstance(parameter_type, str) or parameter_type not in allowed:
        raise WhatsAppApiError("WhatsApp template parameter type is invalid")
    field = {
        "text": "text",
        "currency": "currency",
        "date_time": "date_time",
        "image": "media",
        "document": "media",
        "video": "media",
        "payload": "payload",
        "action": "action",
        "coupon_code": "coupon_code",
    }[parameter_type]
    if set(parameter) != {"parameter_type", field}:
        raise WhatsAppApiError("WhatsApp template parameter is invalid")
    return _build_parameter(parameter_type, parameter[field], button_subtype=button_subtype)


def _build_parameter(parameter_type: str, value: object, *, button_subtype: str | None) -> dict[str, object]:
    if parameter_type == "text":
        return {"type": "text", "text": _bounded_message_text(value, 1024)}
    if parameter_type == "currency":
        return {"type": "currency", "currency": _template_currency(value)}
    if parameter_type == "date_time":
        return {"type": "date_time", "date_time": _template_date_time(value)}
    if parameter_type in {"image", "document", "video"}:
        return {"type": parameter_type, parameter_type: _template_media(value, parameter_type)}
    if parameter_type == "payload":
        return {"type": "payload", "payload": _public_text(value, 256)}
    if parameter_type == "coupon_code":
        return {"type": "coupon_code", "coupon_code": _public_text(value, 128)}
    if parameter_type == "action":
        return {"type": "action", "action": _template_action(value, button_subtype)}
    raise WhatsAppApiError("WhatsApp template parameter type is invalid")


def _template_media(value: object, media_type: str) -> dict[str, object]:
    media = _closed_object(value, required=set(), optional={"media_id", "link", "filename"})
    sources = [key for key in ("media_id", "link") if key in media]
    if len(sources) != 1 or ("filename" in media and media_type != "document"):
        raise WhatsAppApiError("WhatsApp template media is invalid")
    source = sources[0]
    result: dict[str, object] = {
        "id" if source == "media_id" else "link": (
            _public_text(media[source], 512) if source == "media_id" else _https_url(media[source])
        )
    }
    if "filename" in media:
        result["filename"] = _public_text(media["filename"], 240)
    return result


def _template_currency(value: object) -> dict[str, object]:
    currency = _closed_object(value, required={"fallback_value", "code", "amount_1000"}, optional=set())
    code = _public_text(currency["code"], 3)
    amount = currency["amount_1000"]
    if re.fullmatch(r"[A-Z]{3}", code) is None or isinstance(amount, bool) or not isinstance(amount, int):
        raise WhatsAppApiError("WhatsApp template currency is invalid")
    if not 0 <= amount <= 9_000_000_000_000_000:
        raise WhatsAppApiError("WhatsApp template currency is invalid")
    return {
        "fallback_value": _bounded_message_text(currency["fallback_value"], 100),
        "code": code,
        "amount_1000": amount,
    }


def _template_date_time(value: object) -> dict[str, object]:
    date_time = _closed_object(
        value,
        required={"fallback_value"},
        optional={"day_of_week", "year", "month", "day_of_month", "hour", "minute", "calendar"},
    )
    result: dict[str, object] = {"fallback_value": _bounded_message_text(date_time["fallback_value"], 100)}
    bounds = {
        "day_of_week": (1, 7),
        "year": (1970, 2100),
        "month": (1, 12),
        "day_of_month": (1, 31),
        "hour": (0, 23),
        "minute": (0, 59),
    }
    for field, (minimum, maximum) in bounds.items():
        if field in date_time:
            item = date_time[field]
            if isinstance(item, bool) or not isinstance(item, int) or not minimum <= item <= maximum:
                raise WhatsAppApiError("WhatsApp template date-time is invalid")
            result[field] = item
    if "calendar" in date_time:
        if date_time["calendar"] != "GREGORIAN":
            raise WhatsAppApiError("WhatsApp template calendar is invalid")
        result["calendar"] = "GREGORIAN"
    return result


def _template_action(value: object, button_subtype: str | None) -> dict[str, object]:
    action = _closed_object(
        value,
        required=set(),
        optional={"thumbnail_product_retailer_id", "flow_token", "flow_action_data"},
    )
    if button_subtype == "catalog" and set(action) == {"thumbnail_product_retailer_id"}:
        return {"thumbnail_product_retailer_id": _public_text(action["thumbnail_product_retailer_id"], 256)}
    if button_subtype != "flow" or "flow_token" not in action or "thumbnail_product_retailer_id" in action:
        raise WhatsAppApiError("WhatsApp template action is invalid")
    result: dict[str, object] = {"flow_token": _public_text(action["flow_token"], 1024)}
    if "flow_action_data" in action:
        entries = _bounded_list(action["flow_action_data"], minimum=1, maximum=20)
        data: dict[str, str] = {}
        for entry in entries:
            item = _closed_object(entry, required={"key", "value"}, optional=set())
            key = _public_text(item["key"], 64)
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key) is None or key in data:
                raise WhatsAppApiError("WhatsApp template Flow data is invalid")
            raw_value = item["value"]
            if (
                not isinstance(raw_value, str)
                or len(raw_value) > 1024
                or any(ord(char) < 32 or ord(char) == 127 for char in raw_value)
            ):
                raise WhatsAppApiError("WhatsApp template Flow data is invalid")
            data[key] = raw_value
        result["flow_action_data"] = data
    return result


def _validate_component_uniqueness(components: list[dict[str, object]]) -> None:
    identities: set[tuple[object, object]] = set()
    for component in components:
        identity = (component["type"], component.get("index"))
        if identity in identities:
            raise WhatsAppApiError("WhatsApp template components are duplicated")
        identities.add(identity)
