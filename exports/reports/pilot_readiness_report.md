# Pilot Readiness Report

Generated: 2026-07-21T18:16:29+00:00
Readiness status: demo-ready

## Scorecard

- Golden eval: 51/51 (100.0%)
- Projects: 24
- High-risk projects: 15
- Model tiers: advanced, cheap, mid
- Local observability enabled: True
- Shadow analytics enabled: True
- Config validation: pass
- Integration contract: v1

## Capabilities

- rule-based model routing
- golden regression evaluation
- local web UI
- context pack builder
- DevSpace run packet generator
- outcome feedback logging
- routing profiles, fallbacks, and session stickiness
- local observability and exports
- config validation and Config Studio
- scenario simulation
- DevSpace v1 integration API
- shadow mode analytics

## Scenario Savings Examples

- docs_heavy_week: 33 model units saved, 41 context units saved
- mixed_devspace_month: 22 model units saved, 34 context units saved

## Rollout Sequence

1. local demo
2. shadow mode
3. advise mode for low-risk projects
4. packet mode for normal tasks
5. strict mode for high-risk/live-prod tasks

## Known Limitations

- Rules are keyword/catalog based and do not call an AI model.
- Cost savings use abstract units, not real dollars.
- Shadow analytics depend on callers supplying actual_model_used.
- Config Studio has a guarded add-project form, not a full policy editor.
- Human review gates are reported locally; enforcement depends on the caller using strict mode.

## Privacy And Safety Rules

- No secrets, API keys, bearer tokens, passwords, or credentials.
- No real PII/PHI, veteran records, workers comp claims, legal/client records, or student raw comments.
- No emails, tenant IDs, USB serials, private Windows paths, production logs, or real records.
- High-risk traces and shadow records store hashes/categories instead of raw task text.
- Everything stays local and offline.

## Next Engineering Steps

- Pilot shadow mode against real DevSpace manual choices.
- Review shadow mismatches and adjust routing rules/catalog entries.
- Use advise mode for low-risk projects after agreement is high.
- Add caller-side strict-mode blocking for live-prod and sensitive projects.
- Schedule periodic golden eval, config validation, outcome, and shadow report review.
