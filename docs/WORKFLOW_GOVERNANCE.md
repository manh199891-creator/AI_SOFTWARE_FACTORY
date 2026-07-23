# Workflow Governance: P0 and P1

This layer makes task progress resumable and completion claims auditable.

## P0: durable execution state

`dual-init` creates `.agent/context/TASK_CONTEXT.json` alongside `TASK_SCOPE.json`.
It records the task, repository snapshot, constraints, verification commands,
resume cursor, evidence references, events, and failure budget.

`verify` writes `.agent/state/EVIDENCE_MANIFEST.json`. Each build/test/lint result
contains the exact command, exit code, timestamps, report path, and output hash.
The manifest is fresh only when the repository snapshot is unchanged during the
verification run. Projects opt into release enforcement with:

```json
{
  "evidence_policy": {
    "required_for_gate": true,
    "required_stages": ["build", "test", "lint"]
  }
}
```

Only list stages that the project actually configures. A missing required stage
blocks release.

Repeated failed review attempts consume `failure_budget.max_failed_attempts`
(default 3). Exhaustion writes:

- `.agent/reports/ROOT_CAUSE_HANDOFF.md`
- `.agent/knowledge/memory/bugs/<task-id>.md`

Resume only with new evidence or a new falsifiable hypothesis.

## P1: risk routing and operational knowledge

Code reviews are routed automatically:

- `QUICK`: at most 3 files and 50 changed lines.
- `STANDARD`: changes between the quick and deep thresholds.
- `DEEP`: at least 11 files, 301 changed lines, or any sensitive path.

Thresholds and sensitive globs live under `review_routing` in
`.agent/project_profile.json`. The selected tier and metrics are stored in
`review_run.json` and `CODEX_REVIEW.md`.

Operational knowledge is separated by audience:

- `.agent/knowledge/memory/`: machine-recall facts, decisions, and bug episodes.
- `.agent/knowledge/learn/`: curated human explanations; never auto-generated.
- `.agent/knowledge/later/`: out-of-scope findings recorded by guardrails without
  widening the active task.

Markdown is the source of truth. A future search index must remain disposable
and rebuildable from these files.

## Adoption

For an existing project, add `evidence_policy`, `failure_budget`, and
`review_routing` to its profile. Run `dual-init --force` only when replacing the
current task; normal runs preserve the existing durable context.
# Dual-agent phase checkpoints

`.agent/state/pipeline_status.json` version 2 is the durable authority. Anti submits `WRITER_CHECKPOINT_REQUEST.json`; the harness owns checkpoint persistence and Codex scheduling. Only a committed snapshot with matching `phase_gate` PASS advances lifecycle.

Deployment is manifest-bound and journaled. Validate-only never changes targets. Production replacement requires a unique immutable backup and never overwrites task context, state, reports, knowledge, or learning history.
