# Evidence Gate Contract (Phase C Specification)

## Overview

Evidence Gate collects and verifies evidence before Antigravity is allowed to make code changes.

## Request Contract

- Location: `<ModuleRoot>/.sandbox/evidence_request.json`
- Prepared by Antigravity in sandbox. Must not use absolute paths or path traversal (`..`).

## Preflight Checks

1. Valid `PLAN_LOCK.json` must exist and match current task, scope, plan, branch, and base commit.
2. Current branch must match `SCOPE.json`.
3. Source files must not be modified before evidence collection (`SOURCE_CHANGED_BEFORE_EVIDENCE`).

## Verification Engine

1. **File Verification**: Union of `SCOPE.required_files`, `request.files_to_verify`, and `diagnosis_sources[].path`. Each path must be within allowed paths, not in forbidden paths, exist, be a regular file, and be Git-tracked. Computes raw file SHA-256.
2. **Symbol Verification**: Union of `SCOPE.required_symbols` (literal search across allowed tracked files) and `request.symbols_to_verify` (literal search across specified paths). Search is case-sensitive, literal, no regex execution.
3. **Diagnosis & Excerpt Verification**: Diagnosis string length >= 20. Each diagnosis source line range (line_start -> line_end) is hashed (`excerpt_sha256`) after line ending normalization to LF.
4. **Source Snapshot**: SHA-256 calculated over all tracked files in allowed scope (`sorted_path\0file_sha256\n`).

## Ready Criteria & Overwrite Policy

- `ready_to_implement = true` only when all files exist, are tracked, in-scope, all symbols matched, all diagnosis sources valid, and source snapshot generated cleanly.
- If missing evidence: `ready_to_implement = false` (written to file for diagnostic feedback), script exits with code 5 (`INSUFFICIENT_EVIDENCE`).
- Overwrite Policy:
  - Non-ready evidence (`ready_to_implement == false`) can be replaced.
  - Ready evidence (`ready_to_implement == true`) is immutable. Re-collecting with identical payload returns `NO_CHANGES` (`EVIDENCE_ALREADY_CURRENT`, exit code 0). Attempting to overwrite ready evidence with different content fails with `EVIDENCE_LOCKED` (exit code 3).

## Verify Mode

`python evidence_gate.py verify --repository-root <path> --module-root <rel-path>`
Verifies:
- `EVIDENCE.json` exists and `ready_to_implement == true`.
- Plan lock remains valid.
- Source snapshot matches current state.
- All verified files, line excerpts, and symbols remain unchanged.
Output: `status = VERIFIED`, `reason_code = EVIDENCE_VERIFIED`, exit code 0.
On any drift: exit code 5 (`EVIDENCE_STALE` or `SOURCE_SNAPSHOT_CHANGED`).

## Reason Codes & Exit Codes

- Exit Code 0: `EVIDENCE_READY`, `EVIDENCE_ALREADY_CURRENT`, `EVIDENCE_DRY_RUN`, `EVIDENCE_VERIFIED`.
- Exit Code 2: `PLAN_LOCK_REQUIRED`, `PLAN_LOCK_STALE`, `EVIDENCE_REQUEST_MISSING`, `EVIDENCE_REQUEST_INVALID`, `EVIDENCE_REQUEST_PATH_INVALID`, `EVIDENCE_IDENTITY_MISMATCH`, `SOURCE_CHANGED_BEFORE_EVIDENCE`, `EVIDENCE_SCOPE_VIOLATION`.
- Exit Code 3: `EVIDENCE_LOCKED`, `EVIDENCE_INVALID`.
- Exit Code 4: `EVIDENCE_WRITE_FAILED`.
- Exit Code 5: `INSUFFICIENT_EVIDENCE`, `REQUIRED_FILE_MISSING`, `REQUIRED_FILE_UNTRACKED`, `REQUIRED_SYMBOL_NOT_FOUND`, `DIAGNOSIS_SOURCE_INVALID`, `EVIDENCE_STALE`, `SOURCE_SNAPSHOT_CHANGED`.

## Phase C Non-Goals

- Standalone gate execution only. Does not invoke Codex or Antigravity runtime routines.
