# Quickstart Demo

AgenticRouter is local, offline, and rule-based. The router does not call an AI model.

## Run The Local Web UI

```bash
python scripts/run_web.py
```

The script starts the dashboard on `http://127.0.0.1:8765` or the next available port through `8769`.

You can also run the module directly:

```bash
python -m agentic_router.web
```

## Run Tests

```bash
python -m unittest discover -s tests
```

## Run Golden Eval

```bash
python -m agentic_router.cli eval
```

## Run The Release Smoke Test

```bash
python scripts/smoke_test.py
```

## Demo Examples

Use the web UI route form or the equivalent CLI commands.

1. Low risk:
   `Diana Test Project` + `Make hello world page prettier`
2. High risk:
   `Veteran's Intake Application` + `Fix auth ping redirect`
3. Live-prod bot:
   `Gap Bills Forge Conversion` + `Change PDF output naming format`
4. Official content:
   `Local Budget Book` + `Fix official fund summary table`
5. Cybersecurity:
   `USB Device Approval Application` + `Connect Graph Advanced Hunting API and create TDX ticket`

## Stop The Local Server

Press `Ctrl+C` in the terminal running the server. If it was launched in a separate PowerShell window, close that window.

## What To Show A Lead Developer

- Router recommendation: model, tier, risk, human-review flag, and matched rules.
- Context pack: what to include, exclude, and never send.
- DevSpace run packet: copy-pasteable execution prompt and validation checklist.
- Scenario Simulator: abstract cost/context savings versus all-advanced routing.
- Shadow Analytics: advisory comparison between actual model use and router recommendation.
- Config Studio: local validation and safe config export.
- Pilot Readiness: demo-ready scorecard, rollout plan, and integration modes.
