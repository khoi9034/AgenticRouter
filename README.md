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
- `data/examples.json`: Example routing inputs.
- `data/golden_tasks.json`: Regression examples for the evaluator.
