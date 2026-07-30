import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dual_agent_runtime
import harness
import convergence_pipeline as convergence
import review_pipeline
import workflow_governance as governance


class DualLoopGuardTests(unittest.TestCase):
    def make_project(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / ".agent/context").mkdir(parents=True)
        (root / ".agent/state").mkdir(parents=True)
        (root / "source-code").mkdir()
        (root / ".agent/context/TASK_CONTEXT.json").write_text(
            json.dumps({
                "scope": {
                    "allowed_files": [".agent/context/RESEARCH.md"],
                    "forbidden": [".agent/**", ".agent/state/**", ".agent/reports/**"],
                }
            }),
            encoding="utf-8",
        )
        self.addCleanup(temporary.cleanup)
        return root

    def test_research_handoff_has_editable_artifact_without_broad_agent_ban(self):
        root = self.make_project()
        handoff = dual_agent_runtime.build_handoff(
            root, "task", "feature", 1, "research", {"run_id": "run-1", "findings": []}
        )

        self.assertIn(".agent/context/RESEARCH.md", handoff["required_inputs"])
        self.assertNotIn(".agent/**", handoff["forbidden"])
        self.assertIn(".agent/state/**", handoff["forbidden"])
        self.assertFalse(handoff["completion_contract"]["must_run_verification"])
        self.assertTrue(any("Do not delete substantive sections" in rule for rule in handoff["writer_rules"]))

    def test_artifact_mode_scope_removes_only_broad_agent_ban(self):
        forbidden = [".git/**", ".agent/**", ".agent/state/**", ".agent/reports/**"]

        repaired = harness.normalize_mode_forbidden(forbidden, "research")

        self.assertNotIn(".agent/**", repaired)
        self.assertIn(".agent/state/**", repaired)
        self.assertIn(".agent/reports/**", repaired)
        self.assertIn(".agent/**", harness.normalize_mode_forbidden(forbidden, "code"))

    def test_existing_research_scope_is_repaired_before_pipeline_use(self):
        root = self.make_project()
        scope_path = root / ".agent/context/TASK_SCOPE.json"
        scope_path.write_text(json.dumps({
            "task_id": "task",
            "mode": "research",
            "allowed_files": [".agent/context/RESEARCH.md"],
            "forbidden": [".agent/**", ".agent/state/**"],
        }), encoding="utf-8")

        scope = harness.ensure_task_scope(root, {}, "task", mode="research")

        self.assertNotIn(".agent/**", scope["forbidden"])
        persisted = json.loads(scope_path.read_text(encoding="utf-8"))
        self.assertEqual(scope, persisted)

    def test_finding_fingerprint_is_stable_across_order_body_and_line_changes(self):
        first = {"findings": [
            {"severity": "P1", "file": "A.cs", "title": "Broken gate", "body": "old", "line": 10},
            {"severity": "P2", "file": "B.cs", "title": "Missing test", "body": "one", "line": 20},
        ]}
        second = {"findings": [
            {"severity": "p2", "file": "b.cs", "title": " Missing   test ", "body": "two", "line": 99},
            {"severity": "p1", "file": "a.cs", "title": "Broken gate", "body": "new", "line": 30},
        ]}

        self.assertEqual(
            harness.review_findings_fingerprint(first),
            harness.review_findings_fingerprint(second),
        )
        second["findings"][0]["title"] = "Different defect"
        self.assertNotEqual(
            harness.review_findings_fingerprint(first),
            harness.review_findings_fingerprint(second),
        )

    def test_antigravity_fixer_uses_project_root_for_research(self):
        root = self.make_project()
        completed = SimpleNamespace(returncode=0, communicate=lambda timeout: ("fixed", ""))
        with patch.object(dual_agent_runtime, "find_antigravity", return_value="anti.exe"), \
             patch.object(dual_agent_runtime.subprocess, "Popen", return_value=completed) as run:
            ok, _ = dual_agent_runtime.run_antigravity_fixer(
                root, {"mode": "research"}, timeout_seconds=60
            )

        self.assertTrue(ok)
        self.assertEqual(root, run.call_args.kwargs["cwd"])

    def test_antigravity_fixer_uses_source_root_for_code(self):
        root = self.make_project()
        completed = SimpleNamespace(returncode=0, communicate=lambda timeout: ("fixed", ""))
        with patch.object(dual_agent_runtime, "find_antigravity", return_value="anti.exe"), \
             patch.object(dual_agent_runtime.subprocess, "Popen", return_value=completed) as run:
            ok, _ = dual_agent_runtime.run_antigravity_fixer(
                root, {"mode": "code"}, timeout_seconds=60
            )

        self.assertTrue(ok)
        self.assertEqual(root / "source-code", run.call_args.kwargs["cwd"])

    def test_markdown_handoff_does_not_delegate_pipeline_control(self):
        root = self.make_project()
        harness.write_fixer_handoff(
            "navis", root, "task", "feature", 1, "review failed", "research", {"findings": []}
        )
        content = (root / ".agent/reports/FIXER_HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn(".agent/context/RESEARCH.md", content)
        self.assertIn("Do not invoke Codex or rerun the dual pipeline", content)
        self.assertNotIn("harness.py navis dual", content)

    def test_external_fixer_handoff_is_actionable_not_terminal(self):
        root = self.make_project()
        (root / ".agent/state/workflow_state.json").write_text(
            json.dumps({"task_id": "task", "dual_status": "running"}), encoding="utf-8"
        )

        with self.assertRaises(SystemExit) as stopped:
            harness.pause_dual_for_external_fixer(
                root, "task", "feature", "research", [], "writer required"
            )

        self.assertEqual(2, stopped.exception.code)
        state = json.loads((root / ".agent/state/workflow_state.json").read_text(encoding="utf-8"))
        self.assertEqual("needs_fix", state["dual_status"])
        self.assertEqual("external_fixer", state["next_step"])
        report = (root / ".agent/reports/DUAL_AGENT_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("## Status: NEEDS_FIX", report)
        self.assertNotIn("## Status: BLOCKED_HANDOFF", report)

    def test_semantic_finding_identity_survives_reword_and_relocation(self):
        first = {"severity": "P1", "file": "RESEARCH.md", "line": 10,
                 "title": "Gold set cannot be reproduced", "body": "Missing adjudication protocol"}
        second = {"severity": "P2", "file": "PLAN.md", "line": 800,
                  "title": "Benchmark truth data is not repeatable", "body": "Gold-set adjudicators are unspecified"}
        self.assertEqual(convergence.normalize_finding_id(first), convergence.normalize_finding_id(second))

    def test_contract_deletion_is_detected_before_review(self):
        root = self.make_project()
        artifact = root / ".agent/context/RESEARCH.md"
        artifact.write_text("# Benchmark protocol\n- Gold construction\n- Adjudication\n- Versioning\n", encoding="utf-8")
        convergence.seed_contract_ledger(root, "sha-a", ["RESEARCH.md"])
        artifact.write_text("# Summary\nShortened.\n", encoding="utf-8")
        regressions = convergence.check_contract_regressions(root, ["RESEARCH.md"])
        self.assertTrue(any(item["contract_id"].startswith("benchmark.") for item in regressions))

    def test_section_transport_covers_every_character(self):
        root = self.make_project()
        text = "preamble\n# One\n" + ("a" * 30) + "\n# Two\n" + ("b" * 30)
        (root / ".agent/context/RESEARCH.md").write_text(text, encoding="utf-8")
        transport = convergence.section_batches(root, ["RESEARCH.md"], 35)
        reconstructed = "".join(item["content"] for item in transport["sections"])
        self.assertEqual(text, reconstructed)
        self.assertEqual(0, transport["excluded_bytes"])
        self.assertTrue(transport["complete"])

    def test_two_non_progress_snapshots_require_checkpoint(self):
        root = self.make_project()
        empty = {"entries": []}
        one = {"entries": [{"finding_id": "benchmark.gold", "status": "OPEN"}]}
        first = convergence.evaluate_convergence(root, "task", "research", "r1", "s1", empty, one)
        two = {"entries": one["entries"] + [{"finding_id": "security.auth", "status": "OPEN"}]}
        second = convergence.evaluate_convergence(root, "task", "research", "r2", "s2", one, two)
        self.assertEqual("NEEDS_FIX", first["decision"])
        self.assertEqual("NO_PROGRESS", second["decision"])

    def test_pipeline_status_is_single_structured_authority(self):
        root = self.make_project()
        status = convergence.write_pipeline_status(
            root, status="NEEDS_FIX", task_id="task", mode="research", run_id="run",
            snapshot_hash="sha", reason_code="LINT", reason="fix", next_action="writer",
        )
        persisted = json.loads((root / ".agent/state/pipeline_status.json").read_text(encoding="utf-8"))
        self.assertEqual(status, persisted)
        self.assertEqual(2, persisted["status_version"])
        for field in ("terminal", "lifecycle_phase", "review_kind", "review_boundary_id",
                      "writer_status", "writer_checkpoint_id", "work_item_current",
                      "work_item_total", "phase_review_count", "failure_budget_remaining",
                      "ready_for_codex"):
            self.assertIn(field, persisted)

    def test_pipeline_status_transition_matrix_and_invalid_write_preserves_file(self):
        root = self.make_project()
        status = convergence.write_pipeline_status(root, status="RUNNING", task_id="task", mode="plan",
            run_id=None, snapshot_hash="s1")
        status = convergence.write_pipeline_status(root, status="NEEDS_FIX", task_id="task", mode="plan",
            run_id="r1", snapshot_hash="s1")
        status = convergence.write_pipeline_status(root, status="READY_FOR_REVIEW", task_id="task", mode="plan",
            run_id="r1", snapshot_hash="s2", ready_for_codex=True)
        before = (root / ".agent/state/pipeline_status.json").read_bytes()
        with self.assertRaises(ValueError):
            convergence.write_pipeline_status(root, status="PASS", task_id="other", mode="plan",
                run_id="r2", snapshot_hash="s2")
        self.assertEqual(before, (root / ".agent/state/pipeline_status.json").read_bytes())
        self.assertEqual("READY_FOR_REVIEW", status["status"])

    def test_legacy_status_migration_is_idempotent(self):
        root = self.make_project()
        path = root / ".agent/state/pipeline_status.json"
        path.write_text(json.dumps({"status_version": 1, "status": "NEEDS_FIX", "task_id": "task",
            "mode": "plan", "run_id": "r1", "snapshot_hash": "s1", "updated_at": "now"}), encoding="utf-8")
        first = convergence.migrate_pipeline_status(root, task_id="task", mode="plan")
        second = convergence.migrate_pipeline_status(root, task_id="task", mode="plan")
        self.assertEqual(first, second)
        self.assertEqual(2, second["status_version"])

    def test_writer_checkpoint_requires_all_finding_evidence(self):
        root = self.make_project()
        (root / ".agent/context/TASK_CONTEXT.json").write_text(json.dumps({"task_id":"task","mode":"plan",
            "scope":{"allowed_files":["docs/**"],"forbidden":[]}}), encoding="utf-8")
        (root / ".agent/context/TASK_SCOPE.json").write_text(json.dumps({"task_id":"task",
            "allowed_files":["docs/**"],"forbidden":[]}), encoding="utf-8")
        (root / ".agent/state/finding_ledger.json").write_text(json.dumps({"entries":[
            {"finding_id":"schema.contract","status":"OPEN"}]}), encoding="utf-8")
        payload = {"task_id":"task","phase":"plan","work_item_current":1,"work_item_total":1,
            "status":"PHASE_COMPLETE","snapshot_hash":"s2","changed_files":["docs/plan.md"],
            "checks":[{"name":"tests","status":"PASS","evidence":"ok"}],"finding_claims":[],
            "blockers":[],"risks":[],"retry_hypothesis":"fixed contract","ready_for_codex":True,
            "review_kind":"phase_gate","review_boundary_id":"RB-1"}
        with self.assertRaisesRegex(ValueError, "FINDINGS_UNACCOUNTED"):
            governance.record_writer_checkpoint(root, payload, "s2")
        payload["finding_claims"] = [{"finding_id":"schema.contract","evidence":"test_contract passes"}]
        checkpoint = governance.record_writer_checkpoint(root, payload, "s2")
        self.assertEqual("READY", checkpoint["reservation"]["state"])

    def test_checkpoint_reservation_allows_one_logical_review(self):
        root = self.make_project()
        checkpoint = {"schema_version":1,"checkpoint_id":"cp1","task_id":"task","phase":"plan",
            "snapshot_hash":"s2","ready_for_codex":True,
            "reservation":{"state":"READY","run_id":None,"updated_at":"now"}}
        (root / ".agent/state/writer_checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
        governance.reserve_writer_checkpoint(root, "task", "plan", "s2", "run1", "checkpoint", "RB-1")
        with self.assertRaisesRegex(ValueError, "ALREADY_RESERVED"):
            governance.reserve_writer_checkpoint(root, "task", "plan", "s2", "run2", "checkpoint", "RB-1")
        governance.transition_checkpoint_reservation(root, "run1", "LAUNCHED")
        consumed = governance.transition_checkpoint_reservation(root, "run1", "CONSUMED")
        self.assertEqual("CONSUMED", consumed["reservation"]["state"])

    def test_stale_prelaunch_reservation_recovers_but_launched_run_does_not(self):
        root = self.make_project()
        checkpoint = {"schema_version":1,"checkpoint_id":"cp1","task_id":"task","phase":"plan",
            "snapshot_hash":"s2","ready_for_codex":True,
            "reservation":{"state":"RESERVED","run_id":"run1","updated_at":"2026-01-01T00:00:00+00:00"}}
        path = root / ".agent/state/writer_checkpoint.json"
        path.write_text(json.dumps(checkpoint), encoding="utf-8")
        recovered = governance.reconcile_checkpoint_reservation(root, stale_after_seconds=1)
        self.assertEqual("READY", recovered["reservation"]["state"])
        self.assertIsNone(recovered["reservation"]["run_id"])
        recovered["reservation"].update(state="LAUNCHED", run_id="run2", updated_at="2026-01-01T00:00:00+00:00")
        path.write_text(json.dumps(recovered), encoding="utf-8")
        observed = governance.reconcile_checkpoint_reservation(root, stale_after_seconds=1)
        self.assertEqual("LAUNCHED", observed["reservation"]["state"])
        self.assertEqual("run2", observed["reservation"]["run_id"])

    def test_phase_and_batch_review_counts_are_durable(self):
        root = self.make_project()
        before = {"entries":[
            {"finding_id":"a","status":"OPEN"}, {"finding_id":"b","status":"OPEN"}]}
        after = {"entries":[
            {"finding_id":"a","status":"VERIFIED_RESOLVED"}, {"finding_id":"b","status":"OPEN"}]}
        decisions = [convergence.evaluate_convergence(root,"task","plan",f"r{i}",f"s{i}",before,after)
                     for i in range(1,4)]
        self.assertEqual([1,2,3], [item["phase_review_count"] for item in decisions])
        self.assertEqual("BATCH_REVIEW_CEILING", decisions[-1]["decision"])
        state = json.loads((root / ".agent/state/convergence_state.json").read_text(encoding="utf-8"))
        self.assertEqual(3, state["phases"]["task:plan"]["review_count"])

    def test_multi_lens_partial_completion_is_infra_fail(self):
        root = self.make_project()
        (root / ".agent/reports").mkdir(parents=True, exist_ok=True)
        (root / ".agent/context/RESEARCH.md").write_text("# Complete\nEvidence\n", encoding="utf-8")
        calls = []

        def child(*args, **kwargs):
            calls.append(kwargs.get("review_lens"))
            status = review_pipeline.ReviewStatus.INFRA_FAIL if len(calls) == 2 else review_pipeline.ReviewStatus.PASS
            return {"run_id": f"r{len(calls)}", "status": status, "snapshot_hash": "sha",
                    "reason": status, "findings": []}

        with patch.object(review_pipeline, "get_artifact_snapshot", return_value=("sha", ["RESEARCH.md"])), \
             patch.object(review_pipeline, "get_review_config", return_value={"max_diff_chars": 10000}), \
             patch.object(review_pipeline, "run_codex_artifact_review", side_effect=child):
            result = review_pipeline.run_multi_lens_artifact_review(
                root, "task", "feature", "codex", "research", ["RESEARCH.md"], lenses=("scope", "security"),
                checkpoint_authorization={"logical_run_id": "test_logical_run"}
            )

        self.assertEqual(review_pipeline.ReviewStatus.INFRA_FAIL, result["status"])
        self.assertEqual(3, len(result["lens_results"]))  # two lenses plus final consistency

    def test_writer_claim_records_evidence_but_not_resolution(self):
        root = self.make_project()
        (root / ".agent/state/finding_ledger.json").write_text(json.dumps({
            "schema_version": 1, "entries": [{"finding_id": "benchmark.metric-formula", "status": "OPEN"}]
        }), encoding="utf-8")
        harness.cmd_claim_fix("project", root, ["benchmark.metric-formula", "formula added at Benchmark section"])
        completion = json.loads((root / ".agent/state/fixer_completion.json").read_text(encoding="utf-8"))
        ledger = json.loads((root / ".agent/state/finding_ledger.json").read_text(encoding="utf-8"))
        self.assertEqual("formula added at Benchmark section", completion["resolved_findings"][0]["evidence"])
        self.assertEqual("OPEN", ledger["entries"][0]["status"])


if __name__ == "__main__":
    unittest.main()
