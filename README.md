# WhatsApp Assistant

An independently published Shimpz Assistant for reviewed WhatsApp Cloud API automation.

The first Action sends one text message through Meta's fixed Graph API endpoint. Every send requires an explicit
human approval. The Meta access token is collected as the `whatsapp-token` Stored Input just in time, sealed by the
Team after a successful Action, and reused without another prompt. This Assistant never persists the token itself.

## First live test

Provide the Meta sender phone-number id, a recipient number including country code, and a text message in the task.
When the Action pauses, enter the Meta access token in the password input. A successful result returns only the
normalized recipient, WhatsApp id, and Meta message id.

The client pins Graph API `v23.0`, disables redirects and retries, and admits only `graph.facebook.com` egress.
