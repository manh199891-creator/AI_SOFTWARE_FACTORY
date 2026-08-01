"""
test_module_workflow_bootstrap.py — Phase B tests for module_bootstrap.py

Every test uses a temporary Git repository; no test touches the real
AI_SOFTWARE_FACTORY repository or any production module.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

# ---------------------------------------------------------------------------
# Locate the script under test
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "module_bootstrap.py"
PS1_SCRIPT = REPO_ROOT / "skills" / "module-workflow" / "scripts" / "module_init.ps1"
SCHEMA_DIR = REPO_ROOT / "schemas" / "module-workflow"


def load_schema(name: str) -> dict:
    with open(SCHEMA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Temporary Git repository fixture
# ---------------------------------------------------------------------------


def init_temp_repo(
    tmp_path: Path,
    branch: str = "task/test-init",
    module_rel: str = "src/Sample.DrawBeams",
    csproj_rel: str = "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
) -> tuple[Path, Path, Path]:
    """
    Create a minimal Git repo in tmp_path.

    Returns (repo_root, module_abs, csproj_abs).
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", branch], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    module_abs = repo / module_rel
    module_abs.mkdir(parents=True)
    csproj_abs = repo / csproj_rel
    csproj_abs.write_text('<Project Sdk="Microsoft.NET.Sdk" />\n', encoding="utf-8")

    # Initial commit so the branch is real
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, capture_output=True)

    return repo, module_abs, csproj_abs


def run_bootstrap(
    repo: Path,
    *extra_args: str,
    module_rel: str = "src/Sample.DrawBeams",
    csproj_rel: str = "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
    module_id: str = "sample.drawbeams",
    module_name: str = "Sample.DrawBeams",
    platform_: str = "revit",
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(BOOTSTRAP_SCRIPT),
        "--repository-root", str(repo),
        "--module-root", module_rel,
        "--module-id", module_id,
        "--module-name", module_name,
        "--project-file", csproj_rel,
        "--platform", platform_,
        *extra_args,
    ]
    return subprocess.run(args, capture_output=True, text=True)


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# 20.1 Happy path
# ---------------------------------------------------------------------------


def test_bootstrap_creates_expected_tree(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo)
    assert result.returncode == 0, result.stderr
    out = parse_stdout(result)
    assert out["status"] == "CREATED"

    expected_files = [
        module_abs / ".ai-workflow" / "MODULE.json",
        module_abs / ".ai-workflow" / "TASK.md",
        module_abs / ".ai-workflow" / "SCOPE.json",
        module_abs / ".ai-workflow" / "REVIEW.md",
        module_abs / ".ai-workflow" / "history" / ".gitkeep",
        module_abs / ".sandbox" / "README.md",
    ]
    for f in expected_files:
        assert f.exists(), f"Missing expected file: {f}"

    expected_dirs = [
        module_abs / ".sandbox" / "bin",
        module_abs / ".sandbox" / "obj",
        module_abs / ".sandbox" / "addin",
        module_abs / ".sandbox" / "test-models",
        module_abs / ".sandbox" / "logs",
        module_abs / ".sandbox" / "results",
    ]
    for d in expected_dirs:
        assert d.is_dir(), f"Missing expected directory: {d}"


def test_generated_module_json_validates_phase_a_schema(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)
    module_json_path = module_abs / ".ai-workflow" / "MODULE.json"
    assert module_json_path.exists()
    with open(module_json_path, encoding="utf-8") as f:
        instance = json.load(f)
    schema = load_schema("module.schema.json")
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema).validate(instance)


def test_generated_scope_json_validates_phase_a_schema(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)
    scope_path = module_abs / ".ai-workflow" / "SCOPE.json"
    assert scope_path.exists()
    with open(scope_path, encoding="utf-8") as f:
        instance = json.load(f)
    schema = load_schema("scope.schema.json")
    Draft7Validator.check_schema(schema)
    # scope.schema.json rejects "main" and "master" work_branch via `not` enum.
    # The placeholder uses "task/replace-task-id" which is fine.
    Draft7Validator(schema).validate(instance)
    assert instance["status"] == "DRAFT"
    assert instance["base_commit"] == "0" * 40


def test_generated_markdown_matches_canonical_templates(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)

    template_base = REPO_ROOT / "templates" / "module-workflow"
    for rel in [
        ".ai-workflow/TASK.md",
        ".ai-workflow/REVIEW.md",
        ".sandbox/README.md",
    ]:
        generated = (module_abs / rel).read_text(encoding="utf-8")
        canonical = (template_base / rel).read_text(encoding="utf-8")
        assert generated == canonical, f"Content mismatch for {rel}"


def test_sandbox_generated_files_are_not_created(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)
    forbidden = [
        module_abs / ".ai-workflow" / "PLAN_LOCK.json",
        module_abs / ".ai-workflow" / "EVIDENCE.json",
        module_abs / ".ai-workflow" / "DELIVERY.json",
        module_abs / ".sandbox" / "manifest.json",
    ]
    for f in forbidden:
        assert not f.exists(), f"Must not be created: {f}"

    # No DLL or PDB
    for ext in (".dll", ".pdb"):
        found = list((module_abs / ".sandbox").rglob(f"*{ext}"))
        assert not found, f"Unexpected {ext} file: {found}"


def test_module_gitignore_managed_block_created(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)
    gi = (module_abs / ".gitignore").read_text(encoding="utf-8")
    assert "# BEGIN AI MODULE WORKFLOW" in gi
    assert "# END AI MODULE WORKFLOW" in gi
    assert ".sandbox/*" in gi
    assert "!.sandbox/README.md" in gi


def test_existing_gitignore_content_is_preserved(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    existing = "# My custom rules\n*.user\n*.suo\n"
    (module_abs / ".gitignore").write_text(existing, encoding="utf-8")
    run_bootstrap(repo)
    gi = (module_abs / ".gitignore").read_text(encoding="utf-8")
    assert "# My custom rules" in gi
    assert "*.user" in gi
    assert "*.suo" in gi
    assert "# BEGIN AI MODULE WORKFLOW" in gi


def test_bootstrap_second_run_is_no_changes(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    r1 = run_bootstrap(repo)
    assert r1.returncode == 0
    r2 = run_bootstrap(repo)
    assert r2.returncode == 0
    out = parse_stdout(r2)
    assert out["status"] == "NO_CHANGES"
    assert out["reason_code"] == "BOOTSTRAP_ALREADY_CURRENT"


def test_second_run_does_not_duplicate_gitignore_block(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    run_bootstrap(repo)
    run_bootstrap(repo)
    gi = (module_abs / ".gitignore").read_text(encoding="utf-8")
    assert gi.count("# BEGIN AI MODULE WORKFLOW") == 1
    assert gi.count("# END AI MODULE WORKFLOW") == 1


def test_dry_run_creates_no_files(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, "--dry-run")
    assert result.returncode == 0
    out = parse_stdout(result)
    assert out["status"] == "DRY_RUN"
    assert out["dry_run"] is True
    # Nothing created
    assert not (module_abs / ".ai-workflow").exists()
    assert not (module_abs / ".sandbox").exists()
    assert not (module_abs / ".gitignore").exists()


def test_stdout_is_single_valid_json_object(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo)
    # Must parse as a single JSON object
    obj = json.loads(result.stdout)
    assert isinstance(obj, dict)
    assert "status" in obj
    assert "schema_version" in obj
    assert "reason_code" in obj
    # Exactly one JSON object — no extra output
    assert result.stdout.strip() == json.dumps(obj, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 20.2 Input/context rejection
# ---------------------------------------------------------------------------


def _assert_no_workflow_created(module_abs: Path) -> None:
    assert not (module_abs / ".ai-workflow").exists(), ".ai-workflow must not be created on failure"
    assert not (module_abs / ".sandbox").exists(), ".sandbox must not be created on failure"
    assert not (module_abs / ".gitignore").exists(), ".gitignore must not be partially created"


def test_rejects_protected_main_branch_before_writes(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path, branch="main")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "PROTECTED_BRANCH_BLOCKED"
    _assert_no_workflow_created(module_abs)


def test_rejects_protected_master_branch_before_writes(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path, branch="master")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "PROTECTED_BRANCH_BLOCKED"
    _assert_no_workflow_created(module_abs)


def test_rejects_absolute_module_root(tmp_path: Path) -> None:
    repo, module_abs, csproj_abs = init_temp_repo(tmp_path)
    args = [
        sys.executable, str(BOOTSTRAP_SCRIPT),
        "--repository-root", str(repo),
        "--module-root", str(module_abs),   # absolute!
        "--module-id", "sample.drawbeams",
        "--module-name", "Sample.DrawBeams",
        "--project-file", "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
        "--platform", "revit",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] in ("INVALID_RELATIVE_PATH", "PATH_ESCAPES_REPOSITORY")


def test_rejects_parent_traversal_module_root(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, module_rel="src/../../../etc")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "INVALID_RELATIVE_PATH"


def test_rejects_missing_module_root(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, module_rel="src/Nonexistent.Module")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "MODULE_ROOT_NOT_FOUND"


def test_rejects_missing_project_file(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, csproj_rel="src/Sample.DrawBeams/Missing.csproj")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "PROJECT_FILE_NOT_FOUND"


def test_rejects_project_file_outside_module(tmp_path: Path) -> None:
    repo, module_abs, csproj_abs = init_temp_repo(tmp_path)
    # Create a csproj outside the module dir
    outside = repo / "other" / "Other.csproj"
    outside.parent.mkdir(parents=True)
    outside.write_text('<Project />', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add outside"], cwd=repo, capture_output=True)
    result = run_bootstrap(repo, csproj_rel="other/Other.csproj")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "PROJECT_FILE_OUTSIDE_MODULE"


def test_rejects_invalid_module_id(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, module_id="INVALID MODULE ID!")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "INVALID_MODULE_ID"


def test_rejects_invalid_workflow_version(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, "--workflow-version", "not-a-version")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "INVALID_WORKFLOW_VERSION"


def test_rejects_invalid_dll_name(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    result = run_bootstrap(repo, "--dll-name", "no_extension_exe")
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "INVALID_DLL_NAME"


def test_rejects_non_git_repository(tmp_path: Path) -> None:
    # Plain directory, no git
    plain_repo = tmp_path / "plain"
    plain_repo.mkdir()
    module_dir = plain_repo / "src" / "Sample"
    module_dir.mkdir(parents=True)
    csproj = module_dir / "Sample.csproj"
    csproj.write_text('<Project />')
    args = [
        sys.executable, str(BOOTSTRAP_SCRIPT),
        "--repository-root", str(plain_repo),
        "--module-root", "src/Sample",
        "--module-id", "sample",
        "--module-name", "Sample",
        "--project-file", "src/Sample/Sample.csproj",
        "--platform", "dotnet",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "NOT_A_GIT_REPOSITORY"


def test_rejects_repository_root_mismatch(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    # Pass a subdirectory as RepositoryRoot — git root will be the parent
    subdir = repo / "src" / "Sample.DrawBeams"
    args = [
        sys.executable, str(BOOTSTRAP_SCRIPT),
        "--repository-root", str(subdir),
        "--module-root", "src/Sample.DrawBeams",
        "--module-id", "sample.drawbeams",
        "--module-name", "Sample.DrawBeams",
        "--project-file", "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
        "--platform", "revit",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] in ("NOT_A_GIT_REPOSITORY", "REPOSITORY_ROOT_MISMATCH")


# ---------------------------------------------------------------------------
# 20.3 Conflict / rollback
# ---------------------------------------------------------------------------


def test_existing_different_module_json_causes_conflict(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    ai_wf = module_abs / ".ai-workflow"
    ai_wf.mkdir()
    (ai_wf / "MODULE.json").write_text('{"different": "content"}', encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 3
    out = parse_stdout(result)
    assert out["reason_code"] == "BOOTSTRAP_CONFLICT"


def test_existing_different_task_md_causes_conflict(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    ai_wf = module_abs / ".ai-workflow"
    ai_wf.mkdir()
    (ai_wf / "TASK.md").write_text("# Different content\n", encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 3
    out = parse_stdout(result)
    assert out["reason_code"] == "BOOTSTRAP_CONFLICT"


def test_invalid_gitignore_managed_block_causes_failure(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Write BEGIN without END
    (module_abs / ".gitignore").write_text("# BEGIN AI MODULE WORKFLOW\nbin/\n", encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "GITIGNORE_MANAGED_BLOCK_INVALID"


def test_conflict_detection_occurs_before_any_write(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Place conflict only in SCOPE.json (last in list) but NOT in MODULE.json
    ai_wf = module_abs / ".ai-workflow"
    ai_wf.mkdir()
    (ai_wf / "SCOPE.json").write_text('{"conflicting": true}', encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 3
    # MODULE.json must not have been created (proves no partial write)
    assert not (ai_wf / "MODULE.json").exists()


def test_write_failure_rolls_back_created_files(tmp_path: Path) -> None:
    """
    Simulate write failure by placing a plain *file* at the .sandbox path.
    The bootstrapper will fail when trying to mkdir(.sandbox/bin) because
    .sandbox is a file — triggering atomic rollback.
    """
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Place a plain file where .sandbox directory must be created
    (module_abs / ".sandbox").write_text("blocking file", encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 4, f"Expected exit 4, got {result.returncode}\n{result.stderr}"
    out = parse_stdout(result)
    assert out["reason_code"] == "BOOTSTRAP_WRITE_FAILED"
    # .ai-workflow must have been rolled back — no partial state left
    assert not (module_abs / ".ai-workflow").exists(), \
        ".ai-workflow must be rolled back after write failure"


def test_preexisting_files_are_never_deleted_during_rollback(tmp_path: Path) -> None:
    """
    A pre-existing source file inside the module must survive even when a
    write-failure rollback occurs. We trigger the failure via the .sandbox
    blocker trick (pre-existing .sandbox file prevents mkdir(.sandbox/bin)).
    """
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Pre-existing source file — must survive rollback
    pre_existing = module_abs / "MyExistingClass.cs"
    pre_existing.write_text("// existing\n", encoding="utf-8")
    # Block .sandbox to force write failure → rollback
    (module_abs / ".sandbox").write_text("blocker", encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 4
    # Pre-existing source file must be intact
    assert pre_existing.exists()
    assert pre_existing.read_text(encoding="utf-8") == "// existing\n"
    # The .sandbox blocker must still be a file (not deleted by rollback)
    assert (module_abs / ".sandbox").is_file()


# ---------------------------------------------------------------------------
# Rollback restore tests — direct BootstrapWriter unit tests
# ---------------------------------------------------------------------------


def _load_bootstrap_module():
    """Import module_bootstrap.py via importlib for direct function/class access."""
    spec = importlib.util.spec_from_file_location(
        "module_bootstrap", str(BOOTSTRAP_SCRIPT)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_temp_template_root(tmp_path: Path) -> Path:
    """
    Create a minimal but complete template root under tmp_path,
    mirroring the structure of templates/module-workflow/.
    Returns the factory root (parent of templates/).
    """
    real_tmpl = REPO_ROOT / "templates" / "module-workflow"
    factory = tmp_path / "factory"
    tmpl_dest = factory / "templates" / "module-workflow"
    tmpl_dest.mkdir(parents=True)

    # Copy all templates from the real location
    for item in real_tmpl.rglob("*"):
        if item.is_file():
            rel = item.relative_to(real_tmpl)
            dest = tmpl_dest / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)

    return factory


def test_writer_rollback_restores_modified_file_bytes(tmp_path: Path) -> None:
    """BootstrapWriter.rollback() restores overwritten file to original bytes."""
    mod = _load_bootstrap_module()
    writer = mod.BootstrapWriter()

    # Create pre-existing .gitignore with known bytes
    gitignore = tmp_path / ".gitignore"
    original_bytes = b"# Custom rule\n*.user\n"
    gitignore.write_bytes(original_bytes)

    # Overwrite it via writer
    writer.overwrite_existing_file(gitignore, "# Changed content\nbin/\nobj/\n")

    # Verify file was actually changed
    assert gitignore.read_bytes() != original_bytes

    # Rollback must restore byte-for-byte
    writer.rollback()
    assert gitignore.read_bytes() == original_bytes


def test_writer_rollback_removes_created_artifacts_only(tmp_path: Path) -> None:
    """
    After rollback:
    - new_file is deleted
    - new_directory is deleted (if empty after file removal)
    - pre-existing source file is untouched
    - pre-existing directory is untouched
    - pre-existing .gitignore is restored byte-for-byte
    """
    mod = _load_bootstrap_module()
    writer = mod.BootstrapWriter()

    # Pre-existing items
    pre_src = tmp_path / "MyClass.cs"
    pre_src.write_text("// existing source\n", encoding="utf-8")
    pre_dir = tmp_path / "existing_dir"
    pre_dir.mkdir()
    gitignore = tmp_path / ".gitignore"
    original_bytes = b"# original gitignore\n"
    gitignore.write_bytes(original_bytes)

    # Create new artifacts via writer
    new_dir = tmp_path / "new_dir"
    writer.mkdir(new_dir)
    new_file = new_dir / "new_file.txt"
    writer.write_new_file(new_file, "new content")
    writer.overwrite_existing_file(gitignore, "# changed\n")

    # Verify artifacts were created / modified
    assert new_file.exists()
    assert new_dir.exists()
    assert gitignore.read_bytes() != original_bytes

    # Rollback
    writer.rollback()

    # new_file must be deleted
    assert not new_file.exists()
    # new_directory must be deleted (empty after file removal)
    assert not new_dir.exists()
    # pre-existing source file untouched
    assert pre_src.exists()
    assert pre_src.read_text(encoding="utf-8") == "// existing source\n"
    # pre-existing directory untouched
    assert pre_dir.exists()
    # pre-existing .gitignore restored byte-for-byte
    assert gitignore.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# Canonical template completeness tests (importlib + capsys)
# ---------------------------------------------------------------------------


def test_missing_canonical_module_template_rejected(tmp_path: Path, capsys) -> None:
    """Missing MODULE.json template file must cause CANONICAL_TEMPLATE_MISSING."""
    mod = _load_bootstrap_module()
    tmpl_root = _make_temp_template_root(tmp_path / "t1")
    # Remove MODULE.json template
    module_tmpl = tmpl_root / "templates" / "module-workflow" / ".ai-workflow" / "MODULE.json"
    module_tmpl.unlink()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_canonical_templates(tmpl_root)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["reason_code"] == "CANONICAL_TEMPLATE_MISSING"


def test_missing_canonical_scope_template_rejected(tmp_path: Path, capsys) -> None:
    """Missing SCOPE.json template file must cause CANONICAL_TEMPLATE_MISSING."""
    mod = _load_bootstrap_module()
    tmpl_root = _make_temp_template_root(tmp_path / "t2")
    scope_tmpl = tmpl_root / "templates" / "module-workflow" / ".ai-workflow" / "SCOPE.json"
    scope_tmpl.unlink()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_canonical_templates(tmpl_root)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["reason_code"] == "CANONICAL_TEMPLATE_MISSING"


def test_invalid_canonical_json_template_rejected(tmp_path: Path, capsys) -> None:
    """Unparseable JSON in canonical template must cause CANONICAL_TEMPLATE_MISSING."""
    mod = _load_bootstrap_module()
    tmpl_root = _make_temp_template_root(tmp_path / "t3")
    module_tmpl = tmpl_root / "templates" / "module-workflow" / ".ai-workflow" / "MODULE.json"
    module_tmpl.write_text("{ INVALID JSON !!!", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_canonical_templates(tmpl_root)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["reason_code"] == "CANONICAL_TEMPLATE_MISSING"


# ---------------------------------------------------------------------------
# Duplicate gitignore marker tests
# ---------------------------------------------------------------------------


def test_duplicate_gitignore_managed_blocks_rejected(tmp_path: Path) -> None:
    """Two complete BEGIN/END blocks must cause GITIGNORE_MANAGED_BLOCK_INVALID."""
    repo, module_abs, _ = init_temp_repo(tmp_path)
    block = "# BEGIN AI MODULE WORKFLOW\nbin/\n# END AI MODULE WORKFLOW\n"
    (module_abs / ".gitignore").write_text(block + "\n" + block, encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "GITIGNORE_MANAGED_BLOCK_INVALID"
    assert not (module_abs / ".ai-workflow").exists()
    assert not (module_abs / ".sandbox").exists()


def test_duplicate_begin_marker_rejected(tmp_path: Path) -> None:
    """Two BEGIN markers (one END) must cause GITIGNORE_MANAGED_BLOCK_INVALID."""
    repo, module_abs, _ = init_temp_repo(tmp_path)
    content = (
        "# BEGIN AI MODULE WORKFLOW\n"
        "bin/\n"
        "# BEGIN AI MODULE WORKFLOW\n"
        "# END AI MODULE WORKFLOW\n"
    )
    (module_abs / ".gitignore").write_text(content, encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "GITIGNORE_MANAGED_BLOCK_INVALID"
    assert not (module_abs / ".ai-workflow").exists()


def test_duplicate_end_marker_rejected(tmp_path: Path) -> None:
    """One BEGIN, two END markers must cause GITIGNORE_MANAGED_BLOCK_INVALID."""
    repo, module_abs, _ = init_temp_repo(tmp_path)
    content = (
        "# BEGIN AI MODULE WORKFLOW\n"
        "bin/\n"
        "# END AI MODULE WORKFLOW\n"
        "# END AI MODULE WORKFLOW\n"
    )
    (module_abs / ".gitignore").write_text(content, encoding="utf-8")
    result = run_bootstrap(repo)
    assert result.returncode == 2
    out = parse_stdout(result)
    assert out["reason_code"] == "GITIGNORE_MANAGED_BLOCK_INVALID"
    assert not (module_abs / ".ai-workflow").exists()


# ---------------------------------------------------------------------------
# Dry-run output tests — gitignore semantics
# ---------------------------------------------------------------------------


def test_dry_run_existing_gitignore_not_reported_as_created(tmp_path: Path) -> None:
    """
    When .gitignore already exists and will be updated, dry-run must report
    gitignore_updated=true but NOT include .gitignore in files_created.
    Semantics must match the real run.
    """
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Pre-existing .gitignore — will be updated (managed block appended)
    (module_abs / ".gitignore").write_text("# existing rules\n*.user\n", encoding="utf-8")
    result = run_bootstrap(repo, "--dry-run")
    assert result.returncode == 0
    out = parse_stdout(result)
    assert out["status"] == "DRY_RUN"
    assert out["gitignore_updated"] is True
    # .gitignore must NOT be in files_created (it pre-existed)
    gitignore_rel = str((module_abs / ".gitignore").relative_to(repo))
    assert gitignore_rel not in out["files_created"], (
        f".gitignore pre-existed; must not appear in files_created: {out['files_created']}"
    )


def test_dry_run_new_gitignore_reported_as_created(tmp_path: Path) -> None:
    """
    When .gitignore does NOT exist, dry-run must include it in files_created.
    Semantics must match the real run.
    """
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # No pre-existing .gitignore
    assert not (module_abs / ".gitignore").exists()
    result = run_bootstrap(repo, "--dry-run")
    assert result.returncode == 0
    out = parse_stdout(result)
    assert out["status"] == "DRY_RUN"
    # .gitignore must be in files_created (it's new)
    gitignore_rel = str((module_abs / ".gitignore").relative_to(repo))
    assert gitignore_rel in out["files_created"], (
        f"New .gitignore must appear in files_created: {out['files_created']}"
    )


# ---------------------------------------------------------------------------
# Nonexistent repository root — must return JSON, not traceback
# ---------------------------------------------------------------------------


def test_nonexistent_repository_root_returns_json_failure(tmp_path: Path) -> None:
    """
    Passing a non-existent RepositoryRoot must return a valid JSON failure object
    on stdout — NOT a Python traceback — and exit code 2.
    """
    nonexistent = tmp_path / "does" / "not" / "exist"
    args = [
        sys.executable, str(BOOTSTRAP_SCRIPT),
        "--repository-root", str(nonexistent),
        "--module-root", "src/Sample",
        "--module-id", "sample",
        "--module-name", "Sample",
        "--project-file", "src/Sample/Sample.csproj",
        "--platform", "dotnet",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}\n{result.stderr}"
    # stdout must parse as a single valid JSON object — no traceback
    out = json.loads(result.stdout)
    assert isinstance(out, dict)
    assert out["reason_code"] == "NOT_A_GIT_REPOSITORY"
    assert out["status"] == "FAILED"


# ---------------------------------------------------------------------------
# 20.4 PowerShell wrapper (Windows only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell test only runs on Windows")
def test_powershell_wrapper_passes_args_and_exit_code(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Sample.DrawBeams",
        "-ModuleId", "sample.drawbeams",
        "-ModuleName", "Sample.DrawBeams",
        "-ProjectFile", "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
        "-Platform", "revit",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["status"] == "CREATED"


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell test only runs on Windows")
def test_powershell_wrapper_preserves_error_exit_code(tmp_path: Path) -> None:
    """Protected branch should yield exit code 2 from wrapper."""
    repo, _, _ = init_temp_repo(tmp_path, branch="main")
    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Sample.DrawBeams",
        "-ModuleId", "sample.drawbeams",
        "-ModuleName", "Sample.DrawBeams",
        "-ProjectFile", "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
        "-Platform", "revit",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    out = json.loads(result.stdout)
    assert out["reason_code"] == "PROTECTED_BRANCH_BLOCKED"


@pytest.mark.skipif(platform.system() != "Windows", reason="PowerShell test only runs on Windows")
def test_powershell_wrapper_stdout_is_unmodified_json(tmp_path: Path) -> None:
    """Wrapper must not add any extra output around the JSON."""
    repo, _, _ = init_temp_repo(tmp_path)
    args = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", str(PS1_SCRIPT),
        "-RepositoryRoot", str(repo),
        "-ModuleRoot", "src/Sample.DrawBeams",
        "-ModuleId", "sample.drawbeams",
        "-ModuleName", "Sample.DrawBeams",
        "-ProjectFile", "src/Sample.DrawBeams/Sample.DrawBeams.csproj",
        "-Platform", "revit",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    # stdout must parse as a single JSON object
    obj = json.loads(result.stdout)
    assert isinstance(obj, dict)


# ---------------------------------------------------------------------------
# Phase C PLAN.md Bootstrap Tests
# ---------------------------------------------------------------------------


def test_bootstrap_creates_plan_md(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    res = run_bootstrap(repo)
    assert res.returncode == 0, res.stderr
    plan_path = module_abs / ".ai-workflow" / "PLAN.md"
    assert plan_path.exists()


def test_generated_plan_md_matches_canonical_template(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    res = run_bootstrap(repo)
    assert res.returncode == 0, res.stderr
    plan_path = module_abs / ".ai-workflow" / "PLAN.md"
    canonical_path = REPO_ROOT / "templates" / "module-workflow" / ".ai-workflow" / "PLAN.md"
    assert plan_path.read_text(encoding="utf-8") == canonical_path.read_text(encoding="utf-8")


def test_existing_different_plan_md_causes_conflict(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    plan_path = module_abs / ".ai-workflow" / "PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Custom PLAN\nDifferent content\n", encoding="utf-8")

    res = run_bootstrap(repo)
    assert res.returncode == 3
    out = parse_stdout(res)
    assert out["reason_code"] == "BOOTSTRAP_CONFLICT"


def test_second_run_preserves_plan_md(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    res1 = run_bootstrap(repo)
    assert res1.returncode == 0
    res2 = run_bootstrap(repo)
    assert res2.returncode == 0
    out2 = parse_stdout(res2)
    assert out2["status"] == "NO_CHANGES"


def test_old_bootstrap_tree_is_upgraded_with_plan_md(tmp_path: Path) -> None:
    repo, module_abs, _ = init_temp_repo(tmp_path)
    # Run bootstrap first
    res1 = run_bootstrap(repo)
    assert res1.returncode == 0

    # Remove PLAN.md simulating old tree
    plan_path = module_abs / ".ai-workflow" / "PLAN.md"
    plan_path.unlink()

    # Re-run bootstrap
    res2 = run_bootstrap(repo)
    assert res2.returncode == 0
    out2 = parse_stdout(res2)
    assert out2["status"] == "CREATED"
    assert plan_path.exists()


def test_generated_contracts_contains_plan_md(tmp_path: Path) -> None:
    repo, _, _ = init_temp_repo(tmp_path)
    res = run_bootstrap(repo)
    assert res.returncode == 0
    out = parse_stdout(res)
    assert ".ai-workflow/PLAN.md" in out["generated_contracts"]
