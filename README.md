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

Profile/session routing:

```bash
python -m agentic_router.cli route --project "Diana Test Project" --task "Make page prettier" --profile cost_saver --session-id demo-low
python -m agentic_router.cli route --project "Veteran's Intake Application" --task "Fix auth redirect" --profile max_savings --session-id vet-auth-1 --json
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

Summarize session stickiness:

```bash
python -m agentic_router.cli sessions
```

Summarize local traces:

```bash
python -m agentic_router.cli traces
```

Export LangSmith-app-compatible local files:

```bash
python -m agentic_router.cli export-langsmith-files
```

Check local observability status:

```bash
python -m agentic_router.cli observability-status
```

Validate and bundle local config:

```bash
python -m agentic_router.cli validate-config
python -m agentic_router.cli config-summary
python -m agentic_router.cli export-config --output exports/config/agentic_router_config_bundle.json
python -m agentic_router.cli import-config --input exports/config/agentic_router_config_bundle.json --dry-run
```

Run scenario simulations:

```bash
python -m agentic_router.cli list-scenarios
python -m agentic_router.cli simulate --scenario mixed_devspace_month
python -m agentic_router.cli simulate --scenario forge_bot_maintenance_week --json
```

DevSpace integration contract:

```bash
python -m agentic_router.cli api-contract
python -m agentic_router.cli export-devspace-contract
python -m agentic_router.cli integration-test
```

Shadow mode analytics:

```bash
python -m agentic_router.cli shadow-add-demo-data
python -m agentic_router.cli shadow-summary
python -m agentic_router.cli export-shadow-report
```

Pilot/demo kit:

```bash
python -m agentic_router.cli pilot-report
python -m agentic_router.cli demo-script
python -m agentic_router.cli rollout-plan
python -m agentic_router.cli pilot-scorecard
```

Local web UI:

```bash
python -m agentic_router.web
```

Then open http://127.0.0.1:8765.

If that port is already in use:

```bash
$env:AGENTIC_ROUTER_PORT=8766; python -m agentic_router.web
```

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
- `session_id`, optional sticky-routing key
- `profile_name`, optional routing profile
- `cost_quality_tradeoff`, optional integer from `0` max quality to `10` max savings
- `allowed_models`, optional aliases or exact model names

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
- `selected_model_alias`
- `selected_model`
- `fallback_candidates`
- `profile_name`
- `cost_quality_tradeoff`
- `sticky_route_used`
- `previous_model`

Every route also writes a sanitized local trace to `data/traces.jsonl`.

## Routing Rules

1. Docs, copy, simple static HTML/CSS, README, placeholder files, and simple summaries route cheap.
2. Normal UI, forms, dashboards, report logic, workflow design, and non-production bot analysis route mid.
3. Auth, SQL, database, Laserfiche, TeamDynamix writes, Microsoft Graph, Intune, cybersecurity, infrastructure, production deployment, credentials, secrets, PII, HR/payroll, veteran data, legal records, public safety, workers comp, official public budget content, and live Forge bots route advanced.
4. `previous_failure_count >= 2` escalates one tier.
5. Live production code changes never route cheap.
6. Sensitive data or security controls require human review.
7. Context policy prefers the smallest useful context and excludes secrets, tokens, credentials, PII, PHI, and real case records for sensitive work.

## Profiles, Aliases, and Sessions

Model aliases live in `data/model_aliases.json`; fallback pools live in `data/fallback_policies.json`. The default aliases are `devspace-cheap`, `devspace-mid`, `devspace-advanced`, `devspace-docs`, `devspace-live-prod`, `devspace-security`, and `devspace-public-official-content`.

Routing profiles live in `data/routing_profiles.json`: `max_savings`, `cost_saver`, `balanced`, `quality_first`, `max_quality`, `claude_only`, `codex_only`, and `safe_prod`.

Profiles can steer normal tasks toward cheaper or higher-quality models, but they cannot downgrade live prod, auth, SQL/database, Laserfiche, TeamDynamix, Graph, Intune, cybersecurity, sensitive data, public safety, HR/payroll, legal, veteran, workers comp, or official public budget work below advanced routing.

Session stickiness reuses a previous model alias/model only when the project is the same, risk has not increased, prior failures are below two, and the new task does not newly touch a high-risk domain. Session records are stored in `data/session_cache.jsonl` with sanitized summaries; high-risk task text is redacted and only a hash is kept.

## Local Observability

AgenticRouter observability is fully local and offline. It does not use the LangSmith API, does not require a LangSmith API key, does not import `langsmith`, and does not send remote traces.

Routes append sanitized trace records to `data/traces.jsonl`. High-risk routes do not store raw task text; they keep a task hash and category with `prompt_body_logged=false`. Low-risk routes may keep a sanitized task summary capped at 180 characters.

`python -m agentic_router.cli export-langsmith-files` writes manual JSONL/CSV files under `exports/langsmith/` for inspection or later UI import. These are files only, not API uploads.

## Config Studio

Config Studio validates and summarizes local routing policy without cloud calls or dependencies. It checks project/model/rule/profile/fallback/golden-task JSON, cross-file alias/model references, unknown golden projects, high-risk sensitive defaults, and secret-looking values or private Windows paths.

The web UI includes a mostly read-only Config Studio panel plus one safe Add Project form. Imports are dry-run by default and only overwrite config files with `--apply`, after writing a timestamped local backup.

## Scenario Simulator

The Scenario Simulator runs named batches from `data/simulation_scenarios.json` through the local router and summarizes tiers, models, aliases, risk, context sizes, human-review counts, live-prod counts, sensitive-task counts, escalation counts, top rules, and top advanced/review projects.

Savings are abstract planning units, not dollars: cheap = 1, mid = 3, advanced = 8. Context units are tiny = 1, small = 2, medium = 5, large = 10.

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
- `/api/sessions`
- `/api/observability`
- `/api/config/summary`
- `/api/config/validate`
- `/api/config/export`
- `/api/config/add-project`
- `/api/config/eval`
- `/api/scenarios`
- `/api/simulate`
- `/api/health`
- `/api/version`
- `/api/contracts`
- `/api/v1/route`
- `/api/v1/packet`
- `/api/v1/shadow`
- `/api/v1/strict-check`
- `/api/shadow/summary`
- `/api/shadow/report`
- `/api/pilot/scorecard`
- `/api/pilot/report`
- `/api/pilot/demo-script`
- `/api/pilot/rollout-plan`

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
- `data/model_aliases.json`: Local model alias primary/fallback mapping.
- `data/routing_profiles.json`: Cost/quality and family profile settings.
- `data/fallback_policies.json`: Fallback candidates by route type.
- `data/session_cache.jsonl`: Local sanitized session stickiness records.
- `data/traces.jsonl`: Local sanitized route trace records.
- `data/config_schemas.json`: Lightweight schema notes for config validation.
- `data/simulation_scenarios.json`: Named hypothetical task batches for the simulator.
- `data/api_contracts.json`: Stable v1 DevSpace request/response contract metadata.
- `data/shadow_runs.jsonl`: Local sanitized shadow-mode comparison records.
- `data/examples.json`: Example routing inputs.
- `data/golden_tasks.json`: Regression examples for the evaluator.
- `data/outcomes.jsonl`: Local JSONL feedback records.

## Web UI

The web UI loads projects from `data/projects.json`, routes tasks through the same rule-based router as the CLI, and shows the recommendation, selected model alias, fallback candidates, profile, sticky-route status, route ID, risk, human-review flag, context pack, DevSpace run packet, context policy, escalation policy, and matched rules. It also captures sanitized feedback, shows a local observability panel with trace counts and export links, includes Config Studio for local validation, provides a Scenario Simulator panel for hypothetical batch routing, shows the local DevSpace Integration contract status, summarizes Shadow Analytics for rollout pilots, and includes a Pilot Readiness scorecard for demos. It is local-only and uses Python `http.server`; no Flask, FastAPI, LangSmith API, or AI calls.

Run packets are copy-pasteable prompts for DevSpace/Codex. They include model choice, risk notes, context instructions, forbidden context, safety constraints, validation steps, stop conditions, and escalation plan. They must not include secrets, PII, real records, tokens, passwords, emails, tenant IDs, USB serials, or production log content.

## Enterprise Gateway Templates

AgenticRouter is the policy brain: it decides tier, effort, risk, context, safety, validation, and human-review flags. A LiteLLM-style or internal gateway is the traffic layer: it handles model aliases, provider credentials, fallbacks, budgets, virtual keys, logging, and enforcement.

The files under `exports/` are safe placeholder templates, not production configs. They include no real secrets, tokens, emails, URLs, tenant IDs, production values, or records. Replace `CHANGE_ME_*` placeholders outside this repo before adapting them to a real gateway.

## DevSpace Integration Contract

The stable local API contract lives in `data/api_contracts.json` and is documented in `docs/devspace_integration_contract.md` and `docs/api_reference.md`.

Modes:

- `shadow`: log what AgenticRouter would recommend while DevSpace keeps its current routing.
- `advise`: return a model recommendation.
- `packet`: return a recommendation plus a DevSpace run packet.
- `strict`: return `block=true` for human-review-required work or forbidden context.

Export safe local contract files:

```bash
python -m agentic_router.cli export-devspace-contract
```

This writes `exports/devspace/agentic_router_api_contract.json` and `exports/devspace/example_requests.json`. Example stdlib clients live in `examples/devspace_client.py` and `examples/devspace_client.js`.

## Shadow Mode Analytics

`/api/v1/shadow` is advisory. It logs a sanitized local comparison between the actual model DevSpace used and the model AgenticRouter recommended. It does not change DevSpace model selection.

Shadow summaries include agreement rates, overkill count, too-weak/safety-risk count, strict-mode would-block count, abstract cost units for actual vs router usage, and top mismatch projects.

Reports are local files only:

```bash
python -m agentic_router.cli shadow-summary
python -m agentic_router.cli export-shadow-report
```

For local testing:

```bash
python -m agentic_router.cli shadow-add-demo-data
```

Before committing, keep `data/shadow_runs.jsonl` empty unless you intentionally want sanitized runtime logs in version control. Exported reports under `exports/reports/` may be kept when they contain only sanitized demo data.

## Pilot Readiness Demo Kit

Generate the leadership/developer pilot pack:

```bash
python -m agentic_router.cli pilot-report
python -m agentic_router.cli pilot-scorecard
python -m agentic_router.cli demo-script
python -m agentic_router.cli rollout-plan
```

The demo kit includes:

- `docs/pilot_readiness_report.md`
- `docs/demo_script.md`
- `docs/rollout_plan.md`
- `exports/reports/pilot_readiness_report.md`
- `exports/reports/pilot_readiness_report.json`
- `exports/reports/demo_scorecard.json`
