import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/sync_dual_agent_pipeline.ps1"


class SyncPipelineTests(unittest.TestCase):
    def run_sync(self, target: Path, *extra):
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                   "-FactoryRoot", str(ROOT), "-Targets", str(target), *map(str, extra)]
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")

    def make_target(self, name="RevitAddinSolution"):
        root = ROOT / "scratch/sync-tests" / next(tempfile._get_candidate_names()) / name
        root.mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(root.parents[1], ignore_errors=True))
        return root

    def test_validate_only_does_not_modify_target(self):
        target = self.make_target()
        marker = target / "marker.txt"; marker.write_text("same", encoding="utf-8")
        before = marker.read_bytes()
        result = self.run_sync(target, "-ValidateOnly")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("MISSING_RUNTIME_MODULE", result.stderr + result.stdout)
        self.assertEqual(before, marker.read_bytes())

    def test_unsafe_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_sync(Path(temp), "-ValidateOnly")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("UNSAFE_TARGET", result.stderr + result.stdout)

    def test_deploy_backup_validate_and_restore(self):
        target = self.make_target()
        profile = target / ".agents/factory/RevitAddinSolution/.agent/project_profile.json"
        profile.parent.mkdir(parents=True); profile.write_text('{"build_command":"keep","dual_agents":{"auto_fix":true}}', encoding="utf-8")
        backup_root = ROOT / "scratch/sync-tests/backups"
        result = self.run_sync(target, "-BackupRoot", backup_root, "-BackupRunId", "run-one")
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("SYNCED", result.stdout)
        self.assertIn('"keep"', profile.read_text(encoding="utf-8"))
        validate = self.run_sync(target, "-ValidateOnly")
        self.assertEqual(0, validate.returncode, validate.stderr + validate.stdout)
        repeat = self.run_sync(target, "-BackupRoot", backup_root, "-BackupRunId", "run-one")
        self.assertNotEqual(0, repeat.returncode)
        self.assertIn("IMMUTABLE_BACKUP_EXISTS", repeat.stderr + repeat.stdout)


if __name__ == "__main__": unittest.main()
