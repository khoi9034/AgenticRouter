# Routing Methodology

AgenticRouter is intentionally rule-based. It does not call an AI model during routing or evaluation.

## Decision Inputs

The router considers:

- project name
- task description
- files touched
- previous failure count
- project catalog risk, production, and sensitivity flags

## Tier Selection

The router starts from the project catalog default tier, then applies keyword rules:

- cheap: docs, copy, README, placeholder, simple summary, static HTML/CSS
- mid: UI, forms, dashboards, reports, workflows, non-production bot analysis
- advanced: auth, SQL, database, Laserfiche, TeamDynamix, Graph, Intune, cybersecurity, infrastructure, production deployment, credentials, PII, HR/payroll, public safety, workers comp, official public budget, live Forge

Two or more previous failures escalate the tier once. Live production code changes are never allowed to remain cheap.

## Model Aliases, Profiles, and Fallbacks

After the rule engine chooses the tier and risk, the profile layer chooses a model alias and concrete model. Aliases live in `data/model_aliases.json`; fallback candidates live in `data/fallback_policies.json`.

Default alias families:

- `devspace-cheap`: Haiku 4.5, then GPT-5.4 mini
- `devspace-mid`: Sonnet 4.6, then GPT-5.4
- `devspace-advanced`: GPT-5.5, then Opus 4.8
- `devspace-docs`: Haiku 4.5, then Sonnet 4.6
- `devspace-live-prod`, `devspace-security`, and `devspace-public-official-content`: GPT-5.5, then Opus 4.8

Profiles live in `data/routing_profiles.json`. The cost/quality scale runs from `0` for max quality to `10` for max savings. Profiles may upgrade or downgrade normal low-risk work, and `claude_only` or `codex_only` filter selected and fallback models by family.

Safety-locked work cannot be downgraded by a profile or allowed-model pool. Safety-locked work includes live prod, auth, SQL/database, Laserfiche, TeamDynamix writes, Microsoft Graph, Intune, cybersecurity, sensitive data, public safety, HR/payroll, legal records, veteran data, workers comp, official public budget claims, and anything already routed advanced by rules.

Every route includes `selected_model_alias`, `selected_model`, `fallback_candidates`, `profile_name`, and `cost_quality_tradeoff`. `recommended_model` is the selected concrete model.

## Session Stickiness

When `session_id` is provided, AgenticRouter checks `data/session_cache.jsonl` for the latest prior route in that session. It reuses the previous alias/model only when:

- the project is the same
- risk has not increased
- `previous_failure_count` is less than `2`
- the new task does not newly touch a high-risk domain

Repeated failures ignore stickiness and let the normal escalation rule run. If risk increases, the sticky model is ignored and the task is rerouted.

Session records are sanitized JSON lines. Low-risk tasks keep only a short summary. High-risk or sensitive tasks keep a hash and the placeholder `[redacted-sensitive-task]`; they do not store task text, files, secrets, records, tokens, emails, serials, PII, PHI, or production log content.

## Local Observability

Every route appends a sanitized local trace to `data/traces.jsonl`. Tracing is local and offline: no LangSmith API, no API key, no `langsmith` import, no remote tracing, and no billing-dependent functionality.

Trace records include route ID, timestamp, project name, task class, risk, tier, selected alias/model, profile, context size, human-review flag, sticky-route flag, fallback candidates, matched rules, and whether prompt body was logged.

Low-risk routes may include a sanitized task summary capped at 180 characters. High-risk routes set `prompt_body_logged=false`, omit raw task text, and store only `task_description_hash` plus `sanitized_task_category`.

The sanitizer removes emails, token/API-key/password/secret patterns, tenant-ID-like GUIDs, USB serial patterns, and private Windows paths. Traces must not contain secrets, API keys, bearer tokens, passwords, emails, tenant IDs, USB serials, real veteran records, workers comp claims, legal/client records, student raw comments, production logs, or private Windows paths.

`exports/langsmith/` contains manual JSONL/CSV exports for inspection or later UI import. They are not API uploads.

## Config Validation

Config Studio validates local JSON policy before export/import. It checks required project/model/rule/profile fields, model aliases against known models, routing profiles against known aliases, fallback candidates against known aliases/models, golden-task project names, and secret-looking values or private Windows paths.

Imports are dry-run by default. Applying an import requires `--apply` and writes a timestamped local backup first.

## Scenario Simulation

Scenario Simulator uses the same `route()` path as normal CLI and web routing. Scenarios in `data/simulation_scenarios.json` are hypothetical batches with project, task, files, failure count, and live-prod flag.

Summaries include tier/model/alias/risk/context distributions, human-review count, live-prod count, sensitive-task count, sticky routes, escalations, top matched rules, top advanced projects, and top human-review projects.

Savings estimates use abstract planning units only. Model units are cheap = 1, mid = 3, advanced = 8, compared against naive all-advanced routing. Context units are tiny = 1, small = 2, medium = 5, large = 10, compared against naive full-repo context.

## Human Review

Human review is required when a project is marked sensitive or when task/project text hits sensitive data or security-control rules. That includes credentials, tokens, PII, PHI, veteran data, HR/payroll, legal records, public safety, workers comp, authentication, cybersecurity, Microsoft Graph, Intune, network, and infrastructure work.

## Context Policy

The router prefers the smallest useful context: listed files, direct callers, tests, and config. It avoids whole-repo context by default. Sensitive tasks add an explicit exclusion for secrets, tokens, credentials, bearer tokens, PII, PHI, and real case records.

The Context Pack Builder adds structured guidance beside that plain-language policy:

- `context_size`: tiny, small, medium, or large
- include patterns and file types
- notes for what to include
- exclude patterns
- forbidden context
- booleans for repo map, recent errors, and summarizing large files
- redaction warning and reason

Rules stay conservative. Docs/static work only gets touched docs/static files. UI work gets nearby UI/CSS and API contracts only if needed. Backend/report/bot work gets the script or endpoint, config example, project rules, and tests. Sensitive/security/live-prod work gets direct auth/API/SQL/config/test context and a strong warning against real PII, tokens, emails, tenant IDs, serials, records, private logs, or production secrets.

Public official content such as Local Budget Book and Transparency Portal requires source verification and forbids invented numbers or unverified claims. Live Forge bot work includes bot scripts, CLAUDE.md, implementation notes, manifests, and env-var docs without real values, with extra caution around email delivery, SQL, delete/archive behavior, naming conventions, and deployment.

When files are not listed, the builder recommends patterns/categories instead of exact paths. When many files are listed, it recommends summarizing large or generated files rather than sending all content.

## Run Packets

The DevSpace Run Packet Generator wraps a route result and context pack into a copy-pasteable execution packet for a DevSpace/Codex run. It uses the existing router result, so the packet keeps the same `route_id`, recommended model, effort, risk, human-review flag, and context pack.

Each packet includes:

- execution prompt
- context checklist
- safety checklist
- validation checklist
- stop conditions
- escalation plan

Validation playbooks live in `data/validation_playbooks.json` and cover static UI/docs, normal web apps, Forge bots, live-prod Forge bots, Laserfiche, TeamDynamix, Microsoft Graph/cybersecurity, public official budget content, sensitive intake/claims, and infrastructure/network security.

Generated prompts explicitly forbid secrets, PII, real records, tokens, passwords, emails, tenant IDs, USB serials, and production log content. Sensitive projects require sanitized context only. Live-prod projects explicitly prohibit broad refactors and require human review before deployment.

## Outcome Feedback

Every route result includes a `route_id`. The route ID encodes only non-sensitive routing metadata needed for later feedback: project name, broad task category, recommended tier/model, and escalation reason names. It does not encode task text, files touched, context, secrets, records, or user data.

Feedback is stored as JSON lines in `data/outcomes.jsonl`. Each record keeps project name, task category, recommended tier/model, actual model, accepted flag, task success flag, recommendation fit, escalation reason names, and sanitized notes.

Feedback notes must be sanitized before saving. Do not include secrets, credentials, bearer tokens, emails, serial numbers, PII, PHI, legal records, HR records, veteran records, medical records, or real case details.

## Golden Evaluation

`data/golden_tasks.json` is the regression set. Each case records the expected tier, risk, human-review flag, and reason keywords. The evaluator runs the real router against every case and exits nonzero on any mismatch.

Add new cases when:

- a new DevSpace project is added
- a routing rule changes
- a production or sensitive-data boundary is discovered
- a real task exposes a missed escalation or over-escalation
