# AGENTS.md

## Project Overview

**Project:** TrendingUpdate — Bot tự động quét và tổng hợp tin tức xu hướng.  
**Stack:** Python 3.12, SQLite (FTS5), Telegram Bot API.  
**Source code:** `source-code/` (mirror từ `e:\Antigravity\TrendingUpdate`)

## Build / Test / Lint

- Run bot: `python source-code/scan_news.py`
- Test: `python -m pytest source-code/tests/ -v` (nếu có)
- Lint: `python -m flake8 source-code/ --max-line-length=120`

## General Rules

- Không sửa file ngoài phạm vi phase hiện tại.
- Không xóa code cũ khi chưa có lý do rõ ràng.
- Không push trực tiếp lên main/master.
- Không báo "done" nếu chưa chạy build/test thành công.
- Mọi thay đổi phải ánh xạ tới acceptance criteria trong file `.agent/context/ACCEPTANCE_CRITERIA.md`.

## Definition of Done

Một task chỉ hoàn tất khi:
- [ ] Build / run không lỗi.
- [ ] Tests pass (nếu có).
- [ ] Lint pass.
- [ ] QA_REPORT.md trả PASS.
- [ ] CODEX_REVIEW.md trả PASS.
- [ ] FINAL_REPORT.md đã được tạo.
- [ ] Human review đồng ý trước khi commit.
