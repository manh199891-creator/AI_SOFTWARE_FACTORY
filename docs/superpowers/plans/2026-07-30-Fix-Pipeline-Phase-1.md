# Phase 1 Report: STATE_DESYNC Fixes

## 1. Các lỗi đã khắc phục
- Viết lại `reconcile_state.py` để sử dụng `argparse` cho `--project-root` thay vì hard-code đường dẫn.
- `reconcile_state.py` giờ đây đọc đủ 3 nguồn (pipeline_status.json, workflow_state.json, review_run.json) để xác định xem có mâu thuẫn (`conflict`) trạng thái không (thay vì buộc chuyển về `STATE_DESYNC` một cách vô cớ).
- Nếu mâu thuẫn, trạng thái sẽ được cập nhật thành `STATE_DESYNC`, thêm 1 lịch sử với mã `STATE_SOURCES_CONFLICT`, `terminal: true` và `ready_for_codex: false`.
- Thay vì sửa `harness.py` (điều bị cấm), tôi đã sửa function `preflight_integrity` trong `runtime_integrity.py`. Nếu file `pipeline_status.json` đã là `terminal: true` và có status là `STATE_DESYNC`, `preflight_integrity` sẽ tung `IntegrityError` với mã `STATE_DESYNC_TERMINAL`. Lỗi này sẽ được catch bởi `harness.py` (bởi `enforce_runtime_integrity` -> `preflight_integrity`) và in ra mã lỗi ngăn chạy subprocess hay cập nhật sang `RUNNING`. Điều này chặn triệt để resume logic mà không đụng chạm một dòng nào trong `harness.py`.

## 2. Kết quả Test
- File: `tests/test_state_reconciliation.py`
- Test cases đã phủ:
  1. `test_three_sources_conflict`: Mô phỏng mâu thuẫn, mong đợi `STATE_DESYNC`
  2. `test_three_sources_consistent`: Mô phỏng bình thường, mong đợi không đổi trạng thái
  3. `test_idempotency`: Gọi nhiều lần hàm khắc phục, trạng thái vẫn không sinh lỗi và chỉ nối thêm lịch sử 1 lần.
  4. `test_resume_blocked_by_terminal`: Gọi trực tiếp logic resume (thông qua `preflight_integrity`) để chứng minh nó từ chối task đang có terminal = True và ném đúng lỗi `STATE_DESYNC_TERMINAL` mà chưa khởi tạo bất cứ subprocess nào.
- 4/4 Test pass (100%).

## 3. Request
Tôi đã hoàn tất Phase 1. Vui lòng duyệt qua report, mã nguồn đã sửa đổi.
Nếu mọi thứ đạt chuẩn Phase 1 Acceptance, hãy tạo file `PHASE_1_APPROVED.json` để tôi tiếp tục triển khai Phase 2.
