"""Send one reviewed WhatsApp reply-button or list message."""

from shimpz import Context, action

from lib.interactives import ChoiceMessage, build_choice_message, choice_message_summary
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult


@action(
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
    interactive, reply_to = build_choice_message(message)
    summary = choice_message_summary(message)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp choice",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_interactive_message(sender_phone_number_id, recipient, interactive, reply_to)
