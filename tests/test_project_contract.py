from __future__ import annotations

import inspect
import re
import tomllib
from pathlib import Path

from shimpz.action import ActionMetadata, get_action_metadata

from actions.send_location_message import run as send_location_message
from actions.send_media_message import run as send_media_message
from actions.send_text_message import run as send_text_message

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_declares_one_stored_token_and_fixed_egress() -> None:
    manifest = tomllib.loads((ROOT / "shimpz.toml").read_text(encoding="utf-8"))

    assert set(manifest) == {"shimpz", "network", "stored_inputs"}
    metadata = manifest["shimpz"]
    assert set(metadata) == {"spec", "id", "version", "name", "summary", "creators", "github", "genesis"}
    assert metadata["spec"] == 1
    assert metadata["id"] == "whatsapp"
    assert re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", metadata["version"])
    assert manifest["network"] == {"allowed_hosts": ["graph.facebook.com"]}
    assert manifest["stored_inputs"] == {
        "whatsapp-token": {
            "kind": "password",
            "label": "WhatsApp access token",
            "description": "Meta access token used by the WhatsApp Cloud API.",
        }
    }


def test_action_declares_exact_human_and_stored_input_contract() -> None:
    for body in (send_location_message, send_media_message, send_text_message):
        assert inspect.iscoroutinefunction(body)
        context = inspect.signature(body).parameters["ctx"]
        assert context.kind is inspect.Parameter.KEYWORD_ONLY
        assert context.default is inspect.Parameter.empty
        metadata = get_action_metadata(body)
        assert isinstance(metadata, ActionMetadata)
        assert metadata.integrations == ()
        assert metadata.stored_inputs == ("whatsapp-token",)
        assert metadata.human_requests == ("approval", "input:password")
