"""Send one reviewed WhatsApp product or catalog message."""

from shimpz import Context, action, text

from lib.approvals import commerce_approval
from lib.interactives import CommerceMessage
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: CommerceMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    interactive, description = commerce_approval(sender_phone_number_id, recipient, message)
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp catalog message", max_length=80),
        description=description,
    ) as client:
        return await client.send_interactive_message(sender_phone_number_id, recipient, interactive)
