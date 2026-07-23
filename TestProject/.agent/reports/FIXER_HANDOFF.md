# FIXER_HANDOFF.md

## Status: NEEDS_FIX
- task_id: task1
- feature: A dummy feature
- cycle: 2
- reason: Review failed with 1 findings.

## Instructions For Antigravity Fixer

Read these files:

1. `.agent/reports/CODEX_REVIEW.md`
2. `.agent/context/PLAN.md`
3. `.agent/context/TECHNICAL_DESIGN.md`
4. `.agent/context/ACCEPTANCE_CRITERIA.md`
5. `.agent/context/TASK_SCOPE.json`

Fix only the issues listed by Codex and only within `TASK_SCOPE.json`.

After fixing, run:

```powershell
python E:\AI_SOFTWARE_FACTORY\harness.py TestProject dual --task-id task1 --feature "A dummy feature"
```
