# Automatic Formwork MVP — Acceptance Criteria

Task ID: `automatic_formwork_mvp`

## AC-01 — Scope and architecture

Trace: Plan Task 1. Core loads and its tests execute without Autodesk assemblies; the Revit adapter targets net48 and references Core in one direction. Every implementation/test/document path remains allowed by `TASK_SCOPE.json`.  
Evidence: project-reference inspection plus Core smoke test and Revit adapter target test.

## AC-02 — Versioned catalog contract

Trace: Plan Task 2. A catalog with schema_version, CatalogVersion, SystemId and stable CatalogItemId values validates panel/corner/filler/stop-end/tie/rail dimensions, orientation, insertion origin, family/type and writable parameter contracts. Invalid/unknown versions fail before preview.  
Evidence: `tests/Antigravity.Formwork.Core.Tests/CatalogContractTests.cs` and Revit family mapping tests from Plan Task 9.

## AC-03 — Deterministic topology and selection order

Trace: Plan Task 3. Reversing host selection order, loop direction or Revit enumeration order produces identical ordered topology and FaceKey values. Straight walls and rectangular columns use millimeter-normalized immutable DTOs.  
Evidence: permutation fixtures in `tests/Antigravity.Formwork.Core.Tests/TopologyBuilderTests.cs` with byte-for-byte expected snapshots.

## AC-04 — Catalog solver, junctions and coverage

Trace: Plan Task 4 and Plan Task 5. Repeated/permuted input produces identical placements. Supported wall faces achieve at least 98% coverage; every remainder is a classified gap. L/T/X-junction and stop-end fixtures have catalog-compatible items and no generated overlap beyond configured assembly tolerance.  
Evidence: solver golden tests and junction fixtures in `tests/Antigravity.Formwork.Core.Tests/PanelLayoutSolverTests.cs` and `tests/Antigravity.Formwork.Core.Tests/JunctionRuleEngineTests.cs`.

## AC-05 — Cycle ownership and validation

Trace: Plan Task 6. Planning one cycle or all cycles gives the same result for each CycleId. No FaceKey is owned twice unless an explicit connection rule owns the shared boundary. Missing family/type, tie, out-of-face placement, overlap and cross-cycle conflicts block commit.  
Evidence: cycle/validator unit fixtures in `tests/Antigravity.Formwork.Core.Tests/CycleAndValidationTests.cs`.

## AC-06 — Side-effect-free preview

Trace: Plan Task 7 and Plan Task 10. Preview returns hosts, cycles, placements, coverage, classified gaps, conflicts and BOM without opening a Transaction or writing model/storage. Generate/Update is disabled for blocking conflicts or a stale preview hash.  
Evidence: mutation-port spy tests in `tests/Antigravity.Formwork.Core.Tests/PlanningServiceTests.cs` plus Revit command/UI boundary tests.

## AC-07 — Metadata and idempotent deterministic diff

Trace: Plan Task 8. Every generated placement has RunId, HostUniqueId, FaceKey, CycleId, SystemId, CatalogItemId, Locked and Manual metadata. An unchanged rerun yields an empty diff and no duplicate. Changing one host changes only its affected unlocked placements.  
Evidence: create/update/keep/conflict/delete golden cases in `tests/Antigravity.Formwork.Core.Tests/FormworkDiffEngineTests.cs`.

## AC-08 — Locked/Manual preservation and deletion safety

Trace: Plan Task 8 and Plan Task 11. Locked or Manual instances survive host/cycle/catalog updates and appear as conflicts when incompatible. Deletion is constrained by RunId and confirmed scope; FamilyName + HostUniqueId alone can never establish ownership.  
Evidence: Core diff tests and `tests/Antigravity.Formwork.RevitTests/RevitCommitUpdateTests.cs` lifecycle assertions.

## AC-09 — Transaction rollback and native placement

Trace: Plan Task 11. Commit creates native schedulable FamilyInstance elements only after preview freshness and catalog validation. A failure during create/update/delete, parameter write or storage write causes complete rollback and leaves the model unchanged.  
Evidence: failure-injection and transaction status tests in `tests/Antigravity.Formwork.RevitTests/RevitCommitUpdateTests.cs`.

## AC-10 — BOM CSV reconciliation

Trace: Plan Task 12. BOM quantities and areas grouped by item/level/cycle/host reconcile exactly with committed instances. BOM CSV ordering is deterministic, invariant-culture numeric output is used, and comma/quote/newline fields follow CSV escaping rules.  
Evidence: `tests/Antigravity.Formwork.Core.Tests/BomCsvWriterTests.cs` plus committed-model reconciliation in `tests/Antigravity.Formwork.RevitTests/FormworkLifecycleTests.cs`.

## AC-11 — Performance and diagnostics

Trace: Plan Task 12. The versioned 100 wall benchmark completes pure preview within the budget recorded in its fixture before implementation; extraction and commit are timed separately. Diagnostics contain task/run/input/catalog/solver identifiers, counts, coverage and classified gaps.  
Evidence: `tests/Antigravity.Formwork.Core.Tests/FormworkBenchmarkTests.cs` benchmark artifact and runtime diagnostic assertions.

## AC-12 — Review and release gate

Trace: Plan Task 12. Runtime recovery tests and the artifact-contract test pass twice. Exactly one fresh Codex plan review covers PLAN.md, TECHNICAL_DESIGN.md and ACCEPTANCE_CRITERIA.md on the same changed snapshot; manifest and report agree on task ID, run ID, snapshot hash, reviewed files and PASS.  
Evidence: unittest logs, `.agent/state/review_run.json`, and `.agent/reports/CODEX_REVIEW.md`. The repository implementation plan is published only after this gate.
