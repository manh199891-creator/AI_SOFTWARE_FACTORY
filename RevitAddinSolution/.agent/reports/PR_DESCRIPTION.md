# PR: TagArranger Optimization — Phase 1 & 2

## Summary

Fixes 7 issues (2 critical, 3 medium, 2 low) identified in code review of `Antigravity.TagArranger`. No new features — pure quality and safety improvements.

## Changes

### Critical Bug Fixes

| ID | File | Change |
|----|------|--------|
| F3 | `ArrangerEventHandler.cs` | Capture `MinSpacingFeet` into local before arrange loop; no mutation of `Options` |
| F5 | `MergeTagService.cs` | Guard `AddReferences()` call behind `revitYear >= 2022` check |
| F5 | `TagArrangeCommand.cs` | Extract `revitYear` from `VersionNumber`, pass to `ArrangerWindow` |
| F5 | `ArrangerWindow.xaml` | Add `x:Name=BtnMergeTags` to Merge Tags button |
| F5 | `ArrangerWindow.xaml.cs` | Accept `revitYear` in ctor; disable button + set tooltip if < 2022 |

### Medium Bug Fixes

| ID | File | Change |
|----|------|--------|
| F1 | `ArrangeOptions.cs` | Remove `MaintainLeader` property |
| F1 | `ArrangerWindow.xaml` | Remove `ChkMaintainLeader` checkbox |
| F1 | `ArrangerWindow.xaml.cs` | Remove corresponding binding/mapping |
| F4 | `LeaderService.cs` | Add `CalculateOrthogonalElbow()` shared helper |
| F4 | `AutoTagService.cs` | Replace inline duplicate with call to `LeaderService` helper |
| F6 | `AnnotationBoxExtractor.cs` | Replace silent catch with logged exception via `logMessages` param |
| F7 | `AlignService.cs` | Fix `CenterH/V` to use median-closest box instead of `First()` |

### Low / UI

| ID | File | Change |
|----|------|--------|
| F8 | `ArrangerWindow.xaml.cs` | Wire `result.LogMessages` to `TxtLog` Expander |

## Testing

- Build: MSBuild 18.7, Release, 0 errors, 0 warnings
- QA acceptance criteria: AC-1.1, AC-1.2, AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5 — all PASS after fix
- Manual: Verified `BtnMergeTags` disabled on Revit < 2022 path via code inspection

## Notes

- Do NOT merge to `main` without human review
- Phases 3–6 tracked separately in PLAN.md
- Post-build copy failed (Revit process held DLL) — expected; compilation itself succeeded
