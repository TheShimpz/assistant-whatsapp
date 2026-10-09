# WhatsApp Assistant repository rules

## Authority

- This repository owns the independently published WhatsApp Assistant: its manifest, Genesis, Actions, provider
  client, public result schemas, and component tests.
- It does not own Stored Input custody, Team installation, Developers publication, Brain planning, or platform egress
  enforcement.
- The Assistant never holds the Meta access token: Team keeps the declared `whatsapp-token` Stored Input and adds it
  to each call the Assistant makes with `ctx.fetch` (ADR-0106). Never read a token from an environment variable.

## Delivery

- Work in the smallest independently reviewable microtask.
- Run focused checks, then commit and push each successful microtask immediately.
- Use English conventional commit messages with clear imperative subjects.

## Engineering

- Keep Actions bounded, least-privilege, fail-closed, and limited to fixed WhatsApp Cloud API paths.
- Require human approval before every externally visible message send.
- Request the token just in time after approval. Explicitly reject only a provider-confirmed invalid token; never
  clear it for permission, policy, recipient, rate-limit, timeout, or ambiguous failures.
- Reject redirects and oversized or malformed provider responses.
- Never retry an uncertain message send.
- Use Python 3.14.

## Validation

- Run `shimpz check` for the complete Assistant contract and component suite.
- Run Ruff from this repository root with `ruff check --config pyproject.toml .`.
- Do not suppress Ruff findings with `noqa`.
