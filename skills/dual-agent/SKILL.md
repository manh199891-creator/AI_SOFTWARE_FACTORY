---
name: dual-agent
description: Orchestrate Antigravity as the single writer and Codex as the independent verifier through durable phase checkpoints.
---

# Dual Agent Orchestrator

Use `scripts/dual_orchestrate.ps1`; never simulate either agent and never let both write the same worktree.

## Phase contract

- Anti owns research, planning, implementation, fixes, and initial checks.
- The harness owns writer checkpoints and Codex scheduling.
- Codex alone verifies finding closure and phase gates.
- A task checkpoint does not advance phase. Only a matching `phase_gate` PASS does.
- Default policy is `checkpointed`; `continuous` is an explicit task opt-in and stops at configured boundaries.

Before review, Anti writes `.agent/context/WRITER_CHECKPOINT_REQUEST.json` and invokes the checkpoint action. It must include phase, monotonic work-item progress, changed files, checks, finding claims/blockers, risks, hypothesis, and readiness. Anti must not write `.agent/state/**`, invoke Codex, or rerun the dual pipeline.

Run doctor before init/run. Treat integrity drift, state desynchronization, missing checkpoint, infrastructure failure, and scope regression as fail-closed conditions.

Read [references/orchestration_contract.md](references/orchestration_contract.md) before a multi-phase task.
