import re

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_batch_reviews_summary_in_report():
    print("\\n--- Running Phase 5: test_batch_reviews_summary_in_report ---")
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
"""

if "def test_batch_reviews_summary_in_report():" not in content:
    content = content.replace("def test_scope_validation():", test_code + "\ndef test_scope_validation():")
    content = content.replace("test_scope_validation()", "test_batch_reviews_summary_in_report()\n        test_scope_validation()")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 5 test")
else:
    print("Already injected")
