# Shadow Mode Rollout

Shadow mode lets DevSpace compare real model choices against AgenticRouter recommendations before enforcing router policy.

It is advisory only. It does not change DevSpace model selection.

## Rollout Steps

1. Start DevSpace calls in `mode: "shadow"` and send `actual_model_used`.
2. Review `python -m agentic_router.cli shadow-summary` after a small pilot batch.
3. Export a local report with `python -m agentic_router.cli export-shadow-report`.
4. Look first for safety-risk mismatches, especially human cheap while router recommended advanced.
5. Move low-risk, high-agreement categories to `advise` mode.
6. Use `strict` mode only after reviewing human-review and would-block cases.

## What To Watch

- Agreement rate: how often actual tier matches router tier.
- Overkill: human used a stronger model than the router recommended.
- Too weak or safety risk: human used a weaker model than the router recommended.
- Strict would-block: work that should stop for human review.
- Estimated units saved/lost: abstract units, not dollars.

Cost units are:

- cheap = 1
- mid = 3
- advanced = 8

## Privacy

Shadow records are sanitized local JSON lines in `data/shadow_runs.jsonl`.

Do not send secrets, API keys, bearer tokens, passwords, emails, tenant IDs, USB serials, real veteran records, workers comp claims, legal/client records, student raw comments, production logs, private Windows paths, or real PII/PHI.

High-risk or sensitive shadow records do not store raw task text. They store a short hash and task category only.

## Local Reports

Reports are generated under `exports/reports/`:

- `shadow_mode_report.md`
- `shadow_mode_report.json`

These files are local artifacts, not uploads.
