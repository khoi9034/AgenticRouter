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

## Golden Evaluation

`data/golden_tasks.json` is the regression set. Each case records the expected tier, risk, human-review flag, and reason keywords. The evaluator runs the real router against every case and exits nonzero on any mismatch.

Add new cases when:

- a new DevSpace project is added
- a routing rule changes
- a production or sensitive-data boundary is discovered
- a real task exposes a missed escalation or over-escalation

