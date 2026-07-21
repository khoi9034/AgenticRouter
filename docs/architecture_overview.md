# Architecture Overview

AgenticRouter is a local policy brain for DevSpace model selection. It decides how risky a task is, which model tier is appropriate, what context should be sent, and when a human review gate is needed.

It is rule-based and offline. The router does not call an AI model, cloud service, LangSmith API, or remote tracing endpoint.

## Policy Brain

The central routing path is `agentic_router.router.route()`. It combines the project catalog, normalized intrinsic task risk, touched files, failure count, live-prod flag, sensitivity rules, routing profiles, fallback policies, and session stickiness.

## Model Routing

Model tiers are `cheap`, `mid`, and `advanced`. The Task Normalizer first detects task-level capabilities such as auth, SQL/database, admin users, APIs, security, deployment, docs/static work, reports, and CSV imports. Rules then route docs/static work cheap, normal app/report work mid, and sensitive/security/live-prod/integration work advanced. Profiles and allowed-model pools can steer normal tasks but cannot downgrade safety-locked or high intrinsic-risk work.

## Context Routing

`agentic_router.context` builds a context pack for each route. The pack recommends context size, include patterns, file types, notes, exclusions, forbidden context, and redaction warnings. It prefers smallest useful context over whole-repo context.

## Run Packets

`agentic_router.packets` turns a route and context pack into a DevSpace/Codex execution packet. Packets include a prompt, context checklist, safety checklist, validation checklist, stop conditions, and escalation plan.

## Shadow Mode

The v1 integration API supports `shadow` mode. Shadow mode logs a sanitized local comparison between the model DevSpace actually used and the model AgenticRouter recommended. It is advisory and does not change model selection.

## Config Studio

Config Studio validates local JSON policy files, summarizes config, exports/imports bundles, and supports a guarded add-project form. It rejects secret-looking values and private paths.

## Scenario Simulator

The simulator runs named hypothetical task batches through the real router. It summarizes tier/model/risk/context distribution and abstract model/context savings.

## Integration API

The stable local v1 API exposes health/version/contracts plus route, packet, shadow, and strict-check endpoints. DevSpace can start in shadow mode, move low-risk work to advise mode, use packet mode for normal work, and use strict mode for high-risk/live-prod tasks.

## Local-Only Observability

Routes write sanitized local JSONL traces. High-risk tasks store hashes/categories instead of raw task text. Exports are local files only; no remote trace sending is used.

## Enterprise Gateway Exports

Enterprise export files are sanitized templates for LiteLLM-style or internal gateway setup. They describe routing, guardrails, observability, budgets, and context policy without real secrets or production values.
