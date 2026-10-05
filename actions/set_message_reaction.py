"""Add or remove one reviewed WhatsApp message reaction."""

from shimpz import Context, action, text

from lib.approvals import reaction_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, ReactionMessage, Recipient, SendMessageResult


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
    async with approved_whatsapp_client(
        ctx,
        title=text("Change this WhatsApp reaction", max_length=80),
        description=reaction_approval(sender_phone_number_id, recipient, reaction),
    ) as client:
        return await client.set_message_reaction(sender_phone_number_id, recipient, reaction)
