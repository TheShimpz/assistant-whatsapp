"""Send one reviewed WhatsApp text message."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import (
    PhoneNumberId,
    Recipient,
    SendMessageResult,
    TextMessage,
    text_message_summary,
)


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: TextMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    summary = text_message_summary(message)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp message",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} "
            f"to {recipient}."
        ),
    ) as client:
        return await client.send_text_message(sender_phone_number_id, recipient, message)
