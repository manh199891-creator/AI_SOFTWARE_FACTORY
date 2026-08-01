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
# Path Validation & Relative Normalization
# ---------------------------------------------------------------------------

def validate_relative_path(path_str: str) -> bool:
    if not path_str:
        return False
    norm = path_str.replace("\\", "/")
    if norm.startswith("/") or ":" in norm or ".." in norm.split("/"):
        return False
    return True


def normalize_rel_path(path_str: str) -> str:
    norm = path_str.replace("\\", "/").strip("/")
    parts = [p for p in norm.split("/") if p and p != "."]
    return "/".join(parts)


def path_matches_pattern(rel_path: str, glob_pattern: str) -> bool:
    norm_path = normalize_rel_path(rel_path)
    norm_pattern = normalize_rel_path(glob_pattern)

    # Convert glob pattern with **, *, ? to regular expression
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

    # Check forbidden first
    for f_pat in forbidden_paths:
        if path_matches_pattern(norm_path, f_pat):
            return False

    # Check allowed
    for a_pat in allowed_paths:
        if path_matches_pattern(norm_path, a_pat):
            return True
    return False


# ---------------------------------------------------------------------------
# Hashing & Canonicalization
# ---------------------------------------------------------------------------

def canonical_text_bytes(text_str: str) -> bytes:
    # Remove UTF-8 BOM if present
    if text_str.startswith("\ufeff"):
        text_str = text_str[1:]
    # Normalize CRLF and CR to LF
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
    """
    Returns (file_sha256, excerpt_sha256).
    """
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

    module_norm = normalize_rel_path(module_root_rel)

    for rel_path in all_tracked:
        norm_path = normalize_rel_path(rel_path)

        # Must be under module_root if module_root specified
        if module_norm and not norm_path.startswith(module_norm + "/") and norm_path != module_norm:
            continue

        # Must not be in .ai-workflow or .sandbox
        path_in_module = norm_path[len(module_norm) :].lstrip("/") if module_norm else norm_path
        if path_in_module.startswith(".ai-workflow/") or path_in_module.startswith(".sandbox/"):
            continue

        # Must be allowed and not forbidden according to SCOPE
        if is_path_allowed(norm_path, allowed_paths, forbidden_paths):
            full_path = repo_root / norm_path
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
# Output Format & Execution Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_result(result_dict: Dict[str, Any]) -> None:
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))


def fail(exit_code: int, result_dict: Dict[str, Any]) -> None:
    print_result(result_dict)
    sys.exit(exit_code)
