# SCOPE EXCEPTION REQUEST

- **Requested file**: `runtime_integrity.py`
- **Reason**: Cần chặn logic resume đối với trạng thái `STATE_DESYNC` terminal ngay lập tức mà không để state cập nhật thành `RUNNING` hay gọi bất cứ subprocess nào. Phase 1 cấm sửa đổi `harness.py`, nên `preflight_integrity()` trong `runtime_integrity.py` (được gọi ở những dòng đầu tiên của hàm `cmd_dual` trong `harness.py`) là vị trí nhỏ nhất, an toàn nhất để ngắt execution qua một `IntegrityError` (với mã `STATE_DESYNC_TERMINAL`).
- **Minimal change**: Thêm 5 dòng code vào `preflight_integrity` đọc trực tiếp file `pipeline_status.json` để phát hiện terminal, nếu đúng ném `IntegrityError("STATE_DESYNC_TERMINAL", ...)`
- **Alternatives considered**: Sửa trong `convergence_pipeline.py` (tuy nhiên logic này lại chạy sau khi `harness.py` đã đổi state sang `RUNNING`), sửa trong `harness.py` (bị cấm theo checklist Phase 1).
- **Regression risk**: Rất thấp. Logic chỉ can thiệp và ném lỗi duy nhất khi pipeline thực sự ở trạng thái terminal = True. Khi ở trạng thái bình thường, code đi qua tiếp như cũ. 
- **Tests**: `test_resume_blocked_by_terminal` trong `test_state_reconciliation.py` đã xác nhận hệ thống throw chính xác lỗi `STATE_DESYNC_TERMINAL` thông qua `preflight_integrity` và thoát trước khi spawn bất cứ sub-process nào.
