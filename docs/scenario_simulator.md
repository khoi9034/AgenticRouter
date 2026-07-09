# Scenario Simulator

The Scenario Simulator runs named batches of hypothetical DevSpace tasks through the local router and summarizes routing distribution, risk, review needs, context size, and abstract savings.

It is local-only: no cloud, API keys, remote calls, or external dependencies.

## CLI

```bash
python -m agentic_router.cli list-scenarios
python -m agentic_router.cli simulate --scenario mixed_devspace_month
python -m agentic_router.cli simulate --scenario forge_bot_maintenance_week --json
```

Scenarios live in `data/simulation_scenarios.json`.

## Savings Units

Model cost is abstract:

- cheap = 1 unit
- mid = 3 units
- advanced = 8 units

Context is abstract:

- tiny = 1 unit
- small = 2 units
- medium = 5 units
- large = 10 units

The simulator compares routed results against naive all-advanced routing and naive full-repo context. These are planning units only, not dollars.
