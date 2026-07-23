# Dual-Agent Infinite Review/Implementation Loop — Containment Plan

Task ID: `dual_agent_loop_containment`

Permanent follow-up: `docs/superpowers/plans/2026-07-22-dual-agent-phase-checkpoint-implementation.md`

## Objective

Stop automatic and sequential `fix → review → implement → review` loops immediately, preserve all task evidence, and require an explicit human checkpoint after a small durable review budget is exhausted.

## Incident evidence converted to invariants

- `automatic_formwork_mvp` produced 26 Codex reports within two hours.
- `MaxCycles` is scoped to one process invocation, so calling the command again resets the local loop.
- Failure budget histories were repeatedly reopened after artifact changes, allowing the same phase to continue indefinitely.
- The deployed Revit profile has `dual_agents.auto_fix=true`.
- `review_run.json` and `pipeline_status.json` held different run IDs/statuses while status fallback still reported a usable state.
- A plan failure repeatedly triggered more plan editing/review; implementation of the loop fix never started.

The hotfix must enforce:

1. At most one logical Codex review per pipeline invocation.
2. At most three completed content reviews per `task_id + mode`, across all invocations and changed snapshots.
3. `INFRA_FAIL`, `STALE`, duplicate snapshot, invalid state, and cancelled runs do not consume the three-review budget.
4. A third content failure produces terminal `BLOCKED_HANDOFF`; artifact changes and a new hypothesis cannot reopen it automatically.
5. Anti never launches Codex and never recursively invokes the dual pipeline from a fixer session.
6. Plan PASS is required before code; code PASS is required before release. No command automatically crosses a phase boundary.
7. State identity mismatch becomes terminal `STATE_DESYNC`; readers do not fall back to another report/context as authority.

## Execution order

This containment plan ships before the permanent checkpoint/convergence plan. Do not run `automatic_formwork_mvp` again until all four tasks below pass the incident regression suite and the hotfix is deployed.

### Task 1: Add a durable per-phase review circuit breaker

**Files:** Modify `workflow_governance.py`, `harness.py`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add an integration fixture that invokes the same plan task ten times with a changed artifact snapshot and Codex FAIL each time. Assert only the first three completed content reviews launch Codex, the third writes `BLOCKED_HANDOFF`, and invocations four through ten launch zero Codex/fixer processes.
- [ ] Add tests proving `initialize_task_context`, repeated `dual-init`, process restart, changed snapshot, and `--resume-hypothesis` do not reset `review_attempts_by_phase[task_id][mode]`.
- [ ] Add tests proving `INFRA_FAIL`, `STALE`, duplicate attempt, schema failure, state desync, and cancellation do not consume the content-review counter.
- [ ] Run `python test_pipeline.py` → verify FAIL because current failure-budget reopening permits further reviews.
- [ ] **GREEN:** Persist `review_attempts_by_phase` in `TASK_CONTEXT.json`. Increment it only after a terminal Codex `FAIL` bound to the current task/mode/run/snapshot. Preflight this counter before verification, fixer launch, or Codex launch.
- [ ] Change `prepare_failure_budget_retry` so snapshot changes and retry hypotheses cannot reopen a phase after three completed content failures. Reopening requires a separate human approval record. For this incident the exact command is `python harness.py RevitAddinSolution approve-phase-resume --task-id automatic_formwork_mvp --mode plan --blocked-run-id aaa02615-bd99-4015-ac24-0ba71e83f9c4 --reason "Human approved one additional plan review"`; the dual/fixer code path must never call this command.
- [ ] Persist every approval with approval ID, blocked run ID, UTC time, previous counter, and reason. One approval permits one additional review and is consumed atomically; it does not reset history.
- [ ] Run `python test_pipeline.py` → verify PASS, including the ten-invocation incident fixture.
- [ ] **Commit:** `fix(factory): add durable dual review circuit breaker`

### Task 2: Remove recursive automatic fixing and phase auto-advance

**Files:** Modify `dual_agent_runtime.py`, `harness.py`, `RevitAddinSolution/.agent/project_profile.json`, `NavisAddinSolution/.agent/project_profile.json`, `skills/dual-agent-pipeline/scripts/dual_run.ps1`, `test_dual_loop_guards.py`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add tests proving a Codex FAIL writes one `FIXER_HANDOFF.json`, returns `NEEDS_FIX`, and exits without starting Antigravity. Assert the generated Anti prompt prohibits Codex, `dual_orchestrate`, `dual_run`, and phase transition commands.
- [ ] Add wrapper tests proving plan/research/code/release default to `MaxCycles=1` and reject `MaxCycles > 1` with `AUTOMATIC_MULTI_REVIEW_DISABLED`.
- [ ] Add lifecycle tests proving plan FAIL cannot enter code, plan PASS opens only code, code PASS opens only release validation, and no PASS automatically executes the next phase.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify FAIL because active profiles and the harness still support nested auto-fix/multiple cycles.
- [ ] **GREEN:** Set canonical Revit and Navis profiles to `dual_agents.auto_fix=false`. Remove automatic calls to `run_antigravity_fixer` from the production review path; retain the function only for explicitly isolated tests or future human-approved execution policy.
- [ ] Change `dual_run.ps1` and `parse_dual_args` to default to one cycle and reject production values above one. A failed review always terminates the invocation after writing the handoff.
- [ ] Enforce explicit phase initialization and PASS evidence before a new mode. Never call the next mode from the current mode handler.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Commit:** `fix(factory): disable recursive dual auto-fix and phase advance`

### Task 3: Enforce one authoritative run state and an execution lease

**Files:** Modify `convergence_pipeline.py`, `workflow_governance.py`, `review_pipeline.py`, `harness.py`, `schemas/pipeline_status.schema.json`, `skills/dual-agent-pipeline/scripts/dual_status.ps1`, `skills/dual-agent-pipeline/scripts/dual_wait.ps1`, `test_dual_loop_guards.py`, `test_pipeline.py`

**Steps:**

- [ ] **RED:** Add fixtures where `pipeline_status.json`, `review_run.json`, task context, and Markdown reports contain different task IDs, run IDs, modes, or snapshot hashes. Status must return terminal `STATE_DESYNC`, and dual run must launch zero processes.
- [ ] Add concurrency tests: two simultaneous invocations for the same `task_id + mode` compete for a durable lease; one acquires it and the other exits `RUN_ALREADY_ACTIVE`. Test stale lease reconciliation only after the owner process is absent and the heartbeat exceeds the configured timeout.
- [ ] Add bypass tests for `python harness.py RevitAddinSolution codex`, `cmd_codex`, `run_codex_artifact_review`, and `run_multi_lens_artifact_review`. Every production entry point must call the same durable budget plus lease authorization before creating a Codex process; unauthorized direct calls launch zero processes.
- [ ] Add deterministic injectable clock, process-identity provider, process launcher, and fault points in the review launch owner. Use them for crash tests at lease acquisition, PREPARING/RUNNING persistence, Codex launch, terminal manifest/report write, and lease release. Recovery must never duplicate a review or leave raw RUNNING alongside terminal state.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify FAIL because readers currently fall back across conflicting authorities and no durable task-phase lease exists.
- [ ] **GREEN:** Make schema-valid `pipeline_status.json` the only externally authoritative state. Other files validate identity and provide evidence only. Any identity mismatch writes terminal `STATE_DESYNC` before returning status.
- [ ] Centralize review launch authorization in `workflow_governance.py`; both harness entry points and `review_pipeline.py` artifact/multi-lens launch paths must use it. No public production function may create Codex without an authorization bound to task, mode, snapshot, budget counter, and lease.
- [ ] Add an atomic lease keyed by project, task ID, and mode with owner PID, owner process start time, random invocation token, acquired time, and heartbeat. PID alone is invalid because Windows may reuse it. Acquire the lease before state mutation; release it only after `review_pipeline.py` has durably written matching terminal manifest and report evidence.
- [ ] Integrate lease transitions with `review_pipeline.py` PREPARING, RUNNING, terminal success/failure, batch aggregation, timeout, and stale reconciliation paths. Terminal evidence and authoritative status must agree before the lease becomes reusable.
- [ ] Update status/wait so every terminal state exits immediately and a stale RUNNING lease is reconciled once. Remove Markdown/task-context fallback as a source of effective status.
- [ ] Run `python -m unittest test_dual_loop_guards.py` and `python test_pipeline.py` → verify PASS.
- [ ] **Commit:** `fix(factory): enforce authoritative state and single review lease`

### Task 4: Deploy the containment bundle and prove the incident cannot recur

**Files:** Create `scripts/deploy_dual_loop_containment.ps1`, `test_dual_loop_containment_deploy.py`; Modify `scripts/sync_dual_agent_pipeline.ps1`, `skills/dual-agent-pipeline/SKILL.md`, `skills/dual-agent/SKILL.md`, `docs/WORKFLOW_GOVERNANCE.md`, `docs/DUAL_AGENT_AND_EVOLUTION.md`

**Steps:**

- [ ] **RED:** Add deployment tests using isolated fake Revit/Navis targets. Verify the bundle includes `harness.py`, `workflow_governance.py`, `dual_agent_runtime.py`, `review_pipeline.py`, `convergence_pipeline.py`, status schema, run/status/wait wrappers, both skill contracts, and managed profile projection.
- [ ] Test validate-only non-mutation, unique immutable backup creation, partial-copy failure restoration, missing-module rejection, profile merge preserving build/test settings, and refusal to touch `.agent/context`, `.agent/state`, `.agent/reports`, knowledge, or learning history.
- [ ] Run `python -m unittest test_dual_loop_containment_deploy.py` → verify FAIL because no containment deployer exists and the general sync omits convergence runtime/profile updates.
- [ ] **GREEN:** Implement a narrow staged containment deployer. It validates hashes/imports, backs up every replaceable file, records a transaction journal, applies the bundle, and restores on any failure. Completed backup directories are immutable and keyed by UTC timestamp plus GUID.
- [ ] Update the general sync source list so future syncs cannot remove `convergence_pipeline.py` or revert managed containment fields. Document that generated `.agents` copies are never edited directly.
- [ ] Run `python -m unittest test_dual_loop_containment_deploy.py test_dual_loop_guards.py` → verify PASS.
- [ ] Run `python test_pipeline.py` → verify PASS.
- [ ] Run validate-only against Revit and Navis; confirm current drift is detected without mutation.
- [ ] Deploy to Navis first as the canary. Run the ten-invocation FAIL fixture and concurrent-run fixture against the deployed runtime; verify exactly three content reviews total, zero auto-fixer launches, terminal `BLOCKED_HANDOFF`, and consistent state.
- [ ] After Navis canary passes, deploy the identical hash-bound bundle to Revit. Do not resume the existing Formwork task; status must preserve its history and report it blocked.
- [ ] Run Revit doctor/status and a new disposable containment smoke task. Verify one review per invocation, no phase auto-advance, and no process remains after terminal status.
- [ ] **Commit:** `fix(factory): deploy dual loop containment controls`

## Acceptance gate before resuming Formwork

- Ten sequential FAIL invocations produce no more than three completed content reviews.
- Two concurrent invocations produce exactly one logical review.
- `auto_fix=false` is effective in both canonical and deployed profiles.
- No production command accepts `MaxCycles > 1`.
- No failed phase starts the next phase or an Antigravity fixer.
- State mismatch returns `STATE_DESYNC` and launches no process.
- Existing Formwork reports and failure history remain intact.
- Resuming a terminal phase requires one explicit human approval record bound to its blocked run.
- Only after this containment gate passes may the permanent phase-checkpoint plan begin.
