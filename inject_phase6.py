import re

content = open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", encoding="utf-8").read()

test_code = """
def test_project_profile_has_codex_review():
    print("\\n--- Running Phase 6: test_project_profile_has_codex_review ---")
    import json
    # Run setup to create dummy project with current harness logic
    res = run_harness_args(["setup", "test_project", "test_project", "A dummy idea"])
    
    profile_file = PROJECT_ROOT / ".agent/project_profile.json"
    profile = json.loads(profile_file.read_text(encoding="utf-8"))
    
    assert "codex_review" in profile
    assert profile["codex_review"]["timeout_seconds"] == 180
    assert profile["codex_review"]["batch_max_files"] == 3
    print("SUCCESS: test_project_profile_has_codex_review")
"""

if "def test_project_profile_has_codex_review():" not in content:
    content = content.replace("def test_scope_validation():", test_code + "\ndef test_scope_validation():")
    content = content.replace("test_scope_validation()", "test_project_profile_has_codex_review()\n        test_scope_validation()")
    open("E:/AI_SOFTWARE_FACTORY/test_pipeline.py", "w", encoding="utf-8").write(content)
    print("Injected Phase 6 test")
else:
    print("Already injected")
