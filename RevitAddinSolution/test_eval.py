import json, sys
sys.path.insert(0, "E:/AI_SOFTWARE_FACTORY")
from review_pipeline import evaluate_task_scope
from pathlib import Path
r = evaluate_task_scope(
    Path("E:/AI_SOFTWARE_FACTORY/RevitAddinSolution/source-code"),
    Path("E:/AI_SOFTWARE_FACTORY/RevitAddinSolution/.agent/context/TASK_SCOPE.json"),
    Path("E:/AI_SOFTWARE_FACTORY/RevitAddinSolution/.agent/state/task_baseline.json"),
    require_delta=True
)
print(json.dumps(r, indent=2))
