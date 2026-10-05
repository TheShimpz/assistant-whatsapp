"""Send one reviewed WhatsApp text message."""

from shimpz import Context, action, text

from lib.approvals import text_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult, TextMessage


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
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp message", max_length=80),
        description=text_approval(sender_phone_number_id, recipient, message),
    ) as client:
        return await client.send_text_message(sender_phone_number_id, recipient, message)
