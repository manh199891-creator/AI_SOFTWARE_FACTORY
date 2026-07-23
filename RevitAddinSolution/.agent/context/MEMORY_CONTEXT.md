# MEMORY_CONTEXT.md

Compact operational memory for this task. Use these prevention rules before planning, coding, fixing, or reviewing.

- task_id: auto_foundation_cleanup_fix
- mode: release
- source_count: 29
- matched_rule_count: 4

## Prevention Rules
- P1 dirty_baseline_or_scope (6 hits): Initialize a clean task baseline before copying task changes; never widen Allowed to hide unrelated dirty files.
- P1 blind_retry_after_failure_budget (3 hits): Do not rerun the same hypothesis. Change scoped code or provide a new falsifiable resume hypothesis.
- P2 review_batch_context_split (2 hits): Keep related production, project, and test files together in review context where possible.
- P3 codex_sandbox_degraded (2 hits): Treat sandbox helper errors as a diagnostic warning unless Codex cannot return a valid review contract.

## Recent Outcomes
- code BLOCKED: Guardrails failed
- code BLOCKED: BLOCKED
- code BLOCKED_VERIFY: Required verification failed
- release BLOCKED: TASK_SCOPE.json mode mismatch. Expected release, found code
- release BLOCKED: TASK_SCOPE.json mode mismatch. Expected release, found code

## Token Policy
- This file is the default memory payload for agents.
- Load full bug memories only when a listed prevention rule is directly relevant.
