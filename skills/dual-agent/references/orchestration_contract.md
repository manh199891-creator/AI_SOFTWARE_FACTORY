# Orchestration Contract

Lifecycle is `research → plan → code → release`. Reuse one task ID. Each transition requires a committed snapshot and a matching Codex `phase_gate` PASS.

Checkpoint reservation is `READY → RESERVED(run_id) → LAUNCHED → CONSUMED`. A checkpoint authorizes at most one logical parent review. Multi-lens children inherit that authorization.

`CHECKPOINT_PASS` continues inside the current phase. `CHECKPOINT_FAIL` returns to the owning work item. `INFRA_FAIL`, `STATE_DESYNC`, scope regression, or a P0/P1 blocker stops execution without consuming content budget.

Anti checkpoints after each work item but cannot invoke Codex. `READY_FOR_CODEX` requires passing checks and evidence/explicit blocker for every current-batch finding. Claims remain unverified until Codex omits them from a complete changed-snapshot review.
