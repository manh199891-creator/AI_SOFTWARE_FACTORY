"""
test_module_plan_lock.py — Unit and integration tests for plan_lock.py & plan_lock.ps1
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_LOCK_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "plan_lock.py"
PS1_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "plan_lock.ps1"
SCHEMA_DIR = REPO_ROOT / "schemas" / "module-workflow"

sys.path.insert(0, str(REPO_ROOT / "skills" / "module-workflow" / "scripts"))
from module_contract_utils import (
    canonical_json_bytes,
    canonical_text_bytes,
    hash_plan_file,
    hash_scope_file,
    hash_task_file,
    sha256_bytes,
)


def load_schema(name: str) -> dict:
    with open(SCHEMA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def init_test_module_repo(tmp_path: Path, branch: str = "task/drawbeams-fix-corridor") -> Tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-b", branch], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    module_rel = "src/Antigravity.DrawBeams"
    mod_dir = repo / module_rel
    ai_dir = mod_dir / ".ai-workflow"
    history_dir = ai_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    # Initial commit for base_commit
    subprocess.run(["git", "commit", "--allow-empty", "-m", "initial base commit"], cwd=repo, check=True, capture_output=True)
    res_base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
    base_commit = res_base.stdout.strip()

    # Create templates dir inside repo for script lookup
    tmpl_dir = repo / "templates" / "module-workflow" / ".ai-workflow"
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    (tmpl_dir / "TASK.md").write_text("# Task\n- Task ID:\n- Module:\n- Requested by:\n", encoding="utf-8")
    (tmpl_dir / "PLAN.md").write_text("# Plan\n- Task ID:\n- Module:\n- Base commit:\n- Work branch:\n", encoding="utf-8")

    # MODULE.json
    mod_data = {
        "schema_version": 1,
        "module_id": "antigravity-drawbeams",
        "module_name": "Antigravity.DrawBeams",
        "module_root": module_rel,
        "project_file": f"{module_rel}/Antigravity.DrawBeams.csproj",
        "platform": "revit",
        "workflow_root": f"{module_rel}/.ai-workflow",
        "sandbox_root": f"{module_rel}/.sandbox",
        "sandbox_dll": f"{module_rel}/.sandbox/bin/Antigravity.DrawBeams.dll",
        "stable_output_root": f"{module_rel}/bin",
        "default_test_paths": [f"{module_rel}/tests"],
        "shared_dependencies": [],
        "workflow_version": "1.0.0"
    }
    with open(ai_dir / "MODULE.json", "w", encoding="utf-8") as f:
        json.dump(mod_data, f, indent=2)

    # TASK.md
    task_content = f"# Task\n- Task ID: drawbeams-fix-corridor\n- Module: antigravity-drawbeams\n- Requested by: user\n\n## Goal\nFix corridor bug\n"
    (ai_dir / "TASK.md").write_text(task_content, encoding="utf-8")

    # SCOPE.json
    scope_data = {
        "schema_version": 1,
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "base_branch": "main",
        "work_branch": branch,
        "base_commit": base_commit,
        "allowed_paths": [f"{module_rel}/**"],
        "forbidden_paths": [".github/**"],
        "required_files": [f"{module_rel}/CreateBeamCommand.cs"],
        "required_symbols": ["CreateBeamCommand"],
        "max_files_changed": 5,
        "max_changed_lines": 300,
        "test_commands": ["dotnet test"],
        "sandbox_build": True,
        "direct_main_changes": False,
        "auto_merge": False,
        "status": "READY"
    }
    with open(ai_dir / "SCOPE.json", "w", encoding="utf-8") as f:
        json.dump(scope_data, f, indent=2)

    # PLAN.md
    plan_content = f"# Implementation Plan\n## Identity\n- Task ID: drawbeams-fix-corridor\n- Module: antigravity-drawbeams\n- Base commit: {base_commit}\n- Work branch: {branch}\n\n## Proposed changes\nFix beam selection\n\n## Test plan\nRun tests\n\n## Acceptance criteria\nTests pass\n"
    (ai_dir / "PLAN.md").write_text(plan_content, encoding="utf-8")

    # Create dummy source file
    src_file = mod_dir / "CreateBeamCommand.cs"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("// CreateBeamCommand\npublic class CreateBeamCommand {}\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add workflow contracts"], cwd=repo, check=True, capture_output=True)

    return repo, mod_dir, base_commit


def run_plan_lock(repo: Path, action: str, *extra_args: str, module_rel: str = "src/Antigravity.DrawBeams") -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(PLAN_LOCK_SCRIPT),
        action,
        "--repository-root", str(repo),
        "--module-root", module_rel,
        *extra_args,
    ]
    return subprocess.run(args, capture_output=True, text=True)


# --- Hashing Tests ---

def test_task_hash_normalizes_line_endings(tmp_path: Path) -> None:
    f1 = tmp_path / "task1.md"
    f2 = tmp_path / "task2.md"
    f1.write_bytes(b"# Task\r\n- Task ID: 1\r\n")
    f2.write_bytes(b"# Task\n- Task ID: 1\n")
    assert hash_task_file(f1) == hash_task_file(f2)


def test_plan_hash_normalizes_line_endings(tmp_path: Path) -> None:
    f1 = tmp_path / "plan1.md"
    f2 = tmp_path / "plan2.md"
    f1.write_bytes(b"# Plan\r\n- Task ID: 1\r\n")
    f2.write_bytes(b"# Plan\n- Task ID: 1\n")
    assert hash_plan_file(f1) == hash_plan_file(f2)


def test_scope_hash_ignores_json_key_order(tmp_path: Path) -> None:
    f1 = tmp_path / "s1.json"
    f2 = tmp_path / "s2.json"
    f1.write_text('{\n  "b": 2,\n  "a": 1\n}', encoding="utf-8")
    f2.write_text('{\n"a": 1,\n"b": 2\n}', encoding="utf-8")
    assert hash_scope_file(f1) == hash_scope_file(f2)


def test_scope_hash_changes_when_value_changes(tmp_path: Path) -> None:
    f1 = tmp_path / "s1.json"
    f2 = tmp_path / "s2.json"
    f1.write_text('{"a": 1}', encoding="utf-8")
    f2.write_text('{"a": 2}', encoding="utf-8")
    assert hash_scope_file(f1) != hash_scope_file(f2)


def test_plan_lock_hash_is_canonical() -> None:
    payload = {"b": "two", "a": "one"}
    b = canonical_json_bytes(payload)
    assert b == b'{"a":"one","b":"two"}'


# --- Happy Path Tests ---

def test_create_plan_lock_from_valid_codex_approval(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"

    task_sha = hash_task_file(ai_dir / "TASK.md")
    scope_sha = hash_scope_file(ai_dir / "SCOPE.json")
    plan_sha = hash_plan_file(ai_dir / "PLAN.md")

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": task_sha,
        "scope_sha256": scope_sha,
        "plan_sha256": plan_sha,
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["status"] == "CREATED"
    assert out["reason_code"] == "PLAN_LOCK_CREATED"
    assert (ai_dir / "PLAN_LOCK.json").exists()


def test_generated_plan_lock_validates_schema(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 0

    schema = load_schema("plan_lock.schema.json")
    instance = json.loads((ai_dir / "PLAN_LOCK.json").read_text(encoding="utf-8"))
    Draft7Validator(schema).validate(instance)


def test_create_second_run_is_no_changes(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res1 = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res1.returncode == 0
    res2 = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res2.returncode == 0
    out2 = json.loads(res2.stdout)
    assert out2["status"] == "NO_CHANGES"


def test_plan_lock_dry_run_creates_no_file(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel, "--dry-run")
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["dry_run"] is True
    assert not (ai_dir / "PLAN_LOCK.json").exists()


def test_plan_lock_stdout_is_single_json_object(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    obj = json.loads(res.stdout)
    assert isinstance(obj, dict)


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell wrapper test on Windows")
def test_plan_lock_powershell_wrapper_preserves_exit_code(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-Action", "create",
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Antigravity.DrawBeams",
        "-ApprovalFile", app_rel,
    ]
    res = subprocess.run(args, capture_output=True, text=True)
    assert res.returncode == 0
    obj = json.loads(res.stdout)
    assert obj["status"] == "CREATED"


# --- Preflight Rejections ---

def test_rejects_protected_branch(tmp_path: Path) -> None:
    repo, _, _ = init_test_module_repo(tmp_path, branch="main")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PROTECTED_BRANCH_BLOCKED"


def test_rejects_missing_module_contract(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    (mod_dir / ".ai-workflow" / "MODULE.json").unlink()
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "MODULE_WORKFLOW_MISSING"


def test_rejects_placeholder_task(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    (mod_dir / ".ai-workflow" / "TASK.md").write_text("# Task\n- Task ID:\n- Module:\n- Requested by:\n", encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "TASK_PLACEHOLDER"


def test_rejects_scope_not_ready(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    scope_p = mod_dir / ".ai-workflow" / "SCOPE.json"
    data = json.loads(scope_p.read_text(encoding="utf-8"))
    data["status"] = "DRAFT"
    scope_p.write_text(json.dumps(data), encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "SCOPE_NOT_READY"


def test_rejects_branch_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    scope_p = mod_dir / ".ai-workflow" / "SCOPE.json"
    data = json.loads(scope_p.read_text(encoding="utf-8"))
    data["work_branch"] = "task/other-branch"
    scope_p.write_text(json.dumps(data), encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "BRANCH_MISMATCH"


def test_rejects_missing_base_commit(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    scope_p = mod_dir / ".ai-workflow" / "SCOPE.json"
    data = json.loads(scope_p.read_text(encoding="utf-8"))
    data["base_commit"] = "0000000000000000000000000000000000000000"
    scope_p.write_text(json.dumps(data), encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "BASE_COMMIT_NOT_FOUND"


def test_rejects_placeholder_plan(tmp_path: Path) -> None:
    repo, mod_dir, _ = init_test_module_repo(tmp_path)
    (mod_dir / ".ai-workflow" / "PLAN.md").write_text("# Implementation Plan\n## Identity\n- Task ID:\n- Module:\n- Base commit:\n- Work branch:\n", encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/history/rev.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_PLACEHOLDER"


def test_rejects_approval_outside_history(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    bad_app = repo / "src/Antigravity.DrawBeams/.ai-workflow/plan-review.json"
    bad_app.write_text("{}", encoding="utf-8")
    res = run_plan_lock(repo, "create", "--approval-file", "src/Antigravity.DrawBeams/.ai-workflow/plan-review.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_PATH_INVALID"


def test_rejects_non_codex_reviewer(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "human",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_INVALID"


def test_rejects_non_approved_decision(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "NEEDS_CHANGES",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_NOT_APPROVED"


def test_rejects_approval_identity_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "different-task-id",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_IDENTITY_MISMATCH"


def test_rejects_task_hash_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_HASH_MISMATCH"


def test_rejects_scope_hash_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_HASH_MISMATCH"


def test_rejects_plan_hash_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_REVIEW_HASH_MISMATCH"


# --- Immutability and Verify Tests ---

def test_existing_different_plan_lock_causes_conflict(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    # Pre-write conflicting PLAN_LOCK.json
    conflicting_lock = {
        "schema_version": 1,
        "task_id": "drawbeams-fix-corridor",
        "plan_status": "APPROVED",
        "task_sha256": "differing_task_sha",
        "scope_sha256": "differing_scope_sha",
        "plan_sha256": "differing_plan_sha",
        "approved_by": "codex",
        "approved_review_run": "plan-review-run-000",
        "approved_at": "2026-08-01T00:00:00Z",
        "base_commit": base_commit,
        "amendment_count": 0
    }
    with open(ai_dir / "PLAN_LOCK.json", "w", encoding="utf-8") as f:
        json.dump(conflicting_lock, f, indent=2)

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 3
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_LOCK_CONFLICT"


def test_plan_lock_is_not_overwritten(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    conflicting_content = "ORIGINAL_CONFLICTING_CONTENT\n"
    (ai_dir / "PLAN_LOCK.json").write_text(conflicting_content, encoding="utf-8")

    res = run_plan_lock(repo, "create", "--approval-file", app_rel)
    assert res.returncode == 3
    assert (ai_dir / "PLAN_LOCK.json").read_text(encoding="utf-8") == conflicting_content


def test_verify_valid_plan_lock(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["status"] == "VERIFIED"
    assert out["reason_code"] == "PLAN_LOCK_VERIFIED"


def test_verify_detects_task_change(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    # Modify TASK.md
    (ai_dir / "TASK.md").write_text("# Modified Task\n", encoding="utf-8")

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["reason_code"] == "TASK_CHANGED"


def test_verify_detects_scope_change(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    # Modify SCOPE.json
    scope_p = ai_dir / "SCOPE.json"
    s_data = json.loads(scope_p.read_text(encoding="utf-8"))
    s_data["max_files_changed"] = 99
    scope_p.write_text(json.dumps(s_data), encoding="utf-8")

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["reason_code"] == "SCOPE_CHANGED"


def test_verify_detects_plan_change(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    # Modify PLAN.md
    (ai_dir / "PLAN.md").write_text("# Modified Plan\n", encoding="utf-8")

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_CHANGED"


def test_verify_detects_branch_change(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    # Switch branch
    subprocess.run(["git", "checkout", "-b", "task/other-branch"], cwd=repo, check=True, capture_output=True)

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["reason_code"] == "BRANCH_MISMATCH"


def test_verify_performs_no_write(tmp_path: Path) -> None:
    repo, mod_dir, base_commit = init_test_module_repo(tmp_path)
    ai_dir = mod_dir / ".ai-workflow"
    app_rel = "src/Antigravity.DrawBeams/.ai-workflow/history/plan-review-run-001.json"

    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": "task/drawbeams-fix-corridor",
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    run_plan_lock(repo, "create", "--approval-file", app_rel)

    lock_file = ai_dir / "PLAN_LOCK.json"
    mtime_before = lock_file.stat().st_mtime

    res = run_plan_lock(repo, "verify")
    assert res.returncode == 0
    assert lock_file.stat().st_mtime == mtime_before
