# WhatsApp Assistant

An independently published Shimpz Assistant for reviewed outbound WhatsApp Cloud API automation.

Version 0.2.0 provides ten bounded Actions for text, media, locations, contacts, approved templates, buttons and
lists, products and catalogs, published Flows, reactions, read receipts, and typing indicators. Media can reference
an existing Meta media id or a public HTTPS link; the Assistant never fetches a user-supplied URL itself.

Every externally visible effect requires explicit human approval. The Meta access token is collected as the
`whatsapp-token` Stored Input just in time, sealed by the Team after a successful secret-free Action, and reused
without another token prompt. Team is the sole persistent custodian: the token does not belong in chat, the repo,
an environment variable, or Neuron.

## First live test

Use a Meta test sender, one controlled and consenting recipient, and one effect per Team turn. For free-form messages,
first send a message from the recipient to open the 24-hour customer-service window. Templates, media ids, catalog
products, and Flows must already exist in the test account before their Actions can be exercised.

The Action first asks for approval and then, when no Stored Input exists, asks for the token in the final password
prompt. A successful send returns only the normalized recipient, WhatsApp id, and Meta message id. That id proves
Meta accepted the request; delivery status requires webhook events and is not claimed by this outbound Assistant.

The client pins Graph API `v23.0`, disables redirects and retries, rejects malformed or oversized responses, and
admits only `graph.facebook.com` egress. Live validation should perform one approved effect per turn so a later denial
or expiry cannot make a partially completed matrix look atomic.
