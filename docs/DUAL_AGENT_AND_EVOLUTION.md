# Dual Agent and Controlled Evolution

## Operating model

The factory uses **single writer, independent verifier**:

- Antigravity is the only agent allowed to edit the live task worktree.
- Codex reviews an immutable read-only copy and returns schema-bound findings.
- Agents exchange durable files, not private chat state.
- A retry is valid only after the repository snapshot changes.
- No candidate is promoted automatically.

This matches Antigravity's artifact-oriented workflow and Codex non-interactive
automation (`codex exec`, structured output, explicit sandbox).

## First-time setup

1. Sign in to Antigravity CLI by launching `agy` interactively once.
2. Verify both runtimes:

   ```powershell
   python E:\AI_SOFTWARE_FACTORY\harness.py revit doctor
   ```

3. Require both checks to show `READY`. The report is stored at
   `.agent/reports/DUAL_AGENT_DOCTOR.json`.
4. Keep `dual_agents.auto_fix: true` only on projects where Antigravity CLI is
   authenticated and allowed to edit the workspace.

Do not use `--dangerously-skip-permissions`. Codex remains read-only; Antigravity
receives only the scoped fixer role.

## Dual-agent cycle

```text
Antigravity implementation
        ↓
build/test/lint evidence
        ↓
Codex read-only review (JSON Schema)
        ↓ FAIL
FIXER_HANDOFF.json + CODEX_REVIEW.md
        ↓
Antigravity scoped fix
        ↓
fresh verification + snapshot + Codex retry
```

Important files:

- `TASK_CONTEXT.json`: durable task state and failure budget.
- `TASK_SCOPE.json`: allowed and forbidden paths.
- `review_run.json`: exact Codex run, snapshot and reviewed files.
- `FIXER_HANDOFF.json`: machine contract from Codex to Antigravity.
- `FIXER_COMMAND_REPORT.json`: Antigravity CLI execution evidence.

## P2 — Observability and learning data

Every dual pipeline result appends an event under
`.agent/learning/trajectories/<task-id>.jsonl`.

Add human outcome labels and build a reproducible dataset:

```powershell
python harness.py revit learn-label <task-id> success "Validated in Revit"
python harness.py revit learn-dataset operations
```

The split is deterministic: 70% train, 15% validation and 15% holdout by task
hash. JSONL is the source of truth; generated datasets are disposable.

## P3 — Shadow improvement

Candidates are created outside production and compared against a baseline:

```powershell
python harness.py revit shadow `
  skills/baseline/SKILL.md `
  .agent/learning/candidates/new/SKILL.md `
  .agent/learning/datasets/golden.json
```

The golden dataset should contain validation and holdout examples with
`rubric.required_terms` and `rubric.forbidden_terms`. Trajectory datasets are
useful for failure discovery but should not be the only promotion evidence.

## P4 — Evolution gate

```powershell
python harness.py revit evolution-gate .agent/learning/runs/<run-id>.json
```

The gate checks shadow eligibility, candidate hash, security patterns and fresh
verification evidence. A pass means `APPROVED_FOR_CANARY`, never production.

## P5 — Canary and continuous status

```powershell
python harness.py revit canary .agent/learning/candidates/<gate-id>.json 10
python harness.py revit canary-outcome .agent/learning/canary/<id>.json success
python harness.py revit learning-status
```

Any regression changes status to `ROLLBACK_REQUIRED`. Ten observations with at
least 90% success produce `READY_FOR_HUMAN_PROMOTION`. Promotion remains manual.

## Current known blockers

- `ANTIGRAVITY_AUTH_REQUIRED`: run `agy` interactively and sign in.
- `PERMISSION_BLOCKED`: ensure Antigravity can write its own app-data/log folder.
- Codex Windows `orchestrator_helper_launch_failed`: repair/update the Codex
  installation or Windows sandbox helper. The pipeline can review embedded diff
  evidence, but deep repository inspection is degraded until this is fixed.
- `BLOCKED_HANDOFF`: failure budget exhausted; change scoped code and provide a
  new falsifiable `--resume-hypothesis`.

## Primary references

- OpenAI Codex non-interactive mode: https://developers.openai.com/codex/noninteractive
- OpenAI Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Google Antigravity IDE codelab: https://codelabs.developers.google.com/getting-started-agy-ide
- Google Antigravity platform: https://developers.googleblog.com/en/build-with-google-antigravity-our-new-agentic-development-platform/
# Checkpointed convergence control

Writer claims authorize readiness but remain unverified until Codex closes them. Recurrence becomes `REGRESSED`. Counters persist by task and lifecycle phase: the third review of one finding batch stops at `BATCH_REVIEW_CEILING`, the seventh phase review stops at `PHASE_REVIEW_CEILING`, and two non-positive net-closure reviews stop at `NO_PROGRESS`.
