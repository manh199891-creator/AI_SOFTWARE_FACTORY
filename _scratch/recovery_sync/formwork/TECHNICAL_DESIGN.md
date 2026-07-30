# Automatic Formwork MVP — Technical Design

Task ID: `automatic_formwork_mvp`  
Targets: Revit 2024/net48 adapter plus Revit-free Core domain

## 1. Architecture and dependency direction

`src/Antigravity.Formwork.Core/` contains all catalog, topology, cycle, solver, validation, deterministic diff, and BOM CSV logic. Its immutable inputs and outputs use millimeter values and contain no Autodesk types. `src/Antigravity.Formwork/` owns selection, UnitUtils conversion, Revit geometry extraction, family validation, WPF/ExternalEvent, persistence, and Transaction mutation. The adapter depends on Core; Core never depends on Revit.

Preview is a pure operation:

`Revit snapshot → immutable Core DTOs → topology → cycle plan → catalog solver → validation → preview/diff/BOM`

Commit is a separate operation:

`approved preview snapshot + current Revit snapshot → freshness check → deterministic diff → one transaction boundary`

## 2. Immutable contracts and units

Core records are immutable and normalized to millimeter and radians before hashing:

- `HostSnapshot`: HostUniqueId, category, level, ordered faces, source change fingerprint.
- `FormworkFace`: FaceKey, plane, outer loop, openings, contact classification, supported area.
- `CycleDefinition`: CycleId, source (`Manual` or parameter), stable ordering and boundary rules.
- `Catalog`: schema_version, CatalogVersion, SystemId, items and compatibility tables.
- `CatalogItem`: CatalogItemId, kind, dimensions, valid orientation, insertion origin, connectors, family/type mapping and required parameter contract.
- `Placement`: RunId, HostUniqueId, FaceKey, CycleId, SystemId, CatalogItemId, transform, quantity and status.
- `FormworkMetadata`: the same ownership tuple plus `Locked`, `Manual`, catalog version and plan fingerprint.

Unknown schema_version, duplicate stable IDs, non-positive dimensions, unsupported orientations, missing connectors, or incomplete family/type contracts fail closed before preview.

## 3. Stable identity

FaceKey is not a Revit face reference. It is the SHA-256 digest of HostUniqueId, quantized plane normal/origin, ordered quantized boundary segments and contact class. Quantization uses the configured geometric tolerance. Loop rotation and direction are canonicalized, so selection order and Revit enumeration order cannot change FaceKey.

Run identity is explicit. Generated elements are never discovered or deleted using FamilyName alone. Shared parameters expose fields needed by schedules/filters: RunId, HostUniqueId, FaceKey, CycleId, SystemId, CatalogItemId, Locked and Manual. Extensible Storage or DataStorage holds run config, catalog version, solver version, preview hash and update history.

## 4. Topology model

The topology builder removes concrete-to-concrete contact faces according to configuration, clusters endpoints by actual distance, and orders straight wall segments deterministically. MVP node types are isolated end, L-junction, T-junction, X-junction, column corner, thickness transition and stop-end.

- L-junction chooses compatible inside/outside corner items and reserves connector depth.
- T-junction reserves the through-wall run, then places the branch rule with a stable side convention.
- X-junction applies the catalog's cross connection table; no generic corner fallback is allowed.
- stop-end uses a catalog item compatible with wall thickness and orientation.

When no rule matches, the engine emits a classified unsupported-junction gap. It never invents a panel size.

## 5. Catalog solver

For each ordered face interval, the solver enumerates compatible catalog items and minimizes this lexicographic objective:

1. unsupported or unclassified length;
2. out-of-tolerance overlap;
3. filler length and filler count;
4. total panel count;
5. stable CatalogItemId sequence.

Tie-break evaluation uses quantized integers and ordinal stable IDs, never dictionary order. The same hosts, cycle definitions, catalog version and settings therefore yield the same placements and diagnostics. The MVP supports one versioned system catalog with multiple family/type mappings; it is not a single embedded FormworkPanel.rfa or a fixed 1000×2000 grid.

## 6. Cycle lifecycle and validation

CycleId comes from an explicit manual assignment or configured host parameter. Planning one cycle and planning all cycles use the same topology snapshot. A FaceKey may have one owning cycle; a catalog-defined connection rule may reserve a boundary shared by two cycles without duplicating its face area.

Validation runs before commit and reports:

- supported-face coverage and every classified gap;
- panel/panel overlap beyond assembly tolerance;
- missing or incompatible family/type mapping;
- placement outside its host face;
- missing required tie/rail connection;
- duplicate face/cycle ownership and cross-cycle collision;
- catalog or host snapshot changes since preview.

Any blocking diagnostic disables Generate/Update. Warnings stay visible in the conflict inspector.

## 7. Preview and UI boundary

`src/Antigravity.Formwork/UI/FormworkWorkbench.xaml` is a modeless workbench. Its left pane selects host/level/cycle/system, center pane lists run and host coverage, and right pane shows rules and conflicts. Preview calls the pure planner and creates no Revit element, DataStorage, parameter, or Transaction. Revit reads and writes execute only on the main thread through the ExternalEvent handler.

The approved preview stores source, catalog and configuration hashes. Commit rejects a preview if any hash changed.

## 8. Deterministic update diff

The diff engine compares desired placements with persisted ownership metadata and returns stably ordered Create, Update, Keep, Conflict and Delete sets.

- Unchanged input returns an empty diff and creates no duplicate.
- A changed host affects only placements sharing that HostUniqueId/FaceKey.
- A catalog or cycle change affects only its owned unlocked placements.
- Locked or Manual instances are always preserved; incompatible desired placements become explicit conflicts.
- Deletion is constrained by RunId and confirmed scope, never FamilyName.

## 9. Revit mutation and rollback

The commit service revalidates family/type parameters and preview freshness, then applies the full diff within one TransactionGroup with a dedicated Transaction. Family activation, create/update/delete, shared parameters and storage writes are checked. Any exception, failed parameter write, stale snapshot or non-committed transaction triggers rollback of all changes. Preview and export never share this transaction boundary.

## 10. Catalog-to-family validation

Before preview, every mapped family/type is checked for category, insertion origin, orientation convention, connector alignment, writable dimension parameters and supported catalog item kind. Mapping uses stable CatalogItemId, not display name. Binary family paths come from the authenticated existing Revit test/runtime configuration; there is no “install path or standard team directory” placeholder.

## 11. BOM CSV

BOM rows derive from the immutable committed placement plan and group by CatalogItemId, level, CycleId and HostUniqueId. Counts and areas reconcile exactly with committed native instances. CSV escaping follows RFC 4180 semantics: quote fields containing comma, quote or newline and double embedded quotes. Rows use stable ordinal ordering and invariant numeric formatting.

## 12. Performance and observability

The benchmark contains 100 wall segments with recorded catalog/config versions. It measures pure preview separately from Revit extraction and commit. The agreed preview budget is written into the test fixture before implementation and is never inferred after a run. Diagnostics record task/run ID, input hashes, solver version, counts, coverage, classified gaps and duration without secret/catalog payload leakage.

## 13. Explicit exclusions

Curved/sloped/variable-height walls, slab/deck/shoring, full scaffolding, multi-site inventory optimization and structural certification are excluded. Unsupported geometry is classified and shown; it is not approximated silently.
