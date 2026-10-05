"""Send one reviewed WhatsApp location message."""

from shimpz import Context, action, text

from lib.approvals import location_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import LocationMessage, PhoneNumberId, Recipient, SendMessageResult


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
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp location", max_length=80),
        description=location_approval(sender_phone_number_id, recipient, location),
    ) as client:
        return await client.send_location_message(sender_phone_number_id, recipient, location)
