"""Send one reviewed WhatsApp reply-button or list message."""

from shimpz import Context, action, text

from lib.approvals import choice_approval
from lib.interactives import ChoiceMessage
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult


@action(
    description="Send a message with reply buttons or a list.",
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: ChoiceMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    interactive, reply_to, description = choice_approval(sender_phone_number_id, recipient, message)
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp choice", max_length=80),
        description=description,
    ) as client:
        return await client.send_interactive_message(sender_phone_number_id, recipient, interactive, reply_to)
