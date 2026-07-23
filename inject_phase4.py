import re

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_gate_blocks_batch_fail():
    print("\\n--- Running Gate: batch fail blocks ---")
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
    print("\\n--- Running Gate: all batch pass allows ---")
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
    
    res = run_harness_command("gate")
    assert res.returncode == 0, f"Gate should allow if all batches pass. Output: {res.stdout}"
    assert "ALLOW_RELEASE" in res.stdout
    assert "Batch reviews complete" in res.stdout
    print("SUCCESS: test_gate_allows_all_batch_pass")
"""

if "def test_gate_blocks_batch_fail():" not in content:
    content = content.replace("def test_gate_allows_bound_pass():", test_code + "\ndef test_gate_allows_bound_pass():")
    content = content.replace("test_gate_allows_bound_pass()", "test_gate_blocks_batch_fail()\n        test_gate_allows_all_batch_pass()\n        test_gate_allows_bound_pass()")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 4 tests")
else:
    print("Already injected")
