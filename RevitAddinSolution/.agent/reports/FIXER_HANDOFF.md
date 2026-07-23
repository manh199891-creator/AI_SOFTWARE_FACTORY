# FIXER_HANDOFF.md

## Status: NEEDS_FIX
- task_id: auto_foundation_cleanup_fix
- feature: Cleanup AutoFoundation scope and encoding issues
- cycle: 1
- reason: Review failed with 7 findings.

## Instructions For Antigravity Fixer

Read these files:

1. `.agent/reports/CODEX_REVIEW.md`
2. `.agent/context/MEMORY_CONTEXT.md`
3. `.agent/context/PLAN.md`
4. `.agent/context/TECHNICAL_DESIGN.md`
5. `.agent/context/ACCEPTANCE_CRITERIA.md`
6. `.agent/context/TASK_SCOPE.json`

Fix only the issues listed by Codex and only within `TASK_SCOPE.json`.

After fixing, run:

```powershell
python E:\AI_SOFTWARE_FACTORY\harness.py RevitAddinSolution dual --task-id auto_foundation_cleanup_fix --feature "Cleanup AutoFoundation scope and encoding issues" --mode code
```
