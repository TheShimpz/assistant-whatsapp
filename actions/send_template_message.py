"""Send one reviewed approved WhatsApp message template."""

from shimpz import Context, action, text

from lib.approvals import template_approval
from lib.runtime import approved_whatsapp_client
from lib.templates import TemplateMessage
from lib.whatsapp import PhoneNumberId, Recipient, SendMessageResult


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
    template, description = template_approval(sender_phone_number_id, recipient, message)
    async with approved_whatsapp_client(
        ctx,
        title=text("Send this WhatsApp template", max_length=80),
        description=description,
    ) as client:
        return await client.send_template_message(sender_phone_number_id, recipient, template)
