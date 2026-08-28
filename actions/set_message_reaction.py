"""Add or remove one reviewed WhatsApp message reaction."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import (
    PhoneNumberId,
    ReactionMessage,
    Recipient,
    SendMessageResult,
    reaction_message_summary,
)


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    recipient: Recipient,
    reaction: ReactionMessage,
    *,
    ctx: Context,
) -> SendMessageResult:
    summary = reaction_message_summary(reaction)
    async with approved_whatsapp_client(
        ctx,
        title="Change this WhatsApp reaction",
        description=(
            f"Send one reviewed {summary} from Meta phone-number id {sender_phone_number_id} to {recipient}."
        ),
    ) as client:
        return await client.set_message_reaction(sender_phone_number_id, recipient, reaction)
