# RELEASE NOTES
**Feature:** Antigravity.HoanThien — Tu dong tao tuong hoan thien & san hoan thien tu phong
**Date:** 2026-07-21
**Pipeline task_id:** auto_foundation_cleanup_fix (code phase)
**Build:** PASS | **QA:** PASS (11/11 AC) | **Codex review (plan gate for auto_column):** FAIL

---

## Tinh nang moi

### Antigravity.HoanThien module

| Component | Mo ta |
|-----------|-------|
| HoanThienHandler | ExternalEventHandler dieu phoi toan bo luong tao tuong/san hoan thien |
| RoomBoundaryService | Trich xuat boundary canh phong, tich hop OpeningHandler.SplitCurveAroundOpening |
| FinishWallBuilder | Tao tuong hoan thien, gan AG_FinishType, AG_RoomNumber, AG_RoomName |
| FinishFloorBuilder | Tao san hoan thien, thiet lap FLOOR_HEIGHTABOVELEVEL_PARAM (gia tri am) + Shared Params |
| FinishTypeManager | GetOrCreateWallType - tai su dung type cu hoac tao moi, khong duplicate |
| HeightCalculator | Tinh chieu cao tuong hoan thien theo thong so phong |
| OpeningHandler | Ngat curve tai vi tri cua/lo mo |

### Bao ve & kiem tra

| Logic | Chi tiet |
|-------|----------|
| Duplicate guard | FilteredElementCollector ket hop AG_RoomNumber + AG_FinishType chan tao trung |
| ComputeVolumes guard | Kiem tra ComputeVolumes bat truoc khi thuc thi; tra Result.Failed neu tat |
| Transaction rollback | Toan bo wrapped trong single Transaction, rollback khi exception |

---

## Fixes ap dung trong release nay

| Fix | Van de goc | Trang thai |
|-----|-----------|-----------|
| Fix 1 | RoomBoundaryService thieu SplitCurveAroundOpening tai cua | PASS |
| Fix 2 | HoanThienHandler khong chan duplicate elements | PASS |
| Fix 3 | FinishWallBuilder thieu gan Shared Parameters | PASS |
| Fix 4 | FinishFloorBuilder sai FLOOR_HEIGHTABOVELEVEL_PARAM | PASS |
| Fix 5 | Thieu ComputeVolumes guard | PASS |

---

## Test Coverage

- 6/6 xUnit tests PASS
- AC-01 den AC-11 PASS (11/11 acceptance criteria)
- Integration test tren Revit live: can kiem tra thu cong

---

## Gioi han con lai

1. Codex review (plan gate) FAIL - 4 P1 + 2 P2 findings thuoc ve task auto_column (feature moi), KHONG phai HoanThien
2. Integration test chua chay tren Revit thuc
3. Tuong hoan thien tai goc phong phuc tap (non-orthogonal) chua duoc test

---

## Deployment

- Build: Release
- Target: Revit 2024 / 2025
- Deploy path: src\Antigravity.Main\App.cs ribbon registration

KHONG commit, KHONG push len main - cho human review.
