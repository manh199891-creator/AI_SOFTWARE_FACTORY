import argparse
import json
import os
import sys
from pathlib import Path
import datetime

def load_json(path):
    if not path.exists():
        print(f"STATE_SOURCE_MISSING: {path.name}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"STATE_SOURCE_INVALID: {path.name}")
        sys.exit(1)

def check_consistency(pipeline, workflow, review):
    p_status = pipeline.get("status")
    w_status = workflow.get("dual_status", workflow.get("status"))
    r_status = review.get("status")

    # Formal Rule Table for Three-Source Reconciliation
    ALLOWED_STATE_COMBINATIONS = [
        {"pipeline": "CODING", "workflow": ["running", "needs_fix", "RUNNING", "CODING", None]},
        {"pipeline": "REVIEWING", "workflow": ["AWAITING_REVIEW", "running", "needs_fix"], "review": ["RUNNING"]},
        {"pipeline": "REVIEWED_APPROVED", "workflow": ["TASK_COMPLETE", "running", "AWAITING_REVIEW"], "review": ["PASS"]},
        {"pipeline": "REVIEWED_NEEDS_FIX", "workflow": ["AWAITING_REVIEW", "needs_fix", "running"], "review": ["FAIL"]},
        {"pipeline": "INFRA_FAIL", "review": ["INFRA_FAIL"]},
        {"pipeline": "STALE", "review": ["STALE"]}
    ]

    for rule in ALLOWED_STATE_COMBINATIONS:
        if p_status == rule.get("pipeline"):
            w_allowed = rule.get("workflow")
            if w_allowed is not None and w_status not in w_allowed:
                continue
                
            r_allowed = rule.get("review")
            if r_allowed is not None and r_status not in r_allowed:
                continue
                
            return True, "States are consistent"

    return False, f"Conflict: pipeline={p_status}, workflow={w_status}, review={r_status}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    state_dir = project_root / ".agent" / "state"
    
    pipeline_file = state_dir / "pipeline_status.json"
    workflow_file = state_dir / "workflow_state.json"
    review_file = state_dir / "review_run.json"

    # Infrastructure checks
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
