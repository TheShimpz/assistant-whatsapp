"""Send one reviewed WhatsApp product or catalog message."""

from shimpz import Context, action

from lib.interactives import CommerceMessage, build_commerce_message, commerce_message_summary
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
    interactive = build_commerce_message(message)
    summary = commerce_message_summary(interactive)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp catalog message",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_interactive_message(sender_phone_number_id, recipient, interactive)
