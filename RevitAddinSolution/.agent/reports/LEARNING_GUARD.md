# LEARNING_GUARD.md

## Status: PASS
- task_id: auto_foundation_cleanup_fix
- mode: release
- generated_at: 2026-07-21T09:03:30.098879+00:00
- source_count: 29
- matched_rule_count: 4

## Token Strategy
- Agents read `.agent/context/MEMORY_CONTEXT.md` by default.
- Full memories stay in `.agent/knowledge/**` and are loaded only when a rule matches the active issue.

## Rules
- **dirty_baseline_or_scope** [P1] hits=6: Initialize a clean task baseline before copying task changes; never widen Allowed to hide unrelated dirty files.
  source: `E:\AI_SOFTWARE_FACTORY\RevitAddinSolution\.agent\learning\trajectories\auto_foundation_cleanup_fix.jsonl`
- **blind_retry_after_failure_budget** [P1] hits=3: Do not rerun the same hypothesis. Change scoped code or provide a new falsifiable resume hypothesis.
  source: `E:\AI_SOFTWARE_FACTORY\RevitAddinSolution\.agent\knowledge\memory\bugs\auto_column.md`
- **review_batch_context_split** [P2] hits=2: Keep related production, project, and test files together in review context where possible.
  source: `E:\AI_SOFTWARE_FACTORY\RevitAddinSolution\.agent\reports\CODEX_REVIEW.md`
- **codex_sandbox_degraded** [P3] hits=2: Treat sandbox helper errors as a diagnostic warning unless Codex cannot return a valid review contract.
  source: `E:\AI_SOFTWARE_FACTORY\RevitAddinSolution\.agent\reports\CODEX_REVIEW.md`
