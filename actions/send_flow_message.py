"""Send one reviewed published WhatsApp Flow message."""

from shimpz import Context, action

from lib.interactives import FlowMessage, build_flow_message, flow_message_summary
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: FlowMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    interactive = build_flow_message(message)
    summary = flow_message_summary(interactive)
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp Flow",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_interactive_message(sender_phone_number_id, recipient, interactive)
