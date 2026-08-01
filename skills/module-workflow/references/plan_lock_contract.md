# Plan Lock Contract (Phase C Specification)

## Overview

Plan Lock is a deterministic gate that locks the plan contract files (`TASK.md`, `SCOPE.json`, `PLAN.md`) by computing their SHA-256 hashes after Codex plan review approval.

## Inputs & Output

- Input: Codex Plan Review JSON inside `<ModuleRoot>/.ai-workflow/history/`
- Output: `<ModuleRoot>/.ai-workflow/PLAN_LOCK.json`

## Canonical Hashing Contract

- `TASK.md` and `PLAN.md`: Strip UTF-8 BOM if present, normalize line endings (CRLF/CR -> LF), compute SHA-256 over raw UTF-8 bytes.
- `SCOPE.json` and `PLAN_LOCK.json`: Canonical JSON formatting (`json.dumps` with `ensure_ascii=False`, `sort_keys=True`, `separators=(",", ":")`), encode UTF-8, compute SHA-256.

## Preflight Checks

1. Git repo and working tree check (protected branch blocking: main/master/develop/release).
2. Required files exist: `MODULE.json`, `TASK.md`, `SCOPE.json`, `PLAN.md`.
3. Task, Scope, Plan files do not contain unfulfilled placeholders.
4. Scope `status == "READY"`, work branch matches current branch, base commit exists in Git.
5. Codex Plan Review JSON validated against `plan_review.schema.json`, `decision == "APPROVED"`, `reviewer == "codex"`, hashes match current files.

## Immutability & Lifecycle

- Initial creation: `status = CREATED`, `reason_code = PLAN_LOCK_CREATED`.
- Identical re-run: `status = NO_CHANGES`, `reason_code = PLAN_LOCK_ALREADY_CURRENT`.
- Conflicting existing lock: `status = FAILED`, `reason_code = PLAN_LOCK_CONFLICT`, exit code 3.
- Immutability: Existing `PLAN_LOCK.json` is never overwritten with different content. Any changes to task, scope, or plan require a plan amendment workflow in subsequent phases (`PLAN_AMENDMENT_REQUIRED`).

## Verify Mode

`python plan_lock.py verify --repository-root <path> --module-root <rel-path>`
Recomputes current file hashes and verifies branch, base commit, and plan lock SHA-256.
Output: `status = VERIFIED`, `reason_code = PLAN_LOCK_VERIFIED`, exit code 0.
On drift: exit code 5 with reason code `TASK_CHANGED`, `SCOPE_CHANGED`, `PLAN_CHANGED`, or `BRANCH_MISMATCH`.

## Reason Codes & Exit Codes

- Exit Code 0: `PLAN_LOCK_CREATED`, `PLAN_LOCK_ALREADY_CURRENT`, `PLAN_LOCK_DRY_RUN`, `PLAN_LOCK_VERIFIED`.
- Exit Code 2: `NOT_A_GIT_REPOSITORY`, `PROTECTED_BRANCH_BLOCKED`, `MODULE_WORKFLOW_MISSING`, `TASK_PLACEHOLDER`, `SCOPE_NOT_READY`, `BRANCH_MISMATCH`, `BASE_COMMIT_NOT_FOUND`, `PLAN_MISSING`, `PLAN_PLACEHOLDER`, `PLAN_REVIEW_INVALID`, `PLAN_REVIEW_NOT_APPROVED`, `PLAN_REVIEW_IDENTITY_MISMATCH`, `PLAN_REVIEW_HASH_MISMATCH`, `PLAN_REVIEW_PATH_INVALID`.
- Exit Code 3: `PLAN_LOCK_CONFLICT`.
- Exit Code 4: `PLAN_LOCK_WRITE_FAILED`.
- Exit Code 5: `PLAN_LOCK_REQUIRED`, `PLAN_LOCK_INVALID`, `TASK_CHANGED`, `SCOPE_CHANGED`, `PLAN_CHANGED`.

## Phase C Non-Goals

- Phase C does not run Codex or Antigravity.
- Phase C does not build DLLs or promote releases.
- Phase C does not modify production pipeline runtimes (`harness.py`, `review_pipeline.py`, `dual_agent_runtime.py`).
