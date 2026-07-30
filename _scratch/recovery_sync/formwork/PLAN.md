# Automatic Formwork MVP — Executable TDD Plan

Task ID: `automatic_formwork_mvp`  
Mode: `plan`  
Source specification: `docs/superpowers/plans/2026-07-22-automatic-formwork-spec.md`

## Objective and boundaries

Deliver a deterministic, catalog-driven wall and rectangular-column formwork workflow for Revit 2024. The MVP includes cycle assignment, preview, validation, native placement, Locked/Manual preservation, deterministic diff/update, and BOM CSV. Curved/sloped walls, slab/shoring, multi-vendor optimization, and structural certification remain out of scope.

## Task 1: Create testable project seams

**Files:** `Antigravity.sln`, `src/Antigravity.Formwork.Core/Antigravity.Formwork.Core.csproj`, `src/Antigravity.Formwork/Antigravity.Formwork.csproj`, `tests/Antigravity.Formwork.Core.Tests/Antigravity.Formwork.Core.Tests.csproj`, `tests/Antigravity.Formwork.RevitTests/Antigravity.Formwork.RevitTests.csproj`  
**RED:** Add a core smoke test proving the domain assembly loads without Revit API and a Revit test proving the adapter assembly targets net48.  
**GREEN:** Add the two production projects and two test projects with references flowing Revit adapter → Core only.  
**PASS:** Core tests execute outside Revit; dependency inspection shows Core has no Autodesk reference.  
**Commit:** `build(formwork): add core and Revit project seams`

## Task 2: Define immutable geometry, run, and catalog contracts

**Files:** `src/Antigravity.Formwork.Core/Models/FormworkContracts.cs`, `src/Antigravity.Formwork.Core/Catalog/FormworkCatalog.cs`, `src/Antigravity.Formwork.Core/Catalog/FormworkCatalogParser.cs`, `tests/Antigravity.Formwork.Core.Tests/CatalogContractTests.cs`  
**RED:** Test schema_version rejection, duplicate stable IDs, invalid dimensions/orientations, missing family/type mapping, and mutation attempts.  
**GREEN:** Implement immutable millimeter DTOs for Host/Face/Edge/Cycle/Placement/Run metadata and a versioned catalog containing panel, corner, filler, stop-end, tie, and rail items.  
**PASS:** Valid catalogs round-trip deterministically; invalid origin/orientation/parameter contracts fail before planning.  
**Commit:** `feat(formwork): define immutable catalog contracts`

## Task 3: Extract pure face topology

**Files:** `src/Antigravity.Formwork.Core/Geometry/FaceKeyFactory.cs`, `src/Antigravity.Formwork.Core/Geometry/TopologyBuilder.cs`, `tests/Antigravity.Formwork.Core.Tests/TopologyBuilderTests.cs`  
**RED:** Cover reversed selection order, tolerance-bound endpoints, duplicate contact faces, straight wall ends, and rectangular columns.  
**GREEN:** Build normalized planar topology in millimeters and a stable FaceKey derived from host identity plus quantized face geometry, never a transient Revit reference alone.  
**PASS:** Equivalent inputs produce byte-identical ordered topology and FaceKey values.  
**Commit:** `feat(formwork): add deterministic face topology`

## Task 4: Implement the deterministic panel solver

**Files:** `src/Antigravity.Formwork.Core/Solver/PanelLayoutSolver.cs`, `src/Antigravity.Formwork.Core/Solver/LayoutObjective.cs`, `tests/Antigravity.Formwork.Core.Tests/PanelLayoutSolverTests.cs`  
**RED:** Test multiple catalog widths, exact fits, bounded fillers, unsupported gaps, selection-order permutations, and explicit tie-break collisions.  
**GREEN:** Minimize classified uncovered length, then filler count, panel count, and finally stable CatalogItemId sequence; never replace the catalog with a fixed 1000×2000 grid.  
**PASS:** Repeated/permuted inputs return the same placements, coverage, diagnostics, and objective score.  
**Commit:** `feat(formwork): implement deterministic catalog solver`

## Task 5: Add junction and stop-end rules

**Files:** `src/Antigravity.Formwork.Core/Solver/JunctionRuleEngine.cs`, `tests/Antigravity.Formwork.Core.Tests/JunctionRuleEngineTests.cs`  
**RED:** Add isolated end, L-junction, T-junction, X-junction, wall-thickness transition, inside/outside corner, and stop-end fixtures.  
**GREEN:** Select system-specific corner/stop-end items by stable ID, reserve connector depth, and emit a classified conflict when no compatible item exists.  
**PASS:** Each fixture has deterministic placements with no out-of-tolerance overlap and no silent fallback.  
**Commit:** `feat(formwork): encode junction placement rules`

## Task 6: Plan cycles and validate conflicts

**Files:** `src/Antigravity.Formwork.Core/Cycles/CyclePlanner.cs`, `src/Antigravity.Formwork.Core/Validation/FormworkPlanValidator.cs`, `tests/Antigravity.Formwork.Core.Tests/CycleAndValidationTests.cs`  
**RED:** Test manual/parameter cycles, all-cycle and one-cycle planning, duplicate face ownership, gap classification, missing catalog items, missing ties, and cross-cycle collision.  
**GREEN:** Produce immutable per-cycle plans and diagnostics; reject two cycles claiming one FaceKey unless an explicit connection rule owns the boundary.  
**PASS:** Coverage, overlap, missing-item, tie, and cycle conflicts are complete and stably ordered.  
**Commit:** `feat(formwork): add cycle and validation lifecycle`

## Task 7: Build preview-only placement plans

**Files:** `src/Antigravity.Formwork.Core/Planning/FormworkPlanningService.cs`, `src/Antigravity.Formwork.Core/Planning/PreviewModel.cs`, `tests/Antigravity.Formwork.Core.Tests/PlanningServiceTests.cs`  
**RED:** Assert Preview produces placements/diagnostics/BOM without calling a mutation port and that invalid plans cannot become commit requests.  
**GREEN:** Separate pure planning from Revit mutation and expose one immutable preview model containing hosts, cycles, coverage, classified gaps, conflicts, and BOM CSV rows.  
**PASS:** Preview is side-effect free and byte-identical for unchanged input.  
**Commit:** `feat(formwork): add side-effect-free preview plan`

## Task 8: Persist ownership and calculate deterministic diff

**Files:** `src/Antigravity.Formwork.Core/Update/FormworkDiffEngine.cs`, `src/Antigravity.Formwork.Core/Models/FormworkMetadata.cs`, `tests/Antigravity.Formwork.Core.Tests/FormworkDiffEngineTests.cs`  
**RED:** Test unchanged rerun, catalog/host/cycle changes, deletion by RunId, and Locked/Manual items across create/update/delete sets.  
**GREEN:** Key generated ownership by RunId/HostUniqueId/FaceKey/CycleId/SystemId/CatalogItemId and calculate a deterministic diff that preserves Locked/Manual instances while reporting conflicts.  
**PASS:** Unchanged rerun yields an empty diff; one-host change touches only its unlocked placements.  
**Commit:** `feat(formwork): implement metadata-aware deterministic diff`

## Task 9: Adapt Revit geometry and validate family mappings

**Files:** `src/Antigravity.Formwork/Geometry/RevitHostExtractor.cs`, `src/Antigravity.Formwork/Catalog/RevitCatalogValidator.cs`, `tests/Antigravity.Formwork.RevitTests/RevitExtractionTests.cs`, `tests/Antigravity.Formwork.RevitTests/RevitCatalogValidationTests.cs`  
**RED:** Use the existing Revit test harness to cover wall/column extraction, unit conversion, insertion origin, orientation, writable parameter mapping, and missing family/type.  
**GREEN:** Convert Revit geometry through UnitUtils into Core DTOs and validate every catalog family/type contract before preview.  
**PASS:** No placeholder install/team path is required; fixtures use authenticated harness model paths supplied by the existing Revit test runner.  
**Commit:** `feat(formwork): add Revit extraction and catalog validation`

## Task 10: Implement the workbench and ExternalEvent boundary

**Files:** `src/Antigravity.Formwork/UI/FormworkWorkbench.xaml`, `src/Antigravity.Formwork/UI/FormworkWorkbenchViewModel.cs`, `src/Antigravity.Formwork/Commands/OpenFormworkCommand.cs`, `src/Antigravity.Formwork/Events/FormworkExternalEventHandler.cs`, `src/Antigravity.Main/App.cs`, `src/Antigravity.Main/Antigravity.Main.csproj`  
**RED:** Test command prerequisites, disabled commit with conflicts, cycle/system selections, and that Preview never opens a Transaction.  
**GREEN:** Add host/cycle/system controls, preview summary, conflict inspector, Generate/Update, Export, and Close; route every Revit operation through the main-thread ExternalEvent boundary.  
**PASS:** Preview performs zero model writes; Generate/Update requires the exact approved preview snapshot.  
**Commit:** `feat(formwork): add preview workbench boundary`

## Task 11: Commit and update native instances transactionally

**Files:** `src/Antigravity.Formwork/Placement/RevitFormworkCommitService.cs`, `src/Antigravity.Formwork/Persistence/FormworkRunStore.cs`, `tests/Antigravity.Formwork.RevitTests/RevitCommitUpdateTests.cs`  
**RED:** Test create/update/delete, failure midway, parameter write failure, stale preview, RunId deletion, Locked/Manual preservation, and rollback.  
**GREEN:** Validate preview freshness, then apply one deterministic diff inside an isolated Transaction/TransactionGroup; map schedule fields to shared parameters and run/config/catalog version to Extensible Storage or DataStorage.  
**PASS:** Any failure rolls back all mutation; successful instances contain complete metadata and remain native schedulable FamilyInstance elements.  
**Commit:** `feat(formwork): commit native instances with rollback`

## Task 12: Reconcile BOM CSV and performance gates

**Files:** `src/Antigravity.Formwork.Core/Export/BomCsvWriter.cs`, `tests/Antigravity.Formwork.Core.Tests/BomCsvWriterTests.cs`, `tests/Antigravity.Formwork.Core.Tests/FormworkBenchmarkTests.cs`, `tests/Antigravity.Formwork.RevitTests/FormworkLifecycleTests.cs`  
**RED:** Test RFC-compatible CSV escaping, stable ordering, exact instance reconciliation, classified gaps, and a 100 wall preview benchmark.  
**GREEN:** Export item/level/cycle/host quantities and area from the immutable committed plan, then add full preview→commit→update→delete lifecycle fixtures.  
**PASS:** BOM CSV reconciles exactly with committed instances; supported-face coverage is at least 98%; the 100 wall benchmark meets the recorded budget.  
**Commit:** `test(formwork): gate lifecycle BOM and performance`

## Review and publication gate

Run the machine artifact contract first. Then run exactly one plan review on a changed stable snapshot with hypothesis: `Restored approved catalog-cycle-preview-update-BOM scope and added machine artifact contract`. Create `docs/superpowers/plans/2026-07-22-automatic-formwork-implementation.md` only after manifest and report both return PASS for the same run ID, snapshot hash, and reviewed files.
