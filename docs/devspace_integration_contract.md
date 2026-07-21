# DevSpace Integration Contract

AgenticRouter is the local policy brain. DevSpace, Codex, or another app is the caller.

The caller sends a small task description, project name, touched files, optional session/profile controls, and no secrets or real records. AgenticRouter returns a stable v1 recommendation with model, tier, project-plus-intrinsic task risk, normalized task brief, context pack, optional run packet, warnings, and whether the caller should stop.

## Modes

- `shadow`: safest starting point. DevSpace keeps using its current model while AgenticRouter logs what it would have recommended. Send `actual_model_used` when available.
- `advise`: returns a recommendation for the caller to display or follow.
- `packet`: returns the recommendation plus a copy-pasteable DevSpace run packet.
- `strict`: returns `block=true` when human review is required or forbidden context is detected.

## Recommended Rollout

1. Start in `shadow` mode for normal work and compare recommendations against actual model choices.
2. Move low-risk docs/static/UI tasks to `advise`.
3. Use `packet` for guided Codex/DevSpace runs where the user wants a full prompt.
4. Use `strict` for live-prod, security, auth, SQL, Laserfiche, TeamDynamix, Microsoft Graph, Intune, infrastructure, public official content, and sensitive-data projects.

## Privacy Rules

Requests must not include secrets, API keys, bearer tokens, passwords, emails, tenant IDs, USB serials, real veteran records, workers comp claims, legal/client records, student raw comments, production logs, private Windows paths, or any real PII/PHI.

If forbidden-looking context is detected, AgenticRouter returns a warning. Strict mode blocks. Packet generation is suppressed so tainted task text is not copied into an execution prompt.

## Local Only

The integration layer uses the same offline router engine as the CLI and web UI. It makes no cloud calls, uses no API keys, imports no LangSmith package, and sends no remote traces.

## Contract Files

- `data/api_contracts.json`: source v1 contract metadata.
- `exports/devspace/agentic_router_api_contract.json`: exported contract bundle.
- `exports/devspace/example_requests.json`: safe example payloads.
- `examples/devspace_client.py`: stdlib Python client.
- `examples/devspace_client.js`: fetch client.
