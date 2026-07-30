# PLAN.md - incident_plan

## Goal

Incident containment

## Pipeline Contract

- Antigravity implements the feature only inside `TASK_SCOPE.json`.
- Codex reviews the exact snapshot.
- Pipeline mode: `plan`.
- Release is blocked until build/QA/Codex/gate pass when mode is `release`.

## Phases

1. Inspect current code and identify impacted files.
2. Implement the smallest scoped change.
3. Add or update tests proportional to risk.
4. Run verify, guardrails, Codex review, and release gate.
5. If Codex fails, fix only the reported issues and rerun dual.

SNAPSHOT_1

SNAPSHOT_2

SNAPSHOT_3

SNAPSHOT_4

SNAPSHOT_5

SNAPSHOT_6

SNAPSHOT_7

SNAPSHOT_8

SNAPSHOT_9

SNAPSHOT_10
