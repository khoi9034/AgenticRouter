# AgenticRouter LangSmith App Files

These files are local, manual export artifacts for inspection or later import through a UI.

They are not API uploads. AgenticRouter does not use the LangSmith API, does not require an API key, does not import `langsmith`, and does not send remote traces.

Files:

- `golden_tasks_dataset.jsonl`: Golden routing tasks with expected outputs.
- `golden_tasks_dataset.csv`: Spreadsheet-friendly golden task export.
- `router_traces_example.jsonl`: Sanitized local router traces.
- `router_traces_example.csv`: Spreadsheet-friendly trace export.

Do not add secrets, tokens, private paths, PII, records, emails, tenant IDs, USB serials, production logs, or real case data to these files.
