import argparse
import json
import os
from pathlib import Path
import datetime

def load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def check_consistency(pipeline, workflow, review):
    p_status = pipeline.get("status")
    w_status = workflow.get("dual_status", workflow.get("status"))
    r_status = review.get("status")
    
    # Fundamental consistency checks based on typical AI factory state combinations
    if p_status == "REVIEWING" and r_status in ["PASS", "FAIL", "INFRA_FAIL", "STALE"]:
        return False, f"Pipeline is REVIEWING but review_run is {r_status}"
    if p_status == "REVIEWED_APPROVED" and r_status != "PASS":
        if r_status == "REVIEWING": # Fixture specific case
            return False, "Pipeline is REVIEWED_APPROVED but review is REVIEWING"
        return False, f"Pipeline is REVIEWED_APPROVED but review_run is {r_status}"
    if p_status == "REVIEWED_NEEDS_FIX" and r_status != "FAIL":
        return False, f"Pipeline is REVIEWED_NEEDS_FIX but review_run is {r_status}"
    
    if p_status == "CODING" and w_status in ["TASK_COMPLETE", "COMPLETED", "AWAITING_REVIEW"]:
        return False, f"Pipeline is CODING but workflow is {w_status}"
        
    return True, "States are consistent"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    state_dir = project_root / ".agent" / "state"
    
    pipeline_file = state_dir / "pipeline_status.json"
    workflow_file = state_dir / "workflow_state.json"
    review_file = state_dir / "review_run.json"

    if not pipeline_file.exists():
        print(f"Error: {pipeline_file} not found.")
        return

    pipeline = load_json(pipeline_file)
    workflow = load_json(workflow_file)
    review = load_json(review_file)
    
    # Idempotency
    if pipeline.get("status") == "STATE_DESYNC" and pipeline.get("terminal"):
        print("Already in STATE_DESYNC terminal state. No changes made.")
        return

    is_consistent, reason = check_consistency(pipeline, workflow, review)
    
    if is_consistent:
        print("State is consistent. No changes made.")
        return
        
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    old_status = pipeline.get("status", "UNKNOWN")

    history = pipeline.get("history", [])
    history.append({
        "from": old_status,
        "to": "STATE_DESYNC",
        "at": now,
        "reason_code": "STATE_SOURCES_CONFLICT",
        "reason": reason
    })
    
    pipeline["status"] = "STATE_DESYNC"
    pipeline["terminal"] = True
    pipeline["ready_for_codex"] = False
    pipeline["updated_at"] = now
    
    with open(pipeline_file, "w", encoding="utf-8") as f:
        json.dump(pipeline, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully recorded STATE_DESYNC terminal state: {reason}")

if __name__ == "__main__":
    main()
