"""Shared human-gated runtime for WhatsApp Actions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shimpz import Context, InputRequest

from lib.whatsapp import WhatsAppApiClient, WhatsAppTokenRejected, create_http_session


@asynccontextmanager
async def approved_whatsapp_client(
    ctx: Context,
    *,
    title: str,
    description: str,
) -> AsyncIterator[WhatsAppApiClient]:
    """Approve one effect, then expose a token-bound client for that effect."""
    ctx.request_approval(title=title, description=description)
    token = ctx.request_input(
        InputRequest(
            kind="password",
            title="WhatsApp access token",
            description="Enter the Meta access token used by this WhatsApp Action.",
            label="Meta access token",
            min_length=1,
            max_length=1024,
            stored_input="whatsapp-token",
        )
    )
    try:
        async with create_http_session() as session:
            client = WhatsAppApiClient(session, token)
            try:
                yield client
            finally:
                del client
    except WhatsAppTokenRejected:
        ctx.reject_stored_input("whatsapp-token")
        raise AssertionError("Stored Input rejection unexpectedly returned") from None
    finally:
        token = ""
