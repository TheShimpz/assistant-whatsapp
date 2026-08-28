"""Send reviewed WhatsApp contact cards."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import (
    ContactsMessage,
    PhoneNumberId,
    Recipient,
    SendMessageResult,
    contacts_message_summary,
)


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
    summary = contacts_message_summary(message)
    async with approved_whatsapp_client(
        ctx,
        title="Send these WhatsApp contacts",
        description=(
            f"Send {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.send_contacts_message(sender_phone_number_id, recipient, message)
