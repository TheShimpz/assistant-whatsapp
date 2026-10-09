"""Shared human-gated runtime for WhatsApp Actions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shimpz import Context, InputRequest, Text, text

from lib.whatsapp import WhatsAppApiClient, WhatsAppTokenRejected


@asynccontextmanager
async def approved_whatsapp_client(
    ctx: Context,
    *,
    title: Text,
    description: Text,
) -> AsyncIterator[WhatsAppApiClient]:
    """Approve one effect, make sure the Team holds the token, then expose a client whose calls the Team signs."""
    ctx.request_approval(title=title, description=description)
    ctx.request_input(
        InputRequest(
            kind="password",
            title=text("WhatsApp access token"),
            description=text("Enter the Meta access token used by this WhatsApp Action."),
            label=text("Meta access token"),
            min_length=1,
            max_length=1024,
            stored_input="whatsapp-token",
        )
    )
    try:
        yield WhatsAppApiClient(ctx)
    except WhatsAppTokenRejected:
        ctx.reject_stored_input("whatsapp-token")
        raise AssertionError("Stored Input rejection unexpectedly returned") from None
