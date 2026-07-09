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
