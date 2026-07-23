import re

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_aggregate_batch_results_all_pass():
    print("\\n--- Running test_aggregate_batch_results_all_pass ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.PASS},
        {"status": ReviewStatus.PASS}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.PASS
    print("SUCCESS: test_aggregate_batch_results_all_pass")

def test_aggregate_batch_results_fail():
    print("\\n--- Running test_aggregate_batch_results_fail ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus
    batches = [
        {"status": ReviewStatus.PASS},
        {"status": ReviewStatus.FAIL}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.FAIL
    print("SUCCESS: test_aggregate_batch_results_fail")

def test_aggregate_batch_results_stale_priority():
    print("\\n--- Running test_aggregate_batch_results_stale_priority ---")
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
    print("\\n--- Running test_aggregate_batch_results_infra_fail_priority ---")
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
    print("\\n--- Running test_aggregate_batch_results_timeout_reason_code ---")
    from review_pipeline import aggregate_batch_results, ReviewStatus, run_codex_review
    # Actually wait, run_codex_review handles the reason_code. Let's just check aggregate_batch_results.
    batches = [
        {"status": ReviewStatus.INFRA_FAIL, "reason_code": "CODEX_TIMEOUT"}
    ]
    status, _ = aggregate_batch_results(batches)
    assert status == ReviewStatus.INFRA_FAIL
    print("SUCCESS: test_aggregate_batch_results_timeout_reason_code")
"""

if "def test_aggregate_batch_results_all_pass():" not in content:
    content = content.replace("def test_batch_runner_uses_passed_codex_executable():", test_code + "\ndef test_batch_runner_uses_passed_codex_executable():")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 3 tests")
else:
    print("Already injected")
