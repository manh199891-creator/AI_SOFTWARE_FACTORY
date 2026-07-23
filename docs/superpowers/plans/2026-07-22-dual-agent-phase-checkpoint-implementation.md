# Dual-Agent Phase Checkpoint and Convergence Control — Implementation Plan

Task ID: `dual_agent_phase_checkpoint`

Source specification: `docs/superpowers/plans/2026-07-22-dual-agent-phase-checkpoint-spec.md`

## Objective and execution boundary

Make `pipeline_status.json` the single durable authority, require an evidence-backed Antigravity checkpoint before every Codex retry, support checkpointed and continuous writer policies without crossing phase gates, and prevent stale Factory runtimes/profiles from running.

Only canonical Factory files under `E:\AI_SOFTWARE_FACTORY` are edited. Generated copies under `E:\Antigravity\*\.agents` are deployment targets and must be updated only by `scripts/sync_dual_agent_pipeline.ps1` after canonical tests pass. Existing task state and reports are never deleted or reset.

## Mandatory invariants

- `READY_FOR_CODEX` means every current-batch finding has an Anti claim with evidence or an explicit blocker; it does not mean Codex has verified closure. Only Codex may change a claimed finding to `VERIFIED_RESOLVED`. A phase-gate PASS requires no active findings.
- Review checkpoint reservation is crash-safe: `READY → RESERVED(run_id) → LAUNCHED → CONSUMED`. A stale `RESERVED` checkpoint is reconciled without launching Codex twice.
- Every review boundary uses a committed immutable snapshot. The order is tests → commit → checkpoint → review. A failed review requires a correction commit and a new checkpoint.
- `checkpoint` review never advances lifecycle phase. Only `phase_gate` PASS may open the next phase.
- Boundary verdict routing is fixed: `CHECKPOINT_PASS` continues; `CHECKPOINT_FAIL` creates one coherent finding batch and returns to the owning task; `INFRA_FAIL`, `STATE_DESYNC`, P0/P1 blocker, or scope regression stops continuous execution without consuming content budget.
- Deployment occurs only after the RB-3 canonical `phase_gate` PASS. Deployment uses stage → validate → immutable full backup → journaled transactional replacement → post-deploy doctor/smoke. While the journal is `DEPLOYING` or `ROLLING_BACK`, integrity preflight blocks orchestration; a crash triggers restoration before the next run. No live target is used as a canonical source.

## Review boundaries

- RB-1: Tasks 1–4 complete — runtime package, authoritative state, checkpoint contract, and crash-safe review scheduling are testable together.
- RB-2: Tasks 4–6 complete — scheduling, continuous execution, and convergence guards are complete.
- RB-3: Tasks 7–8 complete — status surfaces, migration, sync, and full regression suite pass.
- Codex reviews the changed snapshot only at RB-1, RB-2, and RB-3. Antigravity records task checkpoints between boundaries and must not invoke Codex itself.

### Task 1: Bootstrap Factory self-review and make runtime deployment verifiable

**Files:** Create `.agent/project_profile.json`, `runtime_integrity.py`, `schemas/runtime_manifest.schema.json`, `test_runtime_integrity.py`, `test_sync_dual_agent_pipeline.py`, `skills/dual-agent/SKILL.md`, `skills/dual-agent/scripts/dual_orchestrate.ps1`, `skills/dual-agent/references/orchestration_contract.md`, `skills/dual-agent/agents/openai.yaml`; Modify `harness.py`, `review_pipeline.py`, `dual_agent_runtime.py`, `scripts/sync_dual_agent_pipeline.ps1`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add tests proving a deployment manifest contains SHA-256 entries for runtime Python, schemas, both skill packages and their scripts/references/agent metadata, plus the pipeline-managed profile projection. Reject every missing or modified artifact and detect a target profile whose managed fields differ from canonical. Include `convergence_pipeline.py` and `runtime_integrity.py` in the required runtime set.
- [ ] Add a Factory self-review test using registered alias `factory`, project root `E:\AI_SOFTWARE_FACTORY`, and profile `source_path="."`. Verify plan/code snapshots include only explicit task scope and exclude `.agent/**`, generated project mirrors, `scratch/**`, caches, and unrelated repositories. Remove hardcoded `project_root/source-code` assumptions from self-review paths through one tested source-root resolver. Define integrity mode `canonical` for this alias and `deployed` for Revit/Navis; both modes verify a complete manifest and neither may silently skip checks.
- [ ] Add sync integration tests using isolated fake targets. Verify validate-only is byte-for-byte non-mutating; unsafe/overlapping paths are rejected; partial failure leaves the target unchanged; project-specific profile fields survive; full-bundle backup/restore succeeds; and an existing immutable backup cannot be overwritten.
- [ ] Run `python -m unittest test_runtime_integrity.py test_sync_dual_agent_pipeline.py` → verify FAIL because no complete manifest, canonical orchestrator package, safe staging, restore, or managed-profile merge exists.
- [ ] **GREEN:** Register the Factory root through `.agent/project_profile.json` and alias `factory`. Implement one source-root resolver used by harness, review snapshotting, scope evaluation, and writer snapshotting so `source_path="."` is supported without weakening path containment. This enables real executable Codex reviews of canonical Factory commits at RB-1, RB-2, and RB-3.
- [ ] Implement deterministic manifest creation and verification in `runtime_integrity.py`. Define pipeline-managed profile keys as `dual_agents.auto_fix`, `dual_agents.convergence_v2`, `dual_agents.convergence_shadow`, `dual_agents.max_reviews_per_phase`, `dual_agents.execution_policy`, and `dual_agents.review_boundaries`; preserve project-specific build, test, lint, model, timeout, and sensitive-path settings.
- [ ] Seed the four canonical `skills/dual-agent` files from the explicitly audited Revit package, review their content, and thereafter require this Factory directory as the only orchestrator source. Remove all live-target fallback sources from sync.
- [ ] Modify `scripts/sync_dual_agent_pipeline.ps1` so `$runtimeFiles` includes `convergence_pipeline.py` and `runtime_integrity.py`; add `-BackupRoot`, `-BackupRunId`, and `-RestoreBackup`. Stage the full deployable bundle outside the target, validate it, create a unique immutable backup, then replace runtime, skills, schemas, and profile through a durable transaction journal. On crash or partial failure, the next invocation must restore every replaceable path before orchestration is allowed. Never back up or overwrite task context, state, reports, knowledge, or learning history.
- [ ] Add a `-ValidateOnly` switch that performs manifest/profile/import checks without modifying targets. A failed check must return non-zero with one of `MISSING_RUNTIME_MODULE`, `RUNTIME_DRIFT`, `PROFILE_DRIFT`, or `IMPORT_SMOKE_FAILED`.
- [ ] Run `python -m unittest test_runtime_integrity.py test_sync_dual_agent_pipeline.py` and `python test_pipeline.py` → verify PASS, including the Factory self-review fixture.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync_dual_agent_pipeline.ps1 -ValidateOnly -Targets E:\Antigravity\RevitAddinSolution` → verify the current stale deployment fails with a specific drift reason and does not change files.
- [ ] **Checkpoint:** Record `ANTI_PHASE=CODE`, `ANTI_PROGRESS=1/8`, tests, changed files, drift evidence, and `READY_FOR_CODEX=NO`.
- [ ] **Commit:** `fix(factory): verify complete dual runtime deployment`

### Task 2: Make pipeline status the only authoritative state

**Files:** Modify `schemas/pipeline_status.schema.json`, `convergence_pipeline.py`, `workflow_governance.py`, `harness.py`, `test_dual_loop_guards.py`

**Steps:**

- [ ] **RED:** Extend tests to require status version 2 fields: `terminal`, `lifecycle_phase`, `review_kind`, `review_boundary_id`, `writer_status`, `writer_checkpoint_id`, `work_item_current`, `work_item_total`, `phase_review_count`, `failure_budget_remaining`, and `ready_for_codex`. Test atomic replacement and preservation of the previous valid file when validation fails.
- [ ] Add a transition test covering `RUNNING → NEEDS_FIX → READY_FOR_REVIEW → REVIEWING → PASS` and terminal transitions `NO_PROGRESS`, `BLOCKED_HANDOFF`, `STATE_DESYNC`, `INFRA_FAIL`.
- [ ] Add migration tests for valid version 1, malformed version 1, missing status, repeated migration, stale run identity, and preservation of task/run/failure/history evidence. Migration must be idempotent and must run before any version 2 writer or reader becomes active.
- [ ] Run `python -m unittest test_dual_loop_guards.py` → verify FAIL because version 1 status lacks the new fields and transitions.
- [ ] **GREEN:** Define the explicit transition matrix in code and tests, including allowed same-state idempotence, forbidden backward transitions, terminal booleans, lifecycle phase/mode mapping, checkpoint versus phase verdicts, and reopening rules for `STALE`, `STATE_DESYNC`, `PHASE_REVIEW_CEILING`, and `BLOCKED_HANDOFF`.
- [ ] Implement idempotent version 1 → version 2 migration before switching readers/writers. Malformed or identity-conflicting legacy state becomes `STATE_DESYNC`; it is never silently replaced.
- [ ] Centralize validation and atomic writes in `convergence_pipeline.write_pipeline_status`. Remove the `convergence_active` condition from status persistence so every pipeline mode and every terminal path writes the same authority.
- [ ] Update `workflow_governance.initialize_task_context`, `update_task_context`, `record_failed_attempt`, and `prepare_failure_budget_retry` to mirror only durable counters/evidence into task context; they must not independently decide the externally visible pipeline status.
- [ ] Update `harness.save_dual_terminal_state`, `pause_dual_for_external_fixer`, `stop_dual_no_progress`, PASS paths, verification failures, stale reconciliation, and infrastructure failures to use the centralized transition writer.
- [ ] Run `python -m unittest test_dual_loop_guards.py` → verify PASS.
- [ ] **Checkpoint:** Record `ANTI_PROGRESS=2/8`, transition coverage, and `READY_FOR_CODEX=NO`.
- [ ] **Commit:** `refactor(factory): centralize authoritative pipeline state`

### Task 3: Add the Antigravity writer checkpoint contract

**Files:** Create `schemas/writer_checkpoint.schema.json`, `skills/dual-agent-pipeline/scripts/dual_checkpoint.ps1`; Modify `workflow_governance.py`, `dual_agent_runtime.py`, `harness.py`, `test_dual_loop_guards.py`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add tests for a `writer-checkpoint` command accepting `task_id`, `phase`, `work_item_current`, `work_item_total`, `status`, changed files, checks, claimed finding IDs, explicit blockers, risks, retry hypothesis, and `ready_for_codex`. Reject task mismatch, invalid phase/status, decreasing progress, unchanged snapshot, out-of-scope files, missing checks, unknown finding IDs, and readiness with any current-batch finding that is neither claimed with evidence nor explicitly blocked.
- [ ] Test that Anti cannot write `.agent/state/writer_checkpoint.json` directly through the handoff allow-list; only the harness command may write it.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify the new tests FAIL.
- [ ] **GREEN:** Implement schema validation plus `record_writer_checkpoint` and `validate_writer_readiness` in `workflow_governance.py`. Persist `.agent/state/writer_checkpoint.json` atomically and bind it to task ID, phase, current snapshot, latest review run, and finding ledger. Claims authorize review readiness but remain OPEN/CLAIMED until Codex verifies them.
- [ ] Add `cmd_writer_checkpoint` and CLI routing in `harness.py`. Keep `cmd_claim_fix` as evidence recording only; it must never mark a finding verified-resolved.
- [ ] Implement `dual_checkpoint.ps1` to read the schema-valid request at `.agent/context/WRITER_CHECKPOINT_REQUEST.json` and invoke the deployed local harness resolved through `dual_paths.ps1`. This single request file is the only additional writer-allowed metadata path; `.agent/state/**` and `.agent/reports/**` remain forbidden. Define exit codes and machine-readable output.
- [ ] Extend `dual_agent_runtime.build_handoff`, `antigravity_prompt`, and `harness.write_fixer_handoff` with the fully rendered target-specific checkpoint command, exact request path/schema, and completion requirements. Explicitly prohibit Anti from invoking Codex or the dual run command.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Commit:** `feat(factory): add evidence-backed writer checkpoints`
- [ ] **Checkpoint:** From the commit above, record `ANTI_PROGRESS=3/8`, `ANTI_STATUS=TASK_COMPLETE`, all checks, and the committed snapshot hash with `READY_FOR_CODEX=NO`; continue to Task 4 because checkpoint review semantics are not available yet.

### Task 4: Gate every Codex review on writer readiness

**Files:** Modify `harness.py`, `workflow_governance.py`, `dual_agent_runtime.py`, `review_pipeline.py`, `schemas/review_run.schema.json`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add integration tests proving a second logical review is rejected when the latest writer checkpoint is missing, belongs to another run/phase, has `ready_for_codex=false`, has an unchanged snapshot, or omits resolution evidence for any open finding. Verify zero parent or lens Codex processes launch in all rejection cases.
- [ ] Add a positive test: one failed review, a changed scoped snapshot, claims for the entire finding batch, passing required checks, and a valid checkpoint permit exactly one logical parent review. Multi-lens mode may launch its configured child subprocesses, all bound to the same parent run and reservation.
- [ ] Add review-kind tests: `checkpoint` review may return `CHECKPOINT_PASS` or `CHECKPOINT_FAIL` but can never open the next lifecycle phase; only a `phase_gate` review over a phase-complete checkpoint may produce the existing phase PASS semantics.
- [ ] Add crash/resume tests for `READY → RESERVED(run_id) → LAUNCHED → CONSUMED`: crash before launch releases/reconciles a stale reservation; crash after launch resumes observation of the same run; no retry can launch a second Codex process for one checkpoint.
- [ ] Run `python test_pipeline.py` → verify FAIL because preflight currently checks only snapshot/failure budget.
- [ ] **GREEN:** Add `WRITER_CHECKPOINT_REQUIRED` once at the top-level logical review scheduler. Version `schemas/review_run.schema.json` and require `review_kind`, `review_boundary_id`, and parent logical run identity for checkpoint-aware runs. `run_multi_lens_artifact_review` receives one internal authorization bound to the reserved parent run and passes it to child `run_codex_artifact_review` calls; children cannot reserve or consume checkpoints.
- [ ] Reserve a valid checkpoint with an atomic compare-and-swap before process launch, mark it `LAUNCHED` only after the Codex process exists, and mark it `CONSUMED` only after terminal review evidence is persisted. Reconcile stale reservations without duplicate launch.
- [ ] Remove success-by-process-exit behavior from `run_antigravity_fixer`: an exit code of zero is only `WRITER_COMPLETED`; scheduling continues only after checkpoint validation.
- [ ] Ensure `MaxCycles` cannot authorize multiple reviews without a distinct valid checkpoint between reviews. Default `MaxCycles=1` for external-writer operation; retain compatibility only for test fixtures and explicitly configured nested writers.
- [ ] Run `python test_pipeline.py` → verify PASS.
- [ ] **Checkpoint:** Record `ANTI_PROGRESS=4/8`, review launch counts, and `READY_FOR_CODEX=NO`.
- [ ] **Commit:** `fix(factory): require writer readiness before Codex retry`
- [ ] **Checkpoint RB-1:** From the commit above, record `ANTI_PROGRESS=4/8`, `ANTI_STATUS=TASK_COMPLETE`, `READY_FOR_CODEX=YES`, all checks, and the committed snapshot. `CHECKPOINT_PASS` continues to Task 5, `CHECKPOINT_FAIL` returns to Task 4, and infrastructure/desync/scope failures stop without advancing phase.

### Task 5: Support checkpointed and continuous writer policies

**Files:** Modify `RevitAddinSolution/.agent/project_profile.json`, `NavisAddinSolution/.agent/project_profile.json`, `dual_agent_runtime.py`, `harness.py`, `test_dual_loop_guards.py`, `test_pipeline.py`, `skills/dual-agent-pipeline/references/project_profile_contract.md`

**Steps:**

- [ ] **RED:** Add tests for `execution_policy=checkpointed` and `execution_policy=continuous`. Checkpointed must return control after one coherent finding batch. Continuous must allow monotonically increasing work-item checkpoints inside the current phase and must stop at configured review boundaries.
- [ ] Test that neither policy can advance `research → plan`, `plan → code`, or `code → release` without the preceding Codex phase verdict and matching snapshot being PASS.
- [ ] Test boundary triggers for phase completion, configured milestone, P0/P1 blocker, scope change, and contract regression. Ordinary task completion must not trigger Codex automatically.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify FAIL because execution policy and boundaries are not modeled.
- [ ] **GREEN:** Add `execution_policy` and `review_boundaries` profile parsing. Include the remaining phase work items and boundary rules in `FIXER_HANDOFF.json`; update the Anti prompt to checkpoint after each work item and stop at a boundary. Milestones schedule `review_kind=checkpoint`; only phase completion schedules `review_kind=phase_gate`.
- [ ] Implement durable work-item progress in task context and reject skipped, repeated, or decreasing indexes unless an explicit rollback checkpoint includes evidence.
- [ ] Configure canonical Revit and Navis profiles with `checkpointed` as default. Allow `continuous` only as a task-level opt-in captured during `dual-init`.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Checkpoint:** Record `ANTI_PROGRESS=5/8`, both policy test results, and `READY_FOR_CODEX=NO`.
- [ ] **Commit:** `feat(factory): add phase-bound continuous writer execution`

### Task 6: Make convergence and review ceilings durable across CLI invocations

**Files:** Modify `convergence_pipeline.py`, `workflow_governance.py`, `harness.py`, `test_dual_loop_guards.py`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add tests proving `phase_review_count` is keyed by `task_id + lifecycle_phase`, survives separate CLI invocations, and is not reset by a changed snapshot. Test that two consecutive reviews with `net_closure <= 0` produce terminal `NO_PROGRESS` and that six reviews in one phase produce `PHASE_REVIEW_CEILING`.
- [ ] Add `batch_review_count` tests keyed by task, phase, and finding-batch identity. A third review of one batch must stop with `BATCH_REVIEW_CEILING`; creating a genuinely new finding batch does not reset `phase_review_count`.
- [ ] Add tests that a recurring semantic finding becomes `REGRESSED`, a writer claim remains unverified until Codex omits/resolves it, and newly introduced findings offset verified closures.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify FAIL for cross-invocation counters and enforcement while convergence is disabled/shadow-only.
- [ ] **GREEN:** Persist batch and phase counters plus finding-ledger history independently of the in-process `for cycle` loop. Enforce two reviews per finding batch and six reviews per phase with separate reason codes. Enforce convergence decisions for research, plan, code, and release when `convergence_v2=true`; shadow mode may record metrics but may not alter gates.
- [ ] Make `BLOCKED_HANDOFF` reopening require all three: changed relevant snapshot, a new falsifiable hypothesis, and a valid writer checkpoint tied to the blocked phase.
- [ ] Ensure failure budget counts only completed content reviews; `INFRA_FAIL`, `STALE`, `STATE_DESYNC`, invalid checkpoint, and duplicate attempts do not consume it.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Commit:** `fix(factory): persist convergence across review invocations`
- [ ] **Checkpoint RB-2:** From the commit above, record `ANTI_PROGRESS=6/8`, convergence trend evidence and `READY_FOR_CODEX=YES`. Request one Codex checkpoint review; `CHECKPOINT_PASS` continues to Task 7, `CHECKPOINT_FAIL` returns to Task 6, and infrastructure/desync/scope failures stop without consuming content budget.

### Task 7: Expose phase progress and state desynchronization in status tools

**Files:** Modify `skills/dual-agent-pipeline/scripts/dual_status.ps1`, `skills/dual-agent-pipeline/scripts/dual_wait.ps1`, `skills/dual-agent-pipeline/scripts/dual_read_reports.ps1`, `dual_agent_runtime.py`, `convergence_pipeline.py`, `harness.py`, `test_pipeline.py`, `test_dual_loop_guards.py`, `test_runtime_integrity.py`

**Steps:**

- [ ] **RED:** Add wrapper tests for `ANTI_PHASE`, `ANTI_PROGRESS`, `ANTI_STATUS`, `LAST_CHECKPOINT`, `READY_FOR_CODEX`, `CODEX_STATUS`, and `NEXT_ACTION` in text and JSON output.
- [ ] Add mismatch fixtures where authority, review manifest, checkpoint, and report have different task/run/snapshot identities. Status must return terminal `STATE_DESYNC`; wait must exit immediately and must never report raw `RUNNING` simultaneously.
- [ ] Add fail-closed preflight tests proving `dual-init`, `dual`, and direct `codex` launch zero writer/reviewer processes when runtime manifest, schema/skill bundle, managed profile projection, required module, or deployment journal fails integrity validation. Cover `canonical` verification for alias `factory` and `deployed` verification for Revit/Navis.
- [ ] Run `python test_pipeline.py` → verify FAIL because current wrappers fallback across multiple authorities.
- [ ] **GREEN:** Make `dual_status.ps1` read schema-valid `pipeline_status.json` only, using other files solely to validate identity. Remove report/context fallback as a source of effective status. Add explicit legacy migration output rather than silently inferring current state.
- [ ] Update `dual_wait.ps1` terminal set and progress output. Update `dual_read_reports.ps1` to include writer checkpoint and convergence reports without granting them status authority.
- [ ] Extend doctor diagnostics with `RUNTIME_DRIFT`, `PROFILE_DRIFT`, `MISSING_RUNTIME_MODULE`, checkpoint freshness, open finding families, and phase review count.
- [ ] Invoke mode-aware runtime-integrity preflight at the start of `cmd_dual_init`, `cmd_dual`, and `cmd_codex`, before state mutation or process creation. Factory canonical mode verifies source manifest/profile directly; deployed mode verifies the installed target bundle and requires a clean deployment journal. Return the named non-zero reason code; doctor is diagnostic evidence, not the only enforcement point.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Checkpoint:** Record `ANTI_PROGRESS=7/8`, wrapper fixtures, and `READY_FOR_CODEX=NO`.
- [ ] **Commit:** `feat(factory): report writer phase and authoritative dual status`

### Task 8: Migrate profiles, deploy safely, and verify the full lifecycle

**Files:** Modify `RevitAddinSolution/.agent/project_profile.json`, `NavisAddinSolution/.agent/project_profile.json`, `skills/dual-agent-pipeline/SKILL.md`, `skills/dual-agent/SKILL.md`, `skills/dual-agent-pipeline/references/mode_contract.md`, `docs/WORKFLOW_GOVERNANCE.md`, `docs/DUAL_AGENT_AND_EVOLUTION.md`, `test_pipeline.py`, `test_runtime_integrity.py`, `test_sync_dual_agent_pipeline.py`

**Steps:**

- [ ] **RED:** Add profile migration tests starting from the exact legacy Revit profile (`auto_fix=true`, no convergence fields). Verify migration preserves project-specific build/test/review settings and all existing task history while adding only pipeline-managed fields.
- [ ] Add an end-to-end fake lifecycle: plan FAIL → Anti checkpoints work items → one retry → plan PASS → code gate opens; confirm no automatic transition to release and no duplicate Codex invocation.
- [ ] Add crash/resume fixtures for status atomic replacement, checkpoint reservation, Codex launch, deploy staging, each journaled target replacement step, and restore. A second CLI invocation must preserve counters, must not duplicate review, and must complete restoration before orchestration resumes.
- [ ] Run `python -m unittest test_runtime_integrity.py test_dual_loop_guards.py` and `python test_pipeline.py` → verify FAIL until migration/docs/contracts are complete.
- [ ] **GREEN:** Set canonical profiles to `auto_fix=false`, `convergence_v2=true`, `convergence_shadow=false`, `max_reviews_per_phase=6`, and `execution_policy=checkpointed`. Document continuous opt-in, checkpoint commands, review boundaries, no-progress recovery, and the required Anti/Codex status fields.
- [ ] Run `python -m unittest test_runtime_integrity.py test_dual_loop_guards.py` → verify PASS.
- [ ] Run `python test_pipeline.py` → verify PASS.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync_dual_agent_pipeline.ps1 -ValidateOnly -Targets E:\Antigravity\RevitAddinSolution,E:\Antigravity\NavisAddinSolution` → verify drift is detected before deployment.
- [ ] **Commit:** `feat(factory): ship checkpointed dual-agent convergence control`
- [ ] **Checkpoint RB-3:** From the commit above, record `ANTI_PROGRESS=8/8`, `ANTI_STATUS=PHASE_COMPLETE`, full canonical regression evidence, and `READY_FOR_CODEX=YES`. Run one Factory `phase_gate` code review. `FAIL` returns to Task 8 with a new correction commit/checkpoint; infrastructure/desync/scope failure stops. Do not stage or modify either live target until this review is PASS.
- [ ] After RB-3 PASS, create a unique deployment run ID from UTC timestamp plus GUID. Stage the complete Revit and Navis bundles outside live targets and validate manifest, imports, schemas, skill files, wrappers, and managed profiles.
- [ ] Back up the complete current `.agents/runtime`, `.agents/skills/dual-agent`, `.agents/skills/dual-agent-pipeline`, deployed schemas, and project profile for each target under `E:\AI_SOFTWARE_FACTORY\scratch\deploy-backups\$deploymentRunId\RevitAddinSolution` and `E:\AI_SOFTWARE_FACTORY\scratch\deploy-backups\$deploymentRunId\NavisAddinSolution`. The script must fail if the backup run ID exists and must write immutable file hashes. Live task context/state/reports/knowledge/learning are excluded and untouched.
- [ ] Run sync with that deployment run ID and backup root; verify the transaction journal reaches `COMMITTED` and both targets report `SYNCED`. Exercise crash injection plus `-RestoreBackup` against isolated fake targets before relying on it for production recovery.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File E:\Antigravity\RevitAddinSolution\.agents\skills\dual-agent\scripts\dual_orchestrate.ps1 -Action doctor -Project RevitAddinSolution` and the same path with `-Action status -Project RevitAddinSolution`.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File E:\Antigravity\NavisAddinSolution\.agents\skills\dual-agent\scripts\dual_orchestrate.ps1 -Action doctor -Project NavisAddinSolution` and the same path with `-Action status -Project NavisAddinSolution`.
- [ ] Treat post-deploy doctor, manifest, import, wrapper smoke, or status identity failure as release verification failure: stop, restore the exact immutable backup bundle, and rerun doctor/status. Verify the blocked Automatic Formwork task history remains intact and cannot resume without an explicit checkpoint plus hypothesis.

## Rollback

- Before sync, preserve the complete replaceable deployment bundle and profile in a unique immutable, hash-bound backup. Do not include live task context/state/reports, knowledge, or learning history.
- If staging validation fails, do not touch the target. If swap or post-deploy verification fails, invoke the tested `-RestoreBackup` command for that deployment run and verify restored hashes before resuming. Never restore or overwrite live `.agent/context`, `.agent/state`, `.agent/reports`, knowledge, or learning history.
- Reverting canonical code requires reverting the matching schema, runtime manifest version, profile-managed fields, wrappers, and documentation together. Mixed-version runtime/schema deployment is forbidden.

## Final acceptance gate

- `test_runtime_integrity.py`, `test_sync_dual_agent_pipeline.py`, `test_dual_loop_guards.py`, and `test_pipeline.py` all pass.
- Validate-only detects the pre-deployment drift and post-deployment validation passes.
- Active Revit and Navis runtimes exactly match the canonical manifest and import all required modules.
- Status exposes Anti phase/progress independently from Codex status.
- A missing/invalid checkpoint launches zero Codex processes.
- A valid checkpoint launches exactly one logical parent review; multi-lens children remain bound to that parent authorization.
- Two no-closure reviews stop at `NO_PROGRESS`.
- Automatic Formwork history remains intact and cannot resume without a new hypothesis plus checkpoint.
- Final Factory Codex `phase_gate` review binds PASS to the same task ID, run ID, committed snapshot hash, review boundary, and exact changed files before production deployment is allowed.
- Post-deploy release verification binds both targets to the reviewed deployment manifest and proves restore readiness.
