#!/usr/bin/env python3
"""
evidence_gate.py — Module Evidence Gate (Phase C)

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

# Import shared module_contract_utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from module_contract_utils import (
    ContractValidationError,
    PathContainmentError,
    PlanLockVerificationError,
    atomic_write_json,
    canonical_json_bytes,
    compute_scope_snapshot,
    get_current_branch,
    hash_excerpt,
    hash_plan_file,
    hash_plan_lock_file,
    hash_scope_file,
    hash_task_file,
    is_path_allowed,
    list_tracked_files,
    load_json,
    normalize_rel_path,
    path_matches_pattern,
    print_result,
    resolve_contained_path,
    run_git,
    sha256_bytes,
    sha256_file,
    utc_now,
    validate_evidence_contract,
    validate_evidence_request_contract,
    validate_relative_path,
    validate_repository_root,
    verify_plan_lock_context,
)


def make_result(
    action: str,
    status: str,
    reason_code: str,
    repository_root: str = "",
    module_root: str = "",
    branch: str = "",
    task_id: str = "",
    plan_lock_sha256: str = "",
    source_snapshot_sha256: str = "",
    ready_to_implement: bool = False,
    files_checked: int = 0,
    symbols_checked: int = 0,
    diagnosis_sources_checked: int = 0,
    failures: Optional[List[str]] = None,
    dry_run: bool = False,
    files_created: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "action": action,
        "status": status,
        "reason_code": reason_code,
        "repository_root": repository_root,
        "module_root": module_root,
        "branch": branch,
        "task_id": task_id,
        "plan_lock_sha256": plan_lock_sha256,
        "source_snapshot_sha256": source_snapshot_sha256,
        "ready_to_implement": ready_to_implement,
        "files_checked": files_checked,
        "symbols_checked": symbols_checked,
        "diagnosis_sources_checked": diagnosis_sources_checked,
        "failures": failures or [],
        "dry_run": dry_run,
        "files_created": files_created or [],
    }


def fail(exit_code: int, result_dict: Dict[str, Any], diag_msg: str = "") -> None:
    if diag_msg:
        print(f"[ERROR] {result_dict.get('reason_code')}: {diag_msg}", file=sys.stderr)
    print_result(result_dict)
    sys.exit(exit_code)


def search_symbol_literal(
    repo_root: Path,
    tracked_files: List[str],
    symbol: str,
    file_patterns: Optional[List[str]],
    allowed_paths: List[str],
    forbidden_paths: List[str],
) -> List[str]:
    matches: List[str] = []
    norm_symbol = symbol.strip()
    if not norm_symbol:
        return matches

    for rel_path in tracked_files:
        norm_p = normalize_rel_path(rel_path)
        if not is_path_allowed(norm_p, allowed_paths, forbidden_paths):
            continue

        if file_patterns:
            matched_pattern = any(path_matches_pattern(norm_p, pat) for pat in file_patterns)
            if not matched_pattern:
                continue

        try:
            full_p = resolve_contained_path(repo_root, norm_p, must_exist=True)
        except PathContainmentError:
            continue

        # Skip binary files containing NUL
        try:
            with open(full_p, "rb") as f:
                header = f.read(1024)
                if b"\x00" in header:
                    continue

            with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                for idx, line in enumerate(lines, start=1):
                    if norm_symbol in line:
                        matches.append(f"{norm_p}:{idx}")
        except Exception:
            continue

    return matches


def evidence_collect(
    repo_root: Path,
    module_root_rel: str,
    request_file_rel: str,
    dry_run: bool,
) -> None:
    action = "collect"
    repo_root_str = str(repo_root)

    # Step 1. Full Plan Lock verification using shared helper
    try:
        (
            module_json,
            scope_data,
            lock_data,
            mod_dir,
            task_md_path,
            scope_json_path,
            plan_md_path,
            plan_lock_path,
            branch,
        ) = verify_plan_lock_context(repo_root, module_root_rel, require_unprotected_branch=True)
    except PlanLockVerificationError as err:
        mod_norm = normalize_rel_path(module_root_rel) if validate_relative_path(module_root_rel) else ""
        fail(
            err.exit_code,
            make_result(action, "FAILED", err.reason_code, repository_root=repo_root_str, module_root=mod_norm),
            err.message,
        )

    mod_norm = normalize_rel_path(module_root_rel)
    task_id = lock_data["task_id"]
    lock_sha = sha256_bytes(canonical_json_bytes(lock_data))

    # Step 2. Validate request file path and load evidence request
    try:
        sandbox_dir = mod_dir / ".sandbox"
        req_full_path = resolve_contained_path(
            repo_root,
            request_file_rel,
            must_exist=False,
            containment_root=sandbox_dir,
        )
    except PathContainmentError as e:
        fail(
            2,
            make_result(action, "FAILED", "EVIDENCE_REQUEST_PATH_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
            str(e),
        )

    if not req_full_path.exists():
        fail(
            2,
            make_result(action, "FAILED", "EVIDENCE_REQUEST_MISSING", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
            f"Request file missing: {request_file_rel}",
        )

    try:
        req_data = load_json(req_full_path)
    except Exception as e:
        fail(
            2,
            make_result(action, "FAILED", "EVIDENCE_REQUEST_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
            f"Failed to parse JSON: {e}",
        )

    try:
        validate_evidence_request_contract(req_data)
    except ContractValidationError as e:
        fail(
            2,
            make_result(action, "FAILED", "EVIDENCE_REQUEST_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
            str(e),
        )

    if req_data["task_id"] != task_id or req_data["module_id"] != module_json["module_id"]:
        fail(
            2,
            make_result(action, "FAILED", "EVIDENCE_IDENTITY_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
            "Identity mismatch in evidence_request.json",
        )

    allowed_paths = scope_data.get("allowed_paths", [])
    forbidden_paths = scope_data.get("forbidden_paths", [])

    # Step 3. Source dirty check
    res_status = run_git(["status", "--porcelain", "--untracked-files=all"], repo_root)
    if res_status.returncode == 0 and res_status.stdout.strip():
        for line in res_status.stdout.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            parts = clean_line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            changed_p = normalize_rel_path(parts[1])
            if mod_norm and (changed_p.startswith(mod_norm + "/") or changed_p == mod_norm):
                path_in_mod = changed_p[len(mod_norm) :].lstrip("/")
                if not (path_in_mod.startswith(".ai-workflow/") or path_in_mod.startswith(".sandbox/")):
                    fail(
                        2,
                        make_result(action, "FAILED", "SOURCE_CHANGED_BEFORE_EVIDENCE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha),
                        f"Source file changed before evidence: {changed_p}",
                    )

    tracked_files = list_tracked_files(repo_root)

    failures: List[str] = []

    # Gather Files to verify
    req_files_set: Set[str] = set()
    for f in scope_data.get("required_files", []):
        req_files_set.add(normalize_rel_path(f))
    for f in req_data.get("files_to_verify", []):
        req_files_set.add(normalize_rel_path(f))
    for ds in req_data.get("diagnosis_sources", []):
        if ds.get("path"):
            req_files_set.add(normalize_rel_path(ds["path"]))

    files_verified: List[Dict[str, Any]] = []
    for rel_f in sorted(req_files_set):
        if not is_path_allowed(rel_f, allowed_paths, forbidden_paths):
            failures.append(f"Scope violation for file: {rel_f}")
            files_verified.append({
                "path": rel_f,
                "exists": False,
                "tracked": False,
                "evidence_command": f"git ls-files --error-unmatch -- {rel_f}",
            })
            continue

        try:
            full_f = resolve_contained_path(repo_root, rel_f, must_exist=False)
        except PathContainmentError as e:
            failures.append(f"Containment violation for file: {rel_f}")
            files_verified.append({
                "path": rel_f,
                "exists": False,
                "tracked": False,
                "evidence_command": f"git ls-files --error-unmatch -- {rel_f}",
            })
            continue

        f_exists = full_f.exists() and full_f.is_file()
        f_tracked = rel_f in tracked_files

        if not f_exists:
            failures.append(f"Required file missing: {rel_f}")
        elif not f_tracked:
            failures.append(f"Required file untracked: {rel_f}")

        entry: Dict[str, Any] = {
            "path": rel_f,
            "exists": f_exists,
            "tracked": f_tracked,
            "evidence_command": f"git ls-files --error-unmatch -- {rel_f}",
        }
        if f_exists:
            entry["file_sha256"] = sha256_file(full_f)
        files_verified.append(entry)

    # Gather Symbols to verify
    symbols_verified: List[Dict[str, Any]] = []

    # Scope required_symbols
    for sym_str in scope_data.get("required_symbols", []):
        matches = search_symbol_literal(repo_root, tracked_files, sym_str, None, allowed_paths, forbidden_paths)
        if not matches:
            failures.append(f"Required scope symbol not found: {sym_str}")
        symbols_verified.append({
            "symbol": sym_str,
            "evidence_command": f"literal tracked-file search: {sym_str}",
            "matches": matches,
            "found_count": len(matches),
        })

    # Request symbols_to_verify
    for sym_obj in req_data.get("symbols_to_verify", []):
        sym_str = sym_obj.get("symbol", "")
        sym_paths = sym_obj.get("paths", [])
        matches = search_symbol_literal(repo_root, tracked_files, sym_str, sym_paths, allowed_paths, forbidden_paths)
        if not matches:
            failures.append(f"Required request symbol not found: {sym_str}")
        symbols_verified.append({
            "symbol": sym_str,
            "evidence_command": f"literal tracked-file search: {sym_str}",
            "matches": matches,
            "found_count": len(matches),
        })

    # Diagnosis and Diagnosis Sources
    diagnosis_text = req_data.get("diagnosis", "").strip()
    if len(diagnosis_text) < 20 or "replace" in diagnosis_text.lower() or "todo" in diagnosis_text.lower():
        failures.append("Diagnosis text is invalid or placeholder")

    diagnosis_sources_out: List[Dict[str, Any]] = []
    for ds in req_data.get("diagnosis_sources", []):
        ds_path = normalize_rel_path(ds.get("path", ""))
        line_start = ds.get("line_start", 0)
        line_end = ds.get("line_end", 0)
        reason = ds.get("reason", "").strip()

        if not is_path_allowed(ds_path, allowed_paths, forbidden_paths):
            failures.append(f"Diagnosis source scope violation: {ds_path}")
            continue

        try:
            ds_full = resolve_contained_path(repo_root, ds_path, must_exist=True)
        except PathContainmentError as e:
            failures.append(f"Diagnosis source containment violation: {ds_path}")
            continue

        if ds_path not in tracked_files:
            failures.append(f"Diagnosis source untracked: {ds_path}")
            continue

        try:
            f_sha, exc_sha = hash_excerpt(ds_full, line_start, line_end)
            diagnosis_sources_out.append({
                "path": ds_path,
                "line_start": line_start,
                "line_end": line_end,
                "reason": reason,
                "file_sha256": f_sha,
                "excerpt_sha256": exc_sha,
            })
        except Exception as exc:
            failures.append(f"Diagnosis source line range invalid for {ds_path}: {exc}")

    # Compute Source Snapshot
    src_snapshot_sha = compute_scope_snapshot(repo_root, mod_norm, allowed_paths, forbidden_paths)

    ready_to_implement = len(failures) == 0

    gen_at = utc_now()
    evidence_payload: Dict[str, Any] = {
        "schema_version": 1,
        "action": action,
        "status": "READY_FOR_IMPLEMENTATION" if ready_to_implement else "INSUFFICIENT_EVIDENCE",
        "reason_code": "EVIDENCE_READY" if ready_to_implement else "INSUFFICIENT_EVIDENCE",
        "repository_root": repo_root_str,
        "module_root": mod_norm,
        "branch": branch,
        "task_id": task_id,
        "base_commit": scope_data.get("base_commit", ""),
        "task_sha256": lock_data.get("task_sha256", ""),
        "scope_sha256": lock_data.get("scope_sha256", ""),
        "plan_sha256": lock_data.get("plan_sha256", ""),
        "plan_lock_sha256": lock_sha,
        "source_snapshot_sha256": src_snapshot_sha,
        "ready_to_implement": ready_to_implement,
        "files_checked": len(files_verified),
        "symbols_checked": len(symbols_verified),
        "diagnosis_sources_checked": len(diagnosis_sources_out),
        "files_verified": files_verified,
        "symbols_verified": symbols_verified,
        "diagnosis": diagnosis_text,
        "diagnosis_sources": diagnosis_sources_out,
        "failures": failures,
        "dry_run": dry_run,
        "files_created": [],
    }

    try:
        validate_evidence_contract(evidence_payload)
    except ContractValidationError as e:
        fail(2, make_result(action, "FAILED", "EVIDENCE_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha), str(e))

    ai_dir = mod_dir / ".ai-workflow"
    evidence_path = ai_dir / "EVIDENCE.json"
    evidence_rel = f"{mod_norm}/.ai-workflow/EVIDENCE.json"

    # Overwrite Policy Check
    if evidence_path.exists():
        try:
            old_evidence = load_json(evidence_path)
            validate_evidence_contract(old_evidence)
            old_ready = old_evidence.get("ready_to_implement", False)
            old_task = old_evidence.get("task_id", "")
            old_lock_sha = old_evidence.get("plan_lock_sha256", "")

            if old_ready:
                cmp_old = dict(old_evidence)
                cmp_old.pop("generated_at", None)
                cmp_new = dict(evidence_payload)
                cmp_new.pop("generated_at", None)

                if cmp_old == cmp_new:
                    res = make_result(
                        action,
                        "NO_CHANGES",
                        "EVIDENCE_ALREADY_CURRENT",
                        repository_root=repo_root_str,
                        module_root=mod_norm,
                        branch=branch,
                        task_id=task_id,
                        plan_lock_sha256=lock_sha,
                        source_snapshot_sha256=src_snapshot_sha,
                        ready_to_implement=True,
                        files_checked=len(files_verified),
                        symbols_checked=len(symbols_verified),
                        diagnosis_sources_checked=len(diagnosis_sources_out),
                        failures=[],
                        dry_run=dry_run,
                        files_created=[],
                    )
                    print_result(res)
                    sys.exit(0)
                else:
                    fail(3, make_result(action, "FAILED", "EVIDENCE_LOCKED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha), "Existing READY evidence is immutable")
            else:
                if old_task != task_id or old_lock_sha != lock_sha:
                    fail(3, make_result(action, "FAILED", "EVIDENCE_LOCKED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=lock_sha), "Existing EVIDENCE mismatch task or lock")
        except Exception:
            fail(3, make_result(action, "FAILED", "EVIDENCE_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if dry_run:
        status_str = "READY" if ready_to_implement else "INSUFFICIENT_EVIDENCE"
        code_str = "EVIDENCE_DRY_RUN" if ready_to_implement else "INSUFFICIENT_EVIDENCE"
        exit_code = 0 if ready_to_implement else 5
        res = make_result(
            action,
            status_str,
            code_str,
            repository_root=repo_root_str,
            module_root=mod_norm,
            branch=branch,
            task_id=task_id,
            plan_lock_sha256=lock_sha,
            source_snapshot_sha256=src_snapshot_sha,
            ready_to_implement=ready_to_implement,
            files_checked=len(files_verified),
            symbols_checked=len(symbols_verified),
            diagnosis_sources_checked=len(diagnosis_sources_out),
            failures=failures,
            dry_run=True,
            files_created=[],
        )
        print_result(res)
        sys.exit(exit_code)

    evidence_payload["files_created"] = [evidence_rel]

    try:
        atomic_write_json(evidence_path, evidence_payload)
    except Exception as exc:
        fail(4, make_result(action, "FAILED", "EVIDENCE_WRITE_FAILED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(exc))

    if not ready_to_implement:
        res = make_result(
            action,
            "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT_EVIDENCE",
            repository_root=repo_root_str,
            module_root=mod_norm,
            branch=branch,
            task_id=task_id,
            plan_lock_sha256=lock_sha,
            source_snapshot_sha256=src_snapshot_sha,
            ready_to_implement=False,
            files_checked=len(files_verified),
            symbols_checked=len(symbols_verified),
            diagnosis_sources_checked=len(diagnosis_sources_out),
            failures=failures,
            dry_run=False,
            files_created=[evidence_rel],
        )
        print_result(res)
        sys.exit(5)

    res = make_result(
        action,
        "READY",
        "EVIDENCE_READY",
        repository_root=repo_root_str,
        module_root=mod_norm,
        branch=branch,
        task_id=task_id,
        plan_lock_sha256=lock_sha,
        source_snapshot_sha256=src_snapshot_sha,
        ready_to_implement=True,
        files_checked=len(files_verified),
        symbols_checked=len(symbols_verified),
        diagnosis_sources_checked=len(diagnosis_sources_out),
        failures=[],
        dry_run=False,
        files_created=[evidence_rel],
    )
    print_result(res)
    sys.exit(0)


def evidence_verify(
    repo_root: Path,
    module_root_rel: str,
) -> None:
    action = "verify"
    repo_root_str = str(repo_root)

    try:
        (
            module_json,
            scope_data,
            lock_data,
            mod_dir,
            task_md_path,
            scope_json_path,
            plan_md_path,
            plan_lock_path,
            branch,
        ) = verify_plan_lock_context(repo_root, module_root_rel, require_unprotected_branch=True)
    except PlanLockVerificationError as err:
        mod_norm = normalize_rel_path(module_root_rel) if validate_relative_path(module_root_rel) else ""
        fail(
            err.exit_code,
            make_result(action, "FAILED", err.reason_code, repository_root=repo_root_str, module_root=mod_norm),
            err.message,
        )

    mod_norm = normalize_rel_path(module_root_rel)
    task_id = lock_data["task_id"]
    current_lock_sha = sha256_bytes(canonical_json_bytes(lock_data))

    ai_dir = mod_dir / ".ai-workflow"
    try:
        evidence_path = resolve_contained_path(repo_root, f"{mod_norm}/.ai-workflow/EVIDENCE.json", must_exist=True, containment_root=ai_dir)
    except PathContainmentError as e:
        fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(e))

    try:
        evidence_data = load_json(evidence_path)
    except Exception as e:
        fail(5, make_result(action, "FAILED", "EVIDENCE_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), f"Invalid EVIDENCE.json: {e}")

    try:
        validate_evidence_contract(evidence_data)
    except ContractValidationError as e:
        fail(5, make_result(action, "FAILED", "EVIDENCE_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(e))

    if not evidence_data.get("ready_to_implement"):
        fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Cross-field validation against current lock and module
    if (
        evidence_data.get("task_id") != task_id
        or evidence_data.get("module_id") != module_json["module_id"]
        or evidence_data.get("base_commit") != lock_data["base_commit"]
        or evidence_data.get("branch") != branch
        or evidence_data.get("task_sha256") != lock_data["task_sha256"]
        or evidence_data.get("scope_sha256") != lock_data["scope_sha256"]
        or evidence_data.get("plan_sha256") != lock_data["plan_sha256"]
        or evidence_data.get("plan_lock_sha256") != current_lock_sha
    ):
        fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), "Evidence content mismatch with current plan lock")

    allowed_paths = scope_data.get("allowed_paths", [])
    forbidden_paths = scope_data.get("forbidden_paths", [])

    # Verify Source Snapshot
    current_src_snapshot = compute_scope_snapshot(repo_root, mod_norm, allowed_paths, forbidden_paths)
    if current_src_snapshot != evidence_data.get("source_snapshot_sha256"):
        fail(5, make_result(action, "FAILED", "SOURCE_SNAPSHOT_CHANGED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id, plan_lock_sha256=current_lock_sha, source_snapshot_sha256=current_src_snapshot))

    tracked_files = list_tracked_files(repo_root)

    # Verify Files
    for f_item in evidence_data.get("files_verified", []):
        f_path = normalize_rel_path(f_item.get("path", ""))
        try:
            full_f = resolve_contained_path(repo_root, f_path, must_exist=True)
        except PathContainmentError:
            fail(5, make_result(action, "FAILED", "VERIFIED_FILE_CHANGED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

        if f_path not in tracked_files:
            fail(5, make_result(action, "FAILED", "VERIFIED_FILE_CHANGED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))
        if sha256_file(full_f) != f_item.get("file_sha256"):
            fail(5, make_result(action, "FAILED", "VERIFIED_FILE_CHANGED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Verify Diagnosis Sources
    for ds_item in evidence_data.get("diagnosis_sources", []):
        ds_path = normalize_rel_path(ds_item.get("path", ""))
        try:
            full_ds = resolve_contained_path(repo_root, ds_path, must_exist=True)
        except PathContainmentError:
            fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

        if ds_path not in tracked_files:
            fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

        try:
            curr_f_sha, curr_exc_sha = hash_excerpt(full_ds, ds_item.get("line_start", 1), ds_item.get("line_end", 1))
            if curr_f_sha != ds_item.get("file_sha256") or curr_exc_sha != ds_item.get("excerpt_sha256"):
                fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))
        except Exception:
            fail(5, make_result(action, "FAILED", "EVIDENCE_STALE", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Verify Symbols
    for sym_item in evidence_data.get("symbols_verified", []):
        sym_str = sym_item.get("symbol", "")
        matches = search_symbol_literal(repo_root, tracked_files, sym_str, None, allowed_paths, forbidden_paths)
        if not matches:
            fail(5, make_result(action, "FAILED", "REQUIRED_SYMBOL_NOT_FOUND", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    res = make_result(
        action,
        "VERIFIED",
        "EVIDENCE_VERIFIED",
        repository_root=repo_root_str,
        module_root=mod_norm,
        branch=branch,
        task_id=task_id,
        plan_lock_sha256=current_lock_sha,
        source_snapshot_sha256=current_src_snapshot,
        ready_to_implement=True,
        files_checked=len(evidence_data.get("files_verified", [])),
        symbols_checked=len(evidence_data.get("symbols_verified", [])),
        diagnosis_sources_checked=len(evidence_data.get("diagnosis_sources", [])),
        failures=[],
        dry_run=False,
        files_created=[],
    )
    print_result(res)
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence Gate CLI")
    parser.add_argument("action", choices=["collect", "verify"], help="Action to perform")
    parser.add_argument("--repository-root", required=True, help="Absolute path to repository root")
    parser.add_argument("--module-root", required=True, help="Repository-relative path to module root")
    parser.add_argument("--request-file", help="Repository-relative path to evidence request file")
    parser.add_argument("--dry-run", action="store_true", help="Perform preflight without writing output")

    args = parser.parse_args()

    repo_root = validate_repository_root(Path(args.repository_root), Path.cwd())
    if not repo_root:
        fail(2, make_result(args.action, "FAILED", "NOT_A_GIT_REPOSITORY"), "Invalid repository root or not a Git repository")

    if args.action == "collect":
        req_file = args.request_file or f"{normalize_rel_path(args.module_root)}/.sandbox/evidence_request.json"
        evidence_collect(repo_root, args.module_root, req_file, args.dry_run)
    elif args.action == "verify":
        evidence_verify(repo_root, args.module_root)


if __name__ == "__main__":
    main()
