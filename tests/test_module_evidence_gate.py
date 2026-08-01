"""
test_module_evidence_gate.py — Unit, integration, and security tests for evidence_gate.py & evidence_gate.ps1
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "evidence_gate.py"
PLAN_LOCK_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "plan_lock.py"
PS1_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "evidence_gate.ps1"
SCHEMA_DIR = REPO_ROOT / "schemas" / "module-workflow"

sys.path.insert(0, str(REPO_ROOT / "skills" / "module-workflow" / "scripts"))
from module_contract_utils import (
    hash_plan_file,
    hash_scope_file,
    hash_task_file,
)


def load_schema(name: str) -> dict:
    with open(SCHEMA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def setup_locked_module_repo(tmp_path: Path, branch: str = "task/drawbeams-fix-corridor") -> Tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-b", branch], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    module_rel = "src/Antigravity.DrawBeams"
    mod_dir = repo / module_rel
    ai_dir = mod_dir / ".ai-workflow"
    sandbox_dir = mod_dir / ".sandbox"
    history_dir = ai_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    # Base commit
    subprocess.run(["git", "commit", "--allow-empty", "-m", "base"], cwd=repo, check=True, capture_output=True)
    res_base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
    base_commit = res_base.stdout.strip()

    # Templates
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
    (ai_dir / "TASK.md").write_text(f"# Task\n- Task ID: drawbeams-fix-corridor\n- Module: antigravity-drawbeams\n- Requested by: user\n\n## Goal\nFix corridor bug\n", encoding="utf-8")

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
    (ai_dir / "PLAN.md").write_text(f"# Implementation Plan\n## Identity\n- Task ID: drawbeams-fix-corridor\n- Module: antigravity-drawbeams\n- Base commit: {base_commit}\n- Work branch: {branch}\n\n## Proposed changes\nFix beam selection\n\n## Test plan\nRun tests\n\n## Acceptance criteria\nTests pass\n", encoding="utf-8")

    # Source files
    src_file = mod_dir / "CreateBeamCommand.cs"
    src_file.write_text("// CreateBeamCommand\npublic class CreateBeamCommand {\n    public void Execute() {\n        var item = GetSelection();\n    }\n}\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add contracts and source"], cwd=repo, check=True, capture_output=True)

    # Create approval and PLAN_LOCK.json
    app_rel = f"{module_rel}/.ai-workflow/history/plan-review-run-001.json"
    approval_data = {
        "schema_version": 1,
        "review_type": "PLAN",
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "review_run_id": "plan-review-run-001",
        "reviewer": "codex",
        "decision": "APPROVED",
        "reviewed_branch": branch,
        "base_commit": base_commit,
        "task_sha256": hash_task_file(ai_dir / "TASK.md"),
        "scope_sha256": hash_scope_file(ai_dir / "SCOPE.json"),
        "plan_sha256": hash_plan_file(ai_dir / "PLAN.md"),
        "reviewed_at": "2026-08-01T02:00:00Z",
        "findings": []
    }
    with open(repo / app_rel, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    res_lock = subprocess.run([
        sys.executable, str(PLAN_LOCK_SCRIPT), "create",
        "--repository-root", str(repo),
        "--module-root", module_rel,
        "--approval-file", app_rel
    ], capture_output=True, text=True)
    assert res_lock.returncode == 0, res_lock.stderr

    # Create evidence request in sandbox
    req_data = {
        "schema_version": 1,
        "task_id": "drawbeams-fix-corridor",
        "module_id": "antigravity-drawbeams",
        "files_to_verify": [f"{module_rel}/CreateBeamCommand.cs"],
        "symbols_to_verify": [{"symbol": "CreateBeamCommand", "paths": [f"{module_rel}/**/*.cs"]}],
        "diagnosis": "The command reads the selected element before validating input.",
        "diagnosis_sources": [{"path": f"{module_rel}/CreateBeamCommand.cs", "line_start": 1, "line_end": 5, "reason": "Input consumed before validation."}]
    }
    with open(sandbox_dir / "evidence_request.json", "w", encoding="utf-8") as f:
        json.dump(req_data, f, indent=2)

    return repo, mod_dir, base_commit


def run_evidence_gate(repo: Path, action: str, *extra_args: str, module_rel: str = "src/Antigravity.DrawBeams") -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(EVIDENCE_SCRIPT),
        action,
        "--repository-root", str(repo),
        "--module-root", module_rel,
        *extra_args,
    ]
    return subprocess.run(args, capture_output=True, text=True)


# --- Happy Path Tests ---

def test_collect_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["status"] == "READY"
    assert out["reason_code"] == "EVIDENCE_READY"
    assert out["ready_to_implement"] is True
    assert (mod_dir / ".ai-workflow" / "EVIDENCE.json").exists()


def test_generated_evidence_validates_schema(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 0

    schema = load_schema("evidence.schema.json")
    instance = json.loads((mod_dir / ".ai-workflow" / "EVIDENCE.json").read_text(encoding="utf-8"))
    Draft7Validator(schema).validate(instance)


def test_required_scope_files_are_automatically_verified(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 0
    instance = json.loads((mod_dir / ".ai-workflow" / "EVIDENCE.json").read_text(encoding="utf-8"))
    verified_paths = [f["path"] for f in instance["files_verified"]]
    assert "src/Antigravity.DrawBeams/CreateBeamCommand.cs" in verified_paths


def test_required_scope_symbols_are_automatically_verified(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 0
    instance = json.loads((mod_dir / ".ai-workflow" / "EVIDENCE.json").read_text(encoding="utf-8"))
    symbols = [s["symbol"] for s in instance["symbols_verified"]]
    assert "CreateBeamCommand" in symbols


def test_diagnosis_source_hashes_are_generated(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 0
    instance = json.loads((mod_dir / ".ai-workflow" / "EVIDENCE.json").read_text(encoding="utf-8"))
    ds = instance["diagnosis_sources"][0]
    assert "file_sha256" in ds and len(ds["file_sha256"]) == 64
    assert "excerpt_sha256" in ds and len(ds["excerpt_sha256"]) == 64


def test_source_snapshot_is_deterministic(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res1 = run_evidence_gate(repo, "collect")
    out1 = json.loads(res1.stdout)

    # Re-run verify or collect to check snapshot consistency
    res2 = run_evidence_gate(repo, "verify")
    out2 = json.loads(res2.stdout)
    assert out1["source_snapshot_sha256"] == out2["source_snapshot_sha256"]


def test_collect_second_run_is_no_changes(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    res1 = run_evidence_gate(repo, "collect")
    assert res1.returncode == 0
    res2 = run_evidence_gate(repo, "collect")
    assert res2.returncode == 0
    out2 = json.loads(res2.stdout)
    assert out2["status"] == "NO_CHANGES"


def test_collect_dry_run_creates_no_file(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect", "--dry-run")
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["dry_run"] is True
    assert not (mod_dir / ".ai-workflow" / "EVIDENCE.json").exists()


def test_stdout_is_single_json_object(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    res = run_evidence_gate(repo, "collect")
    obj = json.loads(res.stdout)
    assert isinstance(obj, dict)


# --- Scope and Context Tests ---

def test_collect_requires_plan_lock(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    (mod_dir / ".ai-workflow" / "PLAN_LOCK.json").unlink()
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_LOCK_REQUIRED"


def test_collect_rejects_stale_plan_lock(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    (mod_dir / ".ai-workflow" / "TASK.md").write_text("# Changed Task\n", encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_LOCK_STALE"


def test_collect_rejects_request_outside_sandbox(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    bad_req = mod_dir / ".ai-workflow" / "evidence_request.json"
    bad_req.write_text("{}", encoding="utf-8")
    res = run_evidence_gate(repo, "collect", "--request-file", "src/Antigravity.DrawBeams/.ai-workflow/evidence_request.json")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "EVIDENCE_REQUEST_PATH_INVALID"


def test_collect_rejects_request_task_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["task_id"] = "different-task"
    req_p.write_text(json.dumps(r_data), encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "EVIDENCE_IDENTITY_MISMATCH"


def test_collect_rejects_request_module_mismatch(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["module_id"] = "different-module"
    req_p.write_text(json.dumps(r_data), encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "EVIDENCE_IDENTITY_MISMATCH"


def test_collect_rejects_out_of_scope_file(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/OtherModule/File.cs"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_collect_rejects_forbidden_file(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = [".github/workflows/ci.yml"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_collect_rejects_source_dirty_before_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    # Modify source file before evidence collection
    (mod_dir / "CreateBeamCommand.cs").write_text("// edited before evidence\n", encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "SOURCE_CHANGED_BEFORE_EVIDENCE"


# --- Insufficient Evidence Tests ---

def test_missing_required_file_produces_not_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/Antigravity.DrawBeams/NonExistent.cs"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")
    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_untracked_required_file_produces_not_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    untracked = mod_dir / "UntrackedFile.cs"
    untracked.write_text("// untracked\n", encoding="utf-8")
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/Antigravity.DrawBeams/UntrackedFile.cs"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_missing_symbol_produces_not_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["symbols_to_verify"] = [{"symbol": "NonExistentSymbol", "paths": ["src/Antigravity.DrawBeams/**/*.cs"]}]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_invalid_diagnosis_line_range_produces_not_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["diagnosis_sources"][0]["line_start"] = 10
    r_data["diagnosis_sources"][0]["line_end"] = 5
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_diagnosis_line_outside_file_produces_not_ready_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["diagnosis_sources"][0]["line_start"] = 1
    r_data["diagnosis_sources"][0]["line_end"] = 9999
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


def test_placeholder_diagnosis_rejected(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["diagnosis"] = "TODO replace diagnosis here placeholder"
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["ready_to_implement"] is False


# --- Evidence Lifecycle Tests ---

def test_failed_evidence_can_be_replaced(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"

    # Make first run fail
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["symbols_to_verify"] = [{"symbol": "MissingSym", "paths": ["src/**/*.cs"]}]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res1 = run_evidence_gate(repo, "collect")
    assert res1.returncode == 5

    # Fix request and run again
    r_data["symbols_to_verify"] = [{"symbol": "CreateBeamCommand", "paths": ["src/**/*.cs"]}]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res2 = run_evidence_gate(repo, "collect")
    assert res2.returncode == 0
    out2 = json.loads(res2.stdout)
    assert out2["ready_to_implement"] is True


def test_ready_evidence_is_immutable(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    res1 = run_evidence_gate(repo, "collect")
    assert res1.returncode == 0

    # Modify evidence request after ready evidence exists
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["diagnosis"] = "New completely different diagnosis description."
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res2 = run_evidence_gate(repo, "collect")
    assert res2.returncode == 3
    out2 = json.loads(res2.stdout)
    assert out2["reason_code"] == "EVIDENCE_LOCKED"


def test_identical_ready_evidence_is_no_changes(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    res1 = run_evidence_gate(repo, "collect")
    assert res1.returncode == 0
    res2 = run_evidence_gate(repo, "collect")
    assert res2.returncode == 0
    out2 = json.loads(res2.stdout)
    assert out2["status"] == "NO_CHANGES"


def test_different_ready_evidence_is_locked(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["diagnosis"] = "Altered diagnosis text long enough to pass length rule."
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 3


# --- Verify Tests ---

def test_verify_ready_evidence(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")
    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["status"] == "VERIFIED"


def test_verify_detects_source_snapshot_change(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    # Modify source file after evidence
    (mod_dir / "CreateBeamCommand.cs").write_text("// Modified after evidence\n", encoding="utf-8")

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    assert out["reason_code"] == "SOURCE_SNAPSHOT_CHANGED"


def test_verify_detects_verified_file_change(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    (mod_dir / "CreateBeamCommand.cs").write_text("// Change\n", encoding="utf-8")

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 5


def test_verify_detects_diagnosis_excerpt_change(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    (mod_dir / "CreateBeamCommand.cs").write_text("// Excerpt edited\n", encoding="utf-8")

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 5


def test_verify_detects_symbol_removed(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    (mod_dir / "CreateBeamCommand.cs").write_text("// Symbol removed\n", encoding="utf-8")

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 5


def test_verify_detects_plan_lock_change(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    (mod_dir / ".ai-workflow" / "TASK.md").write_text("# Modified Task\n", encoding="utf-8")

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 5


def test_verify_does_not_modify_evidence(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    run_evidence_gate(repo, "collect")

    ev_file = mod_dir / ".ai-workflow" / "EVIDENCE.json"
    mtime_before = ev_file.stat().st_mtime

    res = run_evidence_gate(repo, "verify")
    assert res.returncode == 0
    assert ev_file.stat().st_mtime == mtime_before


# --- Security Tests (Section 42) ---

def test_request_cannot_pass_shell_commands(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/Antigravity.DrawBeams/CreateBeamCommand.cs; echo hacked"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    # Path pattern in script rejects characters like ;
    assert res.returncode in (2, 5)


def test_symbol_searched_literal_not_regex(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["symbols_to_verify"] = [{"symbol": ".*Command.*", "paths": ["src/**/*.cs"]}]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode == 5
    out = json.loads(res.stdout)
    # Literal regex pattern ".*Command.*" will not match literal string unless present
    assert out["ready_to_implement"] is False


def test_path_with_shell_metacharacters_not_executed(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/Antigravity.DrawBeams/CreateBeamCommand.cs & dir"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)


def test_absolute_windows_path_rejected(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["C:/Windows/System32/cmd.exe"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)


def test_unc_path_rejected(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["\\\\server\\share\\file.cs"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)


def test_posix_absolute_path_rejected(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["/etc/passwd"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    req_p = mod_dir / ".sandbox" / "evidence_request.json"
    r_data = json.loads(req_p.read_text(encoding="utf-8"))
    r_data["files_to_verify"] = ["src/Antigravity.DrawBeams/../../secret.txt"]
    req_p.write_text(json.dumps(r_data), encoding="utf-8")

    res = run_evidence_gate(repo, "collect")
    assert res.returncode in (2, 5)


# --- Wrappers Tests ---

@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell wrapper test on Windows")
def test_evidence_powershell_wrapper_passes_args(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-Action", "collect",
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Antigravity.DrawBeams"
    ]
    res = subprocess.run(args, capture_output=True, text=True)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["status"] == "READY"


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell wrapper test on Windows")
def test_evidence_powershell_wrapper_preserves_exit_code(tmp_path: Path) -> None:
    repo, mod_dir, _ = setup_locked_module_repo(tmp_path)
    # Remove PLAN_LOCK to force exit code 2
    (mod_dir / ".ai-workflow" / "PLAN_LOCK.json").unlink()

    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-Action", "collect",
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Antigravity.DrawBeams"
    ]
    res = subprocess.run(args, capture_output=True, text=True)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["reason_code"] == "PLAN_LOCK_REQUIRED"


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell wrapper test on Windows")
def test_evidence_powershell_wrapper_stdout_is_json(tmp_path: Path) -> None:
    repo, _, _ = setup_locked_module_repo(tmp_path)
    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-Action", "collect",
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Antigravity.DrawBeams"
    ]
    res = subprocess.run(args, capture_output=True, text=True)
    obj = json.loads(res.stdout)
    assert isinstance(obj, dict)
