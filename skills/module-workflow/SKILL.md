---
name: module-workflow
description: Initialize and manage canonical module-local AI workflow contracts, Plan Lock, and Evidence Gate for Revit, Navisworks, or .NET add-in modules.
---

# Module Workflow Skill

## What this skill does

1. **Module Bootstrap** (`module_init.ps1` / `module_bootstrap.py`):
   Creates the canonical `.ai-workflow/` and `.sandbox/` skeleton inside an existing module directory (including `MODULE.json`, `SCOPE.json`, `TASK.md`, `PLAN.md`, `REVIEW.md`, and `.gitignore` managed block).

2. **Plan Lock** (`plan_lock.ps1` / `plan_lock.py`):
   Locks `TASK.md` + `SCOPE.json` + `PLAN.md` via SHA-256 after Codex plan review approval, creating `.ai-workflow/PLAN_LOCK.json`.

3. **Evidence Gate** (`evidence_gate.ps1` / `evidence_gate.py`):
   Verifies files, symbols, diagnosis sources, and source snapshot SHA-256 before Antigravity is allowed to make code changes, creating `.ai-workflow/EVIDENCE.json`.

---

## Invocation — Module Bootstrap

### PowerShell Wrapper
```powershell
.\skills\module-workflow\scripts\module_init.ps1 `
  -RepositoryRoot  "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot      "src\Antigravity.DrawBeams" `
  -ModuleId        "antigravity.drawbeams" `
  -ModuleName      "Antigravity.DrawBeams" `
  -ProjectFile     "src\Antigravity.DrawBeams\Antigravity.DrawBeams.csproj" `
  -Platform       "revit" `
  -DllName         "Antigravity.DrawBeams.dll"
```

### Python Directly
```powershell
python skills/module-workflow/scripts/module_bootstrap.py `
  --repository-root "E:\AI_SOFTWARE_FACTORY" `
  --module-root     "src/Antigravity.DrawBeams" `
  --module-id       "antigravity.drawbeams" `
  --module-name     "Antigravity.DrawBeams" `
  --project-file    "src/Antigravity.DrawBeams/Antigravity.DrawBeams.csproj" `
  --platform        "revit" `
  --dll-name        "Antigravity.DrawBeams.dll"
```

---

## Invocation — Plan Lock & Evidence Gate

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

---

## Idempotency & Immutability

- **Bootstrap**: Running `module_init` a second time with the same inputs returns `NO_CHANGES`. No files are modified and `.gitignore` block is not duplicated.
- **Plan Lock**: `PLAN_LOCK.json` is immutable once created. Overwriting with differing payload returns `PLAN_LOCK_CONFLICT` (exit 3).
- **Evidence Gate**: `EVIDENCE.json` with `ready_to_implement == true` is immutable once generated.

---

## Exit Codes

- `0`: Success (`CREATED`, `READY`, `NO_CHANGES`, `DRY_RUN`, `VERIFIED`).
- `2`: Context/input validation failure (`PLAN_REVIEW_INVALID`, `EVIDENCE_REQUEST_INVALID`, `PROTECTED_BRANCH_BLOCKED`).
- `3`: Immutable conflict (`BOOTSTRAP_CONFLICT`, `PLAN_LOCK_CONFLICT`, `EVIDENCE_LOCKED`).
- `4`: Write failure (`BOOTSTRAP_WRITE_FAILED`, `PLAN_LOCK_WRITE_FAILED`, `EVIDENCE_WRITE_FAILED`).
- `5`: Integrity mismatch or insufficient evidence (`PLAN_LOCK_INVALID`, `INSUFFICIENT_EVIDENCE`, `EVIDENCE_STALE`, `SOURCE_SNAPSHOT_CHANGED`).

---

## Non-Goals & Governance

- Does **not** auto-invoke Codex or Antigravity runtime routines.
- Does **not** modify add-in source code or build DLLs.
- Does **not** modify production pipeline runtime scripts (`harness.py`, `review_pipeline.py`, `dual_agent_runtime.py`, `pipeline_status.json`).
- Skill scripts run with Python standard library only.
