"""Send one reviewed WhatsApp location message."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import (
    LocationMessage,
    PhoneNumberId,
    Recipient,
    SendMessageResult,
    location_message_summary,
)


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    location: LocationMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    summary = location_message_summary(location)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp location",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_location_message(sender_phone_number_id, recipient, location)
