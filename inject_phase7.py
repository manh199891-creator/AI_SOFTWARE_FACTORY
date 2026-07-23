import re

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_timeout_split_retry_pass():
    print("\\n--- Running Phase 7: test_timeout_split_retry_pass ---")
    res, _ = run_codex_scenario("TIMEOUT_THEN_PASS")
    
    manifest = get_manifest()
    assert manifest["status"] == "PASS"
    batches = manifest["batches"]
    
    timeout_batch = next(b for b in batches if b["status"] == "INFRA_FAIL" and b.get("reason_code") == "CODEX_TIMEOUT")
    assert "children" in timeout_batch
    assert len(timeout_batch["children"]) > 1
    assert all(c["status"] == "PASS" for c in timeout_batch["children"])
    print("SUCCESS: test_timeout_split_retry_pass")

def test_timeout_single_file_block():
    print("\\n--- Running Phase 7: test_timeout_single_file_block ---")
    res, _ = run_codex_scenario("TIMEOUT_SINGLE_FILE")
    
    manifest = get_manifest()
    assert manifest["status"] == "INFRA_FAIL"
    assert manifest["reason_code"] == "CODEX_TIMEOUT"
    batches = manifest["batches"]
    
    timeout_batch = next(b for b in batches if b.get("reason_code") == "CODEX_TIMEOUT_SINGLE_LARGE_FILE")
    assert timeout_batch["status"] == "INFRA_FAIL"
    assert timeout_batch["needs_chunk_review"] == True
    
    res = run_harness_command("gate")
    assert "BLOCK_RELEASE" in res.stdout
    print("SUCCESS: test_timeout_single_file_block")
"""

if "def test_timeout_split_retry_pass():" not in content:
    content = content.replace("def test_project_profile_has_codex_review():", test_code + "\ndef test_project_profile_has_codex_review():")
    content = content.replace("test_project_profile_has_codex_review()", "test_timeout_split_retry_pass()\n        test_timeout_single_file_block()\n        test_project_profile_has_codex_review()")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 7 tests")
else:
    print("Already injected")
