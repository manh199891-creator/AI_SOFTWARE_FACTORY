#!/usr/bin/env python3
"""
plan_lock.py — Module Plan Lock Gate (Phase C)

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import shared module_contract_utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from module_contract_utils import (
    ContractValidationError,
    PathContainmentError,
    PlanLockVerificationError,
    PROTECTED_BRANCHES,
    atomic_write_json,
    canonical_json_bytes,
    get_current_branch,
    hash_plan_file,
    hash_scope_file,
    hash_task_file,
    load_json,
    normalize_rel_path,
    print_result,
    resolve_contained_path,
    run_git,
    sha256_bytes,
    validate_plan_lock_contract,
    validate_plan_review_contract,
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
    task_sha256: str = "",
    scope_sha256: str = "",
    plan_sha256: str = "",
    plan_lock_sha256: str = "",
    approval_review_run: str = "",
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
        "task_sha256": task_sha256,
        "scope_sha256": scope_sha256,
        "plan_sha256": plan_sha256,
        "plan_lock_sha256": plan_lock_sha256,
        "approval_review_run": approval_review_run,
        "dry_run": dry_run,
        "files_created": files_created or [],
    }


def fail(exit_code: int, result_dict: Dict[str, Any], diag_msg: str = "") -> None:
    if diag_msg:
        print(f"[ERROR] {result_dict.get('reason_code')}: {diag_msg}", file=sys.stderr)
    print_result(result_dict)
    sys.exit(exit_code)


def validate_task_md(task_path: Path, canonical_tmpl_path: Optional[Path] = None) -> Optional[str]:
    if not task_path.exists():
        return "TASK_MISSING"
    content = task_path.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return "TASK_PLACEHOLDER"
    if canonical_tmpl_path and canonical_tmpl_path.exists():
        tmpl_content = canonical_tmpl_path.read_text(encoding="utf-8", errors="replace").strip()
        if content == tmpl_content:
            return "TASK_PLACEHOLDER"

    markers = ["- Task ID:", "- Module:", "- Requested by:"]
    lines = content.splitlines()
    for m in markers:
        found = False
        for line in lines:
            if line.strip().startswith(m):
                val = line.split(m, 1)[1].strip()
                if val:
                    found = True
                    break
        if not found:
            return "TASK_PLACEHOLDER"
    return None


def validate_plan_md(plan_path: Path, canonical_tmpl_path: Optional[Path] = None) -> Optional[str]:
    if not plan_path.exists():
        return "PLAN_MISSING"
    content = plan_path.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return "PLAN_PLACEHOLDER"
    if canonical_tmpl_path and canonical_tmpl_path.exists():
        tmpl_content = canonical_tmpl_path.read_text(encoding="utf-8", errors="replace").strip()
        if content == tmpl_content:
            return "PLAN_PLACEHOLDER"

    req_sections = ["## Proposed changes", "## Test plan", "## Acceptance criteria"]
    for sec in req_sections:
        if sec not in content:
            return "PLAN_PLACEHOLDER"

    markers = ["- Task ID:", "- Module:", "- Base commit:", "- Work branch:"]
    lines = content.splitlines()
    for m in markers:
        found = False
        for line in lines:
            if line.strip().startswith(m):
                val = line.split(m, 1)[1].strip()
                if val:
                    found = True
                    break
        if not found:
            return "PLAN_PLACEHOLDER"
    return None


def plan_lock_create(
    repo_root: Path,
    module_root_rel: str,
    approval_file_rel: str,
    dry_run: bool,
) -> None:
    action = "create"
    repo_root_str = str(repo_root)

    try:
        mod_dir = resolve_contained_path(repo_root, module_root_rel, must_exist=True)
    except PathContainmentError as e:
        fail(2, make_result(action, "FAILED", "INVALID_MODULE_ROOT", repository_root=repo_root_str), str(e))

    mod_norm = normalize_rel_path(module_root_rel)

    try:
        history_dir = mod_dir / ".ai-workflow" / "history"
        approval_full_path = resolve_contained_path(
            repo_root,
            approval_file_rel,
            must_exist=True,
            containment_root=history_dir,
        )
    except PathContainmentError as e:
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_PATH_INVALID", repository_root=repo_root_str, module_root=mod_norm), str(e))

    branch = get_current_branch(repo_root)
    if not branch or branch in PROTECTED_BRANCHES:
        fail(2, make_result(action, "FAILED", "PROTECTED_BRANCH_BLOCKED", repository_root=repo_root_str, module_root=mod_norm, branch=branch), f"Branch '{branch}' is protected or empty")

    ai_dir = mod_dir / ".ai-workflow"
    module_json_path = ai_dir / "MODULE.json"
    task_md_path = ai_dir / "TASK.md"
    scope_json_path = ai_dir / "SCOPE.json"
    plan_md_path = ai_dir / "PLAN.md"

    if not (module_json_path.exists() and task_md_path.exists() and scope_json_path.exists() and plan_md_path.exists()):
        fail(2, make_result(action, "FAILED", "MODULE_WORKFLOW_MISSING", repository_root=repo_root_str, module_root=mod_norm, branch=branch), "Required module workflow files missing")

    try:
        module_data = load_json(module_json_path)
    except Exception:
        fail(2, make_result(action, "FAILED", "MODULE_CONTRACT_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch), "Invalid MODULE.json")

    if module_data.get("module_root") != mod_norm:
        fail(2, make_result(action, "FAILED", "MODULE_CONTRACT_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch), "MODULE.json module_root mismatch")

    # Validate Task
    tmpl_root = repo_root / "templates" / "module-workflow" / ".ai-workflow"
    task_err = validate_task_md(task_md_path, tmpl_root / "TASK.md")
    if task_err:
        fail(2, make_result(action, "FAILED", task_err, repository_root=repo_root_str, module_root=mod_norm, branch=branch))

    # Validate Scope
    try:
        scope_data = load_json(scope_json_path)
    except Exception:
        fail(2, make_result(action, "FAILED", "SCOPE_NOT_READY", repository_root=repo_root_str, module_root=mod_norm, branch=branch))

    if scope_data.get("module_id") != module_data.get("module_id"):
        fail(2, make_result(action, "FAILED", "SCOPE_TASK_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch))

    task_id = scope_data.get("task_id", "")
    if scope_data.get("status") != "READY" or task_id == "replace-task-id":
        fail(2, make_result(action, "FAILED", "SCOPE_NOT_READY", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if scope_data.get("work_branch") != branch or scope_data.get("work_branch") == scope_data.get("base_branch"):
        fail(2, make_result(action, "FAILED", "BRANCH_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if scope_data.get("direct_main_changes") is not False or scope_data.get("auto_merge") is not False or not scope_data.get("allowed_paths"):
        fail(2, make_result(action, "FAILED", "SCOPE_NOT_READY", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    base_commit = scope_data.get("base_commit", "")
    res_git = run_git(["cat-file", "-e", base_commit], repo_root)
    if res_git.returncode != 0:
        fail(2, make_result(action, "FAILED", "BASE_COMMIT_NOT_FOUND", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Validate Plan
    plan_err = validate_plan_md(plan_md_path, tmpl_root / "PLAN.md")
    if plan_err:
        fail(2, make_result(action, "FAILED", plan_err, repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Load & Validate Approval Contract
    try:
        approval_data = load_json(approval_full_path)
    except Exception as e:
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), f"Invalid JSON: {e}")

    try:
        validate_plan_review_contract(approval_data)
    except ContractValidationError as e:
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(e))

    if approval_data.get("decision") != "APPROVED":
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_NOT_APPROVED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if (
        approval_data.get("task_id") != task_id
        or approval_data.get("module_id") != module_data.get("module_id")
    ):
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_IDENTITY_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if approval_data.get("reviewed_branch") != branch:
        fail(2, make_result(action, "FAILED", "BRANCH_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if approval_data.get("base_commit") != base_commit:
        fail(2, make_result(action, "FAILED", "BASE_COMMIT_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    # Check approval commit is in Git history
    res_log = run_git(["log", "--format=%H"], repo_root)
    if res_log.returncode != 0:
        fail(2, make_result(action, "FAILED", "APPROVAL_NOT_IN_HISTORY", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    curr_task_sha = hash_task_file(task_md_path)
    curr_scope_sha = hash_scope_file(scope_json_path)
    curr_plan_sha = hash_plan_file(plan_md_path)

    if (
        approval_data.get("task_sha256") != curr_task_sha
        or approval_data.get("scope_sha256") != curr_scope_sha
        or approval_data.get("plan_sha256") != curr_plan_sha
    ):
        fail(2, make_result(action, "FAILED", "PLAN_REVIEW_HASH_MISMATCH", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    approval_file_sha = sha256_file(approval_full_path)
    approval_rel_norm = normalize_rel_path(approval_file_rel)

    # Construct PLAN_LOCK payload
    lock_payload = {
        "schema_version": 1,
        "module_id": module_data.get("module_id"),
        "branch": branch,
        "task_id": task_id,
        "base_commit": base_commit,
        "task_sha256": curr_task_sha,
        "scope_sha256": curr_scope_sha,
        "plan_sha256": curr_plan_sha,
        "approval_file": approval_rel_norm,
        "approval_sha256": approval_file_sha,
        "approval_commit": base_commit,
        "locked_by": "codex",
        "locked_at": approval_data.get("reviewed_at"),
        "plan_status": "APPROVED",
        "approved_by": "codex",
        "approved_review_run": approval_data.get("review_run_id"),
        "approved_at": approval_data.get("reviewed_at"),
        "amendment_count": 0,
    }

    try:
        validate_plan_lock_contract(lock_payload)
    except ContractValidationError as e:
        fail(2, make_result(action, "FAILED", "PLAN_LOCK_INVALID", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(e))

    lock_sha = sha256_bytes(canonical_json_bytes(lock_payload))
    plan_lock_path = ai_dir / "PLAN_LOCK.json"
    plan_lock_rel = f"{mod_norm}/.ai-workflow/PLAN_LOCK.json"

    # Immutability Check
    if plan_lock_path.exists():
        try:
            existing_payload = load_json(plan_lock_path)
            validate_plan_lock_contract(existing_payload)
            existing_sha = sha256_bytes(canonical_json_bytes(existing_payload))
            if existing_payload == lock_payload or existing_sha == lock_sha:
                res = make_result(
                    action,
                    "NO_CHANGES",
                    "PLAN_LOCK_ALREADY_CURRENT",
                    repository_root=repo_root_str,
                    module_root=mod_norm,
                    branch=branch,
                    task_id=task_id,
                    task_sha256=curr_task_sha,
                    scope_sha256=curr_scope_sha,
                    plan_sha256=curr_plan_sha,
                    plan_lock_sha256=lock_sha,
                    approval_review_run=approval_data.get("review_run_id", ""),
                    dry_run=dry_run,
                    files_created=[],
                )
                print_result(res)
                sys.exit(0)
            else:
                fail(
                    3,
                    make_result(
                        action,
                        "FAILED",
                        "PLAN_LOCK_CONFLICT",
                        repository_root=repo_root_str,
                        module_root=mod_norm,
                        branch=branch,
                        task_id=task_id,
                        task_sha256=curr_task_sha,
                        scope_sha256=curr_scope_sha,
                        plan_sha256=curr_plan_sha,
                        plan_lock_sha256=existing_sha,
                        approval_review_run=approval_data.get("review_run_id", ""),
                    ),
                    "Existing PLAN_LOCK.json conflicts with expected payload",
                )
        except Exception:
            fail(3, make_result(action, "FAILED", "PLAN_LOCK_CONFLICT", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id))

    if dry_run:
        res = make_result(
            action,
            "CREATED",
            "PLAN_LOCK_DRY_RUN",
            repository_root=repo_root_str,
            module_root=mod_norm,
            branch=branch,
            task_id=task_id,
            task_sha256=curr_task_sha,
            scope_sha256=curr_scope_sha,
            plan_sha256=curr_plan_sha,
            plan_lock_sha256=lock_sha,
            approval_review_run=approval_data.get("review_run_id", ""),
            dry_run=True,
            files_created=[],
        )
        print_result(res)
        sys.exit(0)

    try:
        atomic_write_json(plan_lock_path, lock_payload)
    except Exception as exc:
        fail(4, make_result(action, "FAILED", "PLAN_LOCK_WRITE_FAILED", repository_root=repo_root_str, module_root=mod_norm, branch=branch, task_id=task_id), str(exc))

    res = make_result(
        action,
        "CREATED",
        "PLAN_LOCK_CREATED",
        repository_root=repo_root_str,
        module_root=mod_norm,
        branch=branch,
        task_id=task_id,
        task_sha256=curr_task_sha,
        scope_sha256=curr_scope_sha,
        plan_sha256=curr_plan_sha,
        plan_lock_sha256=lock_sha,
        approval_review_run=approval_data.get("review_run_id", ""),
        dry_run=False,
        files_created=[plan_lock_rel],
    )
    print_result(res)
    sys.exit(0)


def plan_lock_verify(
    repo_root: Path,
    module_root_rel: str,
) -> None:
    action = "verify"
    repo_root_str = str(repo_root)

    try:
        (
            module_json,
            scope_json,
            lock_data,
            module_abs,
            task_path,
            scope_path,
            plan_path,
            lock_path,
            current_branch,
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

    res = make_result(
        action,
        "VERIFIED",
        "PLAN_LOCK_VERIFIED",
        repository_root=repo_root_str,
        module_root=mod_norm,
        branch=current_branch,
        task_id=task_id,
        task_sha256=lock_data["task_sha256"],
        scope_sha256=lock_data["scope_sha256"],
        plan_sha256=lock_data["plan_sha256"],
        plan_lock_sha256=lock_sha,
        approval_review_run=lock_data.get("approved_review_run", ""),
        dry_run=False,
        files_created=[],
    )
    print_result(res)
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan Lock CLI")
    parser.add_argument("action", choices=["create", "verify"], help="Action to perform")
    parser.add_argument("--repository-root", required=True, help="Absolute path to repository root")
    parser.add_argument("--module-root", required=True, help="Repository-relative path to module root")
    parser.add_argument("--approval-file", help="Repository-relative path to Codex approval file")
    parser.add_argument("--dry-run", action="store_true", help="Perform preflight without writing output")

    args = parser.parse_args()

    repo_root = validate_repository_root(Path(args.repository_root), Path.cwd())
    if not repo_root:
        fail(2, make_result(args.action, "FAILED", "NOT_A_GIT_REPOSITORY"), "Invalid repository root or not a Git repository")

    if args.action == "create":
        if not args.approval_file:
            fail(2, make_result("create", "FAILED", "PLAN_REVIEW_PATH_INVALID"), "--approval-file is required for create action")
        plan_lock_create(repo_root, args.module_root, args.approval_file, args.dry_run)
    elif args.action == "verify":
        plan_lock_verify(repo_root, args.module_root)


if __name__ == "__main__":
    main()
