# PHASES.md — Antigravity.HoanThien
_Generated: 2026-07-08_

---

## Phase 1 — Project Scaffold
**Priority:** 1 (blocking all)
**Scope:**
- Tạo `Antigravity.HoanThien.csproj` (.NET 8, target Revit 2025+)
- Reference: `Antigravity.Core`, RevitAPI.dll, RevitAPIUI.dll (Copy Local = False)
- Add project vào `Antigravity.sln`
- Tạo folder tree: Models/, Services/, UI/

**Deliverable:** `dotnet build Antigravity.HoanThien.csproj` thành công (0 errors)

---

## Phase 2 — Models & Enums
**Priority:** 2
**Scope:**
- `FinishType.cs` — enum: Trat, Op, Son, SanLat
- `FinishLayerConfig.cs` — thickness (mm), heightOffsetMm, wallTypeName, floorTypeName, isEnabled
- `FinishLayerData.cs` — DTO: RoomId, FinishType, List<Curve> boundaryCurves, levelId
- `FinishResult.cs` — int Created, int Skipped, List<string> Errors

**Deliverable:** 4 model files compile, unit test `FinishLayerConfig_DefaultValues` passes

---

## Phase 3 — FinishTypeManager
**Priority:** 3
**Scope:**
- `GetOrCreateWallType(doc, typeName, thicknessMm, materialFunction)` — lookup by name, duplicate if missing, set CompoundStructure thickness
- `GetOrCreateFloorType(doc, typeName, thicknessMm)` — tương tự
- Reuse pattern từ `RevitWallBuilder.GetOrCreateWallType()` (đã verify hoạt động)
- Phải chạy inside Transaction

**Deliverable:** Manual Revit test: WallType "AG_TRAT_15mm" tồn tại sau lần chạy đầu; lần 2 reuse không duplicate

---

## Phase 4 — HeightCalculator
**Priority:** 3 (parallel với P3)
**Scope:**
- `GetFinishHeight(room, heightOffsetAboveCeilingMm)` → double (feet)
- `ceiling_finish_elevation = ROOM_UPPER_OFFSET + upperLevel.Elevation`
- Convert mm offset → feet, cộng vào ceiling elevation
- Guard: nếu room.UpperLimit == null → throw InvalidOperationException

**Deliverable:** Unit test `HeightCalculator_RectRoom_ReturnsCorrectFeet` passes (mock Room với known params)

---

## Phase 5 — RoomBoundaryService
**Priority:** 4
**Scope:**
- `GetBoundarySegments(room)` → `List<List<BoundarySegment>>`
- Dùng `SpatialElementBoundaryOptions` với `SpatialElementBoundaryLocation.Finish`
- Filter out linked-model segments (LinkElementId != ElementId.InvalidElementId)
- Convert segments → `List<Curve>`

**Deliverable:** Manual test phòng hình chữ nhật 4m×3m → 4 curves đúng length

---

## Phase 6 — OpeningHandler (HIGH RISK)
**Priority:** 5 (phải xong trước P7)
**Scope:**
- `GetInsertCurves(wall, doc)` → List<(Curve cutCurve, double halfWidth)>
- Dùng `wall.FindInserts(true, false, true, true)` để lấy doors/windows
- Với mỗi insert: lấy bounding box trên face của wall → tính start/end point trên wall centerline
- `SplitCurveAroundOpening(wallCurve, insertCurves)` → List<Curve> (curves bỏ qua vùng insert)
- **Prototype first:** test trên 1 wall với 1 door trước khi generalize

**Deliverable:**
- Prototype test file: wall 5m + 1 door 0.9m → output 2 curves (left + right of door)
- Unit test `OpeningHandler_SingleDoor_Returns2Curves` passes

---

## Phase 7 — FinishWallBuilder
**Priority:** 6 (sau P3, P4, P5, P6)
**Scope:**
- `BuildFinishWall(doc, roomCurve, finishConfig, roomLevel, finishHeight)` → Wall
- `Wall.Create(doc, line, wallTypeId, levelId, heightFeet, offsetFeet, flip, structural)`
- `structural = false`, `flip = false` (thin finish wall)
- Sau tạo: set WALL_TOP_CONSTRAINT = Unconnected, WALL_USER_HEIGHT_PARAM = finishHeight
- Guard: `line.Length < 0.01` (feet) → skip (tránh degenerate wall)
- Không join geometry với walls kế cận (JoinGeometryUtils.UnjoinGeometry nếu cần)

**Deliverable:** Manual test: phòng 4m×3m tạo được 4 finish walls AG_TRAT_15mm đúng vị trí

---

## Phase 8 — FinishFloorBuilder
**Priority:** 6 (parallel với P7)
**Scope:**
- `BuildFinishFloor(doc, room, finishConfig, level)` → Floor
- Extract room boundary → CurveLoop
- `Floor.Create(doc, new List<CurveLoop>{loop}, floorTypeId, levelId)`
- Set `FLOOR_HEIGHTABOVELEVEL_PARAM` = -thicknessMm/304.8 (âm = dưới level)
- Reuse pattern từ `RevitFloorBuilder.CreateFloor()`

**Deliverable:** Manual test: tạo được 1 finish floor AG_SAN_LAT_20mm trong phòng test

---

## Phase 9 — Shared Parameters
**Priority:** 7
**Scope:**
- Tạo/bind shared params: `AG_FinishType` (Text, Instance, Walls+Floors), `AG_RoomNumber` (Text), `AG_RoomName` (Text)
- Dùng `SharedParameterElement` API hoặc `.txt` shared param file
- Set values sau khi tạo wall/floor: AG_FinishType = "Trat"/"Op"/"Son"/"SanLat"
- **Duplicate detection:** trước khi tạo, query `FilteredElementCollector` tìm elements có AG_FinishType + room id → skip nếu tồn tại

**Deliverable:** Schedule "AG Finish Walls" group by AG_FinishType hiển thị đúng counts

---

## Phase 10 — HoanThienHandler (IExternalEventHandler)
**Priority:** 8
**Scope:**
- `HoanThienHandler : IExternalEventHandler`
- Properties: `FinishLayerConfig[] Configs`, `List<ElementId> RoomIds`
- Execute: mở Transaction "Đặt lớp hoàn thiện", gọi services theo thứ tự, commit, hiện FinishResult
- Error handling: per-room try-catch, log warning, tiếp tục
- Gọi `AreaVolumeSettings` guard tại đầu Execute

**Deliverable:** Chạy handler trên 1 phòng test → transaction commit, log hiện kết quả

---

## Phase 11 — UI (WPF)
**Priority:** 9
**Scope:**
- `HoanThienWindow.xaml` — DataGrid 4 rows (Trát/Ốp/Sơn/Sàn Lát), columns: WallType dropdown, Thickness NumericBox, Apply checkbox
- `HoanThienViewModel.cs` — ObservableCollection<FinishLayerConfig>, HeightOffset property, ApplyCommand
- `HeightOffset` input: default 50mm
- "Áp dụng tất cả phòng trong View" button → raise ExternalEvent
- WPF binding: INotifyPropertyChanged, RelayCommand

**Deliverable:** Window mở được từ ribbon, binding hoạt động (Thickness hiện đúng giá trị)

---

## Phase 12 — HoanThienCommand
**Priority:** 10
**Scope:**
- `HoanThienCommand : IExternalCommand`
- Execute: tạo ExternalEvent + HoanThienHandler, mở HoanThienWindow, trả Result.Succeeded
- Wrap trong try-catch, log error nếu fail

**Deliverable:** Command execute không throw, window mở

---

## Phase 13 — Ribbon Registration
**Priority:** 11
**Scope:**
- Thêm PushButton "Hoàn Thiện" trong `Antigravity.Main/App.cs`
- Cùng panel với DrawWalls / DrawFloors (hoặc panel riêng "Hoàn Thiện")
- Icon: dùng existing 32x32 PNG pattern từ Antigravity.Main/Resources

**Deliverable:** Revit ribbon hiện button "Hoàn Thiện", click mở window

---

## Phase 14 — xUnit Test Project
**Priority:** 7 (parallel với P9)
**Scope:**
- `Antigravity.HoanThien.Tests.csproj` tại `source-code/tests/`
- Test `HeightCalculator` — pure logic, no Revit API
- Test `FinishLayerConfig` — default values, validation
- Test `OpeningHandler.SplitCurveAroundOpening` — geometry logic
- Test `FinishResult` — aggregation counts
- Mock: dùng Moq nếu cần abstract interfaces

**Deliverable:** `dotnet test` → all tests pass, 0 failures

---

## Phase 15 — Integration Guard + Smoke Test
**Priority:** 12
**Scope:**
- Kiểm tra `VolumeCalculationSetting` guard hoạt động đúng (mock doc trả false → user message)
- Smoke test manual trong Revit: chạy full flow trên model có 1 phòng hình chữ nhật
- Verify: 4 finish walls + 1 finish floor tạo đúng, params set đúng, không duplicate khi chạy lần 2

**Deliverable:** Smoke test pass, tất cả AC trong ACCEPTANCE_CRITERIA.md đạt PASS
