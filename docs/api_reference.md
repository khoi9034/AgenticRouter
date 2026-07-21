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
- `POST /api/v1/contract`: return a run contract for the request.
- `POST /api/v1/contract/check`: check changed files and a sanitized diff summary against a run contract.
- `POST /api/v1/diff-review`: review a supplied git diff or patch with local quality gate rules.
- `POST /api/v1/diff-review/current`: review the current local git diff.
- `POST /api/v1/autogate/start`: start an automated run lifecycle.
- `POST /api/v1/autogate/complete`: complete a run and return the final automated decision.
- `POST /api/v1/evidence/plan`: build a safe local validation plan for an AutoGate run.
- `POST /api/v1/evidence/collect`: collect local git evidence and safe validation results.
- `POST /api/v1/autogate/complete-auto`: collect evidence and complete AutoGate automatically.
- `POST /api/v1/autogate/report`: return a stored AutoGate run report by `run_id`.
- `GET /api/v1/autogate/list`: list latest local AutoGate run records.
- `POST /api/v1/autogate/clear`: clear local AutoGate run records.
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
  "include_packet": false,
  "repo_path": "."
}
```

`mode` must be one of `advise`, `packet`, `shadow`, or `strict`.
`repo_path` is used only by local evidence endpoints and defaults to `.`.

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
  "run_contract": {
    "contract_id": "arc_...",
    "allowed_file_patterns": ["*.html", "*.css"],
    "forbidden_file_patterns": ["Auth/*", "api/*", "database/*", "config*", "*.env"],
    "allowed_actions": ["Visual/layout/copy changes only"],
    "forbidden_actions": ["Auth changes", "API changes", "Schema changes"],
    "required_validation": ["Check affected HTML/CSS renders."],
    "stop_conditions": ["Stop if task expands into backend work."],
    "human_review_required": false
  },
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

`POST /api/v1/contract/check` accepts:

```json
{
  "contract": {"contract_id": "arc_...", "allowed_file_patterns": ["*.html"], "forbidden_file_patterns": ["Auth/*"]},
  "changed_files": ["index.html", "style.css"],
  "diff_summary": "Sanitized summary only",
  "added_dependencies": []
}
```

It returns:

```json
{
  "contract_version": "v1",
  "scope_guard": {
    "decision": "pass",
    "violations": [],
    "warnings": [],
    "changed_files_reviewed": ["index.html", "style.css"],
    "forbidden_matches": [],
    "allowed_matches": ["index.html", "style.css"],
    "human_review_required": false,
    "risk_level": "low",
    "explanation": "Changed files fit the allowed contract scope."
  }
}
```

`POST /api/v1/autogate/start` accepts the same core project/task fields and returns:

```json
{
  "contract_version": "v1",
  "autogate": {
    "run_id": "run_...",
    "recommended_model": "Haiku 4.5",
    "model_tier": "cheap",
    "risk_level": "low",
    "run_contract": {},
    "automated_requirements": {
      "required_checks": ["contract_pass_required", "diff_pass_required"]
    },
    "start_status": "ready"
  }
}
```

`POST /api/v1/autogate/complete` accepts:

```json
{
  "run_id": "run_...",
  "changed_files": ["style.css"],
  "git_diff": "diff --git ...",
  "tests_run": ["unit tests"],
  "test_status": "passed",
  "rollback_plan_present": false,
  "notes": "sanitized notes only"
}
```

It returns a final automated decision: `auto_approved`, `auto_blocked`, `needs_tests`, `needs_retry`, `needs_more_evidence`, or `rollback_required`.

`POST /api/v1/evidence/plan`, `POST /api/v1/evidence/collect`, and `POST /api/v1/autogate/complete-auto` accept:

```json
{
  "run_id": "run_...",
  "repo_path": "."
}
```

The plan endpoint returns safe validation commands only:

```json
{
  "contract_version": "v1",
  "evidence_plan": {
    "project_types": ["python"],
    "changed_files": ["agentic_router/router.py"],
    "commands": [
      {"name": "python_unittest", "command": ["python", "-m", "unittest", "discover", "-s", "tests"], "required": false}
    ],
    "requires_validation": true,
    "static_only": false
  }
}
```

The collect endpoint returns changed files, a compact diff summary, validation results, missing evidence, warnings, and `tests_status`. It does not run installs, deploys, migrations, database commands, delete/purge/sync commands, production commands, or unlisted commands. The complete-auto endpoint returns the evidence summary plus the final AutoGate decision.

`POST /api/v1/diff-review` accepts:

```json
{
  "project_name": "Random Test App",
  "task_description": "Change login button color",
  "run_contract": {},
  "changed_files": ["login.html"],
  "git_diff": "diff --git ...",
  "added_dependencies": [],
  "tests_run": [],
  "live_prod": false
}
```

It returns:

```json
{
  "contract_version": "v1",
  "diff_review": {
    "decision": "warn",
    "risk_level": "medium",
    "human_review_required": false,
    "summary": "Diff review warn with medium risk.",
    "detected_change_types": ["api_contract_change"],
    "violations": [],
    "warnings": ["API contract or endpoint behavior changed"],
    "required_followup_checks": ["Verify endpoint path, HTTP method, request fields, response fields, and status handling."],
    "rollback_required": false,
    "approval_recommendation": "approve_only_after_followup_checks",
    "reasoning": "Decision uses max severity across scope and diff rules."
  }
}
```

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
