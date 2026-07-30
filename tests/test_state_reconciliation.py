import json
import subprocess
from pathlib import Path

def setup_state_fixture(tmp_path, pipeline_status=None, workflow_status=None, review_status=None):
    state_dir = tmp_path / ".agent" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    if pipeline_status is not None:
        (state_dir / "pipeline_status.json").write_text(json.dumps({
            "status": pipeline_status,
            "history": [{"from": "UNKNOWN", "to": pipeline_status, "at": "2026-01-01T00:00:00Z"}]
        }), encoding="utf-8")
        
    if workflow_status is not None:
        (state_dir / "workflow_state.json").write_text(json.dumps({
            "status": workflow_status
        }), encoding="utf-8")
        
    if review_status is not None:
        (state_dir / "review_run.json").write_text(json.dumps({
            "status": review_status
        }), encoding="utf-8")
        
    return state_dir

def run_reconciler(project_root):
    reconciler_script = Path(__file__).parent.parent / "reconcile_state.py"
    res = subprocess.run(
        ["python", str(reconciler_script), "--project-root", str(project_root)],
        capture_output=True, text=True
    )
    return res

def test_three_sources_conflict(tmp_path):
    # Test 1 — Ba nguồn mâu thuẫn
    state_dir = setup_state_fixture(tmp_path, "REVIEWED_APPROVED", "TASK_COMPLETE", "REVIEWING")
    
    res = run_reconciler(tmp_path)
    assert res.returncode == 0
    
    pipeline = json.loads((state_dir / "pipeline_status.json").read_text())
    assert pipeline["status"] == "STATE_DESYNC"
    assert pipeline["terminal"] is True
    assert pipeline["ready_for_codex"] is False
    assert len(pipeline["history"]) == 2 # 1 old, 1 new
    
    latest_history = pipeline["history"][-1]
    assert latest_history["reason_code"] == "STATE_SOURCES_CONFLICT"
    assert "REVIEWED_APPROVED" in latest_history["reason"]

def test_three_sources_consistent(tmp_path):
    # Test 2 — Ba nguồn nhất quán
    state_dir = setup_state_fixture(tmp_path, "REVIEWING", "AWAITING_REVIEW", "RUNNING")
    
    res = run_reconciler(tmp_path)
    assert res.returncode == 0
    
    pipeline = json.loads((state_dir / "pipeline_status.json").read_text())
    assert pipeline["status"] == "REVIEWING" # Unchanged
    assert pipeline.get("terminal") is None
    assert len(pipeline["history"]) == 1 # No new history

def test_idempotency(tmp_path):
    # Test 3 — Idempotency
    state_dir = setup_state_fixture(tmp_path, "REVIEWED_APPROVED", "TASK_COMPLETE", "REVIEWING")
    
    # Run once
    run_reconciler(tmp_path)
    pipeline_run1 = json.loads((state_dir / "pipeline_status.json").read_text())
    
    # Run twice
    run_reconciler(tmp_path)
    pipeline_run2 = json.loads((state_dir / "pipeline_status.json").read_text())
    
    assert pipeline_run1 == pipeline_run2
    assert len(pipeline_run2["history"]) == 2

def test_resume_blocked_by_terminal(tmp_path):
    # Test 4 — Resume bị chặn
    state_dir = setup_state_fixture(tmp_path, "STATE_DESYNC", "AWAITING_REVIEW", "RUNNING")
    pipeline = json.loads((state_dir / "pipeline_status.json").read_text())
    pipeline["terminal"] = True
    (state_dir / "pipeline_status.json").write_text(json.dumps(pipeline))
    
    # Call the preflight_integrity directly which cmd_dual uses to enforce integrity
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from runtime_integrity import preflight_integrity, IntegrityError
    
    # Mock a basic profile
    profile = {"integrity_mode": "canonical"}
    try:
        preflight_integrity(Path(__file__).parent.parent, tmp_path, "TestProject", profile)
        assert False, "Should have raised IntegrityError"
    except IntegrityError as e:
        assert e.reason_code == "STATE_DESYNC_TERMINAL"
