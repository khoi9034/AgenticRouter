# Local Observability

AgenticRouter writes sanitized local route traces to `data/traces.jsonl`. It does not use the LangSmith API, does not require an API key, does not import `langsmith`, and does not send remote traces.

## Commands

```bash
python -m agentic_router.cli traces
python -m agentic_router.cli export-langsmith-files
python -m agentic_router.cli observability-status
```

`export-langsmith-files` writes manual inspection/import files under `exports/langsmith/`:

- `golden_tasks_dataset.jsonl`
- `golden_tasks_dataset.csv`
- `router_traces_example.jsonl`
- `router_traces_example.csv`
- `README.md`

## Trace Privacy

Low-risk traces may include a sanitized task summary capped at 180 characters. High-risk traces store `task_description_hash` and `sanitized_task_category` instead of task text, with `prompt_body_logged=false`.

Trace sanitization excludes secrets, API keys, bearer tokens, passwords, emails, tenant IDs, USB serials, real veteran records, workers comp claims, legal/client records, student raw comments, production logs, and private Windows paths.
