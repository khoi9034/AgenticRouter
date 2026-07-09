# Enterprise Gateway Strategy

AgenticRouter is the policy brain. It decides model tier, effort, risk, context pack, safety warnings, validation, and run packets.

An enterprise gateway such as LiteLLM, Portkey, or an internal DevSpace gateway is the traffic layer. It can enforce aliases, fallbacks, budgets, virtual keys, logging, and guardrails using AgenticRouter's exported policy templates.

## Responsibilities

- AgenticRouter: routing policy, context policy, human review flags, forbidden context, validation guidance.
- Gateway: model alias resolution, provider credentials, rate limits, budgets, logging, and access control.
- Human reviewer: approval for live-prod, sensitive records, cybersecurity, infrastructure, and public official publication.

## Safety

The generated templates are examples only. They use placeholders such as `CHANGE_ME_*` and `os.environ/OPENAI_API_KEY`. They are not production configs and must be reviewed before use.

Do not commit real API keys, tokens, secrets, emails, usernames, tenant IDs, URLs, production values, private logs, records, USB serials, or PII.

## Export Targets

- `litellm`: LiteLLM-style model aliases, proxy config, team budgets, and virtual key notes.
- `gateway`: routing policy, context policy, guardrails, observability, and DevSpace integration contract.
- `all`: both targets.

