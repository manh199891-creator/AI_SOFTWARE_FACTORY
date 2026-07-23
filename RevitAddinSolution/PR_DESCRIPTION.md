# PR DESCRIPTION

## Summary

feat(HoanThien): implement finish wall and floor automation from room boundaries

Implements the Antigravity.HoanThien module providing automated creation of
finish walls and finish floors derived from Revit room boundaries.

---

## Changes

### New Module: src/Antigravity.HoanThien/

**Models & Services:**
- HoanThienHandler.cs - ExternalEventHandler, main orchestrator
- RoomBoundaryService.cs - room boundary extraction with opening split support
- FinishWallBuilder.cs - finish wall creation with full shared parameter assignment
- FinishFloorBuilder.cs - finish floor creation with correct height offset
- FinishTypeManager.cs - wall type reuse/creation strategy
- HeightCalculator.cs - wall height computation
- OpeningHandler.cs - curve splitting at door/opening locations

**Tests:**
- tests/Antigravity.HoanThien.Tests/* - 6 xUnit tests, all PASS

**App.cs update:**
- src/Antigravity.Main/App.cs - ribbon button registration for HoanThien command

---

## QA Results

- Build: PASS (0 errors, 0 warnings critical)
- Unit Tests: 6/6 PASS
- Acceptance Criteria: 11/11 PASS

| AC | Description | Status |
|----|-------------|--------|
| AC-01 | Build succeeds | PASS |
| AC-02 | HoanThienHandler loops via RoomBoundaryService | PASS |
| AC-03 | FinishTypeManager.GetOrCreateWallType reuse/create | PASS |
| AC-04 | FinishWallBuilder assigns all 3 shared parameters | PASS |
| AC-05 | HeightCalculator unit tests pass | PASS |
| AC-06 | ComputeVolumes guard active | PASS |
| AC-07 | SplitCurveAroundOpening integrated | PASS |
| AC-08 | FinishFloorBuilder correct height param (negative) | PASS |
| AC-09 | Duplicate prevention via FilteredElementCollector | PASS |
| AC-10 | 6/6 xUnit pass | PASS |
| AC-11 | UI bindings and command ready | PASS |

---

## Codex Review Status

FAIL - task_id: auto_column (plan review for next feature, NOT this PR scope)
- P1 x4, P2 x2 findings in auto_column PLAN.md / TECHNICAL_DESIGN.md / ACCEPTANCE_CRITERIA.md
- These issues do NOT block HoanThien feature delivery
- auto_column plan must be revised before implementation begins

---

## Known Limitations

1. Non-orthogonal room corners not tested in integration
2. Live Revit integration test requires manual execution
3. auto_column plan requires revision per Codex findings before next phase

---

## Checklist

- [x] Build PASS
- [x] Unit tests PASS
- [x] QA PASS
- [x] No source code modifications outside TASK_SCOPE
- [ ] Live Revit manual test (pending human verification)
- [ ] Codex review PASS for HoanThien code phase (this was plan review for auto_column)
- [ ] Human review sign-off

## Do NOT merge until

Human reviewer confirms live Revit load test passes.
