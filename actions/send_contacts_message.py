"""Send reviewed WhatsApp contact cards."""

from shimpz import Context, action, text

from lib.approvals import contacts_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import ContactsMessage, PhoneNumberId, Recipient, SendMessageResult


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    message: ContactsMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    async with approved_whatsapp_client(
        ctx,
        title=text("Send these WhatsApp contacts", max_length=80),
        description=contacts_approval(sender_phone_number_id, recipient, message),
    ) as client:
        return await client.send_contacts_message(sender_phone_number_id, recipient, message)
