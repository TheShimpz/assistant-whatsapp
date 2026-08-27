"""Send one reviewed WhatsApp text message."""

from shimpz import Context, InputRequest, action

from lib.whatsapp import (
    MessageText,
    PhoneNumberId,
    Recipient,
    SendTextMessageResult,
    WhatsAppApiClient,
    WhatsAppTokenRejected,
    create_http_session,
)


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: MessageText,
    *,
    ctx: Context,
) -> SendTextMessageResult:
    ctx.request_approval(
        title="Send this WhatsApp message",
        description=(
            f"Send one reviewed text message from Meta phone-number id {sender_phone_number_id} "
            f"to {recipient}."
        ),
    )
    token = ctx.request_input(
        InputRequest(
            kind="password",
            title="WhatsApp access token",
            description="Enter the Meta access token used by this WhatsApp Action.",
            label="Meta access token",
            min_length=1,
            max_length=2048,
            stored_input="whatsapp-token",
        )
    )
    try:
        async with create_http_session() as session:
            return await WhatsAppApiClient(session).send_text_message(
                sender_phone_number_id,
                recipient,
                message,
                token,
            )
    except WhatsAppTokenRejected:
        ctx.reject_stored_input("whatsapp-token")
        raise AssertionError("Stored Input rejection unexpectedly returned") from None
