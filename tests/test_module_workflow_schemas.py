"""
Module Workflow Schema Tests — Phase A
Tests for all schemas in schemas/module-workflow/ against examples.
"""
import json
import pytest
from pathlib import Path
from jsonschema import Draft7Validator, FormatChecker, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema_instance(schema: dict, instance: dict) -> None:
    """Validate instance against schema using Draft7Validator + FormatChecker."""
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema, format_checker=FormatChecker()).validate(instance)


def validate_scope_cross_fields(instance: dict) -> None:
    """Enforce cross-field rules not expressible in JSON Schema Draft-07."""
    if instance.get("work_branch") == instance.get("base_branch"):
        raise ValueError("work_branch cannot equal base_branch")
    if instance.get("work_branch") in ("main", "master", "develop", "release"):
        raise ValueError(f"work_branch '{instance['work_branch']}' is a protected branch")


def validate_module_path_relationships(instance: dict) -> None:
    """Enforce that subpaths reside within parent paths."""
    module_root = instance.get("module_root", "")
    for field in ("workflow_root", "sandbox_root", "stable_output_root"):
        val = instance.get(field, "")
        if val and not val.startswith(module_root):
            raise ValueError(f"{field} '{val}' must reside within module_root '{module_root}'")
    sandbox_root = instance.get("sandbox_root", "")
    dll = instance.get("sandbox_dll", "")
    if dll and not dll.startswith(sandbox_root):
        raise ValueError(f"sandbox_dll '{dll}' must reside within sandbox_root '{sandbox_root}'")


def validate_evidence_cross_fields(instance: dict) -> None:
    """Cross-field rules for evidence."""
    for src in instance.get("diagnosis_sources", []):
        if src.get("line_end", 0) < src.get("line_start", 0):
            raise ValueError("line_end must be >= line_start")
    if instance.get("ready_to_implement"):
        for f in instance.get("files_verified", []):
            if not f.get("exists", True):
                raise ValueError(
                    "ready_to_implement cannot be true when a verified file does not exist"
                )


def validate_delivery_cross_fields(instance: dict) -> None:
    """Cross-field rules for READY_FOR_REVIEW delivery."""
    if instance.get("status") != "READY_FOR_REVIEW":
        return
    if not instance.get("sha_match", False):
        raise ValueError("sha_match must be true for READY_FOR_REVIEW")
    if instance.get("commit_sha") != instance.get("remote_sha"):
        raise ValueError("commit_sha must equal remote_sha for READY_FOR_REVIEW")
    if instance.get("scope_check") != "PASS":
        raise ValueError("scope_check must be PASS for READY_FOR_REVIEW")
    for t in instance.get("tests", []):
        if t.get("result") != "PASS":
            raise ValueError("All tests must PASS for READY_FOR_REVIEW")
    if not instance.get("working_tree_clean", False):
        raise ValueError("working_tree_clean must be true for READY_FOR_REVIEW")
    if instance.get("blockers"):
        raise ValueError("blockers must be empty for READY_FOR_REVIEW")
    if not instance.get("sandbox_dll_sha256"):
        raise ValueError("sandbox_dll_sha256 must be present for READY_FOR_REVIEW")


def validate_sandbox_dll_path(instance: dict) -> None:
    """DLL must reside within .sandbox/bin/."""
    dll = instance.get("dll", "")
    if not dll.startswith(".sandbox/bin/"):
        raise ValueError(f"DLL '{dll}' must start with '.sandbox/bin/'")


def validate_relative_paths(instance: dict) -> None:
    """Reject absolute paths in any string field value."""
    for key, value in instance.items():
        if isinstance(value, str):
            if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
                raise ValueError(f"Absolute path in field '{key}': {value!r}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return get_repo_root()


@pytest.fixture(scope="session")
def schemas_dir(repo_root: Path) -> Path:
    return repo_root / "schemas" / "module-workflow"


@pytest.fixture(scope="session")
def templates_dir(repo_root: Path) -> Path:
    return repo_root / "templates" / "module-workflow"


@pytest.fixture(scope="session")
def examples_dir(repo_root: Path) -> Path:
    return repo_root / "examples" / "module-workflow" / "Antigravity.DrawBeams"


# ---------------------------------------------------------------------------
# 9.1 — Valid example tests
# ---------------------------------------------------------------------------

def test_all_schema_files_parse(schemas_dir: Path) -> None:
    schema_files = [
        "module.schema.json",
        "scope.schema.json",
        "plan_lock.schema.json",
        "evidence.schema.json",
        "delivery.schema.json",
        "sandbox_manifest.schema.json",
    ]
    for schema_file in schema_files:
        path = schemas_dir / schema_file
        assert path.exists(), f"Schema not found: {path}"
        schema = load_json(path)
        Draft7Validator.check_schema(schema)


def test_template_json_files_parse(templates_dir: Path) -> None:
    template_files = [
        ".ai-workflow/MODULE.json",
        ".ai-workflow/SCOPE.json",
    ]
    for template_file in template_files:
        path = templates_dir / template_file
        assert path.exists(), f"Template not found: {path}"
        load_json(path)  # must parse as valid JSON


def test_drawbeams_module_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "module.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/MODULE.json")
    validate_schema_instance(schema, instance)
    validate_module_path_relationships(instance)


def test_drawbeams_scope_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    validate_schema_instance(schema, instance)


def test_drawbeams_plan_lock_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    validate_schema_instance(schema, instance)


def test_drawbeams_evidence_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "evidence.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    validate_schema_instance(schema, instance)
    validate_evidence_cross_fields(instance)


def test_drawbeams_delivery_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "delivery.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    validate_schema_instance(schema, instance)
    validate_delivery_cross_fields(instance)


def test_drawbeams_sandbox_manifest_example_validates(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "sandbox_manifest.schema.json")
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    validate_schema_instance(schema, instance)
    validate_sandbox_dll_path(instance)


# ---------------------------------------------------------------------------
# 9.2 — Invalid fixture tests
# ---------------------------------------------------------------------------

def test_missing_task_id_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    del instance["task_id"]
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_work_branch_main_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    """work_branch='main' must be rejected by schema (not enum)."""
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["work_branch"] = "main"
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_work_branch_equal_base_branch_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    """work_branch == base_branch rejected by cross-field helper."""
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["work_branch"] = instance["base_branch"]
    with pytest.raises(ValueError):
        validate_scope_cross_fields(instance)


def test_direct_main_changes_true_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["direct_main_changes"] = True
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_plan_lock_missing_plan_hash_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    del instance["plan_sha256"]
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_invalid_sha256_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    instance["plan_sha256"] = "invalid_hash"
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_evidence_without_diagnosis_source_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "evidence.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["diagnosis_sources"] = []
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_evidence_source_with_invalid_line_range_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    """line_end < line_start rejected by cross-field helper."""
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["diagnosis_sources"][0]["line_start"] = 10
    instance["diagnosis_sources"][0]["line_end"] = 5
    with pytest.raises(ValueError):
        validate_evidence_cross_fields(instance)


def test_ready_evidence_referencing_missing_file_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    """ready_to_implement=true with exists=false rejected by cross-field helper."""
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["ready_to_implement"] = True
    instance["files_verified"][0]["exists"] = False
    with pytest.raises(ValueError):
        validate_evidence_cross_fields(instance)


def test_delivery_ready_for_review_with_sha_match_false_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["sha_match"] = False
    with pytest.raises(ValueError):
        validate_delivery_cross_fields(instance)


def test_delivery_ready_for_review_with_commit_sha_not_equal_remote_sha_rejected(
    schemas_dir: Path, examples_dir: Path
) -> None:
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["remote_sha"] = "3333333333333333333333333333333333333333"
    with pytest.raises(ValueError):
        validate_delivery_cross_fields(instance)


def test_delivery_ready_for_review_with_failed_test_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["tests"][0]["result"] = "FAIL"
    with pytest.raises(ValueError):
        validate_delivery_cross_fields(instance)


def test_delivery_ready_for_review_with_dirty_working_tree_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["working_tree_clean"] = False
    with pytest.raises(ValueError):
        validate_delivery_cross_fields(instance)


def test_sandbox_manifest_missing_dll_sha256_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "sandbox_manifest.schema.json")
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    del instance["dll_sha256"]
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_sandbox_dll_outside_sandbox_bin_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    instance["dll"] = "src/Antigravity.DrawBeams/bin/Antigravity.DrawBeams.dll"
    with pytest.raises(ValueError):
        validate_sandbox_dll_path(instance)


def test_absolute_machine_path_rejected_where_applicable(schemas_dir: Path, examples_dir: Path) -> None:
    instance = load_json(examples_dir / ".ai-workflow/MODULE.json")
    instance["module_root"] = "E:/AI_SOFTWARE_FACTORY/src/Antigravity.DrawBeams"
    with pytest.raises(ValueError):
        validate_relative_paths(instance)


def test_unexpected_additional_property_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "module.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/MODULE.json")
    instance["unexpected_prop"] = "test"
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_approved_at_invalid_datetime_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    instance["approved_at"] = "not-a-datetime"
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)


def test_built_at_invalid_datetime_rejected(schemas_dir: Path, examples_dir: Path) -> None:
    schema = load_json(schemas_dir / "sandbox_manifest.schema.json")
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    instance["built_at"] = "not-a-datetime"
    with pytest.raises(ValidationError):
        validate_schema_instance(schema, instance)
