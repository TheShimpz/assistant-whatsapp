"""Mark one reviewed incoming WhatsApp message as read."""

from shimpz import Context, action

from lib.runtime import approved_whatsapp_client
from lib.whatsapp import PhoneNumberId, ReadReceipt, ReadReceiptResult, read_receipt_summary


@action(
    stored_inputs=["whatsapp-token"],
    human_requests=["approval", "input:password"],
)
async def run(
    sender_phone_number_id: PhoneNumberId,
    receipt: ReadReceipt,
    *,
    ctx: Context,
) -> ReadReceiptResult:
    summary = read_receipt_summary(receipt)
    async with approved_whatsapp_client(
        ctx,
        title="Update this WhatsApp message status",
        description=f"Use Meta phone-number id {sender_phone_number_id} to {summary}.",
    ) as client:
        return await client.mark_message_read(sender_phone_number_id, receipt)
