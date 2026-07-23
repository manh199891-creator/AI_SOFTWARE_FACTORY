import re
from pathlib import Path

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_build_review_batches_by_file_count():
    print("\\n--- Running test_build_review_batches_by_file_count ---")
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
    print("\\n--- Running test_build_review_batches_by_chars ---")
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
"""

if "def test_build_review_batches_by_file_count():" not in content:
    content = content.replace("def test_batch_runner_uses_passed_codex_executable():", test_code + "\ndef test_batch_runner_uses_passed_codex_executable():")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 2 tests")
else:
    print("Already injected")
