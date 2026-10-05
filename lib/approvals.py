"""Catalog copy for the approval that precedes every WhatsApp effect (ADR-0091).

Every description names the exact Meta sender phone-number id and recipient. Copy is English ``shimpz.text`` catalog
messages whose parameters render exactly, so prose that varies is a separate message. A value that no catalog
parameter can show exactly, such as an emoji, free-text Flow name, or provider message id outside the identifier
alphabet, is not interpolated; the message states what the approval covers instead.
"""

import re

from shimpz import Text, identifier, integer, text

from lib.interactives import build_choice_message, build_commerce_message, build_flow_message
from lib.templates import build_template_message
from lib.whatsapp import (
    _contacts_message,
    _location_message,
    _media_message,
    _phone_number_id,
    _reaction_message,
    _read_receipt,
    _recipient,
    _text_message,
)

# The catalog identifier alphabet and bound; a value outside it cannot render exactly in an approval.
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def _displayable(value: str) -> bool:
    return _IDENTIFIER.fullmatch(value) is not None


def _coordinate(value: float) -> str:
    return repr(abs(value))


def text_approval(sender: str, recipient: str, value: object) -> Text:
    """Validate one text request and describe its approval."""
    sender, recipient, message = _phone_number_id(sender), _recipient(recipient), _text_message(value)
    preview = message.get("preview_url", False)
    if "reply_to_message_id" in message:
        if preview:
            return text(
                "Send one reviewed text message with link preview as a reply from Meta phone-number id {sender} "
                "to {recipient}.",
                max_length=500,
                sender=identifier(sender, max_length=32),
                recipient=identifier(recipient, max_length=15),
            )
        return text(
            "Send one reviewed text message as a reply from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if preview:
        return text(
            "Send one reviewed text message with link preview from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Send one reviewed text message from Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def media_approval(sender: str, recipient: str, value: object) -> Text:
    """Validate one media request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    media_type, media, reply_to = _media_message(value)
    if "id" in media:
        if reply_to is not None:
            return text(
                "Send one reviewed {media_type} media message by Meta media id as a reply from Meta phone-number "
                "id {sender} to {recipient}.",
                max_length=500,
                media_type=identifier(media_type, max_length=8),
                sender=identifier(sender, max_length=32),
                recipient=identifier(recipient, max_length=15),
            )
        return text(
            "Send one reviewed {media_type} media message by Meta media id from Meta phone-number id {sender} to "
            "{recipient}.",
            max_length=500,
            media_type=identifier(media_type, max_length=8),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if reply_to is not None:
        return text(
            "Send one reviewed {media_type} media message by public HTTPS link as a reply from Meta phone-number "
            "id {sender} to {recipient}.",
            max_length=500,
            media_type=identifier(media_type, max_length=8),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Send one reviewed {media_type} media message by public HTTPS link from Meta phone-number id {sender} to "
        "{recipient}.",
        max_length=500,
        media_type=identifier(media_type, max_length=8),
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def location_approval(sender: str, recipient: str, value: object) -> Text:
    """Validate one location request and describe its approval with the exact coordinates."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    location, reply_to = _location_message(value)
    if reply_to is not None:
        return _location_reply_approval(sender, recipient, location["latitude"], location["longitude"])
    latitude, longitude = _coordinate(location["latitude"]), _coordinate(location["longitude"])
    if location["latitude"] >= 0 and location["longitude"] >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} north and longitude {longitude} east from Meta "
            "phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if location["latitude"] >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} north and longitude {longitude} west from Meta "
            "phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if location["longitude"] >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} south and longitude {longitude} east from Meta "
            "phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Send one reviewed location at latitude {latitude} south and longitude {longitude} west from Meta "
        "phone-number id {sender} to {recipient}.",
        max_length=500,
        latitude=identifier(latitude, max_length=32),
        longitude=identifier(longitude, max_length=32),
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def _location_reply_approval(sender: str, recipient: str, north: float, east: float) -> Text:
    latitude, longitude = _coordinate(north), _coordinate(east)
    if north >= 0 and east >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} north and longitude {longitude} east as a reply "
            "from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if north >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} north and longitude {longitude} west as a reply "
            "from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if east >= 0:
        return text(
            "Send one reviewed location at latitude {latitude} south and longitude {longitude} east as a reply "
            "from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            latitude=identifier(latitude, max_length=32),
            longitude=identifier(longitude, max_length=32),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Send one reviewed location at latitude {latitude} south and longitude {longitude} west as a reply from "
        "Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        latitude=identifier(latitude, max_length=32),
        longitude=identifier(longitude, max_length=32),
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def contacts_approval(sender: str, recipient: str, value: object) -> Text:
    """Validate one contacts request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    contacts, reply_to = _contacts_message(value)
    count = len(contacts)
    if reply_to is not None:
        if count == 1:
            return text(
                "Send 1 contact as a reply from Meta phone-number id {sender} to {recipient}.",
                max_length=500,
                sender=identifier(sender, max_length=32),
                recipient=identifier(recipient, max_length=15),
            )
        return text(
            "Send {count} contacts as a reply from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            count=integer(count, digits=2),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if count == 1:
        return text(
            "Send 1 contact from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Send {count} contacts from Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        count=integer(count, digits=2),
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def template_approval(sender: str, recipient: str, value: object) -> tuple[dict[str, object], Text]:
    """Build one template request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    template = build_template_message(value)
    name = str(template["name"])
    language = str(template["language"]["code"])
    if _displayable(name):
        return template, text(
            "Send one reviewed approved template {name} in {language} from Meta phone-number id {sender} to "
            "{recipient}.",
            max_length=500,
            name=identifier(name, max_length=128),
            language=identifier(language, max_length=6),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return template, text(
        "Send one reviewed approved template whose name is longer than 128 characters in {language} from Meta "
        "phone-number id {sender} to {recipient}.",
        max_length=500,
        language=identifier(language, max_length=6),
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def choice_approval(sender: str, recipient: str, value: object) -> tuple[dict[str, object], str | None, Text]:
    """Build one choice request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    interactive, reply_to = build_choice_message(value)
    action = interactive["action"]
    if interactive["type"] == "button":
        count = len(action["buttons"])
        if reply_to is not None:
            return (
                interactive,
                reply_to,
                text(
                    "Send one reviewed reply-button choice with {count} options as a reply from Meta phone-number id "
                    "{sender} to {recipient}.",
                    max_length=500,
                    count=integer(count, digits=3),
                    sender=identifier(sender, max_length=32),
                    recipient=identifier(recipient, max_length=15),
                ),
            )
        return (
            interactive,
            reply_to,
            text(
                "Send one reviewed reply-button choice with {count} options from Meta phone-number id {sender} to "
                "{recipient}.",
                max_length=500,
                count=integer(count, digits=3),
                sender=identifier(sender, max_length=32),
                recipient=identifier(recipient, max_length=15),
            ),
        )
    count = sum(len(section["rows"]) for section in action["sections"])
    if reply_to is not None:
        return (
            interactive,
            reply_to,
            text(
                "Send one reviewed list choice with {count} options as a reply from Meta phone-number id {sender} to "
                "{recipient}.",
                max_length=500,
                count=integer(count, digits=3),
                sender=identifier(sender, max_length=32),
                recipient=identifier(recipient, max_length=15),
            ),
        )
    return (
        interactive,
        reply_to,
        text(
            "Send one reviewed list choice with {count} options from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            count=integer(count, digits=3),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        ),
    )


def commerce_approval(sender: str, recipient: str, value: object) -> tuple[dict[str, object], Text]:
    """Build one product or catalog request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    interactive = build_commerce_message(value)
    if interactive["type"] == "product_list":
        count = sum(len(section["product_items"]) for section in interactive["action"]["sections"])
        return interactive, text(
            "Send one reviewed product list with {count} products from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            count=integer(count, digits=3),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if interactive["type"] == "product":
        return interactive, text(
            "Send one reviewed single product from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return interactive, text(
        "Send one reviewed catalog message from Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def flow_approval(sender: str, recipient: str, value: object) -> tuple[dict[str, object], Text]:
    """Build one Flow request and describe its approval, naming the Flow when it can render exactly."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    interactive = build_flow_message(value)
    parameters = interactive["action"]["parameters"]
    if "flow_id" in parameters and _displayable(parameters["flow_id"]):
        return interactive, text(
            "Send one reviewed published Flow with id {flow} from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            flow=identifier(parameters["flow_id"], max_length=128),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    if "flow_name" in parameters and _displayable(parameters["flow_name"]):
        return interactive, text(
            "Send one reviewed published Flow named {flow} from Meta phone-number id {sender} to {recipient}.",
            max_length=500,
            flow=identifier(parameters["flow_name"], max_length=128),
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return interactive, text(
        "Send one reviewed published Flow, identified in the request by a value this approval cannot display, "
        "from Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def reaction_approval(sender: str, recipient: str, value: object) -> Text:
    """Validate one reaction request and describe its approval."""
    sender, recipient = _phone_number_id(sender), _recipient(recipient)
    if _reaction_message(value)["emoji"]:
        return text(
            "Send one reviewed emoji reaction to an incoming message from Meta phone-number id {sender} to "
            "{recipient}.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            recipient=identifier(recipient, max_length=15),
        )
    return text(
        "Remove the reaction to an incoming message from Meta phone-number id {sender} to {recipient}.",
        max_length=500,
        sender=identifier(sender, max_length=32),
        recipient=identifier(recipient, max_length=15),
    )


def read_receipt_approval(sender: str, value: object) -> Text:
    """Validate one read receipt and describe its approval, naming the message when it can render exactly."""
    sender = _phone_number_id(sender)
    message_id, typing_indicator = _read_receipt(value)
    if _displayable(message_id):
        if typing_indicator:
            return text(
                "Use Meta phone-number id {sender} to mark message {message_id} as read and show a typing indicator.",
                max_length=500,
                sender=identifier(sender, max_length=32),
                message_id=identifier(message_id, max_length=128),
            )
        return text(
            "Use Meta phone-number id {sender} to mark message {message_id} as read.",
            max_length=500,
            sender=identifier(sender, max_length=32),
            message_id=identifier(message_id, max_length=128),
        )
    if typing_indicator:
        return text(
            "Use Meta phone-number id {sender} to mark the requested incoming message as read and show a typing "
            "indicator.",
            max_length=500,
            sender=identifier(sender, max_length=32),
        )
    return text(
        "Use Meta phone-number id {sender} to mark the requested incoming message as read.",
        max_length=500,
        sender=identifier(sender, max_length=32),
    )
