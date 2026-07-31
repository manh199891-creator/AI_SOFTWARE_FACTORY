---
name: module-workflow
description: Initialize the canonical module-local AI workflow and sandbox structure for an existing Revit, Navisworks, or .NET add-in module.
---

# Module Workflow Bootstrap Skill

## What this skill does

Runs the `module_init.ps1` / `module_bootstrap.py` tool to create the canonical
`.ai-workflow/` and `.sandbox/` skeleton inside an **already-existing** source
module directory.

It generates:
- `.ai-workflow/MODULE.json` — machine-readable module contract (Phase A schema)
- `.ai-workflow/SCOPE.json` — placeholder scope contract at status `DRAFT`
- `.ai-workflow/TASK.md` — canonical task template
- `.ai-workflow/REVIEW.md` — canonical review template
- `.ai-workflow/history/.gitkeep` — tracked directory placeholder
- `.sandbox/README.md` — sandbox readme from canonical template
- `.sandbox/bin/`, `obj/`, `addin/`, `test-models/`, `logs/`, `results/` — empty dirs
- `<module-root>/.gitignore` — managed block protecting sandbox from version control

## What this skill does NOT do

- Create or scaffold new source modules (tool only bootstraps an existing module).
- Run Antigravity or any agent pipeline.
- Run Codex review.
- Create a task branch automatically.
- Build DLL or run Revit/Navisworks tests.
- Create generated task runtime files: `PLAN_LOCK.json`, `EVIDENCE.json`,
  `DELIVERY.json`, `.sandbox/manifest.json`.
- Sync or promote DLL to production.
- Overwrite an existing, differing workflow contract.
- Run on a protected branch (`main`, `master`, `develop`, `release`).

This skill has **not** been deployed into the production runtime manifest.
It is invoked manually during module onboarding.

---

## Invocation — PowerShell

```powershell
.\skills\module-workflow\scripts\module_init.ps1 `
  -RepositoryRoot  "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot      "src\Antigravity.DrawBeams" `
  -ModuleId        "antigravity.drawbeams" `
  -ModuleName      "Antigravity.DrawBeams" `
  -ProjectFile     "src\Antigravity.DrawBeams\Antigravity.DrawBeams.csproj" `
  -Platform        "revit" `
  -DllName         "Antigravity.DrawBeams.dll"
```

## Invocation — Python directly

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

Append `--dry-run` to preview without writing.

---

## Idempotency

Running the tool a second time with the same inputs returns:

```json
{ "status": "NO_CHANGES", "reason_code": "BOOTSTRAP_ALREADY_CURRENT" }
```

No files are modified, no timestamps change, no `.gitignore` block is duplicated.

---

## Output format

Stdout is always a single JSON object. Do not mix with stderr diagnostics.

```json
{
  "schema_version": 1,
  "status": "CREATED | NO_CHANGES | DRY_RUN | FAILED",
  "reason_code": "BOOTSTRAP_CREATED",
  "repository_root": "E:/AI_SOFTWARE_FACTORY",
  "module_root": "src/Antigravity.DrawBeams",
  "branch": "task/drawbeams-init",
  "dry_run": false,
  "files_created": [...],
  "files_preserved": [...],
  "directories_created": [...],
  "gitignore_updated": true,
  "generated_contracts": [...]
}
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | `CREATED`, `NO_CHANGES`, or `DRY_RUN` |
| `2`  | Context / input validation failure |
| `3`  | Conflict with existing content |
| `4`  | Write or rollback failure |

---

## Reason codes

| Code | Trigger |
|------|---------|
| `BOOTSTRAP_CREATED` | First run, files created successfully |
| `BOOTSTRAP_ALREADY_CURRENT` | Rerun with same inputs, no changes needed |
| `BOOTSTRAP_DRY_RUN` | `--dry-run` flag used |
| `NOT_A_GIT_REPOSITORY` | `RepositoryRoot` is not a Git working tree |
| `REPOSITORY_ROOT_MISMATCH` | Git root differs from `RepositoryRoot` |
| `PROTECTED_BRANCH_BLOCKED` | Current branch is `main`, `master`, `develop`, or `release` |
| `INVALID_RELATIVE_PATH` | A path argument is absolute, empty, or contains `..` |
| `PATH_ESCAPES_REPOSITORY` | A path resolves outside the repository root |
| `MODULE_ROOT_NOT_FOUND` | `ModuleRoot` directory does not exist |
| `PROJECT_FILE_NOT_FOUND` | `ProjectFile` does not exist |
| `PROJECT_FILE_OUTSIDE_MODULE` | `ProjectFile` is not inside `ModuleRoot` |
| `INVALID_MODULE_ROOT` | `ModuleRoot` equals the repository root |
| `INVALID_MODULE_ID` | `ModuleId` does not match `^[a-z0-9][a-z0-9._-]*$` |
| `INVALID_WORKFLOW_VERSION` | `WorkflowVersion` does not match semantic version pattern |
| `INVALID_DLL_NAME` | `DllName` is empty, contains a path separator, or does not end in `.dll` |
| `CANONICAL_TEMPLATE_MISSING` | A required template file is absent from `templates/module-workflow/` |
| `GITIGNORE_MANAGED_BLOCK_INVALID` | `BEGIN` marker found but `END` marker missing/malformed |
| `BOOTSTRAP_CONFLICT` | Existing file content differs from generated output |
| `BOOTSTRAP_WRITE_FAILED` | Write failed mid-run; partial output rolled back |
