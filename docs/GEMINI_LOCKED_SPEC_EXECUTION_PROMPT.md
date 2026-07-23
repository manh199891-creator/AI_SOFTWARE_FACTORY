# Gemini Locked-Spec Execution Prompt

Paste the complete block below into the Antigravity/Gemini implementation conversation.

---

You are Gemini/Antigravity, the single writer for this task.

## Assignment

Implement the locked containment plan completely and sequentially. Do not brainstorm a replacement design, rewrite the plan, broaden scope, or return to the Automatic Formwork plan. Read every locked input completely before editing code, then implement every checklist item without omission.

Task ID: `dual_agent_loop_containment`

Repository root: `E:\AI_SOFTWARE_FACTORY`

## Locked inputs

Read all three files from first byte to EOF in this order:

1. `E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-loop-containment.md`
   - Required SHA-256: `A42BA7C8C0E5DA11304B6477444FEF35A1B4F2B9BA6552FA67A026B44989EAAA`
2. `E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-phase-checkpoint-spec.md`
   - Required SHA-256: `15DC95B9938FC4BB51B46CD64C872D94BCC7F16230B97C409188C412CAC30D58`
3. `E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-phase-checkpoint-implementation.md`
   - Required SHA-256: `BED52C8A39D6ABB72D097E9C27D956CB7C6C5E921704B7F5E099A53B1F9C81CD`

Before doing anything else, run:

```powershell
Get-FileHash `
  "E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-loop-containment.md", `
  "E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-phase-checkpoint-spec.md", `
  "E:\AI_SOFTWARE_FACTORY\docs\superpowers\plans\2026-07-22-dual-agent-phase-checkpoint-implementation.md" `
  -Algorithm SHA256
```

If any hash differs, stop with `SPEC_DRIFT`. Do not edit the changed spec/plan and do not guess which version is intended.

## Priority and scope

Implement only the four tasks in `2026-07-22-dual-agent-loop-containment.md` now. The permanent phase-checkpoint implementation is context and follow-up work, not authorization to implement it in this run.

Task order is mandatory:

1. Durable per-phase review circuit breaker.
2. Remove recursive automatic fixing and phase auto-advance.
3. Authoritative state, central launch authorization, and execution lease.
4. Containment deployment bundle and incident regression.

Do not reorder, merge, skip, or parallelize these tasks.

## Non-negotiable prohibitions

- Do not edit any locked spec or plan.
- Do not edit `E:\Antigravity\RevitAddinSolution\.agents` or any generated target copy directly.
- Do not resume or modify `automatic_formwork_mvp`.
- Do not invoke Codex, `dual_orchestrate`, `dual_run`, or any review pipeline.
- Do not run an Antigravity fixer recursively.
- Do not deploy to Revit before the Navis canary and every Task 4 deployment test pass.
- Do not widen allowed files to make a test pass.
- Do not delete, reset, restore, stage, or modify unrelated user work.
- Do not replace an exact requirement with a simpler approximation.
- Do not claim PASS from partial tests, skipped tests, mocks that bypass the behavior, or process exit alone.
- Do not cross from containment into the permanent implementation plan.

## Read-only intake gate

Before the first code edit:

1. Read every file listed under `Files` for all four tasks.
2. Locate the exact production entry points for `dual`, standalone `codex`, artifact review, multi-lens review, fixer launch, status, wait, failure-budget reopen, and sync/deploy.
3. Inspect existing tests covering those entry points.
4. Produce a traceability matrix in your response with one row for every RED/GREEN/acceptance requirement:

```text
REQ_ID | PLAN_TASK | REQUIREMENT | PRODUCTION_FILES | TEST | STATUS
```

Use stable IDs `T1-R01`, `T1-R02`, continuing through Tasks 2–4. Every plan checkbox must map to at least one requirement row. A row may not be marked complete without file-and-test evidence.

If the locked documents contain a genuine contradiction that makes implementation impossible, stop once with `SPEC_BLOCKED`, quote both conflicting requirements, and identify the smallest decision required. Missing effort, complexity, or a possible refactor is not a blocker.

If no genuine contradiction exists, continue automatically into Task 1. Do not ask for confirmation and do not propose alternative architectures.

## Implementation protocol

For each task, follow this exact sequence:

1. Re-read that complete task and its mapped traceability rows.
2. Inspect current implementations and preserve existing compatible behavior.
3. Write the task's failing tests first.
4. Run the exact focused tests and capture the expected RED reason.
5. Implement the smallest complete production change satisfying every mapped row.
6. Run the focused tests until PASS.
7. Run all previously completed task tests to catch regression.
8. Re-open the diff and compare it line-by-line with every traceability row.
9. Report task evidence using the required status format below.
10. Continue to the next task only when every row for the current task is `PASS`.

Do not perform repeated design review between tasks. Do not call another agent. The locked plan already supplies the design.

## Completeness rules

- “Implemented” means production path plus regression test plus passing execution evidence.
- All Codex launch paths must share the same authorization; testing only `cmd_dual` is incomplete.
- Changed snapshots must not reset the durable task+mode review ceiling.
- The third content FAIL must block; invocations four through ten must launch zero Codex and zero fixer processes.
- `INFRA_FAIL`, `STALE`, duplicate, cancellation, schema error, and `STATE_DESYNC` must not consume content budget.
- Lease ownership must include PID, process start time, and random invocation token.
- Terminal status, review manifest, report evidence, and lease release must agree.
- Canonical and deployed profiles must both have `auto_fix=false`.
- Production must reject `MaxCycles > 1`.
- No phase handler may call the next phase.
- Deployment must include `review_pipeline.py` and every other changed runtime dependency.
- Existing task history and `.agent/context`, `.agent/state`, `.agent/reports`, knowledge, and learning data must remain intact.

## Test gates

At minimum, run the focused test commands named in the locked plan. Before declaring completion, run all of:

```powershell
python -m unittest test_dual_loop_guards.py
python -m unittest test_dual_loop_containment_deploy.py
python test_pipeline.py
```

Also run validate-only deployment and the isolated Navis canary exactly as required by Task 4. Revit deployment is not authorized unless every prior gate is PASS.

If a test fails, remain in the current task, diagnose the failing requirement, and fix it. Do not trigger a review cycle and do not advance progress.

## Required progress report

After intake and after every task, output exactly:

```text
GEMINI_PHASE: INTAKE | TASK_1 | TASK_2 | TASK_3 | TASK_4 | COMPLETE | BLOCKED
SPEC_HASH_STATUS: PASS | SPEC_DRIFT
CURRENT_TASK: <number and title, or NONE>
COMPLETED_REQUIREMENTS: <passed count>/<total count>
CHANGED_FILES: <exact paths, or NONE>
TESTS_RUN: <exact commands and PASS/FAIL>
RED_EVIDENCE: <expected failure proved before implementation, or NONE>
REMAINING_REQUIREMENTS: <stable REQ_ID list, or NONE>
BLOCKERS: <evidence-backed blocker, or NONE>
SPEC_COVERAGE: <percentage>
READY_FOR_CODEX: NO | YES
NEXT_ACTION: <one concrete action>
```

Angle-bracket descriptions above explain the value; replace them with real values in every report.

`READY_FOR_CODEX` remains `NO` during Tasks 1–3 and while any Task 4 row/test/canary is incomplete. Set it to `YES` only when all four tasks pass, spec coverage is 100%, no blocker remains, and the full diff has been checked against every traceability row.

## Completion contract

Do not say “done”, “implemented”, or “ready” unless all conditions below are true:

- All four tasks are complete in order.
- Every traceability row is PASS with production and test evidence.
- Full test gates pass.
- Validate-only and Navis canary pass.
- No Revit target was changed before authorization.
- No locked document changed; recomputed hashes still match.
- No unauthorized file changed.
- No Codex/reviewer process was started.
- `SPEC_COVERAGE: 100%`.

At completion, output the final required progress report followed by:

```text
HANDOFF_TO_CODEX
TASK_ID: dual_agent_loop_containment
WRITER: GEMINI_ANTIGRAVITY
WRITER_STATUS: COMPLETE
CODEX_STATUS: NOT_STARTED
REVIEW_REQUESTED: YES
```

Stop after this handoff. Codex review is owned by the external orchestrator/human and must not be started by Gemini.

---

