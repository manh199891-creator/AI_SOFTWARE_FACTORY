---
name: module-workflow
description: Initialize and manage canonical module-local AI workflow contracts, Plan Lock, and Evidence Gate for Revit, Navisworks, or .NET add-in modules.
---

# Module Workflow Skill

## What this skill does

1. **Module Bootstrap** (`module_init.ps1` / `module_bootstrap.py`):
   Creates the canonical `.ai-workflow/` and `.sandbox/` skeleton inside an existing module directory (including `PLAN.md`).

2. **Plan Lock** (`plan_lock.ps1` / `plan_lock.py`):
   Locks `TASK.md` + `SCOPE.json` + `PLAN.md` via SHA-256 after Codex plan review approval, creating `.ai-workflow/PLAN_LOCK.json`.

3. **Evidence Gate** (`evidence_gate.ps1` / `evidence_gate.py`):
   Verifies files, symbols, diagnosis sources, and source snapshot SHA-256 before Antigravity is allowed to make code changes, creating `.ai-workflow/EVIDENCE.json`.

## Workflows

### Plan Preparation & Review Handoff

1. Planner/User fills `TASK.md`, `SCOPE.json`, `PLAN.md`.
2. Codex reviews plan and generates `plan-review-run-xxx.json` in `.ai-workflow/history/`.
3. Run `plan_lock.ps1 create` to validate review and lock contract files.
4. Verify lock anytime using `plan_lock.ps1 verify`.

### Evidence Request & Collection

1. Antigravity prepares `.sandbox/evidence_request.json`.
2. Run `evidence_gate.ps1 collect` to check file tracking, symbol presence, excerpt hashes, and source snapshot.
3. Run `evidence_gate.ps1 verify` prior to starting implementation.

## Invocations

### Plan Lock CLI
```powershell
.\skills\module-workflow\scripts\plan_lock.ps1 `
  -Action create `
  -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot "src\Antigravity.DrawBeams" `
  -ApprovalFile "src\Antigravity.DrawBeams\.ai-workflow\history\plan-review-run-001.json"

.\skills\module-workflow\scripts\plan_lock.ps1 `
  -Action verify `
  -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot "src\Antigravity.DrawBeams"
```

### Evidence Gate CLI
```powershell
.\skills\module-workflow\scripts\evidence_gate.ps1 `
  -Action collect `
  -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot "src\Antigravity.DrawBeams" `
  -RequestFile "src\Antigravity.DrawBeams\.sandbox\evidence_request.json"

.\skills\module-workflow\scripts\evidence_gate.ps1 `
  -Action verify `
  -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot "src\Antigravity.DrawBeams"
```

## Non-Goals & Governance

- Plan review JSON is produced by Codex adapter in subsequent phases. Phase C does not auto-invoke Codex.
- Evidence request is prepared by Antigravity. Evidence JSON is generated strictly by deterministic scripts.
- `PLAN_LOCK.json` and READY `EVIDENCE.json` are immutable once created.
- This skill has **not** been deployed into the production runtime manifest (`runtime_manifest.json`).

## Exit Codes

- `0`: Success (`CREATED`, `READY`, `NO_CHANGES`, `DRY_RUN`, `VERIFIED`).
- `2`: Context/input validation failure.
- `3`: Immutable conflict (`PLAN_LOCK_CONFLICT`, `EVIDENCE_LOCKED`).
- `4`: Write failure (`PLAN_LOCK_WRITE_FAILED`, `EVIDENCE_WRITE_FAILED`).
- `5`: Integrity mismatch or insufficient evidence (`PLAN_LOCK_INVALID`, `INSUFFICIENT_EVIDENCE`, `EVIDENCE_STALE`, `SOURCE_SNAPSHOT_CHANGED`).
