# TECHNICAL_DESIGN.md - generic_task

## Feature

Generic feature for any project

## Scope

The authoritative file scope is `.agent/context/TASK_SCOPE.json`.

## Implementation Rules

- Keep changes inside `allowed_files`.
- Do not edit `forbidden` paths.
- Preserve existing project architecture and naming.
- Avoid broad refactors unless required by the feature.
- Add focused tests where the project has a test surface.

## Review Rules

Codex must verify:

- changed files match task scope;
- implementation matches this design and acceptance criteria;
- tests or validation are meaningful;
- no unrelated changes are included.
