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
| `PLAN.md` | ChatGPT/Codex planner | Không |
| `PLAN_LOCK.json` | Pipeline gate | Không |
| `EVIDENCE.json` | Anti thông qua preflight | Có kiểm soát |
| `DELIVERY.json` | Delivery script | Không viết tay |
| `REVIEW.md` | ChatGPT/Codex reviewer | Không |
| `.sandbox/evidence_request.json` | Anti temporary request | Có |
| `.sandbox/manifest.json` | Sandbox script | Không viết tay |

## 6. Required files
- `schemas/module-workflow/*.schema.json`
- `templates/module-workflow/.ai-workflow/*`
- `tests/test_module_workflow_schemas.py`
- `tests/test_module_plan_lock.py`
- `tests/test_module_evidence_gate.py`

## 7. Generated files
Generated files include `PLAN_LOCK.json`, `EVIDENCE.json`, `DELIVERY.json`, and `.sandbox/manifest.json`.

## 8. Source-of-truth rules
- `pipeline_status.json` = runtime status authority
- `.ai-workflow` files = task contract và audit evidence
- Git remote SHA = delivery truth
- `PLAN_LOCK.json` = approved-plan identity
- `EVIDENCE.json` = pre-edit audit evidence
- sandbox manifest = DLL build identity

No module-local file replaces `pipeline_status.json`.

## 9. Plan file
`PLAN.md` is a planner-owned markdown file detailing the implementation plan, identity, verified context, proposed changes, expected files, test plan, acceptance criteria, and rollback risks.

## 10. Plan review contract
Codex plan review produces a machine-readable JSON artifact in `.ai-workflow/history/` validating `plan_review.schema.json`. It captures `decision` ("APPROVED"), `reviewer` ("codex"), branch, base commit, and the exact SHA-256 hashes of `TASK.md`, `SCOPE.json`, and `PLAN.md`.

## 11. Plan lock creation
`plan_lock.py create` validates the Codex approval against current files. If all preflight checks and hash matches pass, it generates `.ai-workflow/PLAN_LOCK.json`.

## 12. Canonical hashing
- **Markdown files (`TASK.md`, `PLAN.md`)**: Remove UTF-8 BOM if present, normalize line endings to LF (`\n`), compute SHA-256 over raw UTF-8 bytes.
- **JSON files (`SCOPE.json`, `PLAN_LOCK.json`)**: Sort keys, compact separators (`:`, `,`), encode UTF-8, compute SHA-256. Formatting changes do not affect the SHA-256.

## 13. Plan lock immutability
Existing `PLAN_LOCK.json` is immutable. Overwriting with different content triggers `PLAN_LOCK_CONFLICT` (exit code 3). Any changes to task, scope, or plan require a plan amendment workflow in subsequent phases (`PLAN_AMENDMENT_REQUIRED`).

## 14. Evidence request
Antigravity prepares `.sandbox/evidence_request.json` specifying `files_to_verify`, `symbols_to_verify`, `diagnosis`, and `diagnosis_sources`. Request paths must be relative and inside `.sandbox/`.

## 15. Evidence collection
`evidence_gate.py collect` validates that:
- `PLAN_LOCK.json` is valid and current.
- Current branch matches scope and lock.
- Source files are untouched before evidence collection (`SOURCE_CHANGED_BEFORE_EVIDENCE`).
- Verified files exist, are tracked by Git, and within allowed scope.
- Verified symbols match literally in tracked files.
- Diagnosis sources exist, are tracked, and line excerpt SHA-256 hashes match.
- Source snapshot SHA-256 is calculated deterministically across all tracked files in allowed scope (`sorted_path\0file_sha256\n`).

## 16. Evidence verification
`evidence_gate.py verify` checks that `EVIDENCE.json` exists, `ready_to_implement == true`, source files have not drifted, line excerpts match, symbols exist, and plan lock remains valid. Returns exit code 0 (`EVIDENCE_VERIFIED`) or exit code 5 (`EVIDENCE_STALE` / `SOURCE_SNAPSHOT_CHANGED`).

## 17. Effective module lifecycle
```text
DRAFT
→ READY
→ PLAN_REVIEW_APPROVED
→ PLAN_LOCKED
→ EVIDENCE_READY
→ READY_FOR_IMPLEMENTATION
```

## 18. Scope exception behavior
Changes outside allowed paths are strictly forbidden.

## 19. Schema versioning
Current schema version is 1.

## 20. Git ignore policy
Do not commit DLL, PDB, obj, log, or test results inside `.sandbox/`.

## 21. Phase C non-goals
- Standalone gate execution only.
- Does not auto-invoke Codex or Antigravity runtime routines.
- Does not modify add-in source code or build DLLs.
- Does not modify production pipeline runtime scripts (`harness.py`, `review_pipeline.py`, `dual_agent_runtime.py`, `pipeline_status.json`).

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
| `.ai-workflow/PLAN.md` | Copied from canonical template |
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
