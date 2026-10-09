"""Mark one reviewed incoming WhatsApp message as read."""

from shimpz import Context, action, text

from lib.approvals import read_receipt_approval
from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, ReadReceipt, ReadReceiptResult


@action(
    description="Mark one incoming message as read.",
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    receipt: ReadReceipt,
    *,
    ctx: Context,
) -> ReadReceiptResult:
    async with approved_whatsapp_client(
        ctx,
        title=text("Update this WhatsApp message status", max_length=80),
        description=read_receipt_approval(sender_phone_number_id, receipt),
    ) as client:
        return await client.mark_message_read(sender_phone_number_id, receipt)
