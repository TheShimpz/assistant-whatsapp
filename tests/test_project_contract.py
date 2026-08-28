from __future__ import annotations

import asyncio
import inspect
import re
import tomllib
from pathlib import Path
from types import ModuleType
from typing import NotRequired, Required, get_origin, get_type_hints, is_typeddict

import pytest
from shimpz._human import HumanRequestSuspension
from shimpz._project import AssistantProject
from shimpz._runtime import ActionInvocation, invoke_action
from shimpz._schema import schema_for_type
from shimpz.action import ActionMetadata, get_action_metadata

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
from lib import interactives, templates, whatsapp

ROOT = Path(__file__).resolve().parents[1]
MODEL_MODULES = (whatsapp, templates, interactives)


def test_manifest_declares_one_stored_token_and_fixed_egress() -> None:
    manifest = tomllib.loads((ROOT / "shimpz.toml").read_text(encoding="utf-8"))

    assert set(manifest) == {"shimpz", "network", "stored_inputs"}
    metadata = manifest["shimpz"]
    assert set(metadata) == {"spec", "id", "version", "name", "summary", "creators", "github", "genesis"}
    assert metadata["spec"] == 1
    assert metadata["id"] == "whatsapp"
    assert re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", metadata["version"])
    assert metadata["version"] == "0.2.0"
    assert manifest["network"] == {"allowed_hosts": ["graph.facebook.com"]}
    assert manifest["stored_inputs"] == {
        "whatsapp-token": {
            "kind": "password",
            "label": "WhatsApp access token",
            "description": "Meta access token used by the WhatsApp Cloud API.",
        }
    }


def test_action_declares_exact_human_and_stored_input_contract() -> None:
    for body in (
        mark_message_read,
        send_choice_message,
        send_catalog_message,
        send_contacts_message,
        send_flow_message,
        send_location_message,
        send_media_message,
        send_template_message,
        send_text_message,
        set_message_reaction,
    ):
        assert inspect.iscoroutinefunction(body)
        context = inspect.signature(body).parameters["ctx"]
        assert context.kind is inspect.Parameter.KEYWORD_ONLY
        assert context.default is inspect.Parameter.empty
        metadata = get_action_metadata(body)
        assert isinstance(metadata, ActionMetadata)
        assert metadata.integrations == ()
        assert metadata.stored_inputs == ("whatsapp-token",)
        assert metadata.human_requests == ("approval", "input:password")


def _module_typed_dicts(module: ModuleType) -> tuple[type, ...]:
    return tuple(
        candidate
        for candidate in vars(module).values()
        if is_typeddict(candidate) and candidate.__module__ == module.__name__
    )


def _expected_typed_dict_keys(model: type) -> tuple[set[str], set[str]]:
    hints = get_type_hints(model, include_extras=True)
    required: set[str] = set()
    optional: set[str] = set()
    for name, annotation in hints.items():
        origin = get_origin(annotation)
        if origin is Required or (origin is not NotRequired and model.__total__):
            required.add(name)
        else:
            optional.add(name)
    return required, optional


def test_every_typed_dict_publishes_exact_required_and_optional_keys() -> None:
    for module in MODEL_MODULES:
        for model in _module_typed_dicts(module):
            required, optional = _expected_typed_dict_keys(model)
            assert set(model.__required_keys__) == required, model.__name__
            assert set(model.__optional_keys__) == optional, model.__name__
            assert set(schema_for_type(model)["required"]) == required, model.__name__


def test_model_modules_keep_runtime_typed_dict_annotations() -> None:
    for module in MODEL_MODULES:
        source = (ROOT / f"lib/{module.__name__.removeprefix('lib.')}.py").read_text(encoding="utf-8")
        assert "from __future__ import annotations" not in source


@pytest.fixture(scope="module")
def assistant_project() -> AssistantProject:
    return AssistantProject.load(ROOT)


@pytest.mark.parametrize(
    ("action_id", "inputs"),
    [
        (
            "mark-message-read",
            {"sender_phone_number_id": "123456789012345", "receipt": {"message_id": "wamid.incoming"}},
        ),
        (
            "send-catalog-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "commerce_type": "product",
                    "catalog_id": "367025965434465",
                    "product_retailer_id": "sku-1",
                },
            },
        ),
        (
            "send-choice-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "choice_type": "button",
                    "body": "Choose",
                    "buttons": [{"id": "yes", "title": "Yes"}],
                },
            },
        ),
        (
            "send-choice-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "choice_type": "list",
                    "body": "Choose",
                    "list_button": "Options",
                    "sections": [{"rows": [{"id": "one", "title": "One"}]}],
                },
            },
        ),
        (
            "send-contacts-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "contacts": [
                        {"name": {"formatted_name": "Ana Silva"}, "phones": [{"phone": "+55 11 99999-0000"}]}
                    ]
                },
            },
        ),
        (
            "send-contacts-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "contacts": [
                        {"name": {"formatted_name": "Ana Silva"}, "phones": [{"wa_id": "5511999990000"}]}
                    ]
                },
            },
        ),
        (
            "send-flow-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "flow_id": "987654321",
                    "flow_token": "appointment-42",
                    "flow_cta": "Schedule",
                    "flow_action": "navigate",
                    "screen": "APPOINTMENT",
                    "body": "Choose a time",
                },
            },
        ),
        (
            "send-flow-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "flow_name": "support_intake",
                    "flow_token": "support-43",
                    "flow_cta": "Start",
                    "flow_action": "data_exchange",
                    "body": "Describe the issue",
                },
            },
        ),
        (
            "send-location-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "location": {"latitude": -23.55052, "longitude": -46.633308},
            },
        ),
        (
            "send-media-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {"media_type": "image", "media_id": "123456789"},
            },
        ),
        (
            "send-media-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {"media_type": "image", "link": "https://cdn.example.com/image.jpg"},
            },
        ),
        (
            "send-template-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {"name": "hello_world", "language_code": "en_US"},
            },
        ),
        (
            "send-template-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "name": "image_header",
                    "language_code": "en_US",
                    "components": [
                        {
                            "component_type": "header",
                            "parameters": [{"parameter_type": "image", "media": {"media_id": "123456789"}}],
                        }
                    ],
                },
            },
        ),
        (
            "send-template-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {
                    "name": "image_header",
                    "language_code": "en_US",
                    "components": [
                        {
                            "component_type": "header",
                            "parameters": [
                                {
                                    "parameter_type": "image",
                                    "media": {"link": "https://cdn.example.com/image.jpg"},
                                }
                            ],
                        }
                    ],
                },
            },
        ),
        (
            "send-text-message",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "message": {"body": "Hello"},
            },
        ),
        (
            "set-message-reaction",
            {
                "sender_phone_number_id": "123456789012345",
                "recipient": "15555550123",
                "reaction": {"message_id": "wamid.incoming", "emoji": "✅"},
            },
        ),
    ],
)
def test_minimal_action_forms_reach_approval(
    assistant_project: AssistantProject,
    action_id: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(HumanRequestSuspension) as suspended:
        asyncio.run(
            invoke_action(
                assistant_project,
                action_id,
                ActionInvocation(inputs=inputs, integrations={}, stored_inputs={}, responses=()),
            )
        )

    assert suspended.value.request["kind"] == "approval"
