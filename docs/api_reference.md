# AgenticRouter API Reference

Base URL for the local web server:

```text
http://127.0.0.1:8765
```

Start it with:

```bash
python -m agentic_router.web
```

## Endpoints

- `GET /api/health`: health check and local-only flag.
- `GET /api/version`: app and contract version metadata.
- `GET /api/contracts`: v1 request/response contract metadata.
- `POST /api/v1/route`: route using `mode` from the payload, defaulting to `advise`.
- `POST /api/v1/packet`: forced `packet` mode.
- `POST /api/v1/shadow`: forced `shadow` mode.
- `POST /api/v1/strict-check`: forced `strict` mode.
- `GET /api/shadow/summary`: local shadow analytics summary.
- `GET /api/shadow/report`: write local shadow report files and return paths.

Existing endpoints such as `/api/route`, `/api/context`, `/api/packet`, and `/api/eval` remain available for backward compatibility.

## Request Schema

Required:

```json
{
  "project_name": "Veteran's Intake Application",
  "task_description": "Fix auth ping redirect bug"
}
```

Optional:

```json
{
  "files_touched": ["Auth/ping.php"],
  "previous_failure_count": 0,
  "live_prod": false,
  "session_id": "optional-session",
  "profile": "balanced",
  "cost_quality_tradeoff": 5,
  "allowed_models": [],
  "mode": "advise",
  "actual_model_used": "Sonnet 4.6",
  "caller": "devspace-local",
  "task_id": "TASK-123",
  "include_packet": false
}
```

`mode` must be one of `advise`, `packet`, `shadow`, or `strict`.

## Response Schema

Successful v1 responses include:

```json
{
  "contract_version": "v1",
  "mode": "advise",
  "route_id": "ar_...",
  "recommended_model": "Haiku 4.5",
  "selected_model_alias": "devspace-cheap",
  "model_tier": "cheap",
  "effort_level": "low",
  "risk_level": "low",
  "human_review_required": false,
  "reason": "Routed cheap from rule matches...",
  "matched_rules": [],
  "fallback_candidates": [],
  "normalized_task": {
    "normalized_summary": "Make hello world page prettier",
    "task_type": "docs_static",
    "requested_capabilities": ["docs_static"],
    "operation_type": "visual_polish",
    "complexity": "low",
    "intrinsic_risk": "low",
    "minimum_recommended_tier": "cheap",
    "false_positive_controls_triggered": [],
    "risk_reason": "Low intrinsic risk..."
  },
  "intrinsic_task_risk": "low",
  "requested_capabilities": ["docs_static"],
  "minimum_recommended_tier": "cheap",
  "task_ambiguity_warnings": [],
  "task_type": "docs_static",
  "operation_type": "visual_polish",
  "false_positive_controls_triggered": [],
  "context_pack": {},
  "devspace_run_packet": {},
  "observability": {
    "trace_written": true,
    "prompt_body_logged": true
  },
  "block": false,
  "block_reason": null,
  "warnings": [],
  "recommended_next_action": "use_recommended_model"
}
```

`packet` mode or `include_packet=true` adds a populated `devspace_run_packet` unless forbidden context is detected.

Risk levels may be `low`, `medium`, `medium-high`, `high`, or `critical`.

Shadow responses also include:

```json
{
  "shadow_id": "sh_...",
  "comparison_to_actual": {},
  "actual_tier": "advanced",
  "recommended_tier": "cheap",
  "overkill_or_underpowered": "human_stronger",
  "abstract_cost_delta": 7,
  "router_would_block_in_strict": false
}
```

## Error Format

Bad requests return HTTP 400:

```json
{
  "error": "project_name and task_description are required",
  "contract_version": "v1"
}
```

## Example

```bash
curl -X POST http://127.0.0.1:8765/api/v1/route \
  -H "Content-Type: application/json" \
  -d "{\"project_name\":\"Diana Test Project\",\"task_description\":\"Update README copy\"}"
```

## Compatibility Policy

Contract `v1` is stable for the current local MVP. Additive response fields are allowed. Removing or renaming existing v1 fields requires a new contract version.
