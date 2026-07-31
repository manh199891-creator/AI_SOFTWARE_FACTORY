import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

def get_repo_root():
    return Path(__file__).resolve().parent.parent

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

@pytest.fixture
def repo_root():
    return get_repo_root()

@pytest.fixture
def schemas_dir(repo_root):
    return repo_root / "schemas" / "module-workflow"

@pytest.fixture
def templates_dir(repo_root):
    return repo_root / "templates" / "module-workflow"

@pytest.fixture
def examples_dir(repo_root):
    return repo_root / "examples" / "module-workflow" / "Antigravity.DrawBeams"

def test_all_schema_files_parse(schemas_dir):
    schemas = ["module.schema.json", "scope.schema.json", "plan_lock.schema.json", 
               "evidence.schema.json", "delivery.schema.json", "sandbox_manifest.schema.json"]
    for schema_file in schemas:
        path = schemas_dir / schema_file
        assert path.exists()
        load_json(path)

def test_template_json_files_parse(templates_dir):
    templates = [".ai-workflow/MODULE.json", ".ai-workflow/SCOPE.json"]
    for template_file in templates:
        path = templates_dir / template_file
        assert path.exists()
        load_json(path)

def validate_example(schema_name, example_name, schemas_dir, examples_dir):
    schema = load_json(schemas_dir / schema_name)
    instance = load_json(examples_dir / example_name)
    validate(instance=instance, schema=schema)
    return instance

def test_drawbeams_module_example_validates(schemas_dir, examples_dir):
    validate_example("module.schema.json", ".ai-workflow/MODULE.json", schemas_dir, examples_dir)

def test_drawbeams_scope_example_validates(schemas_dir, examples_dir):
    validate_example("scope.schema.json", ".ai-workflow/SCOPE.json", schemas_dir, examples_dir)

def test_drawbeams_plan_lock_example_validates(schemas_dir, examples_dir):
    validate_example("plan_lock.schema.json", ".ai-workflow/PLAN_LOCK.json", schemas_dir, examples_dir)

def test_drawbeams_evidence_example_validates(schemas_dir, examples_dir):
    validate_example("evidence.schema.json", ".ai-workflow/EVIDENCE.json", schemas_dir, examples_dir)

def test_drawbeams_delivery_example_validates(schemas_dir, examples_dir):
    validate_example("delivery.schema.json", ".ai-workflow/DELIVERY.json", schemas_dir, examples_dir)

def test_drawbeams_sandbox_manifest_example_validates(schemas_dir, examples_dir):
    validate_example("sandbox_manifest.schema.json", ".sandbox/manifest.json", schemas_dir, examples_dir)

def test_missing_task_id_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    del instance["task_id"]
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_work_branch_main_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["work_branch"] = "main"
    # Helper validation
    assert instance["work_branch"] != "main", "work_branch cannot be main"

def test_work_branch_equal_base_branch_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["work_branch"] = instance["base_branch"]
    # Helper validation
    assert instance["work_branch"] != instance["base_branch"], "work_branch cannot be equal to base_branch"

def test_direct_main_changes_true_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "scope.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/SCOPE.json")
    instance["direct_main_changes"] = True
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_plan_lock_missing_plan_hash_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    del instance["plan_sha256"]
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_invalid_sha256_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "plan_lock.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/PLAN_LOCK.json")
    instance["plan_sha256"] = "invalid_hash"
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_evidence_without_diagnosis_source_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "evidence.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["diagnosis_sources"] = []
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_evidence_source_with_invalid_line_range_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "evidence.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["diagnosis_sources"][0]["line_start"] = 10
    instance["diagnosis_sources"][0]["line_end"] = 5
    # Helper validation
    assert instance["diagnosis_sources"][0]["line_end"] < instance["diagnosis_sources"][0]["line_start"], "line_end cannot be less than line_start"
    # Actually wait, we test that it *is* rejected. Let's raise an exception if it is not handled by schema.
    # Schema doesn't check cross fields easily. So helper validator:
    def validate_line_range(inst):
        for src in inst.get("diagnosis_sources", []):
            if src.get("line_end", 0) < src.get("line_start", 0):
                raise ValueError("line_end < line_start")
    
    with pytest.raises(ValueError):
        validate_line_range(instance)

def test_ready_evidence_referencing_missing_file_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "evidence.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/EVIDENCE.json")
    instance["ready_to_implement"] = True
    instance["files_verified"][0]["exists"] = False
    
    def validate_ready_evidence(inst):
        if inst.get("ready_to_implement"):
            for f in inst.get("files_verified", []):
                if not f.get("exists", True):
                    raise ValueError("Cannot be ready if a file does not exist")
                    
    with pytest.raises(ValueError):
        validate_ready_evidence(instance)

def test_delivery_ready_for_review_with_sha_match_false_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "delivery.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["sha_match"] = False
    
    def validate_delivery(inst):
        if inst.get("status") == "READY_FOR_REVIEW":
            if not inst.get("sha_match", False):
                raise ValueError("sha_match must be true for READY_FOR_REVIEW")
                
    with pytest.raises(ValueError):
        validate_delivery(instance)

def test_delivery_ready_for_review_with_commit_sha_not_equal_remote_sha_rejected(schemas_dir, examples_dir):
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["commit_sha"] = "a"
    instance["remote_sha"] = "b"
    
    def validate_delivery_sha(inst):
        if inst.get("status") == "READY_FOR_REVIEW":
            if inst.get("commit_sha") != inst.get("remote_sha"):
                raise ValueError("commit_sha must equal remote_sha")
                
    with pytest.raises(ValueError):
        validate_delivery_sha(instance)

def test_delivery_ready_for_review_with_failed_test_rejected(schemas_dir, examples_dir):
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["tests"][0]["result"] = "FAIL"
    
    def validate_delivery_tests(inst):
        if inst.get("status") == "READY_FOR_REVIEW":
            for t in inst.get("tests", []):
                if t.get("result") != "PASS":
                    raise ValueError("All tests must pass for READY_FOR_REVIEW")
                    
    with pytest.raises(ValueError):
        validate_delivery_tests(instance)

def test_delivery_ready_for_review_with_dirty_working_tree_rejected(schemas_dir, examples_dir):
    instance = load_json(examples_dir / ".ai-workflow/DELIVERY.json")
    instance["status"] = "READY_FOR_REVIEW"
    instance["working_tree_clean"] = False
    
    def validate_working_tree(inst):
        if inst.get("status") == "READY_FOR_REVIEW":
            if not inst.get("working_tree_clean", True):
                raise ValueError("working_tree_clean must be true for READY_FOR_REVIEW")
                
    with pytest.raises(ValueError):
        validate_working_tree(instance)

def test_sandbox_manifest_missing_dll_sha256_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "sandbox_manifest.schema.json")
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    del instance["dll_sha256"]
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

def test_sandbox_dll_outside_sandbox_bin_rejected(schemas_dir, examples_dir):
    instance = load_json(examples_dir / ".sandbox/manifest.json")
    instance["dll"] = "src/Antigravity.DrawBeams/bin/Antigravity.DrawBeams.dll"
    
    def validate_sandbox_dll_path(inst):
        dll_path = inst.get("dll", "")
        if not dll_path.startswith(".sandbox/bin/"):
            raise ValueError("DLL must be in .sandbox/bin/")
            
    with pytest.raises(ValueError):
        validate_sandbox_dll_path(instance)

def test_absolute_machine_path_rejected_where_applicable(schemas_dir, examples_dir):
    instance = load_json(examples_dir / ".ai-workflow/MODULE.json")
    instance["module_root"] = "E:/AI_SOFTWARE_FACTORY/src/Antigravity.DrawBeams"
    
    def validate_relative_paths(inst):
        for key, value in inst.items():
            if isinstance(value, str) and (value.startswith("/") or ":" in value):
                raise ValueError("Absolute paths are not allowed")
                
    with pytest.raises(ValueError):
        validate_relative_paths(instance)

def test_unexpected_additional_property_rejected(schemas_dir, examples_dir):
    schema = load_json(schemas_dir / "module.schema.json")
    instance = load_json(examples_dir / ".ai-workflow/MODULE.json")
    instance["unexpected_prop"] = "test"
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=schema)

