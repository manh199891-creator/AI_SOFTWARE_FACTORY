#!/usr/bin/env python3
"""
module_contract_utils.py — Shared Utilities for Module Workflow Contracts (Phase C)

Standard library only.
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set


# ---------------------------------------------------------------------------
# Exceptions & Constants
# ---------------------------------------------------------------------------

class ContractValidationError(ValueError):
    """Raised when a contract payload violates its schema/specification."""
    pass


class PathContainmentError(ValueError):
    """Raised when a relative path escapes its repository or containment root."""
    pass


class PlanLockVerificationError(Exception):
    """Raised when plan lock verification fails."""
    def __init__(self, reason_code: str, message: str, exit_code: int = 5):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.exit_code = exit_code


PROTECTED_BRANCHES = {"main", "master", "develop", "release"}
ISO_8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
SHA256_LOWER_RE = re.compile(r"^[a-f0-9]{64}$")
GIT_SHA_LOWER_RE = re.compile(r"^[a-f0-9]{40}$")
MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def parse_iso_datetime(dt_str: str) -> datetime.datetime:
    if not isinstance(dt_str, str) or not ISO_8601_RE.match(dt_str):
        raise ContractValidationError(f"Invalid ISO-8601 datetime format: {dt_str!r}")
    try:
        norm_str = dt_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(norm_str)
    except ValueError as e:
        raise ContractValidationError(f"Invalid ISO-8601 datetime value: {dt_str!r} ({e})")


# ---------------------------------------------------------------------------
# Atomic IO & JSON
# ---------------------------------------------------------------------------

def atomic_write_text(target_path: Path, content: str) -> None:
    target_path = Path(target_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path_str = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".tmp_{target_path.name}_",
    )
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        temp_path.replace(target_path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_bytes(target_path: Path, content_bytes: bytes) -> None:
    target_path = Path(target_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path_str = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".tmp_{target_path.name}_",
    )
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(content_bytes)
        temp_path.replace(target_path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(target_path: Path, data: Any, indent: int = 2) -> None:
    content = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    atomic_write_text(target_path, content)


def load_json(filepath: Path) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Git Context Helpers
# ---------------------------------------------------------------------------

def run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def get_git_root(cwd: Path) -> Optional[Path]:
    res = run_git(["rev-parse", "--show-toplevel"], cwd)
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip()).resolve()
    return None


def get_current_branch(cwd: Path) -> str:
    res = run_git(["branch", "--show-current"], cwd)
    if res.returncode == 0:
        return res.stdout.strip()
    return ""


def validate_repository_root(supplied_root: Path, cwd: Path) -> Optional[Path]:
    supplied_resolved = Path(supplied_root).resolve()
    if not supplied_resolved.exists() or not supplied_resolved.is_dir():
        return None
    git_root = get_git_root(supplied_resolved)
    if git_root is None or git_root != supplied_resolved:
        return None
    return git_root


# ---------------------------------------------------------------------------
# Path Validation, Relative Normalization & Containment
# ---------------------------------------------------------------------------

def validate_relative_path(path_str: str) -> bool:
    if not path_str or not isinstance(path_str, str):
        return False
    if "\x00" in path_str:
        return False
    norm = path_str.replace("\\", "/")
    if norm.startswith("/") or ":" in norm or ".." in norm.split("/"):
        return False
    return True



def normalize_rel_path(path_str: str) -> str:
    norm = path_str.replace("\\", "/").strip("/")
    parts = [p for p in norm.split("/") if p and p != "."]
    return "/".join(parts)


def resolve_contained_path(
    repo_root: Path,
    relative_path: str,
    *,
    must_exist: bool = False,
    containment_root: Path | None = None,
) -> Path:
    if not relative_path or not isinstance(relative_path, str):
        raise PathContainmentError(f"Invalid relative path string: {relative_path!r}")

    if not validate_relative_path(relative_path):
        raise PathContainmentError(f"Invalid relative path syntax: {relative_path!r}")

    norm = relative_path.replace("\\", "/")
    repo_abs = Path(repo_root).resolve()
    target = repo_abs / norm

    if must_exist and not target.exists():
        raise PathContainmentError(f"Path does not exist: {relative_path!r} ({target})")

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            real_target = os.readlink(target)
            resolved_link = (target.parent / real_target).resolve()
            try:
                resolved_link.relative_to(repo_abs)
            except ValueError:
                raise PathContainmentError(f"Symlink escapes repository root: {relative_path!r} -> {resolved_link}")
        resolved_target = target.resolve()
    else:
        parent = target.parent
        if parent.exists():
            resolved_target = parent.resolve() / target.name
        else:
            resolved_target = target.resolve()

    try:
        resolved_target.relative_to(repo_abs)
    except ValueError:
        raise PathContainmentError(f"Path escapes repository root: {relative_path!r} -> {resolved_target}")

    if containment_root is not None:
        containment_abs = Path(containment_root).resolve()
        try:
            resolved_target.relative_to(containment_abs)
        except ValueError:
            raise PathContainmentError(
                f"Path escapes containment root '{containment_abs}': {relative_path!r} -> {resolved_target}"
            )

    return resolved_target


def path_matches_pattern(rel_path: str, glob_pattern: str) -> bool:
    norm_path = normalize_rel_path(rel_path)
    norm_pattern = normalize_rel_path(glob_pattern)

    res = "^"
    i = 0
    n = len(norm_pattern)
    while i < n:
        if norm_pattern[i : i + 3] == "**/":
            res += "(?:.*/)?"
            i += 3
        elif norm_pattern[i : i + 3] == "/**":
            res += "(?:/.*)?"
            i += 3
        elif norm_pattern[i : i + 2] == "**":
            res += ".*"
            i += 2
        elif norm_pattern[i] == "*":
            res += "[^/]*"
            i += 1
        elif norm_pattern[i] == "?":
            res += "[^/]"
            i += 1
        else:
            res += re.escape(norm_pattern[i])
            i += 1
    res += "$"

    return bool(re.match(res, norm_path)) or fnmatch.fnmatch(norm_path, norm_pattern)


def is_path_allowed(rel_path: str, allowed_paths: List[str], forbidden_paths: List[str]) -> bool:
    norm_path = normalize_rel_path(rel_path)

    for f_pat in forbidden_paths:
        if path_matches_pattern(norm_path, f_pat):
            return False

    for a_pat in allowed_paths:
        if path_matches_pattern(norm_path, a_pat):
            return True
    return False


# ---------------------------------------------------------------------------
# Hashing & Canonicalization
# ---------------------------------------------------------------------------

def canonical_text_bytes(text_str: str) -> bytes:
    if text_str.startswith("\ufeff"):
        text_str = text_str[1:]
    text_str = text_str.replace("\r\n", "\n").replace("\r", "\n")
    return text_str.encode("utf-8")


def canonical_json_bytes(payload: Any) -> bytes:
    canonical_str = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return canonical_str.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_task_file(filepath: Path) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return sha256_bytes(canonical_text_bytes(content))


def hash_scope_file(filepath: Path) -> str:
    payload = load_json(filepath)
    return sha256_bytes(canonical_json_bytes(payload))


def hash_plan_file(filepath: Path) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return sha256_bytes(canonical_text_bytes(content))


def hash_plan_lock_file(filepath: Path) -> str:
    payload = load_json(filepath)
    return sha256_bytes(canonical_json_bytes(payload))


def hash_excerpt(filepath: Path, line_start: int, line_end: int) -> Tuple[str, str]:
    file_sha = sha256_file(filepath)
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if content.startswith("\ufeff"):
        content = content[1:]
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")

    if line_start < 1 or line_end < line_start or line_end > len(lines):
        raise ValueError(f"Line range {line_start}-{line_end} out of range for file with {len(lines)} lines")

    excerpt_lines = lines[line_start - 1 : line_end]
    excerpt_str = "\n".join(excerpt_lines)
    excerpt_bytes = excerpt_str.encode("utf-8")
    excerpt_sha = sha256_bytes(excerpt_bytes)
    return file_sha, excerpt_sha


# ---------------------------------------------------------------------------
# Tracked Files & Source Snapshot
# ---------------------------------------------------------------------------

def list_tracked_files(repo_root: Path) -> List[str]:
    res = run_git(["ls-files"], repo_root)
    if res.returncode != 0:
        return []
    raw = res.stdout
    lines = [line.strip().replace("\\", "/") for line in raw.splitlines() if line.strip()]
    return lines


def compute_scope_snapshot(
    repo_root: Path,
    module_root_rel: str,
    allowed_paths: List[str],
    forbidden_paths: List[str],
) -> str:
    all_tracked = list_tracked_files(repo_root)
    snapshot_items: List[Tuple[str, str]] = []

    repo_abs = repo_root.resolve()

    for rel_path in all_tracked:
        norm_path = normalize_rel_path(rel_path)

        parts = norm_path.split("/")
        if ".ai-workflow" in parts or ".sandbox" in parts:
            continue

        if is_path_allowed(norm_path, allowed_paths, forbidden_paths):
            full_path = repo_root / norm_path
            if full_path.is_symlink():
                real_target = os.readlink(full_path)
                resolved_link = (full_path.parent / real_target).resolve()
                try:
                    resolved_link.relative_to(repo_abs)
                except ValueError:
                    raise PathContainmentError(f"Symlink in scope snapshot escapes repository: {norm_path!r} -> {resolved_link}")
            else:
                try:
                    full_path.resolve().relative_to(repo_abs)
                except ValueError:
                    raise PathContainmentError(f"File in scope snapshot escapes repository: {norm_path!r}")

            if full_path.exists() and full_path.is_file():
                f_sha = sha256_file(full_path)
                snapshot_items.append((norm_path, f_sha))

    snapshot_items.sort(key=lambda x: x[0])

    stream = bytearray()
    for rel_p, f_sha in snapshot_items:
        stream.extend(rel_p.encode("utf-8"))
        stream.append(0)  # NUL
        stream.extend(f_sha.encode("utf-8"))
        stream.append(10)  # LF

    return sha256_bytes(bytes(stream))



# ---------------------------------------------------------------------------
# Contract Runtime Validators (Pure Python)
# ---------------------------------------------------------------------------

def validate_module_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("MODULE payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "module_id", "module_name", "module_root", "project_file",
        "platform", "workflow_root", "sandbox_root", "sandbox_dll",
        "stable_output_root", "default_test_paths", "shared_dependencies", "workflow_version"
    }
    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"MODULE payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"MODULE payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("MODULE schema_version must be integer 1.")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"MODULE module_id invalid: {payload['module_id']!r}")
    if not isinstance(payload["module_root"], str) or not validate_relative_path(payload["module_root"]):
        raise ContractValidationError(f"MODULE module_root invalid: {payload['module_root']!r}")
    if not isinstance(payload["module_name"], str) or not payload["module_name"].strip():
        raise ContractValidationError("MODULE module_name must be non-empty string.")
    if not isinstance(payload["project_file"], str) or not validate_relative_path(payload["project_file"]):
        raise ContractValidationError(f"MODULE project_file invalid: {payload['project_file']!r}")
    if payload["platform"] not in ("revit", "navisworks", "dotnet"):
        raise ContractValidationError(f"MODULE platform invalid: {payload['platform']!r}")
    if not isinstance(payload["workflow_root"], str) or not validate_relative_path(payload["workflow_root"]):
        raise ContractValidationError(f"MODULE workflow_root invalid: {payload['workflow_root']!r}")
    if not isinstance(payload["sandbox_root"], str) or not validate_relative_path(payload["sandbox_root"]):
        raise ContractValidationError(f"MODULE sandbox_root invalid: {payload['sandbox_root']!r}")
    if not isinstance(payload["sandbox_dll"], str) or not validate_relative_path(payload["sandbox_dll"]):
        raise ContractValidationError(f"MODULE sandbox_dll invalid: {payload['sandbox_dll']!r}")
    if not isinstance(payload["stable_output_root"], str) or not validate_relative_path(payload["stable_output_root"]):
        raise ContractValidationError(f"MODULE stable_output_root invalid: {payload['stable_output_root']!r}")
    if not isinstance(payload["default_test_paths"], list):
        raise ContractValidationError("MODULE default_test_paths must be an array.")
    for p in payload["default_test_paths"]:
        if not isinstance(p, str) or not validate_relative_path(p):
            raise ContractValidationError(f"MODULE default_test_paths item invalid: {p!r}")
    if not isinstance(payload["shared_dependencies"], list):
        raise ContractValidationError("MODULE shared_dependencies must be an array.")
    for p in payload["shared_dependencies"]:
        if not isinstance(p, str) or not validate_relative_path(p):
            raise ContractValidationError(f"MODULE shared_dependencies item invalid: {p!r}")
    if not isinstance(payload["workflow_version"], str) or not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", payload["workflow_version"]):
        raise ContractValidationError(f"MODULE workflow_version invalid: {payload['workflow_version']!r}")


def validate_scope_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("SCOPE payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "task_id", "module_id", "base_branch", "work_branch",
        "base_commit", "allowed_paths", "forbidden_paths", "required_files",
        "required_symbols", "max_files_changed", "max_changed_lines",
        "test_commands", "sandbox_build", "direct_main_changes", "auto_merge", "status"
    }
    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"SCOPE payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"SCOPE payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("SCOPE schema_version must be integer 1.")
    if not isinstance(payload["task_id"], str) or not TASK_ID_RE.match(payload["task_id"]):
        raise ContractValidationError(f"SCOPE task_id invalid: {payload['task_id']!r}")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"SCOPE module_id invalid: {payload['module_id']!r}")
    if not isinstance(payload["base_branch"], str) or not payload["base_branch"].strip():
        raise ContractValidationError("SCOPE base_branch must be non-empty string.")
    if not isinstance(payload["work_branch"], str) or not payload["work_branch"].strip() or payload["work_branch"] in PROTECTED_BRANCHES:
        raise ContractValidationError(f"SCOPE work_branch invalid or protected: {payload['work_branch']!r}")
    if not isinstance(payload["base_commit"], str) or not re.match(r"^[a-f0-9]{40}([a-f0-9]{24})?$", payload["base_commit"]):
        raise ContractValidationError(f"SCOPE base_commit invalid: {payload['base_commit']!r}")

    if not isinstance(payload["allowed_paths"], list) or len(payload["allowed_paths"]) < 1:
        raise ContractValidationError("SCOPE allowed_paths must be a non-empty array.")
    for p in payload["allowed_paths"]:
        if not isinstance(p, str) or not validate_relative_path(p):
            raise ContractValidationError(f"SCOPE allowed_paths item invalid relative path: {p!r}")

    if not isinstance(payload["forbidden_paths"], list):
        raise ContractValidationError("SCOPE forbidden_paths must be an array.")
    for p in payload["forbidden_paths"]:
        if not isinstance(p, str) or not validate_relative_path(p):
            raise ContractValidationError(f"SCOPE forbidden_paths item invalid relative path: {p!r}")

    if not isinstance(payload["required_files"], list):
        raise ContractValidationError("SCOPE required_files must be an array.")
    for p in payload["required_files"]:
        if not isinstance(p, str) or not validate_relative_path(p):
            raise ContractValidationError(f"SCOPE required_files item invalid relative path: {p!r}")

    if not isinstance(payload["required_symbols"], list):
        raise ContractValidationError("SCOPE required_symbols must be an array.")
    for s in payload["required_symbols"]:
        if not isinstance(s, str):
            raise ContractValidationError(f"SCOPE required_symbols item invalid string: {s!r}")

    if not isinstance(payload["max_files_changed"], int) or isinstance(payload["max_files_changed"], bool) or payload["max_files_changed"] < 1:
        raise ContractValidationError("SCOPE max_files_changed must be integer >= 1.")
    if not isinstance(payload["max_changed_lines"], int) or isinstance(payload["max_changed_lines"], bool) or payload["max_changed_lines"] < 1:
        raise ContractValidationError("SCOPE max_changed_lines must be integer >= 1.")

    if not isinstance(payload["test_commands"], list):
        raise ContractValidationError("SCOPE test_commands must be an array.")
    for c in payload["test_commands"]:
        if not isinstance(c, str) or not c.strip():
            raise ContractValidationError("SCOPE test_commands item must be non-empty string.")

    if not isinstance(payload["sandbox_build"], bool):
        raise ContractValidationError("SCOPE sandbox_build must be boolean.")
    if payload["direct_main_changes"] is not False:
        raise ContractValidationError("SCOPE direct_main_changes must be false.")
    if payload["auto_merge"] is not False:
        raise ContractValidationError("SCOPE auto_merge must be false.")

    if payload["status"] not in ("DRAFT", "READY", "LOCKED", "AMENDMENT_REQUIRED"):
        raise ContractValidationError(f"SCOPE status invalid: {payload['status']!r}")


def validate_plan_review_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Plan review payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "review_type", "task_id", "module_id", "review_run_id",
        "reviewer", "decision", "reviewed_branch", "base_commit",
        "task_sha256", "scope_sha256", "plan_sha256", "reviewed_at", "findings"
    }
    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"Plan review payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"Plan review payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("Plan review schema_version must be integer 1.")
    if payload["review_type"] != "PLAN":
        raise ContractValidationError("Plan review review_type must be 'PLAN'.")
    if not isinstance(payload["task_id"], str) or not TASK_ID_RE.match(payload["task_id"]):
        raise ContractValidationError(f"Plan review task_id invalid: {payload['task_id']!r}")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"Plan review module_id invalid: {payload['module_id']!r}")
    if not isinstance(payload["review_run_id"], str) or not payload["review_run_id"].strip():
        raise ContractValidationError("Plan review review_run_id must be a non-empty string.")
    if payload["reviewer"] != "codex":
        raise ContractValidationError("Plan review reviewer must be 'codex'.")
    if payload["decision"] not in ("APPROVED", "NEEDS_CHANGES", "REJECTED"):
        raise ContractValidationError(f"Plan review decision invalid: {payload['decision']!r}")
    if not isinstance(payload["reviewed_branch"], str) or not payload["reviewed_branch"].strip():
        raise ContractValidationError("Plan review reviewed_branch must be a non-empty string.")
    if not isinstance(payload["base_commit"], str) or not GIT_SHA_LOWER_RE.match(payload["base_commit"]):
        raise ContractValidationError(f"Plan review base_commit must be a 40-character lowercase hex SHA: {payload['base_commit']!r}")
    if not isinstance(payload["task_sha256"], str) or not SHA256_LOWER_RE.match(payload["task_sha256"]):
        raise ContractValidationError(f"Plan review task_sha256 must be a 64-character lowercase hex SHA: {payload['task_sha256']!r}")
    if not isinstance(payload["scope_sha256"], str) or not SHA256_LOWER_RE.match(payload["scope_sha256"]):
        raise ContractValidationError(f"Plan review scope_sha256 must be a 64-character lowercase hex SHA: {payload['scope_sha256']!r}")
    if not isinstance(payload["plan_sha256"], str) or not SHA256_LOWER_RE.match(payload["plan_sha256"]):
        raise ContractValidationError(f"Plan review plan_sha256 must be a 64-character lowercase hex SHA: {payload['plan_sha256']!r}")

    parse_iso_datetime(payload["reviewed_at"])

    if not isinstance(payload["findings"], list):
        raise ContractValidationError("Plan review findings must be an array.")
    for item in payload["findings"]:
        if not isinstance(item, dict):
            raise ContractValidationError("Plan review findings item must be an object.")


def validate_plan_lock_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Plan lock payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "module_id", "branch", "task_id", "base_commit",
        "task_sha256", "scope_sha256", "plan_sha256", "approval_file",
        "approval_sha256", "plan_status", "approved_by", "approved_review_run",
        "approved_at", "amendment_count"
    }
    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"Plan lock payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"Plan lock payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("Plan lock schema_version must be integer 1.")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"Plan lock module_id invalid: {payload['module_id']!r}")
    if not isinstance(payload["branch"], str) or not payload["branch"].strip():
        raise ContractValidationError("Plan lock branch must be a non-empty string.")
    if not isinstance(payload["task_id"], str) or not TASK_ID_RE.match(payload["task_id"]):
        raise ContractValidationError(f"Plan lock task_id invalid: {payload['task_id']!r}")
    if not isinstance(payload["base_commit"], str) or not GIT_SHA_LOWER_RE.match(payload["base_commit"]):
        raise ContractValidationError(f"Plan lock base_commit must be a 40-character lowercase hex SHA: {payload['base_commit']!r}")
    if not isinstance(payload["task_sha256"], str) or not SHA256_LOWER_RE.match(payload["task_sha256"]):
        raise ContractValidationError(f"Plan lock task_sha256 must be a 64-character lowercase hex SHA: {payload['task_sha256']!r}")
    if not isinstance(payload["scope_sha256"], str) or not SHA256_LOWER_RE.match(payload["scope_sha256"]):
        raise ContractValidationError(f"Plan lock scope_sha256 must be a 64-character lowercase hex SHA: {payload['scope_sha256']!r}")
    if not isinstance(payload["plan_sha256"], str) or not SHA256_LOWER_RE.match(payload["plan_sha256"]):
        raise ContractValidationError(f"Plan lock plan_sha256 must be a 64-character lowercase hex SHA: {payload['plan_sha256']!r}")
    if not isinstance(payload["approval_file"], str) or not validate_relative_path(payload["approval_file"]):
        raise ContractValidationError(f"Plan lock approval_file must be a valid relative path string: {payload['approval_file']!r}")
    if not isinstance(payload["approval_sha256"], str) or not SHA256_LOWER_RE.match(payload["approval_sha256"]):
        raise ContractValidationError(f"Plan lock approval_sha256 must be a 64-character lowercase hex SHA: {payload['approval_sha256']!r}")
    if payload["plan_status"] != "APPROVED":
        raise ContractValidationError(f"Plan lock plan_status must be 'APPROVED': {payload['plan_status']!r}")
    if payload["approved_by"] != "codex":
        raise ContractValidationError(f"Plan lock approved_by must be 'codex': {payload['approved_by']!r}")
    if not isinstance(payload["approved_review_run"], str) or not payload["approved_review_run"].strip():
        raise ContractValidationError("Plan lock approved_review_run must be a non-empty string.")

    parse_iso_datetime(payload["approved_at"])

    if not isinstance(payload["amendment_count"], int) or isinstance(payload["amendment_count"], bool) or payload["amendment_count"] < 0:
        raise ContractValidationError("Plan lock amendment_count must be an integer >= 0.")


def validate_evidence_request_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Evidence request payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "task_id", "module_id", "files_to_verify",
        "symbols_to_verify", "diagnosis", "diagnosis_sources"
    }
    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"Evidence request payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"Evidence request payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("Evidence request schema_version must be integer 1.")
    if not isinstance(payload["task_id"], str) or not TASK_ID_RE.match(payload["task_id"]):
        raise ContractValidationError(f"Evidence request task_id invalid: {payload['task_id']!r}")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"Evidence request module_id invalid: {payload['module_id']!r}")

    if not isinstance(payload["files_to_verify"], list):
        raise ContractValidationError("files_to_verify must be an array.")
    for item in payload["files_to_verify"]:
        if not isinstance(item, str) or not validate_relative_path(item):
            raise ContractValidationError(f"files_to_verify item must be valid relative path: {item!r}")

    if not isinstance(payload["symbols_to_verify"], list):
        raise ContractValidationError("symbols_to_verify must be an array.")
    for item in payload["symbols_to_verify"]:
        if not isinstance(item, dict):
            raise ContractValidationError("symbols_to_verify item must be an object.")
        item_allowed = {"symbol", "paths"}
        item_extra = set(item.keys()) - item_allowed
        if item_extra:
            raise ContractValidationError(f"symbols_to_verify item has unexpected properties: {sorted(item_extra)}")
        item_missing = item_allowed - set(item.keys())
        if item_missing:
            raise ContractValidationError(f"symbols_to_verify item missing required property: {sorted(item_missing)}")
        if not isinstance(item["symbol"], str) or not item["symbol"].strip():
            raise ContractValidationError("symbols_to_verify item symbol must be non-empty string.")
        if not isinstance(item["paths"], list) or len(item["paths"]) < 1:
            raise ContractValidationError("symbols_to_verify item paths must be an array with at least 1 relative path.")
        for p in item["paths"]:
            if not isinstance(p, str) or not validate_relative_path(p):
                raise ContractValidationError(f"symbols_to_verify item path invalid relative path: {p!r}")

    if not isinstance(payload["diagnosis"], str) or len(payload["diagnosis"]) < 20:
        raise ContractValidationError("diagnosis must be a string with at least 20 characters.")

    if not isinstance(payload["diagnosis_sources"], list) or len(payload["diagnosis_sources"]) < 1:
        raise ContractValidationError("diagnosis_sources must be an array containing at least 1 item.")

    for item in payload["diagnosis_sources"]:
        if not isinstance(item, dict):
            raise ContractValidationError("diagnosis_sources item must be an object.")
        item_allowed = {"path", "line_start", "line_end", "reason"}
        item_extra = set(item.keys()) - item_allowed
        if item_extra:
            raise ContractValidationError(f"diagnosis_sources item has unexpected properties: {sorted(item_extra)}")
        item_missing = item_allowed - set(item.keys())
        if item_missing:
            raise ContractValidationError(f"diagnosis_sources item missing required property: {sorted(item_missing)}")

        if not isinstance(item["path"], str) or not validate_relative_path(item["path"]):
            raise ContractValidationError(f"diagnosis_sources item path must be valid relative path: {item['path']!r}")
        if not isinstance(item["line_start"], int) or isinstance(item["line_start"], bool) or item["line_start"] < 1:
            raise ContractValidationError("diagnosis_sources item line_start must be integer >= 1.")
        if not isinstance(item["line_end"], int) or isinstance(item["line_end"], bool) or item["line_end"] < item["line_start"]:
            raise ContractValidationError("diagnosis_sources item line_end must be integer >= line_start.")
        if not isinstance(item["reason"], str) or not item["reason"].strip():
            raise ContractValidationError("diagnosis_sources item reason must be non-empty string.")


def validate_evidence_contract(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ContractValidationError("Evidence payload must be a JSON object.")

    allowed_keys = {
        "schema_version", "repository_root", "branch", "task_id", "module_id",
        "base_commit", "task_sha256", "scope_sha256", "plan_sha256",
        "plan_lock_sha256", "source_snapshot_sha256", "generated_at",
        "ready_to_implement", "files_verified", "symbols_verified",
        "diagnosis", "diagnosis_sources"
    }

    extra_keys = set(payload.keys()) - allowed_keys
    if extra_keys:
        raise ContractValidationError(f"Evidence payload has unexpected properties: {sorted(extra_keys)}")

    missing_keys = allowed_keys - set(payload.keys())
    if missing_keys:
        raise ContractValidationError(f"Evidence payload missing required property: {sorted(missing_keys)}")

    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ContractValidationError("Evidence schema_version must be integer 1.")
    if payload["repository_root"] != ".":
        raise ContractValidationError(f"Evidence repository_root must be '.': {payload['repository_root']!r}")
    if not isinstance(payload["branch"], str) or not payload["branch"].strip():
        raise ContractValidationError("Evidence branch must be non-empty string.")
    if not isinstance(payload["task_id"], str) or not TASK_ID_RE.match(payload["task_id"]):
        raise ContractValidationError(f"Evidence task_id invalid: {payload['task_id']!r}")
    if not isinstance(payload["module_id"], str) or not MODULE_ID_RE.match(payload["module_id"]):
        raise ContractValidationError(f"Evidence module_id invalid: {payload['module_id']!r}")

    parse_iso_datetime(payload["generated_at"])

    if not isinstance(payload["ready_to_implement"], bool):
        raise ContractValidationError("Evidence ready_to_implement must be boolean.")

    if not isinstance(payload["files_verified"], list):
        raise ContractValidationError("Evidence files_verified must be an array.")
    if not isinstance(payload["symbols_verified"], list):
        raise ContractValidationError("Evidence symbols_verified must be an array.")
    if not isinstance(payload["diagnosis_sources"], list):
        raise ContractValidationError("Evidence diagnosis_sources must be an array.")
    if not isinstance(payload["diagnosis"], str) or not payload["diagnosis"].strip():
        raise ContractValidationError("Evidence diagnosis must be a non-empty string.")

    # Validate files_verified items for all payloads
    for item in payload["files_verified"]:
        if not isinstance(item, dict):
            raise ContractValidationError("files_verified item must be object.")
        allowed_f = {"path", "exists", "tracked", "evidence_command", "file_sha256"}
        required_f = {"path", "exists", "tracked", "evidence_command"}
        missing_f = required_f - set(item.keys())
        if missing_f:
            raise ContractValidationError(f"files_verified item missing required property: {sorted(missing_f)}")
        extra_f = set(item.keys()) - allowed_f
        if extra_f:
            raise ContractValidationError(f"files_verified item has unexpected properties: {sorted(extra_f)}")

        if not isinstance(item["path"], str) or not validate_relative_path(item["path"]):
            raise ContractValidationError(f"files_verified item path invalid relative path: {item.get('path')!r}")
        if not isinstance(item["exists"], bool):
            raise ContractValidationError(f"files_verified item exists must be boolean: {item.get('exists')!r}")
        if not isinstance(item["tracked"], bool):
            raise ContractValidationError(f"files_verified item tracked must be boolean: {item.get('tracked')!r}")
        if not isinstance(item["evidence_command"], str) or not item["evidence_command"].strip():
            raise ContractValidationError("files_verified item evidence_command must be non-empty string.")

        if "file_sha256" in item:
            f_sha = item["file_sha256"]
            if not isinstance(f_sha, str) or not SHA256_LOWER_RE.match(f_sha):
                raise ContractValidationError(f"files_verified item file_sha256 invalid: {f_sha!r}")

    # Validate symbols_verified items for all payloads
    for item in payload["symbols_verified"]:
        if not isinstance(item, dict):
            raise ContractValidationError("symbols_verified item must be object.")
        allowed_s = {"symbol", "evidence_command", "matches", "found_count"}
        missing_s = allowed_s - set(item.keys())
        if missing_s:
            raise ContractValidationError(f"symbols_verified item missing required property: {sorted(missing_s)}")
        extra_s = set(item.keys()) - allowed_s
        if extra_s:
            raise ContractValidationError(f"symbols_verified item has unexpected properties: {sorted(extra_s)}")

        if not isinstance(item["symbol"], str) or not item["symbol"].strip():
            raise ContractValidationError("symbols_verified item symbol must be non-empty string.")
        if not isinstance(item["evidence_command"], str) or not item["evidence_command"].strip():
            raise ContractValidationError("symbols_verified item evidence_command must be non-empty string.")

        matches = item["matches"]
        if not isinstance(matches, list) or not all(isinstance(m, str) for m in matches):
            raise ContractValidationError(f"symbols_verified item matches must be an array of strings: {matches!r}")

        fc = item["found_count"]
        if not isinstance(fc, int) or isinstance(fc, bool):
            raise ContractValidationError(f"symbols_verified item found_count must be integer: {fc!r}")
        if fc != len(matches):
            raise ContractValidationError(f"symbols_verified item found_count {fc} does not match matches count {len(matches)}")

    # Validate diagnosis_sources items for all payloads
    for item in payload["diagnosis_sources"]:
        if not isinstance(item, dict):
            raise ContractValidationError("diagnosis_sources item must be object.")
        allowed_d = {"path", "line_start", "line_end", "reason", "file_sha256", "excerpt_sha256"}
        missing_d = allowed_d - set(item.keys())
        if missing_d:
            raise ContractValidationError(f"diagnosis_sources item missing required property: {sorted(missing_d)}")
        extra_d = set(item.keys()) - allowed_d
        if extra_d:
            raise ContractValidationError(f"diagnosis_sources item has unexpected properties: {sorted(extra_d)}")

        if not isinstance(item["path"], str) or not validate_relative_path(item["path"]):
            raise ContractValidationError(f"diagnosis_sources item path invalid relative path: {item.get('path')!r}")

        l_start = item["line_start"]
        l_end = item["line_end"]
        if not isinstance(l_start, int) or isinstance(l_start, bool) or l_start < 1:
            raise ContractValidationError(f"diagnosis_sources item line_start must be integer >= 1: {l_start!r}")
        if not isinstance(l_end, int) or isinstance(l_end, bool) or l_end < l_start:
            raise ContractValidationError(f"diagnosis_sources item line_end must be integer >= line_start: {l_end!r}")

        if not isinstance(item["reason"], str) or not item["reason"].strip():
            raise ContractValidationError("diagnosis_sources item reason must be non-empty string.")

        f_sha = item["file_sha256"]
        e_sha = item["excerpt_sha256"]
        if not isinstance(f_sha, str) or not SHA256_LOWER_RE.match(f_sha):
            raise ContractValidationError(f"diagnosis_sources item file_sha256 invalid: {f_sha!r}")
        if not isinstance(e_sha, str) or not SHA256_LOWER_RE.match(e_sha):
            raise ContractValidationError(f"diagnosis_sources item excerpt_sha256 invalid: {e_sha!r}")

    # Additional strict checks when ready_to_implement is true
    if payload["ready_to_implement"]:
        if not isinstance(payload["base_commit"], str) or not GIT_SHA_LOWER_RE.match(payload["base_commit"]):
            raise ContractValidationError(f"Evidence base_commit invalid when ready: {payload['base_commit']!r}")
        for sha_key in ("task_sha256", "scope_sha256", "plan_sha256", "plan_lock_sha256", "source_snapshot_sha256"):
            val = payload[sha_key]
            if not isinstance(val, str) or not SHA256_LOWER_RE.match(val):
                raise ContractValidationError(f"Evidence {sha_key} invalid when ready: {val!r}")

        if len(payload["diagnosis"]) < 20:
            raise ContractValidationError("Evidence diagnosis must be at least 20 characters when ready_to_implement is true.")
        if len(payload["files_verified"]) < 1:
            raise ContractValidationError("Evidence files_verified must contain at least 1 item when ready_to_implement is true.")
        if len(payload["diagnosis_sources"]) < 1:
            raise ContractValidationError("Evidence diagnosis_sources must contain at least 1 item when ready_to_implement is true.")

        for item in payload["files_verified"]:
            if item["exists"] is not True:
                raise ContractValidationError(f"files_verified item exists must be true when ready: {item}")
            if item["tracked"] is not True:
                raise ContractValidationError(f"files_verified item tracked must be true when ready: {item}")
            if "file_sha256" not in item:
                raise ContractValidationError(f"files_verified item file_sha256 required when ready: {item}")

        for item in payload["symbols_verified"]:
            if len(item["matches"]) < 1:
                raise ContractValidationError(f"symbols_verified item matches must contain at least 1 match when ready: {item}")



# ---------------------------------------------------------------------------
# Shared Plan Lock Context Verification
# ---------------------------------------------------------------------------

def verify_plan_lock_context(
    repo_root: Path,
    module_root_rel: str,
    *,
    require_unprotected_branch: bool = True,
) -> tuple[dict, dict, dict, Path, Path, Path, Path, Path, str]:
    """
    Shared Plan Lock verification logic used by plan_lock verify, evidence collect, evidence verify.
    Returns (module_json, scope_json, lock_data, module_abs, task_path, scope_path, plan_path, lock_path, current_branch).
    Raises PlanLockVerificationError on any failure.
    """
    repo_abs = validate_repository_root(repo_root, repo_root)
    if repo_abs is None:
        raise PlanLockVerificationError("NOT_A_GIT_REPOSITORY", f"Repository root invalid: {repo_root}", exit_code=2)

    current_branch = get_current_branch(repo_abs)
    if not current_branch:
        raise PlanLockVerificationError("PROTECTED_BRANCH_BLOCKED", "Current Git branch is empty.", exit_code=2)

    if require_unprotected_branch and current_branch in PROTECTED_BRANCHES:
        raise PlanLockVerificationError(
            "PROTECTED_BRANCH_BLOCKED",
            f"Current branch '{current_branch}' is protected.",
            exit_code=2,
        )

    try:
        module_abs = resolve_contained_path(repo_abs, module_root_rel, must_exist=True)
    except PathContainmentError as e:
        raise PlanLockVerificationError("INVALID_MODULE_ROOT", str(e), exit_code=2)

    module_json_path = module_abs / ".ai-workflow" / "MODULE.json"
    if not module_json_path.exists():
        raise PlanLockVerificationError("MODULE_CONTRACT_MISSING", "MODULE.json missing", exit_code=2)
    try:
        module_json = load_json(module_json_path)
        validate_module_contract(module_json)
    except Exception as e:
        raise PlanLockVerificationError("MODULE_CONTRACT_MISMATCH", f"Invalid MODULE.json: {e}", exit_code=2)

    scope_json_path = module_abs / ".ai-workflow" / "SCOPE.json"
    if not scope_json_path.exists():
        raise PlanLockVerificationError("SCOPE_CONTRACT_MISSING", "SCOPE.json missing", exit_code=2)
    try:
        scope_json = load_json(scope_json_path)
        validate_scope_contract(scope_json)
    except Exception as e:
        raise PlanLockVerificationError("SCOPE_CONTRACT_MISMATCH", f"Invalid SCOPE.json: {e}", exit_code=2)

    task_path = module_abs / ".ai-workflow" / "TASK.md"
    plan_path = module_abs / ".ai-workflow" / "PLAN.md"
    lock_path = module_abs / ".ai-workflow" / "PLAN_LOCK.json"

    if not task_path.exists():
        raise PlanLockVerificationError("TASK_CONTRACT_MISSING", "TASK.md missing", exit_code=2)
    if not plan_path.exists():
        raise PlanLockVerificationError("PLAN_CONTRACT_MISSING", "PLAN.md missing", exit_code=2)
    if not lock_path.exists():
        raise PlanLockVerificationError("PLAN_LOCK_MISSING", "PLAN_LOCK.json missing", exit_code=5)

    try:
        lock_data = load_json(lock_path)
    except Exception as e:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", f"Failed to parse PLAN_LOCK.json: {e}", exit_code=5)

    try:
        validate_plan_lock_contract(lock_data)
    except ContractValidationError as e:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", str(e), exit_code=5)

    if lock_data["module_id"] != module_json["module_id"]:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Module ID mismatch in PLAN_LOCK.json", exit_code=5)
    if lock_data["task_id"] != scope_json["task_id"]:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Task ID mismatch in PLAN_LOCK.json", exit_code=5)
    if lock_data["branch"] != current_branch:
        raise PlanLockVerificationError("BRANCH_MISMATCH", f"Branch mismatch in PLAN_LOCK.json ({lock_data['branch']} != {current_branch})", exit_code=5)

    if lock_data["base_commit"] != scope_json["base_commit"]:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Base commit mismatch in PLAN_LOCK.json", exit_code=5)

    curr_task_hash = hash_task_file(task_path)
    curr_scope_hash = hash_scope_file(scope_json_path)
    curr_plan_hash = hash_plan_file(plan_path)

    if curr_task_hash != lock_data["task_sha256"]:
        raise PlanLockVerificationError("TASK_CHANGED", "TASK.md hash mismatch", exit_code=5)
    if curr_scope_hash != lock_data["scope_sha256"]:
        raise PlanLockVerificationError("SCOPE_CHANGED", "SCOPE.json hash mismatch", exit_code=5)
    if curr_plan_hash != lock_data["plan_sha256"]:
        raise PlanLockVerificationError("PLAN_CHANGED", "PLAN.md hash mismatch", exit_code=5)

    if lock_data["approved_by"] != "codex" or lock_data["plan_status"] != "APPROVED":
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "PLAN_LOCK.json approval invalid", exit_code=5)

    # Verify Plan Lock approval provenance
    app_rel = lock_data.get("approval_file", "")
    if not validate_relative_path(app_rel):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", f"Approval file relative path invalid: {app_rel!r}", exit_code=5)

    history_dir = (module_abs / ".ai-workflow" / "history").resolve()
    try:
        app_full = resolve_contained_path(repo_abs, app_rel, must_exist=True)
        app_full.relative_to(history_dir)
    except (PathContainmentError, ValueError) as e:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", f"Approval file path invalid or outside history: {app_rel!r} ({e})", exit_code=5)

    if not app_full.exists() or not app_full.is_file():
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", f"Approval file missing: {app_rel!r}", exit_code=5)

    curr_app_hash = sha256_file(app_full)
    if curr_app_hash != lock_data.get("approval_sha256"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval file SHA-256 mismatch", exit_code=5)

    try:
        app_json = load_json(app_full)
        validate_plan_review_contract(app_json)
    except Exception as e:
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", f"Invalid approval plan review contract: {e}", exit_code=5)

    if app_json["review_run_id"] != lock_data.get("approved_review_run"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval review_run_id mismatch", exit_code=5)
    if app_json["reviewed_at"] != lock_data.get("approved_at"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval reviewed_at mismatch", exit_code=5)
    if app_json["reviewer"] != lock_data.get("approved_by"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval reviewer mismatch", exit_code=5)
    if app_json["decision"] != "APPROVED":
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval decision is not APPROVED", exit_code=5)
    if app_json["task_id"] != lock_data.get("task_id"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval task_id mismatch", exit_code=5)
    if app_json["module_id"] != lock_data.get("module_id"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval module_id mismatch", exit_code=5)
    if app_json["reviewed_branch"] != lock_data.get("branch"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval branch mismatch", exit_code=5)
    if app_json["base_commit"] != lock_data.get("base_commit"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval base_commit mismatch", exit_code=5)
    if app_json["task_sha256"] != lock_data.get("task_sha256"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval task_sha256 mismatch", exit_code=5)
    if app_json["scope_sha256"] != lock_data.get("scope_sha256"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval scope_sha256 mismatch", exit_code=5)
    if app_json["plan_sha256"] != lock_data.get("plan_sha256"):
        raise PlanLockVerificationError("PLAN_LOCK_INVALID", "Approval plan_sha256 mismatch", exit_code=5)

    return (

        module_json,
        scope_json,
        lock_data,
        module_abs,
        task_path,
        scope_json_path,
        plan_path,
        lock_path,
        current_branch,
    )


# ---------------------------------------------------------------------------
# Output Format & Execution Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_result(result_dict: Dict[str, Any]) -> None:
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))


def fail(exit_code: int, result_dict: Dict[str, Any]) -> None:
    print_result(result_dict)
    sys.exit(exit_code)
