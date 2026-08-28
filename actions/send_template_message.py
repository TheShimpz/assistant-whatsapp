"""Send one reviewed approved WhatsApp message template."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.templates import TemplateMessage, build_template_message
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult, approval_identifier


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: TemplateMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    template = build_template_message(message)
    summary = f"approved template {approval_identifier(message['name'])} in {message['language_code']}"
    async with approved_whatsapp_client(
        ctx,
        title="Send this WhatsApp template",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_template_message(sender_phone_number_id, recipient, template)
