# Release Notes — Antigravity.TagArranger

**Version**: 1.1.0
**Date**: 2026-06-27
**Module**: `Antigravity.TagArranger`
**Branch**: `feature/tag-arranger-optimization`

---

## Bug Fixes

### Critical

- **F3 — MinSpacing mutation fixed** (`ArrangerEventHandler.cs`)
  `Options.MinSpacingFeet` no longer mutated during arrange cycle. Local `modelSpacingFeet` prevents permanent data corruption on mid-cycle exceptions.

- **F5 — Revit version guard for Merge Tags** (`MergeTagService.cs`, `ArrangerWindow.xaml`, `ArrangerWindow.xaml.cs`, `TagArrangeCommand.cs`)
  `IndependentTag.AddReferences()` now guarded by version check. On Revit < 2022, **Merge Tags** button disabled with tooltip `Requires Revit 2022+`. No crash.

### Medium

- **F1 — Removed MaintainLeader dead code** (`ArrangeOptions.cs`, `ArrangerWindow.xaml`, `ArrangerWindow.xaml.cs`)
  Checkbox and property never had effect. Removed to reduce confusion.

- **F4 — Deduplicated orthogonal leader logic** (`LeaderService.cs`, `AutoTagService.cs`)
  Extracted `CalculateOrthogonalElbow()` into `LeaderService`. Both call sites now use unified implementation.

- **F6 — Exception logging in AnnotationBoxExtractor** (`AnnotationBoxExtractor.cs`)
  Silent `catch {}` replaced with structured try-catch appending to `logMessages`.

- **F7 — Fixed CenterH/V reference box calculation** (`AlignService.cs`)
  `AlignMode.CenterHorizontal` / `CenterVertical` now computes median and selects closest box. Previously always returned `boxes.First()`.

### Low

- **F8 — Log Panel wired to UI** (`ArrangerWindow.xaml.cs`)
  `ArrangeResult.LogMessages` rendered in expandable `Expander` (`TxtLog`).

---

## Build

- Engine: MSBuild 18.7 | Target: Release | Errors: 0 | Warnings: 0

## Out of Scope (tracked in PLAN.md)

- Phase 3: TextNote support (N1)
- Phase 4: AutoTag category expansion (N2)
- Phase 5: Log Panel UI (N3 already done via F8)
- Phase 6: Configurable magic numbers (N6)
