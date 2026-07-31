#!/usr/bin/env python3
"""
module_bootstrap.py — Module Workflow Bootstrap Tool (Phase B)

Initialises the canonical .ai-workflow/ and .sandbox/ skeleton inside an
existing Revit / Navisworks / .NET add-in module directory.

Requirements:
  - Python 3.10+
  - Standard library only (no third-party packages)

Exit codes:
  0 = CREATED | NO_CHANGES | DRY_RUN
  2 = input/context validation failure
  3 = conflict with existing content
  4 = write/rollback failure
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
GITIGNORE_BEGIN = "# BEGIN AI MODULE WORKFLOW"
GITIGNORE_END = "# END AI MODULE WORKFLOW"
GITIGNORE_BLOCK = """\
# BEGIN AI MODULE WORKFLOW
bin/
obj/
.sandbox/*
!.sandbox/README.md
# END AI MODULE WORKFLOW"""

PROTECTED_BRANCHES = {"main", "master", "develop", "release"}
MODULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

# Planner-owned targets (relative to module root)
PLANNER_OWNED = [
    ".ai-workflow/MODULE.json",
    ".ai-workflow/TASK.md",
    ".ai-workflow/SCOPE.json",
    ".ai-workflow/REVIEW.md",
    ".ai-workflow/history/.gitkeep",
    ".sandbox/README.md",
]

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def make_output(
    *,
    status: str,
    reason_code: str,
    repository_root: str = "",
    module_root: str = "",
    branch: str = "",
    dry_run: bool = False,
    files_created: list[str] | None = None,
    files_preserved: list[str] | None = None,
    directories_created: list[str] | None = None,
    gitignore_updated: bool = False,
    generated_contracts: list[str] | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reason_code": reason_code,
        "repository_root": repository_root,
        "module_root": module_root,
        "branch": branch,
        "dry_run": dry_run,
        "files_created": files_created or [],
        "files_preserved": files_preserved or [],
        "directories_created": directories_created or [],
        "gitignore_updated": gitignore_updated,
        "generated_contracts": generated_contracts or [],
    }


def fail(reason_code: str, message: str, exit_code: int = 2, **kwargs) -> None:
    result = make_output(status="FAILED", reason_code=reason_code, **kwargs)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    print(f"[ERROR] {reason_code}: {message}", file=sys.stderr, flush=True)
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_git_root(repo_root: str) -> str | None:
    code, out, _ = run_git(["-C", repo_root, "rev-parse", "--show-toplevel"], cwd=repo_root)
    if code != 0:
        return None
    return out


def get_current_branch(repo_root: str) -> str | None:
    code, out, _ = run_git(["-C", repo_root, "branch", "--show-current"], cwd=repo_root)
    if code != 0:
        return None
    return out


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_relative_path(value: str, field: str) -> None:
    """Reject empty, absolute, UNC, or traversal paths."""
    if not value:
        fail("INVALID_RELATIVE_PATH", f"{field}: path must not be empty")
    # Windows absolute: starts with drive letter
    if re.match(r"^[A-Za-z]:", value):
        fail("INVALID_RELATIVE_PATH", f"{field}: Windows absolute path not allowed: {value!r}")
    # POSIX absolute
    if value.startswith("/"):
        fail("INVALID_RELATIVE_PATH", f"{field}: POSIX absolute path not allowed: {value!r}")
    # UNC
    if value.startswith("\\\\"):
        fail("INVALID_RELATIVE_PATH", f"{field}: UNC path not allowed: {value!r}")
    # Traversal
    if ".." in Path(value).parts:
        fail("INVALID_RELATIVE_PATH", f"{field}: path traversal with '..' not allowed: {value!r}")


def validate_inside_repo(abs_path: Path, repo_abs: Path, field: str) -> None:
    try:
        abs_path.resolve().relative_to(repo_abs.resolve())
    except ValueError:
        fail("PATH_ESCAPES_REPOSITORY", f"{field}: path escapes repository root: {abs_path}")


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------


def find_template_root(script_path: Path) -> Path:
    """
    Walk up from script location to find AI_SOFTWARE_FACTORY root
    (identified by presence of templates/module-workflow/).
    """
    candidate = script_path.resolve().parent
    for _ in range(10):
        tmpl = candidate / "templates" / "module-workflow"
        if tmpl.is_dir():
            return candidate
        candidate = candidate.parent
    raise FileNotFoundError("Cannot locate templates/module-workflow/ relative to script.")


def read_template(template_root: Path, rel: str) -> str:
    path = template_root / "templates" / "module-workflow" / rel
    if not path.exists():
        fail(
            "CANONICAL_TEMPLATE_MISSING",
            f"Template missing: {path}",
        )
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Content generators
# ---------------------------------------------------------------------------


def generate_module_json(
    *,
    module_id: str,
    module_name: str,
    module_root: str,
    project_file: str,
    platform: str,
    dll_name: str,
    default_test_paths: list[str],
    shared_dependencies: list[str],
    workflow_version: str,
) -> str:
    # Normalise to forward slashes
    mr = module_root.replace("\\", "/")
    pf = project_file.replace("\\", "/")
    dtp = [p.replace("\\", "/") for p in default_test_paths]
    sd = [p.replace("\\", "/") for p in shared_dependencies]
    obj = {
        "schema_version": 1,
        "module_id": module_id,
        "module_name": module_name,
        "module_root": mr,
        "project_file": pf,
        "platform": platform,
        "workflow_root": f"{mr}/.ai-workflow",
        "sandbox_root": f"{mr}/.sandbox",
        "sandbox_dll": f"{mr}/.sandbox/bin/{dll_name}",
        "stable_output_root": f"{mr}/bin",
        "default_test_paths": dtp,
        "shared_dependencies": sd,
        "workflow_version": workflow_version,
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def generate_scope_json(*, module_id: str, module_root: str, project_file: str) -> str:
    mr = module_root.replace("\\", "/")
    pf = project_file.replace("\\", "/")
    obj = {
        "schema_version": 1,
        "task_id": "replace-task-id",
        "module_id": module_id,
        "base_branch": "main",
        "work_branch": "task/replace-task-id",
        "base_commit": "0000000000000000000000000000000000000000",
        "allowed_paths": [f"{mr}/**"],
        "forbidden_paths": [],
        "required_files": [pf],
        "required_symbols": [],
        "max_files_changed": 10,
        "max_changed_lines": 500,
        "test_commands": [],
        "sandbox_build": True,
        "direct_main_changes": False,
        "auto_merge": False,
        "status": "DRAFT",
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# .gitignore managed block
# ---------------------------------------------------------------------------


def parse_gitignore(content: str) -> tuple[str, str, str] | None:
    """
    Returns (before, block, after) if managed block exists and is valid.
    Returns None if no managed block.
    Calls fail() if block is malformed (BEGIN without END).
    """
    begin_idx = content.find(GITIGNORE_BEGIN)
    end_idx = content.find(GITIGNORE_END)
    if begin_idx == -1 and end_idx == -1:
        return None
    if begin_idx != -1 and end_idx == -1:
        fail(
            "GITIGNORE_MANAGED_BLOCK_INVALID",
            ".gitignore has BEGIN AI MODULE WORKFLOW marker but END marker is missing.",
            exit_code=2,
        )
    if begin_idx == -1 and end_idx != -1:
        fail(
            "GITIGNORE_MANAGED_BLOCK_INVALID",
            ".gitignore has END AI MODULE WORKFLOW marker but BEGIN marker is missing.",
            exit_code=2,
        )
    if end_idx < begin_idx:
        fail(
            "GITIGNORE_MANAGED_BLOCK_INVALID",
            ".gitignore END marker appears before BEGIN marker.",
            exit_code=2,
        )
    before = content[:begin_idx]
    end_pos = end_idx + len(GITIGNORE_END)
    block = content[begin_idx:end_pos]
    after = content[end_pos:]
    return before, block, after


def compute_gitignore_content(existing: str) -> tuple[str, bool]:
    """
    Return (new_content, was_updated).
    If managed block already present and correct: no change.
    If managed block absent: append.
    """
    parsed = parse_gitignore(existing)
    if parsed is None:
        # Append block
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_content = existing + sep + GITIGNORE_BLOCK + "\n"
        return new_content, True
    before, block, after = parsed
    if block == GITIGNORE_BLOCK:
        # Already correct — idempotent
        return existing, False
    # Block present but content differs — replace with canonical block
    new_content = before + GITIGNORE_BLOCK + after
    return new_content, True


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------


class BootstrapWriter:
    """Tracks what this run creates so rollback is precise."""

    def __init__(self) -> None:
        self._created_files: list[Path] = []
        self._created_dirs: list[Path] = []

    def mkdir(self, path: Path) -> bool:
        """Create directory if not exists. Returns True if newly created."""
        if path.exists():
            return False
        path.mkdir(parents=True, exist_ok=True)
        self._created_dirs.append(path)
        return True

    def write_file(self, path: Path, content: str | bytes) -> None:
        """Write via temp file + os.replace for atomicity."""
        dir_ = path.parent
        dir_.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix or ".tmp"
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=suffix + ".tmp")
        try:
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content
            os.write(fd, content_bytes)
            os.close(fd)
            os.replace(tmp, path)
            self._created_files.append(path)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise

    def rollback(self) -> None:
        for f in reversed(self._created_files):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        for d in sorted(self._created_dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
            except Exception:
                pass

    @property
    def created_files(self) -> list[Path]:
        return list(self._created_files)

    @property
    def created_dirs(self) -> list[Path]:
        return list(self._created_dirs)


# ---------------------------------------------------------------------------
# Main bootstrap logic
# ---------------------------------------------------------------------------


def bootstrap(args: argparse.Namespace) -> None:
    script_path = Path(__file__)
    dry_run: bool = args.dry_run

    # ------------------------------------------------------------------
    # 1. Resolve and validate repository root
    # ------------------------------------------------------------------
    repo_root_str: str = args.repository_root
    repo_abs = Path(repo_root_str).resolve()

    git_root = get_git_root(str(repo_abs))
    if git_root is None:
        fail("NOT_A_GIT_REPOSITORY", f"Not a Git working tree: {repo_abs}")

    git_root_abs = Path(git_root).resolve()
    if git_root_abs != repo_abs:
        fail(
            "REPOSITORY_ROOT_MISMATCH",
            f"Git root {git_root_abs} != supplied RepositoryRoot {repo_abs}",
        )

    branch = get_current_branch(str(repo_abs)) or ""
    if not branch:
        fail("PROTECTED_BRANCH_BLOCKED", "Current Git branch is empty (detached HEAD?).")
    if branch in PROTECTED_BRANCHES:
        fail("PROTECTED_BRANCH_BLOCKED", f"Current branch '{branch}' is protected. Use a task branch.")

    # ------------------------------------------------------------------
    # 2. Validate relative path arguments
    # ------------------------------------------------------------------
    module_root_rel: str = args.module_root.replace("\\", "/")
    project_file_rel: str = args.project_file.replace("\\", "/")

    validate_relative_path(module_root_rel, "module-root")
    validate_relative_path(project_file_rel, "project-file")

    module_abs = (repo_abs / module_root_rel).resolve()
    project_file_abs = (repo_abs / project_file_rel).resolve()

    validate_inside_repo(module_abs, repo_abs, "module-root")
    validate_inside_repo(project_file_abs, repo_abs, "project-file")

    for i, tp in enumerate(args.default_test_path):
        tp_norm = tp.replace("\\", "/")
        validate_relative_path(tp_norm, f"default-test-path[{i}]")
        validate_inside_repo((repo_abs / tp_norm).resolve(), repo_abs, f"default-test-path[{i}]")

    for i, sd in enumerate(args.shared_dependency):
        sd_norm = sd.replace("\\", "/")
        validate_relative_path(sd_norm, f"shared-dependency[{i}]")
        validate_inside_repo((repo_abs / sd_norm).resolve(), repo_abs, f"shared-dependency[{i}]")

    # ------------------------------------------------------------------
    # 3. Validate module existence
    # ------------------------------------------------------------------
    if module_abs == repo_abs:
        fail("INVALID_MODULE_ROOT", "module-root must not be the repository root itself.")
    if not module_abs.exists() or not module_abs.is_dir():
        fail("MODULE_ROOT_NOT_FOUND", f"Module directory not found: {module_abs}")
    if not project_file_abs.exists() or not project_file_abs.is_file():
        fail("PROJECT_FILE_NOT_FOUND", f"Project file not found: {project_file_abs}")
    try:
        project_file_abs.relative_to(module_abs)
    except ValueError:
        fail("PROJECT_FILE_OUTSIDE_MODULE", f"project-file is not inside module-root: {project_file_abs}")

    # ------------------------------------------------------------------
    # 4. Validate identifiers
    # ------------------------------------------------------------------
    module_id: str = args.module_id
    if not MODULE_ID_RE.match(module_id):
        fail("INVALID_MODULE_ID", f"module-id must match ^[a-z0-9][a-z0-9._-]*$ : {module_id!r}")

    workflow_version: str = args.workflow_version
    if not SEMVER_RE.match(workflow_version):
        fail("INVALID_WORKFLOW_VERSION", f"workflow-version must be semver X.Y.Z: {workflow_version!r}")

    dll_name: str = args.dll_name if args.dll_name else f"{args.module_name}.dll"
    if not dll_name:
        fail("INVALID_DLL_NAME", "dll-name must not be empty.")
    if not dll_name.endswith(".dll"):
        fail("INVALID_DLL_NAME", f"dll-name must end with .dll: {dll_name!r}")
    if "/" in dll_name or "\\" in dll_name:
        fail("INVALID_DLL_NAME", f"dll-name must not contain path separators: {dll_name!r}")

    # ------------------------------------------------------------------
    # 5. Locate templates
    # ------------------------------------------------------------------
    try:
        tmpl_root = find_template_root(script_path)
    except FileNotFoundError as e:
        fail("CANONICAL_TEMPLATE_MISSING", str(e))

    task_md_content = read_template(tmpl_root, ".ai-workflow/TASK.md")
    review_md_content = read_template(tmpl_root, ".ai-workflow/REVIEW.md")
    sandbox_readme_content = read_template(tmpl_root, ".sandbox/README.md")

    # ------------------------------------------------------------------
    # 6. Pre-compute all output
    # ------------------------------------------------------------------
    module_json_content = generate_module_json(
        module_id=module_id,
        module_name=args.module_name,
        module_root=module_root_rel,
        project_file=project_file_rel,
        platform=args.platform,
        dll_name=dll_name,
        default_test_paths=[p.replace("\\", "/") for p in args.default_test_path],
        shared_dependencies=[p.replace("\\", "/") for p in args.shared_dependency],
        workflow_version=workflow_version,
    )
    scope_json_content = generate_scope_json(
        module_id=module_id,
        module_root=module_root_rel,
        project_file=project_file_rel,
    )

    planned_files: dict[Path, str] = {
        module_abs / ".ai-workflow" / "MODULE.json": module_json_content,
        module_abs / ".ai-workflow" / "TASK.md": task_md_content,
        module_abs / ".ai-workflow" / "SCOPE.json": scope_json_content,
        module_abs / ".ai-workflow" / "REVIEW.md": review_md_content,
        module_abs / ".ai-workflow" / "history" / ".gitkeep": "",
        module_abs / ".sandbox" / "README.md": sandbox_readme_content,
    }

    planned_dirs: list[Path] = [
        module_abs / ".ai-workflow",
        module_abs / ".ai-workflow" / "history",
        module_abs / ".sandbox",
        module_abs / ".sandbox" / "bin",
        module_abs / ".sandbox" / "obj",
        module_abs / ".sandbox" / "addin",
        module_abs / ".sandbox" / "test-models",
        module_abs / ".sandbox" / "logs",
        module_abs / ".sandbox" / "results",
    ]

    # .gitignore
    gitignore_path = module_abs / ".gitignore"
    existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    # Validate before computing (will call fail() if malformed)
    parse_gitignore(existing_gitignore)
    new_gitignore, gitignore_updated = compute_gitignore_content(existing_gitignore)

    # ------------------------------------------------------------------
    # 7. Conflict detection (all conflicts before first write)
    # ------------------------------------------------------------------
    conflicts: list[str] = []
    files_preserved: list[str] = []

    for target, content in planned_files.items():
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                files_preserved.append(str(target.relative_to(repo_abs)))
            else:
                conflicts.append(str(target.relative_to(repo_abs)))

    if conflicts:
        result = make_output(
            status="FAILED",
            reason_code="BOOTSTRAP_CONFLICT",
            repository_root=str(repo_abs),
            module_root=module_root_rel,
            branch=branch,
            dry_run=dry_run,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        print(f"[ERROR] BOOTSTRAP_CONFLICT: conflicts detected: {conflicts}", file=sys.stderr, flush=True)
        sys.exit(3)

    # ------------------------------------------------------------------
    # 8. Determine which files actually need to be created
    # ------------------------------------------------------------------
    files_to_create = {p: c for p, c in planned_files.items() if p not in [repo_abs / f for f in files_preserved] and not p.exists()}

    dirs_already_exist = [d for d in planned_dirs if d.exists()]
    dirs_to_create = [d for d in planned_dirs if not d.exists()]

    all_unchanged = (
        not files_to_create
        and not dirs_to_create
        and not gitignore_updated
    )

    # ------------------------------------------------------------------
    # 9. Dry run — report and exit
    # ------------------------------------------------------------------
    if dry_run:
        result = make_output(
            status="DRY_RUN",
            reason_code="BOOTSTRAP_DRY_RUN",
            repository_root=str(repo_abs),
            module_root=module_root_rel,
            branch=branch,
            dry_run=True,
            files_created=[str(p.relative_to(repo_abs)) for p in files_to_create],
            files_preserved=files_preserved,
            directories_created=[str(d.relative_to(repo_abs)) for d in dirs_to_create],
            gitignore_updated=gitignore_updated,
            generated_contracts=[
                ".ai-workflow/MODULE.json",
                ".ai-workflow/TASK.md",
                ".ai-workflow/SCOPE.json",
                ".ai-workflow/REVIEW.md",
            ],
        )
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        sys.exit(0)

    # ------------------------------------------------------------------
    # 10. No-changes shortcut
    # ------------------------------------------------------------------
    if all_unchanged:
        result = make_output(
            status="NO_CHANGES",
            reason_code="BOOTSTRAP_ALREADY_CURRENT",
            repository_root=str(repo_abs),
            module_root=module_root_rel,
            branch=branch,
            dry_run=False,
            files_created=[],
            files_preserved=files_preserved,
            directories_created=[],
            gitignore_updated=False,
            generated_contracts=[
                ".ai-workflow/MODULE.json",
                ".ai-workflow/TASK.md",
                ".ai-workflow/SCOPE.json",
                ".ai-workflow/REVIEW.md",
            ],
        )
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        sys.exit(0)

    # ------------------------------------------------------------------
    # 11. Write atomically
    # ------------------------------------------------------------------
    writer = BootstrapWriter()
    try:
        for d in dirs_to_create:
            writer.mkdir(d)

        for target, content in files_to_create.items():
            writer.write_file(target, content)

        if gitignore_updated:
            writer.write_file(gitignore_path, new_gitignore)

    except Exception as exc:
        print(f"[ERROR] Write failed: {exc}", file=sys.stderr, flush=True)
        writer.rollback()
        result = make_output(
            status="FAILED",
            reason_code="BOOTSTRAP_WRITE_FAILED",
            repository_root=str(repo_abs),
            module_root=module_root_rel,
            branch=branch,
            dry_run=False,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        sys.exit(4)

    # ------------------------------------------------------------------
    # 12. Success output
    # ------------------------------------------------------------------
    result = make_output(
        status="CREATED",
        reason_code="BOOTSTRAP_CREATED",
        repository_root=str(repo_abs),
        module_root=module_root_rel,
        branch=branch,
        dry_run=False,
        files_created=[str(p.relative_to(repo_abs)) for p in writer.created_files],
        files_preserved=files_preserved,
        directories_created=[str(d.relative_to(repo_abs)) for d in writer.created_dirs],
        gitignore_updated=gitignore_updated,
        generated_contracts=[
            ".ai-workflow/MODULE.json",
            ".ai-workflow/TASK.md",
            ".ai-workflow/SCOPE.json",
            ".ai-workflow/REVIEW.md",
        ],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="module_bootstrap",
        description="Bootstrap AI workflow structure inside an existing module directory.",
    )
    p.add_argument("--repository-root", required=True, help="Absolute path to Git working tree root.")
    p.add_argument("--module-root", required=True, help="Repository-relative path to module directory.")
    p.add_argument("--module-id", required=True, help="Lowercase module identifier.")
    p.add_argument("--module-name", required=True, help="Human-readable module name.")
    p.add_argument("--project-file", required=True, help="Repository-relative path to .csproj file.")
    p.add_argument("--platform", required=True, choices=["revit", "navisworks", "dotnet"])
    p.add_argument("--dll-name", default="", help="Output DLL filename (default: <module-name>.dll).")
    p.add_argument("--default-test-path", action="append", default=[], metavar="PATH",
                   help="Repository-relative test path (repeatable).")
    p.add_argument("--shared-dependency", action="append", default=[], metavar="PATH",
                   help="Repository-relative shared dependency path (repeatable).")
    p.add_argument("--workflow-version", default="1.0.0", help="Semantic version (default: 1.0.0).")
    p.add_argument("--dry-run", action="store_true", help="Preview mode — no files written.")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    bootstrap(args)


if __name__ == "__main__":
    main()
