"""Send one reviewed WhatsApp media message."""

from shimpz import Context, action, text

from lib.approvals import media_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import MediaMessage, PhoneNumberId, Recipient, SendMessageResult


@action(
    description="Send a media file.",
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: MediaMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp media message", max_length=80),
        description=media_approval(sender_phone_number_id, recipient, message),
    ) as client:
        return await client.send_media_message(sender_phone_number_id, recipient, message)
