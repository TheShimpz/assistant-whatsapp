# WhatsApp Assistant

An independently published Shimpz Assistant for reviewed outbound WhatsApp Cloud API automation.

Version 0.4.0 provides ten bounded Actions for text, media, locations, contacts, approved templates, buttons and
lists, products and catalogs, published Flows, reactions, read receipts, and typing indicators. Media can reference
an existing Meta media id or a public HTTPS link; the Assistant never fetches a user-supplied URL itself.

Every externally visible effect requires explicit human approval. The Meta access token is collected as the
`whatsapp-token` Stored Input just in time, kept by the Team, and reused without another token prompt. The Assistant
never holds it: every WhatsApp call goes through `ctx.fetch`, and the Team adds the token as an
`Authorization: Bearer` header on `graph.facebook.com`, as `shimpz.toml` declares. The token does not belong in chat,
the repo, an environment variable, or Neuron.

Every approval and token prompt is English `shimpz.text` catalog copy that Team shows in the person's interface
language (ADR-0091); it requires SDK 0.7.2 and CLI 0.8.1 or later. Each approval names the exact sender
phone-number id and recipient as typed parameters, plus the media type, counts, coordinates, template name and
language, Flow id or name, or incoming message id when the value fits the catalog identifier alphabet and 128
characters. A value no parameter can show exactly, such as a reaction emoji, a free-text Flow name, a template name
that is too long or starts with an underscore, or a message id outside that alphabet, is never interpolated; the
approval says that it is not shown. A reaction approval never shows its target message.

Every approval also ends with a request reference: a digest of the validated sender, recipient, and exact content
input. The SDK fingerprints the approval's parameters and replays the approval only for an identical request, so an
approval authorizes exactly the values it was granted for, shown or not, and any changed value asks again.

## First live test

Use a Meta test sender, one controlled and consenting recipient, and one effect per Team turn. For free-form messages,
first send a message from the recipient to open the 24-hour customer-service window. Templates, media ids, catalog
products, and Flows must already exist in the test account before their Actions can be exercised.

The Action first asks for approval and then, when no Stored Input exists, asks for the token in the final password
prompt. A successful send returns only the normalized recipient, WhatsApp id, and Meta message id. That id proves
Meta accepted the request; delivery status requires webhook events and is not claimed by this outbound Assistant.

The client pins Graph API `v23.0`, makes no retry, rejects redirects and malformed or oversized responses, and
calls only `graph.facebook.com`; Team follows no redirect and refuses any other host. Live validation should perform one approved effect per turn so a later denial
or expiry cannot make a partially completed matrix look atomic.
