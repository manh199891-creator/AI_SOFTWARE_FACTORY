# Module Workflow Bootstrap Contract

## Inputs

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `repository-root` | path | yes | Absolute path to Git working tree root |
| `module-root` | rel path | yes | Relative to repository root |
| `module-id` | string | yes | `^[a-z0-9][a-z0-9._-]*$` |
| `module-name` | string | yes | Human-readable |
| `project-file` | rel path | yes | Must be inside `module-root` |
| `platform` | enum | yes | `revit` \| `navisworks` \| `dotnet` |
| `dll-name` | string | no | Default: `<module-name>.dll` |
| `default-test-path` | rel path | repeatable | Added to `MODULE.json` |
| `shared-dependency` | rel path | repeatable | Added to `MODULE.json` |
| `workflow-version` | semver | no | Default: `1.0.0` |
| `dry-run` | flag | no | Preview mode |

## Preflight (all must pass before any write)

1. `repository-root` resolves to Git working tree.
2. Git root matches `repository-root` exactly.
3. Current branch is not empty and not protected (`main`, `master`, `develop`, `release`).
4. All rel paths are non-empty, contain no `..`, are not absolute (Windows or POSIX), are not UNC.
5. All rel paths resolve inside repository root.
6. `module-root` exists and is a directory.
7. `project-file` exists and is a file inside `module-root`.
8. `module-root` is not equal to repository root.
9. `module-id` matches regex.
10. `workflow-version` matches semver.
11. `dll-name` ends with `.dll`, no path separator, not empty.
12. All canonical templates exist under `templates/module-workflow/`.
13. `.gitignore` managed block (if present) is valid (both BEGIN and END markers present).
14. Conflict detection: all planner-owned targets are absent OR byte-identical to planned output.

## Generated tree

```
<module-root>/
├── .ai-workflow/
│   ├── MODULE.json       ← generated from inputs
│   ├── TASK.md           ← copied from canonical template
│   ├── SCOPE.json        ← generated placeholder (DRAFT)
│   ├── REVIEW.md         ← copied from canonical template
│   └── history/
│       └── .gitkeep
├── .sandbox/
│   ├── README.md         ← copied from canonical template
│   ├── bin/
│   ├── obj/
│   ├── addin/
│   ├── test-models/
│   ├── logs/
│   └── results/
└── .gitignore            ← managed block appended or verified
```

Not generated: `PLAN_LOCK.json`, `EVIDENCE.json`, `DELIVERY.json`, `.sandbox/manifest.json`, DLL, PDB.

## Ownership

The following files are **planner-owned** (conflict-checked before write):
- `.ai-workflow/MODULE.json`
- `.ai-workflow/TASK.md`
- `.ai-workflow/SCOPE.json`
- `.ai-workflow/REVIEW.md`
- `.sandbox/README.md`
- `.ai-workflow/history/.gitkeep`

## Conflict behaviour

- File absent → plan to create.
- File present, content matches → preserve (report in `files_preserved`).
- File present, content differs → `BOOTSTRAP_CONFLICT`, abort, no writes.

All conflicts are detected before the first write.

## Atomicity

1. Precompute all output.
2. Validate all targets.
3. Detect all conflicts.
4. Write each file via temp file + `os.replace()` (same filesystem).
5. Track every file/directory created in this run.
6. On any write failure: delete tracked new files, remove empty new directories, leave pre-existing content untouched.

Reason code on write failure: `BOOTSTRAP_WRITE_FAILED`.

## Idempotency

| Run | Status | Side effects |
|-----|--------|-------------|
| First | `CREATED` | Creates tree |
| Repeated (same input) | `NO_CHANGES` | None |

No timestamp changes, no `.gitignore` duplication, exit code `0` both runs.

## Dry run

Runs full preflight + conflict detection. Reports planned files/dirs. Writes nothing. Exit code `0`.

## Output schema

```json
{
  "schema_version": 1,
  "status": "CREATED | NO_CHANGES | DRY_RUN | FAILED",
  "reason_code": "<CODE>",
  "repository_root": "",
  "module_root": "",
  "branch": "",
  "dry_run": false,
  "files_created": [],
  "files_preserved": [],
  "directories_created": [],
  "gitignore_updated": false,
  "generated_contracts": []
}
```

## Exit codes

| Code | Condition |
|------|-----------|
| 0 | `CREATED`, `NO_CHANGES`, `DRY_RUN` |
| 2 | Input / context validation failure |
| 3 | Conflict |
| 4 | Write / rollback failure |

## Non-goals (Phase B)

- Does not run agents.
- Does not create task branches.
- Does not build or copy DLLs.
- Does not run Revit or Navisworks.
- Does not create `PLAN_LOCK.json`, `EVIDENCE.json`, `DELIVERY.json`, or `manifest.json`.
- Does not sync or deploy to production modules.
- Does not add third-party Python packages.
- Does not modify the production runtime manifest.
