# LiteLLM Export Guide

Generate all placeholder templates:

```bash
python -m agentic_router.cli export-enterprise --target all
```

Generate LiteLLM-style templates only:

```bash
python -m agentic_router.cli export-enterprise --target litellm
```

Generated files:

- `exports/litellm/config.example.yaml`
- `exports/litellm/model_aliases.example.yaml`
- `exports/litellm/team_budget_policy.example.yaml`
- `exports/litellm/virtual_keys.example.md`

## Model Aliases

- `devspace-cheap`
- `devspace-mid`
- `devspace-advanced`
- `devspace-safe-docs`
- `devspace-live-prod`
- `devspace-security`
- `devspace-public-official-content`

## Before Production Use

Copy the examples outside the repo, replace `CHANGE_ME_*` placeholders, load real secrets from environment variables or a secret manager, and review budget, logging, guardrail, and human-review rules.

Never put real keys, tokens, tenant IDs, emails, URLs, production logs, records, USB serials, or PII in these files.

