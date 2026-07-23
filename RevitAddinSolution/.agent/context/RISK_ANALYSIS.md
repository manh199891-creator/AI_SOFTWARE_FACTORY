# RISK_ANALYSIS.md — Antigravity.HoanThien
_Generated: 2026-07-08_

## Risk Matrix

| ID | Risk | Likelihood | Impact | Level | Phase |
|----|------|-----------|--------|-------|-------|
| R1 | OpeningHandler geometry failure | High | High | 🔴 HIGH | P6 |
| R2 | Sơn 2mm minimum thickness rejected by Revit | High | High | 🔴 HIGH | P3, P7 |
| R3 | VolumeCalculationSetting not enabled → no room boundary | High | High | 🔴 HIGH | P10 |
| R4 | Corner geometry join artifacts | Medium | Medium | 🟡 MEDIUM | P7 |
| R5 | Double-run duplicate elements | Medium | High | 🟡 MEDIUM | P9 |
| R6 | Shared parameter file conflict | Low | Medium | 🟢 LOW | P9 |
| R7 | WPF window crash on Revit thread | Low | Medium | 🟢 LOW | P11 |
| R8 | FloorType CompoundStructure thin layer rejected | Medium | Medium | 🟡 MEDIUM | P3, P8 |

---

## R1 — OpeningHandler: Door/Window Gap
**Severity:** 🔴 HIGH
**Root cause:** `wall.FindInserts()` trả về host element IDs (doors/windows), nhưng mapping từ insert element id → wall face cut geometry phức tạp. BoundingBox của insert không align với wall curve khi wall không thẳng hoặc khi insert nằm sát góc.

**Failure modes:**
1. Finish wall tạo đè lên cửa → không valid về mặt kiến trúc
2. `SplitCurveAroundOpening` tính sai offset → curve degenerate (length < 0.001 ft) → Wall.Create exception
3. Insert bounding box không overlap wall curve → incorrect split points

**Mitigation strategy:**
1. **Prototype first** (P6 bắt buộc trước P7): Test isolated `OpeningHandler` trên 1 wall + 1 door trong Revit debug session
2. **Algorithm:** Dùng `wall.Location as LocationCurve` để project bounding box corners lên wall axis → tính 1D intervals → subtract → tạo remaining curves
3. **Guard:** `if (splitCurve.Length < 0.05)` (feet ~15mm) → skip, log warning
4. **Fallback:** Nếu FindInserts fails → tạo finish wall full length (không cắt cửa), log warning "Opening handling skipped"
5. **Unit test:** Mock curve + door interval, verify output segments

---

## R2 — Sơn 2mm: Minimum Wall Thickness
**Severity:** 🔴 HIGH
**Root cause:** Revit có minimum wall thickness constraint (~10mm trong nhiều version). Sơn 2mm (0.00656 ft) có thể bị Revit API reject với exception "The wall is too thin" hoặc silently fail tạo wall rỗng.

**Failure modes:**
1. `Wall.Create` throw `Autodesk.Revit.Exceptions.ArgumentException` với message về thickness
2. Wall tạo được nhưng CompoundStructure không set được layer 2mm → actual thickness = 0
3. Model warnings về wall too thin ngay sau khi tạo

**Mitigation strategy:**
1. **Verify sớm (P3):** Tạo prototype WallType AG_SON_2mm trong Revit manually → check xem Revit accept không. Nếu Revit 2025 reject, minimum = 5mm → update spec
2. **API check:** Wrap `Wall.Create` cho Sơn trong try-catch riêng, log warning + skip nếu fail thay vì crash toàn bộ transaction
3. **Config safety:** FinishLayerConfig.Thickness có `MinimumThicknessMm = 2.0` const — nếu Revit reject thì nâng lên 5.0 trong config mà không cần sửa logic
4. **Alternative approach:** Nếu 2mm hoàn toàn không được, sử dụng Paint Face (`doc.Paint()`) thay vì Wall.Create cho loại Sơn — nhưng không schedulable. Ghi nhận trade-off trong ADR

---

## R3 — VolumeCalculationSetting Chưa Bật
**Severity:** 🔴 HIGH
**Root cause:** `room.GetBoundarySegments()` trả về empty list nếu `AreaVolumeSettings.ComputeVolumes = false`. Không có error thrown — chỉ trả về null/empty → tạo 0 finish elements mà không có cảnh báo rõ ràng.

**Failure modes:**
1. `GetBoundarySegments()` trả empty → 0 walls tạo, user không biết tại sao
2. Loop qua empty list → FinishResult.Created = 0, Skipped = 0 → misleading result
3. Nếu không guard, user nghĩ tool broken → trust issue

**Mitigation strategy:**
1. **Entry guard tại P10 (HoanThienHandler.Execute):**
```csharp
var avSettings = AreaVolumeSettings.GetAreaVolumeSettings(doc);
if (!avSettings.ComputeVolumes)
{
    TaskDialog.Show("Antigravity.HoanThien",
        "Room Volume Calculation chưa được bật.\n\n" +
        "Vào Architecture → Room & Area → Area and Volume Computations\n" +
        "→ chọn 'Areas and Volumes'.");
    return; // Không tạo transaction
}
```
2. **Second check:** Sau khi lấy boundary segments, nếu count = 0 → log + TaskDialog "Room không có boundary segments"
3. **Unit test:** Mock `AreaVolumeSettings` → verify guard throws/returns early

---

## R4 — Corner Geometry Joins
**Severity:** 🟡 MEDIUM
**Root cause:** Khi 4 finish walls tạo theo room boundary, các góc tường có thể tự động join geometry theo kiểu không mong muốn (miter joint / butt joint tùy Revit). Dẫn đến corner gaps hoặc overlapping.

**Failure modes:**
1. Revit auto-join tạo ra gap tại góc → schedule area/volume sai
2. Finish wall join với structural wall → cannot unjoin → model corruption

**Mitigation strategy:**
1. **Disable join after create:** Sau `Wall.Create`, gọi `WallUtils.DisallowWallJoinAtEnd(wall, 0)` và `DisallowWallJoinAtEnd(wall, 1)` cho cả 2 đầu finish wall
2. **Không join với host wall:** Dùng `JoinGeometryUtils.UnjoinGeometry(doc, finishWall, hostWall)` nếu auto-join xảy ra
3. **Test:** Verify corner không có gap > 1mm sau khi tạo 4 walls

---

## R5 — Double-Run Duplicate Detection
**Severity:** 🟡 MEDIUM
**Root cause:** Nếu user chạy HoanThienCommand 2 lần trên cùng view, existing finish elements sẽ bị override/duplicate nếu không có guard.

**Failure modes:**
1. Duplicate finish walls + floors → schedule counts sai gấp đôi
2. Transaction error nếu 2 walls cùng curve/location → Revit model warning
3. User không nhận ra đã chạy → model bloated

**Mitigation strategy:**
1. **Pre-run query (P9):** Trước khi tạo, dùng `FilteredElementCollector` tìm Walls/Floors có param `AG_FinishType` + `AG_RoomNumber` match với room đang xử lý
2. **Logic:** `if (existingElements.Any(e => e.RoomNumber == room.Number && e.FinishType == type)) → skip`
3. **Report:** FinishResult.Skipped++ cho mỗi element bị skip → hiện trong TaskDialog
4. **Override mode (future):** Config flag `OverwriteExisting = true` để allow replace — không implement ở v1

---

## R6 — Shared Parameter File Conflict
**Severity:** 🟢 LOW
**Root cause:** Project có thể đã có shared parameter file khác. Thêm AG_* params vào wrong group hoặc duplicate GUID.

**Mitigation strategy:**
1. Check existing shared params trước: `doc.ParameterBindings` + `SharedParameterElement` lookup by GUID
2. Dùng fixed GUID constants trong code (hardcoded per AG standard)
3. Nếu param đã tồn tại với đúng GUID → reuse, không tạo mới

---

## R7 — WPF Window on Revit Thread
**Severity:** 🟢 LOW
**Root cause:** WPF window phải được tạo trên STA thread. Revit main thread là STA, nhưng nếu ExternalEvent raise timing sai có thể dẫn đến cross-thread exception.

**Mitigation strategy:**
1. Follow pattern từ `WallCreationHandler` (đã stable): `window.ShowDialog()` trong `IExternalCommand.Execute`
2. Tất cả Revit API calls trong `HoanThienHandler.Execute` (IExternalEventHandler) — không trong ViewModel
3. ViewModel chỉ chứa pure C# data, không reference Revit API

---

## R8 — FloorType Thin Layer
**Severity:** 🟡 MEDIUM
**Root cause:** FloorType AG_SAN_LAT_20mm cần CompoundStructure với 1 layer Finish1 20mm. Nếu Revit không cho phép FloorType với layer quá mỏng, `Floor.Create` sẽ fail.

**Mitigation strategy:**
1. Verify FloorType creation manually trước (tương tự R2)
2. `FinishFloorBuilder` wrap try-catch, log error per floor thay vì crash transaction
3. Minimum floor thickness = 10mm per spec → nếu Revit reject 10mm, nâng lên 15mm

---

## Risk Timeline

```
Phase 3  → Verify R2 (Son 2mm prototype)
Phase 5  → Verify R3 (VolumeCalc guard)
Phase 6  → Verify R1 (OpeningHandler prototype) ← CRITICAL PATH
Phase 7  → Verify R4 (corner joins)
Phase 9  → Implement R5 (duplicate detection)
Phase 14 → xUnit tests cover R1, R2, R3, R5
Phase 15 → Smoke test all risks cleared
```

**No-Go condition:** R1 hoặc R2 không có acceptable workaround → escalate, update spec trước khi tiếp tục P7.
