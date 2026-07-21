# Routing Methodology

AgenticRouter is intentionally rule-based. It does not call an AI model during routing or evaluation.

## Decision Inputs

The router considers:

- project name
- task description
- files touched
- previous failure count
- project catalog risk, production, and sensitivity flags
- intrinsic task risk from the Task Normalizer

The final route risk is the maximum of the project risk floor and intrinsic task risk.

## Tier Selection

The router first normalizes the task text and touched files. The normalizer returns a sanitized summary, task type, requested capabilities, operation type, complexity, intrinsic risk, minimum tier, human-review recommendation, ambiguity warnings, extracted constraints, forbidden-context hints, matched task signals, false-positive controls, and a short risk reason.

Then the router combines six factors:

1. Project risk profile
2. Intrinsic task risk
3. Routing profile
4. Previous failures
5. Live-prod status
6. Context requirements

The router starts from the project catalog default tier and applies the higher of project risk and intrinsic task risk:

- cheap: docs, copy, README, placeholder, simple summary, static HTML/CSS
- mid: UI, forms, dashboards, reports, workflows, non-production bot analysis
- advanced: sign-in/login/auth, authorization, roles, admin users, SQL/database/schema/migrations, API/backend work, Laserfiche, TeamDynamix, Graph, Intune, cybersecurity, infrastructure, production deployment, credentials, PII, HR/payroll, public safety, workers comp, official public budget, live Forge

The normalizer prevents low-risk projects from staying cheap when the task itself asks for high-risk capabilities. For example, a test project task that asks for login, roles, SQL database work, admin users, or security controls gets an advanced minimum tier. Savings-oriented profiles cannot downgrade high intrinsic-risk tasks.

The normalizer also has false-positive controls for harmless mentions. Documentation about SQL, auth, or APIs can stay cheap/medium when it is clearly docs-only. Visual-only work such as changing a login button color stays low. Static/mock UI with no backend is not treated as auth implementation. Basic read-only API use stays medium unless the task asks to create or modify backend writes.

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

## DevSpace Integration Contract

The v1 integration layer is a stable wrapper around the existing local router. DevSpace or another caller sends a small request to `/api/v1/route`, `/api/v1/packet`, `/api/v1/contract`, `/api/v1/contract/check`, `/api/v1/shadow`, or `/api/v1/strict-check`; AgenticRouter returns the same routing decision plus contract metadata, warnings, block status, and optional packet data.

Modes:

- `shadow`: log what AgenticRouter would have recommended while the caller keeps its current routing.
- `advise`: return the recommendation only.
- `packet`: return the recommendation plus a DevSpace run packet.
- `strict`: block when human review is required or forbidden context is detected.

The integration contract is local-only. It does not call a model, cloud service, LangSmith API, or remote tracing endpoint. Requests must not contain secrets, real records, emails, tenant IDs, USB serials, private Windows paths, production logs, or PII/PHI. If forbidden-looking content is detected, strict mode blocks and packet generation is suppressed.

## Shadow Mode Analytics

Shadow mode lets DevSpace pilot AgenticRouter without changing model selection. A `/api/v1/shadow` request runs the normal route, accepts the caller's `actual_model_used`, and appends a sanitized comparison record to `data/shadow_runs.jsonl`.

Shadow records store route ID, project, broad task class, risk, recommended model/tier/alias, actual model/tier, profile, context size, human-review flag, strict-mode would-block flag, matched rule names, and comparison labels. High-risk or sensitive tasks do not store raw task text; they store only a task-description hash and sanitized category with `prompt_body_logged=false`.

Analytics compare actual usage to router recommendations:

- exact model and tier agreement
- human used stronger than router
- human used weaker than router
- safety-risk mismatches, such as human cheap while router recommended advanced
- abstract cost units using cheap = 1, mid = 3, advanced = 8
- top projects with overkill or too-weak/safety mismatches

Shadow analytics are local-only and advisory. They do not enforce routing, call a model, use a cloud service, or send remote traces.

## Pilot Readiness Reporting

The pilot/demo layer does not change routing decisions. It summarizes existing local evidence for a lead developer or leadership audience:

- golden eval count and pass rate
- project catalog size and risk distribution
- available model tiers and integration modes
- scenario simulator savings examples
- local observability status
- shadow analytics readiness
- config validation status

The readiness status is `demo-ready` when golden evals pass, config validation passes, and local observability is enabled. Otherwise it reports `needs-work`.

Pilot reports recommend a staged rollout: local demo, shadow mode, advise mode for low-risk projects, packet mode for normal tasks, strict mode for high-risk/live-prod tasks, and periodic review using golden evals, shadow reports, outcomes, and config validation.

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

## Run Contracts and Scope Guard

The Run Contract layer converts a route result and normalized task brief into an enforceable local scope contract. It defines allowed file patterns, forbidden file patterns, allowed actions, forbidden actions, validation checks, stop conditions, production cautions, sensitive-data cautions, and whether human review is required.

Policy is intentionally pattern-based and local. Docs and visual/static UI work can allow only Markdown, HTML, CSS, static assets, or web files while forbidding auth, API, config, secrets, database, dependency, and deployment edits. Backend/auth/database, external write, destructive, and production contracts require stronger validation, rollback or dry-run notes where relevant, and human review.

Scope Guard checks changed files, an optional sanitized diff summary, and optional added dependencies against the contract. Forbidden file matches or files outside the allowed scope fail. Unexpected dependencies warn. High-risk compliant changes still warn when human review or rollback notes are required.

## Diff Review and Quality Gate

Diff Review runs after Scope Guard when patch content is available. It accepts a supplied diff or the current local `git diff`, reuses Scope Guard when a run contract is provided, and then applies local regex rules from `data/diff_risk_rules.json`.

The review flags secret-like additions, auth/session/access-control changes, API endpoint or request/response changes, SQL/schema/persistence changes, destructive or bulk operations, external writes, dependency/config/deploy file changes, and weakened validation or error handling. CSS, docs, copy, comments, and static layout-only changes usually pass unless the contract, project risk, or live-prod flag requires review.

The quality gate never downgrades Scope Guard. If file scope fails, the final decision remains `fail`. If file scope passes but the diff adds risky behavior, the decision escalates to `warn` or `fail`, with required follow-up checks and human-review flags.

## DevSpace AutoGate

AutoGate connects the existing local pieces into one automated run lifecycle. Start-run normalizes and routes the task, builds the context pack, run packet, and run contract, generates automated requirements from risk/live-prod status, creates a `run_id`, and writes a sanitized record to `data/run_records.jsonl`.

Complete-run loads the original run, runs Scope Guard, runs Diff Review, checks test and rollback evidence, and returns one machine decision: `auto_approved`, `auto_blocked`, `needs_tests`, `needs_retry`, `needs_more_evidence`, or `rollback_required`.

AutoGate is not a human review queue. Legacy `human_review_required` fields may remain in older route/contract responses for compatibility, but AutoGate decisions are based on automated evidence. Low-risk docs/CSS work can approve with passing scope and diff checks. Medium-risk work requires tests or validation evidence. High-risk work requires passing tests and no blocking secret/auth-bypass/destructive findings; live-prod work also requires rollback evidence.

## Automated Evidence Runner

The Evidence Runner automates the evidence that `complete-run` previously required by hand. It collects local git status, staged and unstaged changed files, staged and unstaged diffs, builds a validation plan from the run contract, normalized task, project risk, changed files, and project type indicators, then runs only allowlisted validation commands.

Allowed validation commands are intentionally narrow: Python unittest discovery, Python compile checks for changed `.py` files, existing npm test/lint/typecheck/build scripts, Node syntax checks for changed JavaScript files, PHP lint checks for changed PHP files, and `dotnet test` when a `.csproj` exists. The runner uses `subprocess` with `shell=False`, captures stdout/stderr, applies timeouts, and treats missing local tools as `unavailable` rather than crashing.

The runner never executes install, deploy, migration, database, delete, purge, sync, production, or unlisted commands. Raw diff text is used locally to feed Scope Guard and Diff Review; API/web summaries show compact diff summaries and validation results. Secret-like diffs, auth bypasses, or destructive changes still block through Diff Review even if validation passes.

## Run Packets

The DevSpace Run Packet Generator wraps a route result, context pack, and run contract into a copy-pasteable execution packet for a DevSpace/Codex run. It uses the existing router result, so the packet keeps the same `route_id`, recommended model, effort, risk, human-review flag, context pack, and scope guardrails.

Each packet includes:

- execution prompt
- context checklist
- run contract
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
