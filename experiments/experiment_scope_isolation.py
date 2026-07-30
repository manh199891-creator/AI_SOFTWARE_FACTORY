import json
import subprocess
import tempfile
from pathlib import Path

from review_pipeline import ReviewStatus, capture_task_baseline, evaluate_task_scope


def run_git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_explicit_included_files_isolate_unrelated_dirty_changes():
    with tempfile.TemporaryDirectory() as temp:
        project = Path(temp)
        repo = project / "source-code"
        context = project / ".agent" / "context"
        repo.mkdir(parents=True)
        context.mkdir(parents=True)
        run_git(repo, "init")
        run_git(repo, "config", "user.email", "test@example.com")
        run_git(repo, "config", "user.name", "Test")
        (repo / "target.txt").write_text("base", encoding="utf-8")
        (repo / "unrelated.txt").write_text("base", encoding="utf-8")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-m", "base")

        scope_path = context / "TASK_SCOPE.json"
        scope_path.write_text(json.dumps({
            "schema_version": 1,
            "task_id": "isolated-task",
            "repository_root": str(repo),
            "allowed_files": ["*.txt"],
            "included_files": ["target.txt"],
            "forbidden": []
        }), encoding="utf-8")
        baseline = capture_task_baseline(project, "isolated-task")
        (repo / "target.txt").write_text("task change", encoding="utf-8")
        (repo / "unrelated.txt").write_text("other change", encoding="utf-8")

        result = evaluate_task_scope(
            repo,
            scope_path,
            project / ".agent" / "state" / "task_baseline.json",
            expected_task_id="isolated-task",
            require_delta=True,
        )
        assert baseline["task_id"] == "isolated-task"
        assert result["status"] == ReviewStatus.PASS
        assert result["task_files"] == ["target.txt"]
        assert "unrelated.txt" not in result["task_files"]


if __name__ == "__main__":
    test_explicit_included_files_isolate_unrelated_dirty_changes()
    print("PASS: explicit included_files isolates unrelated dirty changes")
