"""Send one reviewed WhatsApp media message."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import (
    MediaMessage,
    PhoneNumberId,
    Recipient,
    SendTextMessageResult,
    media_message_summary,
)


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: MediaMessage,
    *,
    ctx: Context,
) -> SendTextMessageResult:
    summary = media_message_summary(message)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp media message",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_media_message(sender_phone_number_id, recipient, message)
