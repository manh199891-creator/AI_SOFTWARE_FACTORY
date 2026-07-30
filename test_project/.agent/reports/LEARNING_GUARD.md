# LEARNING_GUARD.md

## Status: PASS
- task_id: test_task
- mode: release
- generated_at: 2026-07-30T05:52:21.072311+00:00
- source_count: 1
- matched_rule_count: 1

## Token Strategy
- Agents read `.agent/context/MEMORY_CONTEXT.md` by default.
- Full memories stay in `.agent/knowledge/**` and are loaded only when a rule matches the active issue.

## Rules
- **review_batch_context_split** [P2] hits=1: Keep related production, project, and test files together in review context where possible.
  source: `E:\AI_SOFTWARE_FACTORY\test_project\.agent\reports\CODEX_REVIEW.md`
