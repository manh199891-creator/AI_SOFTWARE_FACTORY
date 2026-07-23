# E:\AI_SOFTWARE_FACTORY\signal_check.py
# Co hieu (signal file) de Orchestrator biet khi nao subagent hoan thanh.
# Subagent ghi: echo "PLANNER_DONE" > [PROJECT_ROOT]\.agent\state\step_signal.txt
# Orchestrator doc: python signal_check.py [PROJECT_ROOT] PLANNER_DONE
# Output: DONE (va xoa file) hoac WAITING
import sys
from pathlib import Path

VALID_SIGNALS = [
    "PLANNER_DONE",
    "ARCHITECT_DONE",
    "IMPLEMENTER_DONE",
    "QA_DONE",
    "FIXER_DONE",
    "RELEASE_DONE",
]

def check(project_root_str: str, expected: str) -> str:
    f = Path(project_root_str) / ".agent/state/step_signal.txt"
    if f.exists():
        content = f.read_text(encoding="utf-8").strip()
        if content == expected:
            f.unlink()
            return "DONE"
        return f"MISMATCH:{content}"
    return "WAITING"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python signal_check.py [PROJECT_ROOT] [EXPECTED_SIGNAL]")
        print(f"Valid signals: {', '.join(VALID_SIGNALS)}")
        sys.exit(1)
    print(check(sys.argv[1], sys.argv[2]))
