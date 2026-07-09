from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .models import DATA_DIR
from .projects import find_project


@lru_cache(maxsize=1)
def load_context_policies() -> dict[str, Any]:
    with (DATA_DIR / "context_policies.json").open(encoding="utf-8") as f:
        return json.load(f)


def build_context_pack(
    project_name: str,
    task_description: str,
    files_touched: list[str] | None,
    risk_level: str,
    model_tier: str,
    matched_rules: list[str],
) -> dict[str, Any]:
    files = files_touched or []
    policy = load_context_policies()
    project = find_project(project_name)
    text = " ".join([project_name, task_description, *files, *project.get("keywords", []), *matched_rules]).casefold()
    category = _category(project_name, text, model_tier, matched_rules)
    spec = policy["categories"][category]
    many_files = len(files) > 6
    size = _size(category, model_tier, risk_level, len(files))

    include_patterns = _include_patterns(category, files)
    include_notes = list(spec["include_notes"])
    if not files:
        include_notes.append("No files were listed; use these patterns/categories to pick the smallest relevant context.")
    if many_files:
        include_notes.append("Many files were listed; summarize large or generated files instead of pasting all content.")

    forbidden = _unique(policy["base_forbidden_context"] + spec["forbidden_context"])
    return {
        "context_size": size,
        "include_patterns": include_patterns,
        "include_file_types": spec["include_file_types"],
        "include_notes": include_notes,
        "exclude_patterns": spec["exclude_patterns"],
        "forbidden_context": forbidden,
        "should_summarize_large_files": many_files or category in {"public_official", "live_forge"},
        "should_include_repo_map": not files or category in {"backend", "sensitive", "public_official", "live_forge"},
        "should_include_recent_errors": category in {"backend", "sensitive", "live_forge"} or "previous_failures_escalate" in matched_rules,
        "redaction_warning": _warning(category, text),
        "context_reason": spec["context_reason"],
    }


def format_context_pack(pack: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Context size: {pack['context_size']}",
            "Include patterns: " + ", ".join(pack["include_patterns"]),
            "Include file types: " + ", ".join(pack["include_file_types"]),
            "Exclude patterns: " + ", ".join(pack["exclude_patterns"]),
            "Forbidden context: " + ", ".join(pack["forbidden_context"]),
            f"Summarize large files: {pack['should_summarize_large_files']}",
            f"Include repo map: {pack['should_include_repo_map']}",
            f"Include recent errors: {pack['should_include_recent_errors']}",
            f"Redaction warning: {pack['redaction_warning']}",
            f"Reason: {pack['context_reason']}",
        ]
    )


def _category(project_name: str, text: str, model_tier: str, matched_rules: list[str]) -> str:
    # ponytail: keyword buckets are enough for this local MVP; replace with explicit per-project policies if drift shows up.
    if project_name in {"Local Budget Book", "Transparency Portal"} or "official public" in text:
        return "public_official"
    if "forge" in text and "live_prod_project" in matched_rules:
        return "live_forge"
    if model_tier == "advanced" and any(
        term in text
        for term in [
            "auth",
            "security",
            "cyber",
            "sql",
            "database",
            "laserfiche",
            "graph",
            "intune",
            "pii",
            "payroll",
            "workers comp",
            "veteran",
            "public safety",
            "usb",
        ]
    ):
        return "sensitive"
    if any(term in text for term in ["api", "endpoint", "report", "bot", "sql", "database", "workflow"]):
        return "backend"
    if any(term in text for term in ["ui", "form", "dashboard", "html", "css", "page", "color", "background"]):
        return "ui" if model_tier != "cheap" else "docs_static"
    return "docs_static" if model_tier == "cheap" else "backend"


def _size(category: str, model_tier: str, risk_level: str, file_count: int) -> str:
    if category == "docs_static":
        size = "tiny" if file_count <= 3 else "small"
    elif category == "ui":
        size = "small" if file_count <= 4 else "medium"
    elif category == "backend":
        size = "medium"
    elif category in {"public_official", "live_forge"}:
        size = "large" if file_count > 6 else "medium"
    else:
        size = "large" if risk_level in {"high", "critical"} and model_tier == "advanced" else "medium"
    return size


def _include_patterns(category: str, files: list[str]) -> list[str]:
    if files:
        patterns = list(files)
        if category == "ui":
            patterns.extend(["related CSS", "related API contract if needed"])
        elif category == "backend":
            patterns.extend(["config example", "README.md", "CLAUDE.md", "tests for touched code"])
        elif category == "sensitive":
            patterns.extend(["direct auth/API/SQL/config docs", "tests for touched code"])
        elif category == "public_official":
            patterns.extend(["source docs", "page references", "extracted text for affected pages"])
        elif category == "live_forge":
            patterns.extend(["CLAUDE.md", "implementation notes", "manifest", "env-var docs without values"])
        return _unique(patterns)

    defaults = {
        "docs_static": ["docs/**", "README.md", "web/**/*.html", "web/**/*.css"],
        "ui": ["web/**", "templates/**", "static/**", "related API contract"],
        "backend": ["relevant endpoint/script", "config example", "README.md", "CLAUDE.md", "tests/**"],
        "sensitive": ["direct auth/API/SQL files", "config docs without values", "tests/**"],
        "public_official": ["source docs", "page references", "extracted text", "affected generated files"],
        "live_forge": ["bot script", "CLAUDE.md", "implementation notes", "manifest", "env-var docs without values"],
    }
    return defaults[category]


def _warning(category: str, text: str) -> str:
    if category == "public_official":
        return "Verify source material before publishing; do not invent numbers or unverified public claims."
    if category == "live_forge":
        extra = []
        for term in ["email", "sql", "delete", "archive", "naming", "deployment"]:
            if term in text:
                extra.append(term)
        suffix = f" Extra caution: {', '.join(extra)}." if extra else ""
        return "Live-prod Forge context must exclude real env values and secrets; require human review before risky changes." + suffix
    if category == "sensitive":
        return "Strong human review required. Redact PII, tokens, passwords, emails, serials, tenant IDs, records, logs, and production secrets."
    return "Exclude secrets, credentials, private logs, and unrelated data."


def _unique(items: list[str]) -> list[str]:
    seen = set()
    return [item for item in items if not (item in seen or seen.add(item))]
