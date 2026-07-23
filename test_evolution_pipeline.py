import json
import tempfile
from pathlib import Path

from dual_agent_runtime import build_handoff, write_handoff
from evolution_pipeline import (
    append_trajectory,
    build_dataset,
    continuous_status,
    gate_candidate,
    record_canary_outcome,
    shadow_evaluate,
    start_canary,
)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".agent/context").mkdir(parents=True)
    (root / ".agent/state").mkdir(parents=True)
    (root / "source-code").mkdir()
    (root / ".agent/context/TASK_CONTEXT.json").write_text(json.dumps({
        "task_id": "task-a",
        "scope": {"allowed_files": ["src/**"], "forbidden": [".agent/**"]},
    }), encoding="utf-8")
    return root


def test_p2_trajectory_builds_reproducible_dataset(tmp_path):
    root = _project(tmp_path)
    append_trajectory(root, {
        "type": "pipeline_outcome", "task_id": "task-a", "feature": "Fix A",
        "mode": "code", "status": "PASS", "success": True, "steps": [],
    })
    first = build_dataset(root)
    second = build_dataset(root)
    assert first["examples"] == second["examples"]
    assert sum(first["counts"].values()) == 1


def test_p3_shadow_requires_validation_and_holdout(tmp_path):
    root = _project(tmp_path)
    baseline = root / "baseline.md"
    candidate = root / "candidate.md"
    dataset = root / "golden.json"
    baseline.write_text("# Skill\nDo work safely without a defined rollback.", encoding="utf-8")
    candidate.write_text("# Skill\nVerify scope, run tests, rollback on regression.", encoding="utf-8")
    dataset.write_text(json.dumps({"examples": [
        {"id": "v", "split": "validation", "rubric": {"required_terms": ["tests", "rollback"]}},
        {"id": "h", "split": "holdout", "rubric": {"required_terms": ["scope"]}},
    ]}), encoding="utf-8")
    run = shadow_evaluate(root, baseline, candidate, dataset)
    assert run["eligible_for_gate"] is True
    assert Path(run["path"]).exists()


def test_p4_gate_blocks_without_fresh_evidence(tmp_path):
    root = _project(tmp_path)
    candidate = root / "candidate.md"
    candidate.write_text("# Candidate\nSafe content with tests and rollback.", encoding="utf-8")
    run_path = root / "run.json"
    run_path.write_text(json.dumps({
        "run_id": "r1", "mode": "shadow", "eligible_for_gate": True,
        "candidate": str(candidate), "candidate_hash": __import__("hashlib").sha256(
            candidate.read_text(encoding="utf-8").encode()
        ).hexdigest(),
    }), encoding="utf-8")
    gate = gate_candidate(root, run_path)
    assert gate["status"] == "BLOCKED"
    assert any("evidence" in issue.lower() for issue in gate["issues"])


def test_p5_canary_never_auto_promotes_and_rolls_back_on_regression(tmp_path):
    root = _project(tmp_path)
    candidate = root / "candidate.md"
    candidate.write_text("# Candidate\nSafe.", encoding="utf-8")
    gate_path = root / "gate.json"
    gate_path.write_text(json.dumps({
        "gate_id": "g1", "status": "APPROVED_FOR_CANARY",
        "candidate": str(candidate), "candidate_hash": "hash",
    }), encoding="utf-8")
    canary = start_canary(root, gate_path, 10)
    canary_path = Path(canary["path"])
    updated = record_canary_outcome(canary_path, "regression")
    assert updated["status"] == "ROLLBACK_REQUIRED"
    assert continuous_status(root)["auto_promotion_enabled"] is False


def test_dual_handoff_binds_codex_snapshot_and_single_writer(tmp_path):
    root = _project(tmp_path)
    handoff = build_handoff(root, "task-a", "Fix A", 1, "code", {
        "run_id": "review-1", "snapshot_hash": "abc", "findings": [],
    })
    path = write_handoff(root, handoff)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["role_contract"]["writer"] == "antigravity"
    assert saved["role_contract"]["concurrent_writes_allowed"] is False
    assert saved["review_snapshot_hash"] == "abc"


if __name__ == "__main__":
    tests = [
        test_p2_trajectory_builds_reproducible_dataset,
        test_p3_shadow_requires_validation_and_holdout,
        test_p4_gate_blocks_without_fresh_evidence,
        test_p5_canary_never_auto_promotes_and_rolls_back_on_regression,
        test_dual_handoff_binds_codex_snapshot_and_single_writer,
    ]
    for test in tests:
        with tempfile.TemporaryDirectory(prefix="factory_evolution_test_") as directory:
            test(Path(directory))
        print(f"PASS: {test.__name__}")
