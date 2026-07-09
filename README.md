# AgenticRouter / DevSpace Smart Router

AgenticRouter is a local, rule-based MVP that recommends the safest cheapest DevSpace model for a task. It does not call an AI model.

## Install

```bash
python -m pip install -e .
```

No runtime dependencies are required.

## CLI

JSON output:

```bash
python -m agentic_router.cli route --project "Veteran's Intake Application" --task "Fix auth ping endpoint redirect bug" --files Auth/ping.php api/list_intakes.php --failures 1 --json
```

Text output:

```bash
python -m agentic_router.cli route --project "Diana Test Project" --task "Make the hello world page background prettier"
```

Golden evaluation:

```bash
python -m agentic_router.cli eval
```

Context pack recommendation:

```bash
python -m agentic_router.cli context --project "Veteran's Intake Application" --task "Fix auth ping redirect bug" --files Auth/ping.php api/list_intakes.php
```

DevSpace run packet:

```bash
python -m agentic_router.cli packet --project "Gap Bills Forge Conversion" --task "Change PDF output naming format" --files forge_bot/gap_bills_bot.py --json
```

Enterprise gateway templates:

```bash
python -m agentic_router.cli export-enterprise --target all
```

Save sanitized outcome feedback:

```bash
python -m agentic_router.cli feedback --route-id ROUTE_ID --accepted true --task-succeeded true --actual-model "Sonnet 4.6" --recommendation-fit right --notes "worked well"
```

Summarize outcomes:

```bash
python -m agentic_router.cli outcomes
```

Local web UI:

```bash
python -m agentic_router.web
```

Then open http://127.0.0.1:8765.

Installed console script:

```bash
agentic-router route --project "Grant Quarter Reporting" --task "Create a quarterly dashboard report" --files reports/quarterly.py
```

## Inputs

- `project_name`
- `task_description`
- `files_touched`, optional list
- `previous_failure_count`, default `0`
- `live_prod`, optional boolean override
- `output_format`, `text` or `json`

## Outputs

- `recommended_model`
- `model_tier`
- `effort_level`
- `risk_level`
- `human_review_required`
- `reason`
- `context_policy`
- `escalation_policy`
- `matched_rules`
- `route_id`
- `context_pack`
- `run_packet` in the web route response

## Routing Rules

1. Docs, copy, simple static HTML/CSS, README, placeholder files, and simple summaries route cheap.
2. Normal UI, forms, dashboards, report logic, workflow design, and non-production bot analysis route mid.
3. Auth, SQL, database, Laserfiche, TeamDynamix writes, Microsoft Graph, Intune, cybersecurity, infrastructure, production deployment, credentials, secrets, PII, HR/payroll, veteran data, legal records, public safety, workers comp, official public budget content, and live Forge bots route advanced.
4. `previous_failure_count >= 2` escalates one tier.
5. Live production code changes never route cheap.
6. Sensitive data or security controls require human review.
7. Context policy prefers the smallest useful context and excludes secrets, tokens, credentials, PII, PHI, and real case records for sensitive work.

## Examples

```bash
python -m agentic_router.cli route --project "TD Refresh Users Bot Conversion" --task "Change live Forge bot code that writes TeamDynamix users" --files bots/refresh_users.py --json
python -m agentic_router.cli route --project "Mark's Test Project" --task "Update README copy" --files README.md --failures 2
python -m agentic_router.cli route --project "Local Budget Book" --task "Update official public budget figures" --files data/budget.json --json
```

## Tests

```bash
python -m unittest discover -s tests
```

Run the golden routing evaluation:

```bash
python -m agentic_router.cli eval
```

Run the local web UI:

```bash
python -m agentic_router.web
```

The UI serves a dependency-free local dashboard at http://127.0.0.1:8765 with:

- `/api/projects`
- `/api/route`
- `/api/context`
- `/api/packet`
- `/api/eval`
- `/api/feedback`
- `/api/outcomes`

Record CLI feedback after a route:

```bash
python -m agentic_router.cli route --project "Diana Test Project" --task "make hello world prettier" --json
python -m agentic_router.cli feedback --route-id ROUTE_ID --accepted true --task-succeeded true --actual-model "Haiku 4.5" --recommendation-fit right --notes "sanitized test feedback"
python -m agentic_router.cli outcomes
```

Feedback notes must be sanitized. Do not include secrets, credentials, bearer tokens, emails, serial numbers, PII, PHI, legal records, HR records, veteran records, medical records, or real case details.

## Adding Examples

To add a project, update `data/projects.json` with its default tier, risk, production status, sensitivity flag, and routing keywords.

To add a golden task, update `data/golden_tasks.json` with:

- `project_name`
- `task_description`
- `files_touched`
- `previous_failure_count`
- `expected_tier`
- `expected_risk`
- `expected_human_review_required`
- `expected_reason_keywords`

Keep examples realistic and avoid secrets, tokens, private paths, PII, PHI, and real case records.

## Data Files

- `data/models.json`: DevSpace models and default model per tier.
- `data/projects.json`: DevSpace project catalog with risk, production, and sensitivity flags.
- `data/routing_rules.json`: Keyword rules for cheap, mid, advanced, sensitive, and security matches.
- `data/context_policies.json`: Context pack include/exclude/forbidden guidance.
- `data/validation_playbooks.json`: Validation checklist templates for run packets.
- `data/enterprise_gateway_templates.json`: Enterprise routing, guardrail, observability, and budget template source.
- `data/litellm_model_aliases.json`: DevSpace model aliases for LiteLLM-style exports.
- `data/examples.json`: Example routing inputs.
- `data/golden_tasks.json`: Regression examples for the evaluator.
- `data/outcomes.jsonl`: Local JSONL feedback records.

## Web UI

The web UI loads projects from `data/projects.json`, routes tasks through the same rule-based router as the CLI, and shows the recommendation, route ID, risk, human-review flag, context pack, DevSpace run packet, context policy, escalation policy, and matched rules. It also captures sanitized feedback for the routing outcome. It is local-only and uses Python `http.server`; no Flask, FastAPI, or AI calls.

Run packets are copy-pasteable prompts for DevSpace/Codex. They include model choice, risk notes, context instructions, forbidden context, safety constraints, validation steps, stop conditions, and escalation plan. They must not include secrets, PII, real records, tokens, passwords, emails, tenant IDs, USB serials, or production log content.

## Enterprise Gateway Templates

AgenticRouter is the policy brain: it decides tier, effort, risk, context, safety, validation, and human-review flags. A LiteLLM-style or internal gateway is the traffic layer: it handles model aliases, provider credentials, fallbacks, budgets, virtual keys, logging, and enforcement.

The files under `exports/` are safe placeholder templates, not production configs. They include no real secrets, tokens, emails, URLs, tenant IDs, production values, or records. Replace `CHANGE_ME_*` placeholders outside this repo before adapting them to a real gateway.
