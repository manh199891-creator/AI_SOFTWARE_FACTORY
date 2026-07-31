# Module Workflow Contract

## 1. Purpose
Define the canonical workflow and data structures for module-level AI automation in Revit and Navisworks add-ins.

## 2. Overall architecture
```text
AI_SOFTWARE_FACTORY
    ↓ cung cấp schema, template và skill
RevitAddinSolution / NavisAddinSolution
    └── src/<Module>/
        ├── .ai-workflow/
        ├── .sandbox/
        ├── bin/
        ├── obj/
        ├── source
        └── tests
```

## 3. Module workflow tree
Each module manages its own task state and automation data within `.ai-workflow/`.

## 4. Sandbox DLL lane
`.sandbox` is the test lane for a module DLL. It is not a copy of source code. DLL, PDB, obj, log, or test output inside it must not be committed. The Sandbox DLL cannot be promoted until the review is approved.

## 5. File ownership
| File | Owner | Antigravity được sửa |
|---|---|---:|
| `MODULE.json` | Factory/template | Không |
| `TASK.md` | ChatGPT/Codex planner | Không |
| `SCOPE.json` | ChatGPT/Codex planner | Không |
| `PLAN_LOCK.json` | Pipeline | Không |
| `EVIDENCE.json` | Anti thông qua preflight | Có kiểm soát |
| `DELIVERY.json` | Delivery script | Không viết tay |
| `REVIEW.md` | ChatGPT/Codex reviewer | Không |
| `.sandbox/manifest.json` | Sandbox script | Không viết tay |

## 6. Required files
- schemas/module-workflow/*.schema.json
- templates/module-workflow/.ai-workflow/*
- tests/test_module_workflow_schemas.py

## 7. Generated files
Generated files include `PLAN_LOCK.json`, `EVIDENCE.json`, `DELIVERY.json`, and `.sandbox/manifest.json`.

## 8. Source-of-truth rules
- pipeline_status.json = runtime status authority
- .ai-workflow files = task contract và audit evidence
- Git remote SHA = delivery truth
- PLAN_LOCK.json = approved-plan identity
- sandbox manifest = DLL build identity

## 9. Plan-lock contract
Task, scope, and plan must be locked with SHA-256 hashes by the Codex approval step before execution begins.

## 10. Evidence-before-edit contract
Anti must prove that all required files and symbols exist and match expected patterns before making any changes.

## 11. Delivery and remote SHA contract
Delivery JSON must guarantee local SHA equals remote SHA for readiness.

## 12. Review commit binding
Review must specify the commit it reviewed to prevent drift.

## 13. State lifecycle
DRAFT -> READY -> LOCKED -> READY_FOR_REVIEW -> APPROVED/FAILED.

## 14. Scope exception behavior
Changes outside allowed paths are strictly forbidden.

## 15. Schema versioning
Current schema version is 1.

## 16. Git ignore policy
Do not commit DLL, PDB, obj, log, or test results inside `.sandbox/`.

## 17. What Phase A does not implement
No implementation of runners, scripts, or production pipeline hooks.

## 18. Example DrawBeams lifecycle
See `examples/module-workflow/Antigravity.DrawBeams/`.

---

## Module bootstrap

`module-init` initialises the canonical workflow and sandbox skeleton inside an **existing** module directory. It is invoked once per module during onboarding.

### Command example

```powershell
# PowerShell wrapper
.\skills\module-workflow\scripts\module_init.ps1 `
  -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
  -ModuleRoot     "src\Antigravity.DrawBeams" `
  -ModuleId       "antigravity.drawbeams" `
  -ModuleName     "Antigravity.DrawBeams" `
  -ProjectFile    "src\Antigravity.DrawBeams\Antigravity.DrawBeams.csproj" `
  -Platform       "revit"

# Python directly
python skills/module-workflow/scripts/module_bootstrap.py \
  --repository-root "E:\AI_SOFTWARE_FACTORY" \
  --module-root     "src/Antigravity.DrawBeams" \
  --module-id       "antigravity.drawbeams" \
  --module-name     "Antigravity.DrawBeams" \
  --project-file    "src/Antigravity.DrawBeams/Antigravity.DrawBeams.csproj" \
  --platform        "revit" \
  [--dry-run]
```

### Generated files

| File | Source |
|------|--------|
| `.ai-workflow/MODULE.json` | Generated from CLI inputs |
| `.ai-workflow/SCOPE.json` | Generated placeholder — status `DRAFT` |
| `.ai-workflow/TASK.md` | Copied from canonical template |
| `.ai-workflow/REVIEW.md` | Copied from canonical template |
| `.ai-workflow/history/.gitkeep` | Empty tracked placeholder |
| `.sandbox/README.md` | Copied from canonical template |

### Generated directories

```
.ai-workflow/history/
.sandbox/bin/
.sandbox/obj/
.sandbox/addin/
.sandbox/test-models/
.sandbox/logs/
.sandbox/results/
```

### Protected branch rule

Bootstrap refuses to run when the current Git branch is `main`, `master`, `develop`, or `release`. All workflow initialisation must happen on a task branch.

### Conflict policy

If any planner-owned file already exists with different content, the tool exits with reason code `BOOTSTRAP_CONFLICT` (exit 3) **before writing any file**. No partial state is left.

### Idempotency

Running `module-init` a second time with the same inputs returns `NO_CHANGES` (exit 0). No files are modified, no timestamps change, and no `.gitignore` block is duplicated.

### `.gitignore` managed block

The tool appends exactly one managed block to `<module-root>/.gitignore`:

```gitignore
# BEGIN AI MODULE WORKFLOW
bin/
obj/
.sandbox/*
!.sandbox/README.md
# END AI MODULE WORKFLOW
```

Existing `.gitignore` content is preserved. The block is never duplicated on rerun.

### Phase B non-goals

- Does **not** run Antigravity or Codex.
- Does **not** create task branches.
- Does **not** build or copy DLLs.
- Does **not** create `PLAN_LOCK.json`, `EVIDENCE.json`, `DELIVERY.json`, or `.sandbox/manifest.json`.
- Does **not** sync to production add-in solution.
- Does **not** overwrite a differing existing workflow contract.
- Does **not** add third-party Python packages.
- Does **not** touch the production runtime manifest.
