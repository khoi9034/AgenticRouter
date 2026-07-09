# Rollout Plan

## Phase A: Local-Only Demo

Run the web UI and walk through low-risk, high-risk, live-prod, and official-content examples.

## Phase B: Shadow Mode

Call `/api/v1/shadow` with actual DevSpace model choices and review shadow reports.

## Phase C: Advise Mode

Use `/api/v1/route` for docs, static UI, and test projects where risk is low.

## Phase D: Packet Mode

Use `/api/v1/packet` for normal coding tasks that benefit from a copy-pasteable run packet.

## Phase E: Strict Mode

Use `/api/v1/strict-check` for live-prod, sensitive, security, auth, SQL, Laserfiche, TeamDynamix, Microsoft Graph, Intune, infrastructure, and official-content work.

## Phase F: Periodic Review

Review golden evals, shadow reports, outcomes, and config validation on a recurring cadence.
