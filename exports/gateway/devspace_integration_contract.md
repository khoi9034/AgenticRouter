# DevSpace Integration Contract

AgenticRouter is the policy brain. A LiteLLM-style gateway is the traffic layer.

## Request Metadata

- route_id
- project_name
- task_class
- recommended_model_alias
- model_tier
- risk_level
- context_size
- human_review_required

## Safety Contract

- Send sanitized context only.
- Never send secrets, PII, records, tenant IDs, USB serials, or production logs.
- Require human approval before live-prod deployment or sensitive/security changes.
- Source verification is required for public official content.
