# Config Studio

Config Studio is a local-only maintenance surface for AgenticRouter routing policy. It validates JSON config, exports/imports a bundle, summarizes policy state, and exposes one guarded add-project form in the web UI.

It does not use cloud services, API keys, remote calls, or external dependencies.

## CLI

```bash
python -m agentic_router.cli validate-config
python -m agentic_router.cli config-summary
python -m agentic_router.cli export-config --output exports/config/agentic_router_config_bundle.json
python -m agentic_router.cli import-config --input exports/config/agentic_router_config_bundle.json --dry-run
```

`import-config` validates first and does not overwrite anything unless `--apply` is used. Apply mode writes a timestamped local backup before replacing config files.

## Web UI

The Config Studio panel shows validation status, project counts by risk, model aliases, routing profiles, golden task count, and buttons for validation, bundle export, summary refresh, and golden eval.

The only editable control is Add Project. It accepts:

- project name
- department
- status
- risk level: `low`, `medium`, or `high`
- live/prod flag
- sensitive domains
- routing notes

Add Project validates before writing to `data/projects.json`, rejects duplicate project names, and rejects secret-looking values or private Windows paths.

## Safety

Config files and examples must not contain secrets, real PII, tokens, emails, tenant IDs, USB serials, private Windows paths, production logs, or real records.
