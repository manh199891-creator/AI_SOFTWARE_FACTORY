# FIXER_HANDOFF.md

## Status: NEEDS_FIX
- task_id: incident_plan
- feature: Test dual
- cycle: 1
- reason: Review found issues.

## Instructions For Antigravity Fixer

Read these files:

1. `.agent/reports/CODEX_REVIEW.md`
2. `.agent/context/MEMORY_CONTEXT.md`
3. `.agent/context/PLAN.md`
4. `.agent/context/TECHNICAL_DESIGN.md`
5. `.agent/context/ACCEPTANCE_CRITERIA.md`
6. `.agent/context/TASK_SCOPE.json`

Fix only the issues listed by Codex and only within `TASK_SCOPE.json`.
Fix all findings in one coherent pass. Preserve previously established security,
benchmark, rollback, and traceability contracts. Do not delete substantive sections
merely to reduce file size or fit a presumed context limit.
Do not invoke Codex or rerun the dual pipeline. The harness owns the next review.
Finish by reporting changed files, checks run, remaining risks, and a falsifiable retry hypothesis.
Write `.agent/context/WRITER_CHECKPOINT_REQUEST.json` using `writer_checkpoint.schema.json`, then run:
`powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/dual-agent-pipeline/scripts/dual_checkpoint.ps1 -Project test_project`.
Do not write `.agent/state/writer_checkpoint.json` directly.
