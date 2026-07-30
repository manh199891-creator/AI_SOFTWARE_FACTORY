# PLAN.md - generic_task

## Goal

Generic feature for any project

## Pipeline Contract

- Antigravity implements the feature only inside `TASK_SCOPE.json`.
- Codex reviews the exact snapshot.
- Pipeline mode: `release`.
- Release is blocked until build/QA/Codex/gate pass when mode is `release`.

## Phases

1. Inspect current code and identify impacted files.
2. Implement the smallest scoped change.
3. Add or update tests proportional to risk.
4. Run verify, guardrails, Codex review, and release gate.
5. If Codex fails, fix only the reported issues and rerun dual.
