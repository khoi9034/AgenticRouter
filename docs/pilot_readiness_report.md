# Pilot Readiness Report

AgenticRouter is demo-ready as a local, rule-based DevSpace routing pilot.

## Current Capabilities

- Rule-based model routing
- Golden regression evaluation
- Local web UI
- Context pack builder
- DevSpace run packet generator
- Outcome feedback logging
- Routing profiles, fallbacks, and session stickiness
- Local observability and exports
- Config validation and Config Studio
- Scenario simulation
- DevSpace v1 integration API
- Shadow mode analytics

## Rollout Sequence

1. Local demo
2. Shadow mode
3. Advise mode for low-risk projects
4. Packet mode for normal tasks
5. Strict mode for high-risk/live-prod tasks

## Privacy And Safety

AgenticRouter stays local and offline. Do not send secrets, API keys, bearer tokens, passwords, emails, tenant IDs, USB serials, real records, production logs, private Windows paths, or PII/PHI.

High-risk traces and shadow records store hashes/categories instead of raw task text.

Generate the current report with:

```bash
python -m agentic_router.cli pilot-report
```
