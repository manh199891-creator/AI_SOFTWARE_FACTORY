import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_integrity as integrity
import harness


ROOT = Path(__file__).resolve().parent


class RuntimeIntegrityTests(unittest.TestCase):
    def copy_factory_bundle(self, destination: Path):
        for name in integrity.RUNTIME_FILES:
            shutil.copy2(ROOT / name, destination / name)
        shutil.copytree(ROOT / "schemas", destination / "schemas")
        shutil.copytree(ROOT / "skills", destination / "skills")
        for rel in (".agent/project_profile.json", "RevitAddinSolution/.agent/project_profile.json",
                    "NavisAddinSolution/.agent/project_profile.json"):
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)

    def test_manifest_covers_complete_runtime_skills_schemas_and_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_factory_bundle(root)
            path = root / "runtime_manifest.json"
            manifest = integrity.build_manifest(root, path)
            names = {item["path"] for item in manifest["files"]}
            self.assertIn("convergence_pipeline.py", names)
            self.assertIn("runtime_integrity.py", names)
            self.assertIn("skills/dual-agent/scripts/dual_orchestrate.ps1", names)
            self.assertIn("skills/dual-agent-pipeline/scripts/dual_checkpoint.ps1", names)
            self.assertIn("schemas/writer_checkpoint.schema.json", names)
            self.assertEqual("PASS", integrity.verify_manifest(root, path)["status"])
            (root / "harness.py").write_text("drift", encoding="utf-8")
            with self.assertRaisesRegex(integrity.IntegrityError, "harness.py"):
                integrity.verify_manifest(root, path)

    def test_managed_profile_merge_preserves_project_specific_fields(self):
        target = {"build_command":"custom", "codex_review":{"timeout_seconds":999},
                  "dual_agents":{"auto_fix":True,"antigravity_model":"custom"}}
        canonical = {"dual_agents":{"auto_fix":False,"convergence_v2":True,
            "execution_policy":"checkpointed","review_boundaries":["phase_completion"]}}
        merged = integrity.merge_managed_profile(target, canonical)
        self.assertEqual("custom", merged["build_command"])
        self.assertEqual(999, merged["codex_review"]["timeout_seconds"])
        self.assertEqual("custom", merged["dual_agents"]["antigravity_model"])
        self.assertFalse(merged["dual_agents"]["auto_fix"])

    def test_factory_source_root_is_contained_and_supports_dot(self):
        self.assertEqual(ROOT.resolve(), integrity.resolve_source_root(ROOT, {"source_path":"."}))
        with self.assertRaises(integrity.IntegrityError):
            integrity.resolve_source_root(ROOT, {"source_path":"../outside"})

    def test_integrity_preflight_blocks_all_entry_points_before_process_or_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as temp:
            root = Path(temp)
            (root / ".agent").mkdir()
            profile = {"integrity_mode":"canonical", "source_path":"."}
            failure = integrity.IntegrityError("RUNTIME_DRIFT", "tampered runtime")
            with patch.object(harness, "load_project", return_value=(root, profile)), \
                 patch.object(harness, "preflight_integrity", side_effect=failure), \
                 patch("subprocess.Popen") as popen:
                for command, args in (
                    (harness.cmd_dual_init, ("project", root, "--task-id", "task", "--feature", "feature")),
                    (harness.cmd_dual, ("project", root, "--task-id", "task", "--feature", "feature")),
                    (harness.cmd_codex, ("project", root, "--task-id", "task")),
                ):
                    with self.assertRaises(SystemExit) as raised:
                        command(*args)
                    self.assertEqual(3, raised.exception.code)
            popen.assert_not_called()
            self.assertFalse((root / ".agent/state").exists())

    def test_status_wrapper_exposes_writer_fields_and_wait_fails_fast_on_desync(self):
        fixture_parent = ROOT / "scratch/status-tests"
        fixture_parent.mkdir(parents=True, exist_ok=True)
        fixture = Path(tempfile.mkdtemp(dir=fixture_parent))
        self.addCleanup(lambda: shutil.rmtree(fixture, ignore_errors=True))
        state = fixture / ".agent/state"; reports = fixture / ".agent/reports"
        state.mkdir(parents=True); reports.mkdir(parents=True)
        authority = {
            "status_version":2,"status":"RUNNING","terminal":False,"task_id":"task","mode":"plan",
            "lifecycle_phase":"PLAN","review_kind":"checkpoint","review_boundary_id":"RB-1",
            "run_id":"run-1","snapshot_hash":"sha-1","previous_snapshot_hash":None,
            "reason_code":"CHECKPOINT_PASS","reason":"continue","next_action":"continue_current_phase",
            "writer_status":"TASK_COMPLETE","writer_checkpoint_id":"cp-1","work_item_current":3,
            "work_item_total":8,"phase_review_count":1,"batch_review_count":1,
            "failure_budget_remaining":2,"ready_for_codex":False,"history":[],"updated_at":"now"
        }
        (state / "pipeline_status.json").write_text(json.dumps(authority), encoding="utf-8")
        (state / "review_run.json").write_text(json.dumps({"task_id":"task","run_id":"run-1","snapshot_hash":"sha-1","status":"PASS"}), encoding="utf-8")
        (state / "writer_checkpoint.json").write_text(json.dumps({"task_id":"task","checkpoint_id":"cp-1","snapshot_hash":"sha-1"}), encoding="utf-8")
        (reports / "DUAL_AGENT_REPORT.md").write_text("wrong legacy report identity", encoding="utf-8")
        project = fixture.relative_to(ROOT).as_posix()
        status_script = ROOT / "skills/dual-agent-pipeline/scripts/dual_status.ps1"
        base = ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(status_script),"-Project",project]
        text_result = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, text_result.returncode, text_result.stderr + text_result.stdout)
        for field in ("ANTI_PHASE: PLAN","ANTI_PROGRESS: 3/8","ANTI_STATUS: TASK_COMPLETE",
                      "LAST_CHECKPOINT: cp-1","READY_FOR_CODEX: NO","CODEX_STATUS: PASS",
                      "NEXT_ACTION: continue_current_phase"):
            self.assertIn(field, text_result.stdout)
        json_result = subprocess.run(base + ["-AsJson"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        payload = json.loads(json_result.stdout)
        for field in ("ANTI_PHASE","ANTI_PROGRESS","ANTI_STATUS","LAST_CHECKPOINT",
                      "READY_FOR_CODEX","CODEX_STATUS","NEXT_ACTION"):
            self.assertIn(field, payload)
        (state / "review_run.json").write_text(json.dumps({"task_id":"other","run_id":"wrong","snapshot_hash":"wrong","status":"RUNNING"}), encoding="utf-8")
        wait_script = ROOT / "skills/dual-agent-pipeline/scripts/dual_wait.ps1"
        waited = subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(wait_script),
            "-Project",project,"-TimeoutSeconds","10","-PollSeconds","1"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        self.assertEqual(2, waited.returncode)
        waited_payload = json.loads(waited.stdout)
        self.assertEqual("STATE_DESYNC", waited_payload["status"])
        self.assertTrue(waited_payload["terminal"])


if __name__ == "__main__": unittest.main()
