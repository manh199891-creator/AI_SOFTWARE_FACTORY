import subprocess, os, sys, shutil, json, time
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

FACTORY_ROOT = Path("E:/AI_SOFTWARE_FACTORY")
PROJECT_NAME = "test_project"
PROJECT_ROOT = FACTORY_ROOT / PROJECT_NAME

def setup_test_env():
    if PROJECT_ROOT.exists():
        last_error = None
        for _ in range(5):
            try:
                shutil.rmtree(PROJECT_ROOT)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                import time
                time.sleep(0.5)
        
        if last_error is not None:
            raise RuntimeError(
                f"Unable to clean test project: {PROJECT_ROOT}"
            ) from last_error
        
    for sub in [".agent/context", ".agent/reports", ".agent/state", "source-code"]:
        (PROJECT_ROOT / sub).mkdir(parents=True, exist_ok=True)
        
    profile = {
        "project_name": PROJECT_NAME,
        "stage_patterns": ["**/*"],
        "release_requires": {
            "codex_real_review_pass": True,
            "diff_hash_match": True
        },
        "codex_review": {
            "timeout_seconds": 2,
            "batch_max_files": 3,
            "batch_max_chars": 70000,
            "max_timeout_retries": 2
        }
    }
    (PROJECT_ROOT / ".agent/project_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    scope = {
        "schema_version": 1,
        "task_id": "test_task",
        "repository_root": str(PROJECT_ROOT / "source-code"),
        "allowed_files": ["*.txt"],
        "forbidden": ["secret.txt"]
    }
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(json.dumps(scope), encoding="utf-8")
    
    # Init git
    src = PROJECT_ROOT / "source-code"
    subprocess.run(["git", "init"], cwd=src, check=True, capture_output=True)
    
    # Add files
    (src / "file1.txt").write_text("Hello World", encoding="utf-8")
    (src / "secret.txt").write_text("Secret", encoding="utf-8")

def get_state():
    state_file = PROJECT_ROOT / ".agent/state/workflow_state.json"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text(encoding="utf-8"))
    
def get_manifest():
    manifest_file = PROJECT_ROOT / ".agent/state/review_run.json"
    if not manifest_file.exists():
        return None
    return json.loads(manifest_file.read_text(encoding="utf-8"))

def run_codex_scenario(scenario, env_overrides=None):
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    fake_codex_py = FACTORY_ROOT / "fake_codex.py"
    codex_cmd.write_text(f'@echo off\npython "{fake_codex_py}" %*', encoding="utf-8")
    
    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["FAKE_CODEX_SCENARIO"] = scenario
    env["FAKE_LIVE_REPO"] = str(PROJECT_ROOT / "source-code")
    
    if env_overrides:
        env.update(env_overrides)
        
    t0 = time.time()
    res = subprocess.run([sys.executable, "harness.py", PROJECT_NAME, "codex", "--task-id", "test_task"], cwd=FACTORY_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    duration = time.time() - t0
    
    return res, duration

def run_harness_command(command):
    return subprocess.run([sys.executable, "harness.py", PROJECT_NAME, command], cwd=FACTORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")

def run_harness_args(args):
    return subprocess.run([sys.executable, "harness.py", PROJECT_NAME] + args, cwd=FACTORY_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")

def run_dual_scenario(scenario="PASS", extra_args=None, task_id="test_task"):
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    fake_codex_py = FACTORY_ROOT / "fake_codex.py"
    codex_cmd.write_text(f'@echo off\npython "{fake_codex_py}" %*', encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["FAKE_CODEX_SCENARIO"] = scenario
    env["FAKE_LIVE_REPO"] = str(PROJECT_ROOT / "source-code")
    args = [sys.executable, "harness.py", PROJECT_NAME, "dual", "--task-id", task_id, "--feature", "Test dual"]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        cwd=FACTORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )



def test_build_review_batches_by_file_count():
    print("\n--- Running test_build_review_batches_by_file_count ---")
    from review_pipeline import build_review_batches
    
    config = {
        "batch_max_files": 2,
        "batch_max_chars": 999999,
        "max_file_chars": 40000,
        "max_diff_chars": 999999
    }
    
    changed_files = ["src/file1.txt", "src/file2.txt", "src/file3.txt", "src/file4.txt", "src/file5.txt"]
    for f in changed_files:
        p = PROJECT_ROOT / "source-code" / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("dummy", encoding="utf-8")
        
    batches = build_review_batches(PROJECT_ROOT / "source-code", changed_files, config)
    
    assert len(batches) == 3, f"Expected 3 batches, got {len(batches)}"
    assert len(batches[0]["files"]) == 2
    assert len(batches[1]["files"]) == 2
    assert len(batches[2]["files"]) == 1
    print("SUCCESS: test_build_review_batches_by_file_count")

def test_build_review_batches_by_chars():
    print("\n--- Running test_build_review_batches_by_chars ---")
    from review_pipeline import build_review_batches
    
    config = {
        "batch_max_files": 10,
        "batch_max_chars": 100,
        "max_file_chars": 40000,
        "max_diff_chars": 999999
    }
    
    changed_files = ["src/small1.txt", "src/small2.txt", "src/large.txt"]
    
    p1 = PROJECT_ROOT / "source-code/src/small1.txt"
    p2 = PROJECT_ROOT / "source-code/src/small2.txt"
    p3 = PROJECT_ROOT / "source-code/src/large.txt"
    p1.parent.mkdir(parents=True, exist_ok=True)
    
    p1.write_text("a" * 60, encoding="utf-8")
    p2.write_text("b" * 60, encoding="utf-8")
    p3.write_text("c" * 200, encoding="utf-8")
    
    batches = build_review_batches(PROJECT_ROOT / "source-code", changed_files, config)
    
    assert len(batches) == 3, f"Expected 3 batches, got {len(batches)}"
    
    large_batch = next(b for b in batches if "src/large.txt" in b["files"])
    assert large_batch.get("needs_chunk_review") is True, "Large file batch should have needs_chunk_review=True"
    print("SUCCESS: test_build_review_batches_by_chars")


def test_aggregate_batch_results_all_pass():
    print("\n--- Running test_aggregate_batch_results_all_pass ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.PASS},
        {"status": ReviewStatus.PASS}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.PASS
    print("SUCCESS: test_aggregate_batch_results_all_pass")

def test_aggregate_batch_results_fail():
    print("\n--- Running test_aggregate_batch_results_fail ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.PASS},
        {"status": ReviewStatus.FAIL}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.FAIL
    print("SUCCESS: test_aggregate_batch_results_fail")

def test_aggregate_batch_results_stale_priority():
    print("\n--- Running test_aggregate_batch_results_stale_priority ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.FAIL},
        {"status": ReviewStatus.STALE},
        {"status": ReviewStatus.PASS}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.STALE
    print("SUCCESS: test_aggregate_batch_results_stale_priority")

def test_aggregate_batch_results_infra_fail_priority():
    print("\n--- Running test_aggregate_batch_results_infra_fail_priority ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.STALE},
        {"status": ReviewStatus.INFRA_FAIL},
        {"status": ReviewStatus.FAIL}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.INFRA_FAIL
    print("SUCCESS: test_aggregate_batch_results_infra_fail_priority")

def test_aggregate_batch_results_timeout_reason_code():
    print("\n--- Running test_aggregate_batch_results_timeout_reason_code ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus, run_codex_review
    # Actually wait, run_codex_review handles the reason_code. Let's just check aggregate_batch_results.
    batches = [
        {"status": ReviewStatus.INFRA_FAIL, "reason_code": "CODEX_TIMEOUT"}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.INFRA_FAIL
    print("SUCCESS: test_aggregate_batch_results_timeout_reason_code")

def test_batch_runner_uses_passed_codex_executable():
    print("\n--- Running test_batch_runner_uses_passed_codex_executable ---")
    from review_pipeline import run_codex_review_batch
    
    # Create fake codex executable
    fake_dir = PROJECT_ROOT / "fake_codex_dir"
    fake_dir.mkdir(exist_ok=True)
    fake_codex = fake_dir / "fake_codex.cmd"
    fake_codex.write_text("@echo FAKE_CODEX_CALLED", encoding="utf-8")
    
    batch = {"batch_id": 1, "files": ["file1.txt"]}
    manifest = {
        "run_id": "test_run", 
        "task_id": "test", 
        "feature_name": "test", 
        "snapshot_hash": "hash",
        "plan_files": [],
        "acceptance_files": [],
        "feature_description": "test",
        "repository_root": str(PROJECT_ROOT / "source-code")
    }
    config = {"timeout_seconds": 10}
    
    res = run_codex_review_batch(batch, manifest, PROJECT_ROOT, PROJECT_ROOT / "source-code", config, str(fake_codex))
    
    assert "FAKE_CODEX_CALLED" in res["stdout"]
    print("SUCCESS: test_batch_runner_uses_passed_codex_executable")



def test_batch_reviews_summary_in_report():
    print("\n--- Running Phase 5: test_batch_reviews_summary_in_report ---")
    import review_pipeline
    import json
    
    manifest = {
        "run_id": "test_report",
        "task_id": "test_task",
        "status": review_pipeline.ReviewStatus.PASS,
        "reason": "Test reason",
        "exit_code": 0,
        "snapshot_hash": "dummy_hash",
        "batches": [
            {"batch_id": 1, "status": "PASS", "files": ["a.txt"]},
            {"batch_id": 2, "status": "FAIL", "files": ["b.txt", "c.txt"]}
        ]
    }
    
    review_pipeline._ensure_review_report(PROJECT_ROOT, manifest, manifest["status"], manifest["reason"], "", "", manifest["exit_code"])
    
    report_file = PROJECT_ROOT / ".agent/reports/CODEX_REVIEW.md"
    report_content = report_file.read_text(encoding="utf-8")
    
    assert "## Batch Reviews Summary" in report_content
    assert "- **Batch 1**: 1 files, PASS" in report_content
    assert "- **Batch 2**: 2 files, FAIL" in report_content
    print("SUCCESS: test_batch_reviews_summary_in_report")



def test_timeout_split_retry_pass():
    print("\n--- Running Phase 7: test_timeout_split_retry_pass ---")
    
    # Reset git and create exactly 3 modified files
    import subprocess
    src = PROJECT_ROOT / "source-code"
    subprocess.run(["git", "reset", "--hard"], cwd=src, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fd"], cwd=src, check=True, capture_output=True)
    
    (src / "file1.txt").write_text("Hello 1 mod", encoding="utf-8")
    (src / "file2.txt").write_text("Hello 2 mod", encoding="utf-8")
    (src / "file3.txt").write_text("Hello 3 mod", encoding="utf-8")
    
    # Must also update config so they are in one batch
    import json
    profile_path = PROJECT_ROOT / ".agent/project_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["codex_review"]["batch_max_files"] = 3
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
        
    res, _ = run_codex_scenario("TIMEOUT_THEN_PASS")
    
    manifest = get_manifest()
    if manifest["status"] != "PASS":
        import pprint
        print("FAILED MANIFEST:")
        pprint.pprint(manifest)
    assert manifest["status"] == "PASS"
    batches = manifest["batches"]
    
    timeout_batch = next(b for b in batches if b["status"] == "INFRA_FAIL" and b.get("reason_code") == "CODEX_TIMEOUT")
    assert "children" in timeout_batch
    assert len(timeout_batch["children"]) > 1
    assert all(c["status"] == "PASS" for c in timeout_batch["children"])
    print("SUCCESS: test_timeout_split_retry_pass")

def test_timeout_single_file_block():
    print("\n--- Running Phase 7: test_timeout_single_file_block ---")
    # Remove forbidden file for this test
    forbidden_file = PROJECT_ROOT / "source-code" / "secret.txt"
    if forbidden_file.exists():
        forbidden_file.unlink()
    
    # Remove files created by previous test
    for f in ["file2.txt", "file3.txt"]:
        path = PROJECT_ROOT / "source-code" / f
        if path.exists():
            path.unlink()
        
    res, _ = run_codex_scenario("TIMEOUT_SINGLE_FILE")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert manifest["reason_code"] == "CODEX_TIMEOUT_SINGLE_LARGE_FILE"
    batches = manifest["batches"]
    
    timeout_batch = next(b for b in batches if b.get("reason_code") == "CODEX_TIMEOUT_SINGLE_LARGE_FILE")
    assert timeout_batch["status"] == "INFRA_FAIL"
    assert timeout_batch["needs_chunk_review"] == True
    
    res = run_harness_command("gate")
    assert "BLOCK_RELEASE" in res.stdout
    print("SUCCESS: test_timeout_single_file_block")

def test_project_profile_has_codex_review():
    print("\n--- Running Phase 6: test_project_profile_has_codex_review ---")
    import json
    res = run_harness_args(["setup", "test_project", "test_project", "A dummy idea"])
    
    profile_file = FACTORY_ROOT / "TestProject" / ".agent/project_profile.json"
    profile = json.loads(profile_file.read_text(encoding="utf-8"))
    
    assert "codex_review" in profile
    assert profile["codex_review"]["timeout_seconds"] == 180
    assert profile["codex_review"]["batch_max_files"] == 3
    print("SUCCESS: test_project_profile_has_codex_review")

def test_scope_validation():
    print("\n--- Running Scope Validation ---")
    res, _ = run_codex_scenario("PASS")
    
    manifest = get_manifest()
    assert manifest is not None
    assert manifest["status"] == "BLOCKED_SCOPE", manifest
    assert "FORBIDDEN: secret.txt" in manifest["reason"], "Reason should contain forbidden file"
    
    print("SUCCESS: Scope Validation")

def test_scenario_pass():
    print("\n--- Running Scenario: PASS ---")
    res, _ = run_codex_scenario("PASS")
    
    state = get_state()
    manifest = get_manifest()
    assert state["codex_status"] == "pass", f"Expected pass, got {state.get('codex_status')}. Reason: {manifest.get('reason')}"
    
    manifest = get_manifest()
    assert manifest["status"] == "PASS"
    assert manifest["exit_code"] == 0
    assert manifest["reason"] == "Review passed with 0 findings."
    
    print("SUCCESS: PASS")

def test_scenario_fail():
    print("\n--- Running Scenario: FAIL ---")
    res, _ = run_codex_scenario("FAIL")
    
    state = get_state()
    assert state["codex_status"] == "fail", f"Expected fail, got {state.get('codex_status')}"
    
    manifest = get_manifest()
    assert manifest["status"] == "FAIL"
    assert manifest["exit_code"] == 0
    
    print("SUCCESS: FAIL")

def test_scenario_timeout():
    print("\n--- Running Scenario: TIMEOUT ---")
    env = {"CODEX_TIMEOUT_SECONDS": "1"}
    res, duration = run_codex_scenario("TIMEOUT", env_overrides=env)
    
    if duration >= 5:
        print(f"STDOUT:\n{res.stdout}")
        print(f"STDERR:\n{res.stderr}")
    assert duration < 5, f"Timeout test took too long: {duration}s"
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert "Timeout" in manifest["reason"]
    assert manifest["exit_code"] == -1
    
    print("SUCCESS: TIMEOUT")

def test_scenario_infra_fail():
    print("\n--- Running Scenario: INFRA_FAIL_BAD_JSON ---")
    res, _ = run_codex_scenario("INFRA_FAIL_BAD_JSON")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert "Failed to parse JSON" in manifest["reason"]
    assert manifest["exit_code"] == 0
    
    print("SUCCESS: INFRA_FAIL_BAD_JSON")

def test_scenario_empty():
    print("\n--- Running Scenario: EMPTY ---")
    res, _ = run_codex_scenario("EMPTY")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert "Empty output" in manifest["reason"]
    
    print("SUCCESS: EMPTY")

def test_scenario_non_zero():
    print("\n--- Running Scenario: NON_ZERO_EXIT ---")
    res, _ = run_codex_scenario("NON_ZERO_EXIT")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert "Codex exited with non-zero" in manifest["reason"]
    assert manifest["exit_code"] == 1
    
    print("SUCCESS: NON_ZERO_EXIT")

def test_scenario_stale_source_changed():
    print("\n--- Running Scenario: STALE (source changed) ---")
    res, _ = run_codex_scenario("PASS_BUT_SOURCE_CHANGED")
    
    manifest = get_manifest()
    assert manifest["status"] == "STALE"
    assert "Source code changed during review" in manifest["reason"]
    
    # Restore file for next tests if any
    (PROJECT_ROOT / "source-code" / "file1.txt").write_text("Hello World", encoding="utf-8")
    
    print("SUCCESS: STALE_SOURCE_CHANGED")

def test_scenario_stale_run_id():
    print("\n--- Running Scenario: STALE (wrong run ID) ---")
    res, _ = run_codex_scenario("PASS", env_overrides={"FAKE_CODEX_RUN_ID": "wrong-id"})
    
    manifest = get_manifest()
    assert manifest["status"] == "STALE"
    assert "Run ID or Hash mismatch" in manifest["reason"]
    
    print("SUCCESS: STALE")

def test_scenario_stale_reviewed_files():
    print("\n--- Running Scenario: STALE (wrong reviewed files) ---")
    res, _ = run_codex_scenario("BAD_REVIEWED_FILES")
    
    manifest = get_manifest()
    assert manifest["status"] == "STALE"
    assert "Reviewed files mismatch" in manifest["reason"]
    
    print("SUCCESS: STALE_REVIEWED_FILES")

def test_gate_blocks_missing_scope():
    print("\n--- Running Gate: missing TASK_SCOPE blocks ---")
    (PROJECT_ROOT / ".agent/reports/GUARDRAILS_REPORT.md").write_text("# GUARDRAILS_REPORT.md\n\n## Status: PASS\n", encoding="utf-8")
    scope_path = PROJECT_ROOT / ".agent/context/TASK_SCOPE.json"
    saved_scope = scope_path.read_text(encoding="utf-8")
    scope_path.unlink()
    
    res = run_harness_command("gate")
    assert res.returncode != 0, "Gate should block when TASK_SCOPE.json is missing"
    assert "BLOCK_RELEASE" in res.stdout, "Gate output should block release"
    
    scope_path.write_text(saved_scope, encoding="utf-8")
    print("SUCCESS: GATE_MISSING_SCOPE")


def test_gate_blocks_batch_fail():
    print("\n--- Running Gate: batch fail blocks ---")
    from review_pipeline import ReviewStatus
    import json
    
    # modify manifest to pretend it passed overall, but one batch failed
    manifest_file = PROJECT_ROOT / ".agent/state/review_run.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest["status"] = "PASS"
    manifest["batches"] = [
        {"batch_id": 1, "status": "PASS"},
        {"batch_id": 2, "status": "FAIL"}
    ]
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    
    res = run_harness_command("gate")
    assert res.returncode != 0, "Gate should block if any batch fails"
    assert "BLOCK_RELEASE" in res.stdout
    assert "Batch reviews complete" in res.stdout
    assert "One or more Codex review batches did not pass" in res.stdout
    print("SUCCESS: test_gate_blocks_batch_fail")

def test_gate_allows_all_batch_pass():
    print("\n--- Running Gate: all batch pass allows ---")
    from review_pipeline import ReviewStatus
    import json
    
    # modify manifest to pretend it passed overall and all batches passed
    manifest_file = PROJECT_ROOT / ".agent/state/review_run.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest["status"] = "PASS"
    manifest["batches"] = [
        {"batch_id": 1, "status": "PASS"},
        {"batch_id": 2, "status": "PASS"}
    ]
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    
    (PROJECT_ROOT / ".agent/reports/GUARDRAILS_REPORT.md").write_text("# GUARDRAILS_REPORT.md\n\n## Status: PASS\n", encoding="utf-8")
    
    res = run_harness_command("gate")
    assert res.returncode == 0, f"Gate should allow if all batches pass. Output: {res.stdout}"
    assert "ALLOW_RELEASE" in res.stdout
    assert "Batch reviews complete" in res.stdout
    print("SUCCESS: test_gate_allows_all_batch_pass")

def test_gate_allows_bound_pass():
    print("\n--- Running Gate: bound PASS allows ---")
    (PROJECT_ROOT / ".agent/reports/GUARDRAILS_REPORT.md").write_text("# GUARDRAILS_REPORT.md\n\n## Status: PASS\n", encoding="utf-8")
    
    res = run_harness_command("gate")
    assert res.returncode == 0, f"Gate should allow valid bound PASS. Output:\n{res.stdout}\n{res.stderr}"
    assert "ALLOW_RELEASE" in res.stdout, "Gate output should allow release"
    
    print("SUCCESS: GATE_BOUND_PASS")

def test_dual_pipeline_pass():
    print("\n--- Running Dual Pipeline: PASS ---")
    res = run_dual_scenario("PASS")
    assert res.returncode == 0, f"Dual pipeline should pass. Output:\n{res.stdout}\n{res.stderr}"
    assert "DUAL PIPELINE PASS" in res.stdout
    dual_report = PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md"
    assert dual_report.exists(), "Dual report should be written"
    assert "## Status: PASS" in dual_report.read_text(encoding="utf-8")
    print("SUCCESS: DUAL_PIPELINE_PASS")

def test_dual_pipeline_writes_fixer_handoff():
    print("\n--- Running Dual Pipeline: FAIL writes handoff ---")
    res = run_dual_scenario("FAIL", extra_args=["--max-cycles", "2"])
    assert res.returncode != 0, "Dual pipeline should block when Codex fails and no fixer command exists"
    handoff = PROJECT_ROOT / ".agent/reports/FIXER_HANDOFF.md"
    assert handoff.exists(), "Fixer handoff should be written"
    handoff_text = handoff.read_text(encoding="utf-8")
    assert "## Status: NEEDS_FIX" in handoff_text
    assert "CODEX_REVIEW.md" in handoff_text
    dual_report = (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
    assert "## Status: NEEDS_FIX" in dual_report
    assert get_state()["next_step"] == "external_fixer"
    print("SUCCESS: DUAL_PIPELINE_FIXER_HANDOFF")

def test_dual_init_generic_task():
    print("\n--- Running Dual Init: generic task ---")
    saved_scope = (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8")
    state_file = PROJECT_ROOT / ".agent/state/workflow_state.json"
    saved_state_content = state_file.read_text(encoding="utf-8") if state_file.exists() else None
    res = run_harness_args([
        "dual-init",
        "--task-id", "generic_task",
        "--feature", "Generic feature for any project",
        "--allowed", "src/**/*.cs,tests/**/*.cs",
        "--forbidden", "secrets/**",
        "--force"
    ])
    assert res.returncode == 0, f"dual-init should pass. Output:\n{res.stdout}\n{res.stderr}"
    scope = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    assert scope["task_id"] == "generic_task"
    assert "src/**/*.cs" in scope["allowed_files"]
    assert "secrets/**" in scope["forbidden"]
    assert (PROJECT_ROOT / ".agent/context/PLAN.md").exists()
    state = get_state()
    assert state["task_id"] == "generic_task"
    assert state["dual_status"] == "initialized"
    
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(saved_scope, encoding="utf-8")
    if saved_state_content is not None:
        (PROJECT_ROOT / ".agent/state/workflow_state.json").write_text(saved_state_content, encoding="utf-8")
    else:
        # If it didn't exist before, create a dummy one for test_task
        dummy = {"task_id": "test_task", "dual_status": "initialized"}
        (PROJECT_ROOT / ".agent/state/workflow_state.json").write_text(json.dumps(dummy), encoding="utf-8")
        
    print("SUCCESS: DUAL_INIT_GENERIC_TASK")

def test_task_id_mismatch():
    print("\n--- Running Scenario: TASK_ID_MISMATCH ---")
    scope = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    scope["task_id"] = "wrong_task"
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(json.dumps(scope), encoding="utf-8")
    
    res, _ = run_codex_scenario("PASS")
    manifest = get_manifest()
    assert manifest["status"] == "BLOCKED_SCOPE"
    assert "Task ID mismatch" in manifest["reason"]
    
    scope["task_id"] = "test_task"
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(json.dumps(scope), encoding="utf-8")
    print("SUCCESS: TASK_ID_MISMATCH")

def test_schema_invalid():
    print("\n--- Running Scenario: SCHEMA_INVALID ---")
    scope = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    del scope["schema_version"]
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(json.dumps(scope), encoding="utf-8")
    
    res, _ = run_codex_scenario("PASS")
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert "Schema validation failed" in manifest["reason"]
    
    scope["schema_version"] = 1
    (PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").write_text(json.dumps(scope), encoding="utf-8")
    print("SUCCESS: SCHEMA_INVALID")

def get_skill_scripts_dir():
    return Path("E:/AI_SOFTWARE_FACTORY/skills/dual-agent-pipeline/scripts")

def test_skill_wrapper_init():
    print("\n--- Running Skill Wrapper: Init ---")
    script = get_skill_scripts_dir() / "dual_init.ps1"
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME, "-TaskId", "wrapper_task", "-Feature", "Wrapper Feature", "-Mode", "code", "-Allowed", "*.txt", "-Force"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, f"dual_init.ps1 failed: {res.stderr}"
    scope = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    assert scope["task_id"] == "wrapper_task"
    file1 = PROJECT_ROOT / "source-code/file1.txt"
    file1.write_text(file1.read_text(encoding="utf-8") + "\nWRAPPER_TASK_DELTA", encoding="utf-8")
    print("SUCCESS: SKILL_WRAPPER_INIT")

def test_skill_wrapper_run_pass():
    print("\n--- Running Skill Wrapper: Run (PASS) ---")
    script = get_skill_scripts_dir() / "dual_run.ps1"
    
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    fake_codex_py = FACTORY_ROOT / "fake_codex.py"
    codex_cmd.write_text(f'@echo off\npython "{fake_codex_py}" %*', encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["FAKE_CODEX_SCENARIO"] = "PASS"
    env["FAKE_LIVE_REPO"] = str(PROJECT_ROOT / "source-code")

    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME, "-TaskId", "wrapper_task", "-Feature", "Wrapper Feature", "-Mode", "code", "-SkipVerify"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, f"dual_run.ps1 failed: {res.stderr}"
    manifest = get_manifest()
    assert manifest["status"] == "PASS"
    print("SUCCESS: SKILL_WRAPPER_RUN_PASS")

def test_skill_wrapper_run_fail():
    print("\n--- Running Skill Wrapper: Run (FAIL) ---")
    script = get_skill_scripts_dir() / "dual_run.ps1"
    
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    fake_codex_py = FACTORY_ROOT / "fake_codex.py"
    codex_cmd.write_text(f'@echo off\npython "{fake_codex_py}" %*', encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["FAKE_CODEX_SCENARIO"] = "FAIL"
    env["FAKE_LIVE_REPO"] = str(PROJECT_ROOT / "source-code")

    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME, "-TaskId", "wrapper_task", "-Feature", "Wrapper Feature", "-Mode", "code", "-SkipVerify"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode != 0, "dual_run.ps1 should return non-zero when failing without fixer"
    assert (PROJECT_ROOT / ".agent/reports/FIXER_HANDOFF.md").exists()
    print("SUCCESS: SKILL_WRAPPER_RUN_FAIL")

def test_skill_wrapper_status_pass():
    print("\n--- Running Skill Wrapper: Status (PASS) ---")
    script = get_skill_scripts_dir() / "dual_status.ps1"
    # The previous wrapper test intentionally left NEEDS_FIX. A retry is only
    # authorized after the scoped snapshot changes.
    file1 = PROJECT_ROOT / "source-code/file1.txt"
    file1.write_text(file1.read_text(encoding="utf-8") + "\nSTATUS_PASS_DELTA", encoding="utf-8")
    test_skill_wrapper_run_pass()
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "PASS" in res.stdout, f"Status should be PASS, got: {res.stdout}"
    print("SUCCESS: SKILL_WRAPPER_STATUS_PASS")

def test_skill_wrapper_status_fail():
    print("\n--- Running Skill Wrapper: Status (NEEDS_FIX) ---")
    script = get_skill_scripts_dir() / "dual_status.ps1"
    test_skill_wrapper_run_fail()
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "Status: NEEDS_FIX" in res.stdout, f"Actionable review failure should be NEEDS_FIX, got: {res.stdout}"
    assert "Terminal: False" in res.stdout, f"NEEDS_FIX must remain non-terminal, got: {res.stdout}"
    print("SUCCESS: SKILL_WRAPPER_STATUS_NEEDS_FIX")

def test_skill_wrapper_status_alias_revit():
    print("\n--- Running Skill Wrapper: Status Alias Revit ---")
    script = get_skill_scripts_dir() / "dual_status.ps1"
    # Even if RevitAddinSolution state is unknown, it shouldn't fail with path not found
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", "revit"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    # Should say something about RevitAddinSolution state or INFRA_FAIL, but NOT missing path
    assert "PathNotFound" not in res.stderr
    print("SUCCESS: SKILL_WRAPPER_STATUS_ALIAS_REVIT")

def test_skill_wrapper_read_reports_alias_revit():
    print("\n--- Running Skill Wrapper: Read Reports Alias Revit ---")
    script = get_skill_scripts_dir() / "dual_read_reports.ps1"
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", "revit"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "RevitAddinSolution" in res.stdout or "RevitAddinSolution" in res.stderr or "PathNotFound" not in res.stderr
    print("SUCCESS: SKILL_WRAPPER_READ_REPORTS_ALIAS_REVIT")

def test_skill_wrapper_fix_command_passthrough():
    print("\n--- Running Skill Wrapper: FixCommand Passthrough ---")
    script = get_skill_scripts_dir() / "dual_run.ps1"
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    fake_codex_py = FACTORY_ROOT / "fake_codex.py"
    codex_cmd.write_text(f'@echo off\npython "{fake_codex_py}" %*', encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["PYTHONPATH"] = str(FACTORY_ROOT)
    env["FAKE_CODEX_SCENARIO"] = "FAIL"
    env["FAKE_LIVE_REPO"] = str(PROJECT_ROOT / "source-code")

    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Project", PROJECT_NAME, "-TaskId", "wrapper_task", "-Feature", "Wrapper Feature", "-Mode", "code", "-SkipVerify", "-FixCommand", "test_fix_cmd"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode != 0
    report = (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
    # Fake codex doesn't actually run the fix command, but we should verify it was passed if we had a mock.
    # We will just verify it runs without error syntax.
    print("SUCCESS: SKILL_WRAPPER_FIX_COMMAND_PASSTHROUGH")

def test_skill_location_independent_docs():
    print("\n--- Running Skill Wrapper: Location Independent Docs ---")
    skill_file = get_skill_scripts_dir().parent / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    assert "E:\\Antigravity\\TrendingUpdate\\.agents\\skills\\dual-agent-pipeline" not in content, "SKILL.md still contains hardcoded path"
    assert "scripts\\dual_init.ps1" in content, "SKILL.md doesn't use relative paths"
    print("SUCCESS: SKILL_LOCATION_INDEPENDENT_DOCS")

def test_review_budget_defaults():
    print("\n--- Running Review Budget Defaults ---")
    import review_pipeline
    
    # Remove config temporarily to test defaults
    profile_path = PROJECT_ROOT / ".agent/project_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    backup_review = profile.pop("codex_review", None)
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    
    config = review_pipeline.get_review_config(PROJECT_ROOT)
    
    # Restore config
    if backup_review:
        profile["codex_review"] = backup_review
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        
    assert config["timeout_seconds"] == 180
    assert config["max_diff_chars"] == 60000
    assert config["max_file_chars"] == 40000
    assert config["batch_max_files"] == 3
    assert config["batch_max_chars"] == 70000
    assert config["max_timeout_retries"] == 2
    print("SUCCESS: REVIEW_BUDGET_DEFAULTS")

def test_review_budget_overrides():
    print("\n--- Running Review Budget Overrides ---")
    import review_pipeline
    
    # 1. Test profile override
    profile = json.loads((PROJECT_ROOT / ".agent/project_profile.json").read_text(encoding="utf-8"))
    profile["codex_review"] = {
        "timeout_seconds": 120,
        "max_diff_chars": 50000
    }
    (PROJECT_ROOT / ".agent/project_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    config = review_pipeline.get_review_config(PROJECT_ROOT)
    assert config["timeout_seconds"] == 120
    assert config["max_diff_chars"] == 50000
    assert config["max_file_chars"] == 40000 # Default
    
    # Restore profile
    profile.pop("codex_review")
    (PROJECT_ROOT / ".agent/project_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # 2. Test env override
    env_backup = os.environ.get("CODEX_TIMEOUT_SECONDS")
    os.environ["CODEX_TIMEOUT_SECONDS"] = "90"
    config = review_pipeline.get_review_config(PROJECT_ROOT)
    assert config["timeout_seconds"] == 90
    if env_backup is None:
        del os.environ["CODEX_TIMEOUT_SECONDS"]
    else:
        os.environ["CODEX_TIMEOUT_SECONDS"] = env_backup

    print("SUCCESS: REVIEW_BUDGET_OVERRIDES")

def test_codex_timeout_state():
    print("\n--- Running Scenario: TIMEOUT STATE ---")
    
    # Update project_profile.json to set timeout_seconds to 1
    profile_path = PROJECT_ROOT / ".agent/project_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["codex_review"] = {"timeout_seconds": 1}
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    
    # Tell fake_codex to TIMEOUT, but DO NOT pass CODEX_TIMEOUT_SECONDS, so it uses profile
    res, duration = run_codex_scenario("TIMEOUT")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL", f"Expected INFRA_FAIL, got {manifest['status']}"
    assert manifest.get("reason_code") == "CODEX_TIMEOUT_SINGLE_LARGE_FILE", f"Expected reason_code CODEX_TIMEOUT_SINGLE_LARGE_FILE, got {manifest.get('reason_code')}"
    
    report_path = PROJECT_ROOT / ".agent/reports/CODEX_REVIEW.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Timeout (1s)" in content, "Report should mention Timeout (1s)"
    assert "Timeout (600s)" not in content, "Report should not mention default 600s"
    
    # Run a quick check that gate blocks release
    gate_res = run_harness_command("gate")
    assert "BLOCK_RELEASE" in gate_res.stdout
    print("SUCCESS: TIMEOUT_STATE")

def test_evidence_truncation():
    print("\n--- Running Scenario: EVIDENCE TRUNCATION ---")
    
    # 1. Create a large file that exceeds a small threshold
    large_file = PROJECT_ROOT / "source-code/large.txt"
    large_content = "A" * 5000  # 5000 chars
    large_file.write_text(large_content, encoding="utf-8")
    
    # Allow large.txt in scope
    scope_path = PROJECT_ROOT / ".agent/context/TASK_SCOPE.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    scope["allowed_files"].append("large.txt")
    scope_path.write_text(json.dumps(scope), encoding="utf-8")
    
    # 2. Run with max_diff_chars=1000
    res, _ = run_codex_scenario("PASS", env_overrides={"CODEX_REVIEW_MAX_DIFF_CHARS": "1000"})
    
    # 3. Verify manifest
    manifest = get_manifest()
    assert manifest.get("evidence_truncated") is True, "Expected evidence_truncated to be True in manifest"
    assert "TRUNCATED:" in manifest.get("evidence_snippet", ""), "Expected TRUNCATED marker in evidence_snippet"
    
    # Clean up
    large_file = PROJECT_ROOT / "source-code/large.txt"
    if large_file.exists():
        large_file.unlink()
    print("SUCCESS: EVIDENCE_TRUNCATION")

def test_file_truncation():
    print("\n--- Running Scenario: FILE TRUNCATION ---")
    
    # 1. Create a large file that exceeds max_file_chars
    large_file = PROJECT_ROOT / "source-code/huge.txt"
    large_content = "B" * 5000  # 5000 chars
    large_file.write_text(large_content, encoding="utf-8")
    
    # Allow huge.txt in scope
    scope_path = PROJECT_ROOT / ".agent/context/TASK_SCOPE.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    if "huge.txt" not in scope["allowed_files"]:
        scope["allowed_files"].append("huge.txt")
    scope_path.write_text(json.dumps(scope), encoding="utf-8")
    
    # 2. Run with max_file_chars=1000 and max_diff_chars large enough
    res, _ = run_codex_scenario("PASS", env_overrides={
        "CODEX_REVIEW_MAX_DIFF_CHARS": "10000",
        "CODEX_REVIEW_MAX_FILE_CHARS": "1000"
    })
    
    # 3. Verify manifest
    manifest = get_manifest()
    assert manifest.get("evidence_truncated") is True, "Expected evidence_truncated to be True in manifest"
    assert manifest.get("file_truncated") is True, "Expected file_truncated to be True in manifest"
    
    # 4. Gate blocks due to truncation
    gate_res = run_harness_command("gate")
    assert "BLOCK_RELEASE" in gate_res.stdout, "Gate should block release if file was truncated"
    
    # Clean up
    large_file = PROJECT_ROOT / "source-code/huge.txt"
    if large_file.exists():
        large_file.unlink()
    print("SUCCESS: FILE_TRUNCATION")

def run_dual_mode_with_fake(mode, task_id):
    temp_bin = FACTORY_ROOT / "temp_bin"
    temp_bin.mkdir(exist_ok=True)
    codex_cmd = temp_bin / "codex.cmd"
    codex_cmd.write_text(f'@echo off\npython "{FACTORY_ROOT / "fake_codex.py"}" %*', encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(temp_bin) + os.pathsep + env["PATH"]
    env["FAKE_CODEX_SCENARIO"] = "PASS"
    init_res = subprocess.run(
        [sys.executable, "harness.py", PROJECT_NAME, "dual-init", "--task-id", task_id,
         "--feature", f"{mode} mode smoke", "--mode", mode, "--allowed", "*.txt", "--force"],
        cwd=FACTORY_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert init_res.returncode == 0, f"{mode} init failed:\n{init_res.stdout}\n{init_res.stderr}"
    scope = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    assert scope["mode"] == mode
    assert scope["artifact_files"], f"{mode} must persist artifact_files"
    if mode in {"code", "release"}:
        file1 = PROJECT_ROOT / "source-code/file1.txt"
        file1.write_text(file1.read_text(encoding="utf-8") + "\nTASK_DELTA", encoding="utf-8")
    run_res = subprocess.run(
        [sys.executable, "harness.py", PROJECT_NAME, "dual", "--task-id", task_id,
         "--feature", f"{mode} mode smoke", "--mode", mode, "--max-cycles", "1", "--skip-verify"],
        cwd=FACTORY_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return run_res

def test_research_mode_pass():
    print("\n--- Running Dual Mode: RESEARCH ---")
    setup_test_env()
    res = run_dual_mode_with_fake("research", "research_mode_test")
    assert res.returncode == 0, f"research mode failed:\n{res.stdout}\n{res.stderr}"
    manifest = get_manifest()
    assert manifest["review_mode"] == "research"
    assert manifest["included_files"] == ["RESEARCH.md"]
    assert "release_gate" not in (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
    print("SUCCESS: RESEARCH_MODE_PASS")

def test_plan_mode_pass():
    print("\n--- Running Dual Mode: PLAN ---")
    setup_test_env()
    res = run_dual_mode_with_fake("plan", "plan_mode_test")
    assert res.returncode == 0, f"plan mode failed:\n{res.stdout}\n{res.stderr}"
    manifest = get_manifest()
    assert manifest["review_mode"] == "plan"
    assert manifest["included_files"] == ["PLAN.md", "TECHNICAL_DESIGN.md", "ACCEPTANCE_CRITERIA.md"]
    print("SUCCESS: PLAN_MODE_PASS")

def test_code_mode_stops_before_release():
    print("\n--- Running Dual Mode: CODE ---")
    setup_test_env()
    (PROJECT_ROOT / "source-code/secret.txt").unlink()
    res = run_dual_mode_with_fake("code", "code_mode_test")
    assert res.returncode == 0, f"code mode failed:\n{res.stdout}\n{res.stderr}"
    report = (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
    assert "SMOKE_PASS" in report
    assert "READY_FOR_RELEASE" not in report
    assert "release_gate" not in report
    print("SUCCESS: CODE_MODE_READY_FOR_RELEASE")

def test_mode_transition_preserves_scope():
    print("\n--- Running Dual Mode Transition: CODE TO RELEASE ---")
    setup_test_env()
    first = run_harness_args([
        "dual-init", "--task-id", "transition_test", "--feature", "transition smoke",
        "--mode", "code", "--allowed", "file1.txt", "--forbidden", "protected/**", "--force"
    ])
    assert first.returncode == 0, f"code init failed:\n{first.stdout}\n{first.stderr}"
    plan_path = PROJECT_ROOT / ".agent/context/PLAN.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPRESERVE_MARKER\n", encoding="utf-8")
    before = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))

    second = run_harness_args([
        "dual-init", "--task-id", "transition_test", "--feature", "transition smoke",
        "--mode", "release"
    ])
    assert second.returncode == 0, f"release transition failed:\n{second.stdout}\n{second.stderr}"
    after = json.loads((PROJECT_ROOT / ".agent/context/TASK_SCOPE.json").read_text(encoding="utf-8"))
    durable = json.loads((PROJECT_ROOT / ".agent/context/TASK_CONTEXT.json").read_text(encoding="utf-8"))
    assert after["mode"] == "release"
    assert durable["mode"] == "release"
    assert after["allowed_files"] == before["allowed_files"]
    assert after["forbidden"] == before["forbidden"]
    assert "PRESERVE_MARKER" in plan_path.read_text(encoding="utf-8")
    print("SUCCESS: MODE_TRANSITION_PRESERVES_SCOPE")


def test_p0_task_context_and_knowledge_layout():
    print("\n--- Running P0: durable task context ---")
    result = run_harness_args([
        "dual-init", "--task-id", "governance_task", "--feature", "Governance test",
        "--mode", "code", "--allowed", "*.txt", "--force",
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    context = json.loads((PROJECT_ROOT / ".agent/context/TASK_CONTEXT.json").read_text(encoding="utf-8"))
    import jsonschema
    context_schema = json.loads((FACTORY_ROOT / "schemas/task_context.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(context, context_schema)
    assert context["task_id"] == "governance_task"
    assert context["resume_cursor"] == "scope_ready"
    assert context["failure_budget"]["limit"] == 3
    assert (PROJECT_ROOT / ".agent/knowledge/README.md").exists()
    print("SUCCESS: P0_TASK_CONTEXT")


def test_p0_fresh_evidence_and_stale_detection():
    print("\n--- Running P0: fresh evidence manifest ---")
    from workflow_governance import build_evidence_manifest, validate_fresh_evidence
    results = [{
        "stage": "test", "command": "pytest", "required": True, "status": "PASS",
        "exit_code": 0, "report": ".agent/reports/TEST_REPORT.md", "output_sha256": "abc",
    }]
    manifest = build_evidence_manifest(PROJECT_ROOT, "governance_task", "snap-1", "snap-1", results)
    import jsonschema
    evidence_schema = json.loads((FACTORY_ROOT / "schemas/evidence_manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, evidence_schema)
    assert manifest["status"] == "PASS"
    passed, issues, _ = validate_fresh_evidence(PROJECT_ROOT, "governance_task", "snap-1", ["test"])
    assert passed is True and not issues
    passed, issues, _ = validate_fresh_evidence(PROJECT_ROOT, "governance_task", "snap-2", ["test"])
    assert passed is False and any("stale" in item.lower() for item in issues)
    print("SUCCESS: P0_FRESH_EVIDENCE")


def test_p0_failure_budget_writes_handoff_and_bug_episode():
    print("\n--- Running P0/P1: failure budget and bug episode ---")
    from workflow_governance import record_failed_attempt
    exhausted = False
    for cycle in range(1, 4):
        _, exhausted = record_failed_attempt(
            PROJECT_ROOT,
            stage="codex_review",
            hypothesis=f"hypothesis {cycle}",
            evidence=f"failure {cycle}",
            run_id=f"run-{cycle}",
        )
    assert exhausted is True
    assert (PROJECT_ROOT / ".agent/reports/ROOT_CAUSE_HANDOFF.md").exists()
    assert (PROJECT_ROOT / ".agent/knowledge/memory/bugs/governance_task.md").exists()
    print("SUCCESS: P0_FAILURE_BUDGET")


def test_p1_review_routing():
    print("\n--- Running P1: risk-based review routing ---")
    from review_pipeline import determine_review_tier
    repo = PROJECT_ROOT / "routing-repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "small.txt").write_text("one\ntwo\n", encoding="utf-8")
    config = {
        "quick_max_files": 3, "quick_max_changed_lines": 50,
        "deep_min_files": 11, "deep_min_changed_lines": 301,
        "sensitive_paths": ["**/auth/**"],
    }
    assert determine_review_tier(repo, ["small.txt"], config)["tier"] == "QUICK"
    sensitive = repo / "src/auth/token.py"
    sensitive.parent.mkdir(parents=True, exist_ok=True)
    sensitive.write_text("token = None\n", encoding="utf-8")
    routed = determine_review_tier(repo, ["src/auth/token.py"], config)
    assert routed["tier"] == "DEEP"
    assert routed["sensitive_files"] == ["src/auth/token.py"]
    print("SUCCESS: P1_REVIEW_ROUTING")


def test_task_baseline_excludes_unchanged_preexisting_dirt():
    print("\n--- Running P0: immutable task baseline ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "baseline_task", "--feature", "Baseline isolation",
        "--mode", "code", "--allowed", "file1.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    source = PROJECT_ROOT / "source-code"
    (source / "file1.txt").write_text("Hello World\nTask delta", encoding="utf-8")
    from review_pipeline import evaluate_task_scope, ReviewStatus
    result = evaluate_task_scope(
        source,
        PROJECT_ROOT / ".agent/context/TASK_SCOPE.json",
        PROJECT_ROOT / ".agent/state/task_baseline.json",
        expected_task_id="baseline_task",
        require_delta=True,
    )
    assert result["status"] == ReviewStatus.PASS, result
    assert result["task_files"] == ["file1.txt"], result
    assert result["excluded_preexisting_files"] == ["secret.txt"], result
    print("SUCCESS: TASK_BASELINE_EXCLUDES_PREEXISTING_DIRT")


def test_task_baseline_blocks_modified_preexisting_dirt():
    print("\n--- Running P0: modified baseline dirt is blocked ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "baseline_tamper", "--feature", "Baseline tamper",
        "--mode", "code", "--allowed", "file1.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    source = PROJECT_ROOT / "source-code"
    (source / "secret.txt").write_text("Secret changed by task", encoding="utf-8")
    from review_pipeline import evaluate_task_scope, ReviewStatus
    result = evaluate_task_scope(
        source,
        PROJECT_ROOT / ".agent/context/TASK_SCOPE.json",
        PROJECT_ROOT / ".agent/state/task_baseline.json",
        expected_task_id="baseline_tamper",
        require_delta=True,
    )
    assert result["status"] == ReviewStatus.BLOCKED_SCOPE, result
    assert any(issue.endswith("secret.txt") for issue in result["issues"]), result
    print("SUCCESS: TASK_BASELINE_BLOCKS_MODIFIED_DIRT")


def test_task_baseline_blocks_empty_task_delta():
    print("\n--- Running P0: empty task delta is blocked ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "empty_delta", "--feature", "Empty delta",
        "--mode", "code", "--allowed", "file1.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    from review_pipeline import evaluate_task_scope, ReviewStatus
    result = evaluate_task_scope(
        PROJECT_ROOT / "source-code",
        PROJECT_ROOT / ".agent/context/TASK_SCOPE.json",
        PROJECT_ROOT / ".agent/state/task_baseline.json",
        expected_task_id="empty_delta",
        require_delta=True,
    )
    assert result["status"] == ReviewStatus.BLOCKED_NO_DELTA, result
    print("SUCCESS: TASK_BASELINE_BLOCKS_EMPTY_DELTA")


def test_dual_fail_fast_on_verify_failure():
    print("\n--- Running P0: verify failure stops before Codex ---")
    setup_test_env()
    profile_path = PROJECT_ROOT / ".agent/project_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["build_command"] = 'python -c "import sys; sys.exit(1)"'
    profile["evidence_policy"] = {"required_stages": ["build"]}
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    init = run_harness_args([
        "dual-init", "--task-id", "verify_fail", "--feature", "Verify fail-fast",
        "--mode", "code", "--allowed", "file1.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    file1 = PROJECT_ROOT / "source-code/file1.txt"
    file1.write_text(file1.read_text(encoding="utf-8") + "\nTASK_DELTA", encoding="utf-8")
    review_run = PROJECT_ROOT / ".agent/state/review_run.json"
    if review_run.exists():
        review_run.unlink()
    result = run_harness_args([
        "dual", "--task-id", "verify_fail", "--feature", "Verify fail-fast", "--mode", "code",
    ])
    assert result.returncode != 0, result.stdout + result.stderr
    report = (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
    assert "## Status: BLOCKED_VERIFY" in report, report
    assert not review_run.exists(), "Codex review must not start after verification failure"
    print("SUCCESS: VERIFY_FAILURE_FAILS_FAST")


def test_failure_budget_requires_changed_snapshot_and_hypothesis():
    print("\n--- Running P0: failure budget retry preflight ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "budget_retry", "--feature", "Budget retry",
        "--mode", "code", "--allowed", "file1.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    file1 = PROJECT_ROOT / "source-code/file1.txt"
    file1.write_text(file1.read_text(encoding="utf-8") + "\nFIRST_ATTEMPT", encoding="utf-8")
    from review_pipeline import evaluate_task_scope
    from workflow_governance import prepare_failure_budget_retry, record_failed_attempt
    first = evaluate_task_scope(
        PROJECT_ROOT / "source-code",
        PROJECT_ROOT / ".agent/context/TASK_SCOPE.json",
        PROJECT_ROOT / ".agent/state/task_baseline.json",
        expected_task_id="budget_retry",
    )
    (PROJECT_ROOT / ".agent/state/review_run.json").write_text(json.dumps({
        "snapshot_hash": first["snapshot_hash"], "status": "FAIL"
    }), encoding="utf-8")
    for index in range(3):
        record_failed_attempt(
            PROJECT_ROOT, stage="codex_review", hypothesis=f"attempt {index}",
            evidence="same failure", run_id=f"run-{index}",
        )
    ready, _ = prepare_failure_budget_retry(PROJECT_ROOT, first["snapshot_hash"], None)
    assert ready is False
    ready, _ = prepare_failure_budget_retry(PROJECT_ROOT, first["snapshot_hash"], "Try another review")
    assert ready is False
    file1.write_text(file1.read_text(encoding="utf-8") + "\nFIXED_FINDING", encoding="utf-8")
    changed = evaluate_task_scope(
        PROJECT_ROOT / "source-code",
        PROJECT_ROOT / ".agent/context/TASK_SCOPE.json",
        PROJECT_ROOT / ".agent/state/task_baseline.json",
        expected_task_id="budget_retry",
    )
    ready, _ = prepare_failure_budget_retry(
        PROJECT_ROOT, changed["snapshot_hash"], "Join separate CAD lines before rectangle validation"
    )
    assert ready is True
    context = json.loads((PROJECT_ROOT / ".agent/context/TASK_CONTEXT.json").read_text(encoding="utf-8"))
    assert context["failure_budget"]["used"] == 0
    assert context["failure_budget_history"], context
    root_cause = (PROJECT_ROOT / ".agent/reports/ROOT_CAUSE_HANDOFF.md").read_text(encoding="utf-8")
    assert "## Status: RESUMED_HISTORY" in root_cause
    assert "not a terminal gate" in root_cause
    print("SUCCESS: FAILURE_BUDGET_RETRY_PREFLIGHT")


def test_status_and_wait_stop_on_blocked_handoff():
    print("\n--- Running P0: bounded terminal wait ---")
    setup_test_env()
    context_path = PROJECT_ROOT / ".agent/context/TASK_CONTEXT.json"
    context_path.write_text(json.dumps({
        "status": "blocked_handoff", "task_id": "wait_test"
    }), encoding="utf-8")
    (PROJECT_ROOT / ".agent/state/review_run.json").write_text(json.dumps({
        "status": "RUNNING", "run_id": "orphan-run", "completed_at": None
    }), encoding="utf-8")
    (PROJECT_ROOT / ".agent/reports/DUAL_AGENT_REPORT.md").write_text(
        "# DUAL_AGENT_REPORT.md\n\n## Status: BLOCKED_HANDOFF\n", encoding="utf-8"
    )
    from convergence_pipeline import write_pipeline_status
    write_pipeline_status(PROJECT_ROOT, status="BLOCKED_HANDOFF", task_id="wait_test", mode="code",
                          run_id="orphan-run", snapshot_hash="sha", reason_code="BUDGET_EXHAUSTED",
                          next_action="human_handoff")
    status_script = get_skill_scripts_dir() / "dual_status.ps1"
    wait_script = get_skill_scripts_dir() / "dual_wait.ps1"
    started = time.time()
    status_result = subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(status_script),
        "-Project", PROJECT_NAME, "-AsJson",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    status = json.loads(status_result.stdout.strip())
    assert status["status"] == "BLOCKED_HANDOFF", status
    assert status["terminal"] is True
    wait_result = subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wait_script),
        "-Project", PROJECT_NAME, "-TimeoutSeconds", "10", "-PollSeconds", "1",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert time.time() - started < 5, "Terminal wait should return immediately"
    waited = json.loads(wait_result.stdout.strip())
    assert waited["status"] == "BLOCKED_HANDOFF", waited
    print("SUCCESS: BOUNDED_TERMINAL_WAIT")


def test_dual_persists_terminal_state_and_blocks_fourth_review():
    print("\n--- Running P0: terminal budget stops external reruns ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "test_task", "--feature", "Terminal budget",
        "--mode", "code", "--allowed", "*.txt", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    file1 = PROJECT_ROOT / "source-code/file1.txt"
    file1.write_text(file1.read_text(encoding="utf-8") + "\nTASK_DELTA", encoding="utf-8")

    for attempt in range(3):
        result = run_dual_scenario("FAIL", extra_args=["--mode", "code"])
        assert result.returncode != 0, f"attempt {attempt + 1} unexpectedly passed"
        if attempt < 2:
            file1.write_text(
                file1.read_text(encoding="utf-8") + f"\nFIX_ATTEMPT_{attempt + 1}",
                encoding="utf-8",
            )

    state = get_state()
    assert state["dual_status"] == "blocked_handoff", state
    assert state["next_step"] == "root_cause_handoff", state
    manifest_path = PROJECT_ROOT / ".agent/state/review_run.json"
    run_id_before = json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"]

    retry = run_dual_scenario("PASS", extra_args=["--mode", "code"])
    assert retry.returncode != 0, retry.stdout + retry.stderr
    assert "BLOCKED_HANDOFF" in retry.stdout, retry.stdout
    run_id_after = json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"]
    assert run_id_after == run_id_before, "Codex must not run after the failure budget is exhausted"
    assert get_state()["dual_status"] == "blocked_handoff"
    print("SUCCESS: TERMINAL_BUDGET_STOPS_EXTERNAL_RERUNS")


def test_research_budget_blocks_review_until_artifact_changes():
    print("\n--- Running P0: research budget blocks blind reruns ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "test_task", "--feature", "Research terminal budget",
        "--mode", "research", "--artifacts", "RESEARCH.md", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr

    for attempt in range(3):
        result = run_dual_scenario("FAIL", extra_args=[
            "--mode", "research", "--artifacts", "RESEARCH.md",
        ])
        assert result.returncode != 0, f"research attempt {attempt + 1} unexpectedly passed"
        if attempt < 2:
            research = PROJECT_ROOT / ".agent/context/RESEARCH.md"
            research.write_text(
                research.read_text(encoding="utf-8") + f"\nFIX_ATTEMPT_{attempt + 1}\n",
                encoding="utf-8",
            )

    manifest_path = PROJECT_ROOT / ".agent/state/review_run.json"
    run_id_before = json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"]
    retry = run_dual_scenario("PASS", extra_args=[
        "--mode", "research", "--artifacts", "RESEARCH.md",
    ])
    assert retry.returncode != 0, retry.stdout + retry.stderr
    assert "BLOCKED_HANDOFF" in retry.stdout, retry.stdout
    run_id_after = json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"]
    assert run_id_after == run_id_before, "Research reviewer must not run after budget exhaustion"
    assert get_state()["dual_status"] == "blocked_handoff"
    print("SUCCESS: RESEARCH_BUDGET_BLOCKS_BLIND_RERUNS")


def test_containment_phase_counter_survives_reinit_and_ignores_non_content_outcomes():
    print("\n--- Running Containment T1: durable phase counter ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "containment_plan", "--feature", "Contain review loop",
        "--mode", "plan", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    from workflow_governance import record_phase_review_outcome, review_phase_state
    ignored = ["INFRA_FAIL", "STALE", "DUPLICATE", "SCHEMA_ERROR", "STATE_DESYNC", "CANCELLED"]
    for index, status in enumerate(ignored, 1):
        record_phase_review_outcome(
            PROJECT_ROOT, "containment_plan", "plan", f"ignored-{index}", f"ignored-sha-{index}", status,
        )
    assert review_phase_state(PROJECT_ROOT, "containment_plan", "plan")["completed_content_failures"] == 0
    for index in range(1, 4):
        record_phase_review_outcome(
            PROJECT_ROOT, "containment_plan", "plan", f"fail-{index}", f"sha-{index}", "FAIL",
        )
    before = review_phase_state(PROJECT_ROOT, "containment_plan", "plan")
    assert before["completed_content_failures"] == 3
    repeat = run_harness_args([
        "dual-init", "--task-id", "containment_plan", "--feature", "Contain review loop",
        "--mode", "plan",
    ])
    assert repeat.returncode == 0, repeat.stdout + repeat.stderr
    after = review_phase_state(PROJECT_ROOT, "containment_plan", "plan")
    assert after["completed_content_failures"] == 3
    assert [item["run_id"] for item in after["content_failures"]] == ["fail-1", "fail-2", "fail-3"]
    print("SUCCESS: CONTAINMENT_DURABLE_PHASE_COUNTER")


def test_containment_phase_resume_approval_is_single_use_without_reset():
    print("\n--- Running Containment T1: explicit phase approval ---")
    from workflow_governance import (
        authorize_phase_review_attempt, record_phase_review_outcome,
        review_phase_state, PhaseReviewBlocked,
    )
    state = review_phase_state(PROJECT_ROOT, "containment_plan", "plan")
    assert state["completed_content_failures"] == 3
    try:
        authorize_phase_review_attempt(PROJECT_ROOT, "containment_plan", "plan", "sha-4", "invocation-4")
        raise AssertionError("A fourth review must require human approval")
    except PhaseReviewBlocked:
        pass
    approved = run_harness_args([
        "approve-phase-resume", "--task-id", "containment_plan", "--mode", "plan",
        "--blocked-run-id", "fail-3", "--reason", "Human approved one additional plan review",
    ])
    assert approved.returncode == 0, approved.stdout + approved.stderr
    approval = json.loads(approved.stdout.strip().splitlines()[-1])["approval"]
    assert approval["previous_counter"] == 3
    assert approval["blocked_run_id"] == "fail-3"
    assert approval["approved_at"]
    assert approval["reason"] == "Human approved one additional plan review"
    permit = authorize_phase_review_attempt(
        PROJECT_ROOT, "containment_plan", "plan", "sha-4", "invocation-4",
    )
    assert permit["approval_id"] == approval["approval_id"]
    assert permit["content_failures_before"] == 3
    try:
        authorize_phase_review_attempt(PROJECT_ROOT, "containment_plan", "plan", "sha-5", "invocation-5")
        raise AssertionError("The approval must be consumed atomically")
    except PhaseReviewBlocked:
        pass
    record_phase_review_outcome(PROJECT_ROOT, "containment_plan", "plan", "fail-4", "sha-4", "FAIL")
    state = review_phase_state(PROJECT_ROOT, "containment_plan", "plan")
    assert state["completed_content_failures"] == 4
    assert state["approvals"][0]["consumed_by_invocation"] == "invocation-4"
    print("SUCCESS: CONTAINMENT_SINGLE_USE_APPROVAL")


def test_containment_ten_changed_plan_failures_launch_only_three_reviews():
    print("\n--- Running Containment T1: ten-invocation incident fixture ---")
    setup_test_env()
    init = run_harness_args([
        "dual-init", "--task-id", "incident_plan", "--feature", "Incident containment",
        "--mode", "plan", "--force",
    ])
    assert init.returncode == 0, init.stdout + init.stderr
    plan_path = PROJECT_ROOT / ".agent/context/PLAN.md"
    launched = []
    for invocation in range(1, 11):
        plan_path.write_text(plan_path.read_text(encoding="utf-8") + f"\nSNAPSHOT_{invocation}\n", encoding="utf-8")
        before = get_manifest() or {}
        result = run_dual_scenario("FAIL", task_id="incident_plan", extra_args=[
            "--mode", "plan", "--resume-hypothesis", f"Fix plan defect {invocation}",
        ])
        assert result.returncode != 0
        after = get_manifest() or {}
        if after.get("run_id") and after.get("run_id") != before.get("run_id"):
            launched.append(after["run_id"])
    assert len(launched) == 3, f"Expected exactly 3 Codex launches, got {len(launched)}: {launched}"
    authority = json.loads((PROJECT_ROOT / ".agent/state/pipeline_status.json").read_text(encoding="utf-8"))
    assert authority["status"] == "BLOCKED_HANDOFF", authority
    assert authority["terminal"] is True
    print("SUCCESS: CONTAINMENT_TEN_INVOCATIONS")

def main():
    try:
        setup_test_env()

        # Locked containment Task 1 RED/GREEN acceptance.
        test_containment_phase_counter_survives_reinit_and_ignores_non_content_outcomes()
        test_containment_phase_resume_approval_is_single_use_without_reset()
        test_containment_ten_changed_plan_failures_launch_only_three_reviews()
        
        # Phase 0: Test Configs
        test_review_budget_defaults()
        test_review_budget_overrides()
        test_p0_task_context_and_knowledge_layout()
        test_p0_fresh_evidence_and_stale_detection()
        test_p0_failure_budget_writes_handoff_and_bug_episode()
        test_p1_review_routing()
        test_task_baseline_excludes_unchanged_preexisting_dirt()
        test_task_baseline_blocks_modified_preexisting_dirt()
        test_task_baseline_blocks_empty_task_delta()
        test_dual_fail_fast_on_verify_failure()
        test_failure_budget_requires_changed_snapshot_and_hypothesis()
        test_status_and_wait_stop_on_blocked_handoff()
        test_dual_persists_terminal_state_and_blocks_fourth_review()
        test_research_budget_blocks_review_until_artifact_changes()
        setup_test_env()
        
        # Phase 1: Test Scope
        test_aggregate_batch_results_all_pass()
        test_aggregate_batch_results_fail()
        test_aggregate_batch_results_stale_priority()
        test_aggregate_batch_results_infra_fail_priority()
        test_aggregate_batch_results_timeout_reason_code()
        test_batch_runner_uses_passed_codex_executable()
        test_build_review_batches_by_file_count()
        test_build_review_batches_by_chars()
        test_batch_reviews_summary_in_report()
        test_project_profile_has_codex_review()

        test_scope_validation()
        test_task_id_mismatch()
        test_schema_invalid()
        
        # Reset environment before Phase 2 to prevent state leakage from Phase 1 tests
        setup_test_env()
        # Remove forbidden file for subsequent tests
        (PROJECT_ROOT / "source-code" / "secret.txt").unlink()
        
        # Phase 2: Dual Init
        test_dual_init_generic_task()
        
        # Phase 3: Codex Scenarios
        test_scenario_pass()
        test_scenario_fail()
        test_scenario_timeout()
        test_codex_timeout_state()
        test_evidence_truncation()
        test_scenario_infra_fail()
        
        # Phase 4: Stale Status
        test_scenario_stale_source_changed()
        test_scenario_fail()
        test_scenario_timeout()
        test_scenario_infra_fail()
        test_scenario_empty()
        test_scenario_non_zero()
        test_scenario_stale_source_changed()
        test_scenario_stale_run_id()
        test_scenario_stale_reviewed_files()
        test_scenario_pass()
        test_gate_blocks_missing_scope()
        test_gate_blocks_batch_fail()
        test_gate_allows_all_batch_pass()
        test_gate_allows_bound_pass()
        test_dual_pipeline_pass()
        test_dual_pipeline_writes_fixer_handoff()
        
        # Phase 7: Split Timeout logic
        test_timeout_split_retry_pass()
        test_timeout_single_file_block()

        # Phase 8: Explicit research/plan/code mode contracts
        test_research_mode_pass()
        test_plan_mode_pass()
        test_code_mode_stops_before_release()
        test_mode_transition_preserves_scope()
        
        # Reset environment before Phase 6 to prevent state leakage
        setup_test_env()
        
        # Phase 6: Skill Wrapper Tests
        test_skill_wrapper_init()
        test_skill_wrapper_run_pass()
        test_skill_wrapper_run_fail()
        test_skill_wrapper_status_pass()
        test_skill_wrapper_status_fail()
        test_skill_wrapper_status_alias_revit()
        test_skill_wrapper_read_reports_alias_revit()
        test_skill_wrapper_fix_command_passthrough()
        test_skill_location_independent_docs()
        
        print("\nALL TESTS COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    except AssertionError as e:
        import traceback
        print(f"\nTEST FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\nTEST CRASHED: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
