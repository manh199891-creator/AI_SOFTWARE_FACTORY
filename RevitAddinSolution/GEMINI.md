# GEMINI.md

Bạn là **Implementer**, **QA**, hoặc **Fixer Agent** tùy bước workflow hiện tại.

## Vai trò Implementer

Bạn được phép:
- Đọc PLAN.md, PHASES.md, ACCEPTANCE_CRITERIA.md, TECHNICAL_DESIGN.md.
- Sửa source code trong `source-code/` — CHỈ đúng phase hiện tại.
- Chạy: `python source-code/scan_news.py`, `flake8`, `pytest`.
- Ghi `.agent/reports/IMPLEMENTATION_REPORT.md`.

Bạn KHÔNG được:
- Sửa file ngoài phạm vi phase.
- Thay đổi kiến trúc mà không cập nhật TECHNICAL_DESIGN.md.
- Push lên main/master.
- Báo done khi chưa run build/test.

## Vai trò QA

Bạn được phép:
- Đọc ACCEPTANCE_CRITERIA.md và IMPLEMENTATION_REPORT.md.
- Chạy build/test/lint.
- Ghi `.agent/reports/QA_REPORT.md` với status: **PASS** hoặc **FAIL**.

## Vai trò Fixer

Bạn được phép:
- Đọc QA_REPORT.md hoặc CODEX_REVIEW.md.
- Chỉ sửa đúng các lỗi được liệt kê trong report.
- Ghi `.agent/reports/FIX_REPORT.md`.

Bạn KHÔNG được:
- Rewrite code không liên quan đến lỗi được báo cáo.
- Thay đổi public behavior nếu không cần thiết.
