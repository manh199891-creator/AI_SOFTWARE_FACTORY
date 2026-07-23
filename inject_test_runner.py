import re
from pathlib import Path

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_batch_runner_uses_passed_codex_executable():
    print("\\n--- Running test_batch_runner_uses_passed_codex_executable ---")
    from review_pipeline import run_codex_review_batch
    
    # Create fake codex executable
    fake_dir = PROJECT_ROOT / "fake_codex_dir"
    fake_dir.mkdir(exist_ok=True)
    fake_codex = fake_dir / "fake_codex.cmd"
    fake_codex.write_text("@echo FAKE_CODEX_CALLED", encoding="utf-8")
    
    batch = {"batch_id": 1, "files": ["file1.txt"]}
    manifest = {"run_id": "test_run", "task_id": "test", "feature_name": "test", "snapshot_hash": "hash"}
    config = {"timeout_seconds": 10}
    
    res = run_codex_review_batch(batch, manifest, PROJECT_ROOT, PROJECT_ROOT / "source-code", config, str(fake_codex))
    
    assert "FAKE_CODEX_CALLED" in res["stdout"]
    print("SUCCESS: test_batch_runner_uses_passed_codex_executable")

"""

if "test_batch_runner_uses_passed_codex_executable" not in content:
    content = content.replace("def test_scope_validation():", test_code + "\ndef test_scope_validation():")
    content = content.replace("test_scope_validation()", "test_batch_runner_uses_passed_codex_executable()\n        test_scope_validation()")
    
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected test_batch_runner_uses_passed_codex_executable")
else:
    print("Already injected")
