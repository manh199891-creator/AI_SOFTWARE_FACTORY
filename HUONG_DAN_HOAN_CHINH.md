# AI Software Factory — Hướng Dẫn Hoàn Chỉnh

---

## PHẦN 1 — CÀI ĐẶT (Làm 1 lần duy nhất)

### ✅ Đã hoàn thành
- [x] Hermes Agent cài xong (`C:\Users\Admin\AppData\Local\hermes\`)
- [x] Codex CLI cài xong (`codex-cli 0.142.2`)
- [x] Cấu trúc thư mục `E:\AI_SOFTWARE_FACTORY\` tạo xong với 3 project:
  - `TrendingUpdate\`
  - `RevitAddinSolution\`
  - `NavisAddinSolution\`
- [x] File rule (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) tạo xong cho cả 3 project
- [x] `workflow_state.json`, `watch_codex.py`, `CONVERSATION_PROMPTS.md` tạo xong

---

## PHẦN 2 — CHUẨN BỊ MỖI PROJECT (Làm 1 lần/project)

### Bước 2.1 — Copy Source Code vào Factory

Mở PowerShell, chạy lệnh tương ứng:

```powershell
# TrendingUpdate
xcopy /E /I /Y "e:\Antigravity\TrendingUpdate\*" "E:\AI_SOFTWARE_FACTORY\TrendingUpdate\source-code\"

# RevitAddinSolution
xcopy /E /I /Y "e:\Antigravity\RevitAddinSolution\*" "E:\AI_SOFTWARE_FACTORY\RevitAddinSolution\source-code\"

# NavisAddinSolution
xcopy /E /I /Y "e:\Antigravity\NavisAddinSolution\*" "E:\AI_SOFTWARE_FACTORY\NavisAddinSolution\source-code\"
```

> ⚠️ Mỗi khi source code gốc có thay đổi lớn, chạy lại lệnh xcopy để đồng bộ.

---

## PHẦN 3 — VẬN HÀNH MỖI TASK (Lặp lại cho mỗi tính năng/bugfix mới)

### Bước 3.0 — Điền Yêu Cầu

Mở file `PROJECT_CONTEXT.md` của project muốn làm:

```
E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PROJECT_CONTEXT.md
```

Điền vào mục **"Yêu cầu hiện tại"**, ví dụ:
```
Tích hợp Hermes Cron thay thế Windows Task Scheduler.
Yêu cầu: scan_news.py chạy tự động mỗi 8h sáng, gửi kết quả qua Telegram.
```

---

### Bước 3.1 — Claude Planner (Lập kế hoạch)

**Mở Antigravity → New Conversation → Chọn model: Claude Sonnet 4.6**

Paste prompt sau (thay `[PROJECT]`):

```
Bạn là Planner Agent trong AI Software Factory.

BƯỚC ĐẦU TIÊN — Đọc các file sau theo thứ tự:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\AGENTS.md
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\CLAUDE.md
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PROJECT_CONTEXT.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\source-code\ (đọc tổng quan)

NHIỆM VỤ — Tạo 4 file:
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PLAN.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PHASES.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\ACCEPTANCE_CRITERIA.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\RISK_ANALYSIS.md

QUY TẮC: KHÔNG sửa source code. Chỉ research và lập kế hoạch.
Mỗi phase phải nhỏ đủ để Gemini Implementer làm trong 1 session.

BÁO CÁO KHI XONG: Tóm tắt PLAN.md trong 5 dòng. Chờ xác nhận.
```

**Chờ Claude xong → Bạn đọc PLAN.md → OK thì tiếp bước 3.2.**

---

### Bước 3.2 — Claude Architect (Thiết kế kỹ thuật)

**Mở Antigravity → New Conversation → Chọn model: Claude Sonnet 4.6**

Paste prompt sau:

```
Bạn là Architect Agent trong AI Software Factory.

BƯỚC ĐẦU TIÊN — Đọc các file sau:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\AGENTS.md
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\CLAUDE.md
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PLAN.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PHASES.md
5. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\ACCEPTANCE_CRITERIA.md
6. E:\AI_SOFTWARE_FACTORY\[PROJECT]\source-code\

NHIỆM VỤ — Tạo 3 file:
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\ARCHITECTURE_DECISION.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\TECHNICAL_DESIGN.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\IMPACT_ANALYSIS.md

TECHNICAL_DESIGN.md phải liệt kê: file nào sửa, function nào thêm, dependency mới, rủi ro.
QUY TẮC: KHÔNG sửa source code. Nếu phát hiện rủi ro lớn → dừng và báo cáo.

BÁO CÁO KHI XONG: Tóm tắt TECHNICAL_DESIGN.md trong 5 dòng. Chờ xác nhận.
```

**Chờ Claude xong → Bạn đọc TECHNICAL_DESIGN.md → OK thì tiếp bước 3.3.**

---

### Bước 3.3 — Gemini Implementer (Viết code)

**Mở Antigravity → New Conversation → Chọn model: Gemini 3.1 Pro High**

Paste prompt sau:

```
Bạn là Implementation Agent trong AI Software Factory.

BƯỚC ĐẦU TIÊN — Đọc các file sau:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\AGENTS.md
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\GEMINI.md
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PLAN.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PHASES.md
5. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\ACCEPTANCE_CRITERIA.md
6. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\TECHNICAL_DESIGN.md

NHIỆM VỤ:
- Triển khai ĐÚNG phase hiện tại trong PHASES.md.
- Chỉ sửa file được liệt kê trong TECHNICAL_DESIGN.md.
- Chạy build/test/lint theo lệnh trong AGENTS.md.
- Ghi kết quả vào E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\IMPLEMENTATION_REPORT.md

FORMAT IMPLEMENTATION_REPORT.md:
## Phase: [tên phase]
## Files changed: [danh sách]
## Build result: PASS / FAIL
## Test result: PASS / FAIL / N/A
## Notes: [ghi chú]

QUY TẮC: KHÔNG sửa file ngoài danh sách. KHÔNG báo done khi build chưa pass.
```

---

### Bước 3.4 — Gemini QA (Kiểm thử)

**Mở Antigravity → New Conversation → Chọn model: Gemini 3.1 Pro High**

Paste prompt sau:

```
Bạn là QA Agent trong AI Software Factory.

BƯỚC ĐẦU TIÊN — Đọc các file:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\AGENTS.md
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\GEMINI.md
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\ACCEPTANCE_CRITERIA.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\IMPLEMENTATION_REPORT.md

NHIỆM VỤ — Kiểm tra:
1. Chạy build theo lệnh trong AGENTS.md
2. Chạy test (nếu có)
3. Chạy lint
4. Kiểm tra từng acceptance criteria
5. Kiểm tra edge case

Ghi kết quả vào E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\QA_REPORT.md

FORMAT:
## Status: PASS / FAIL
## Build: PASS / FAIL
## Tests: PASS / FAIL / N/A
## Lint: PASS / FAIL
## Acceptance Criteria: [từng tiêu chí: PASS/FAIL]
## Issues (nếu có): [File / Mô tả / Mức độ: Critical|Major|Minor]

QUY TẮC: Có bất kỳ issue Critical/Major → Status = FAIL.
```

**Nếu QA_REPORT = FAIL → Chạy bước 3.5. Nếu PASS → Chuyển sang bước 3.6.**

---

### Bước 3.5 — Gemini Fixer (Sửa lỗi — Chỉ chạy khi QA hoặc Codex FAIL)

**Mở Antigravity → New Conversation → Chọn model: Gemini 3.1 Pro High**

Paste prompt sau:

```
Bạn là Fix Agent trong AI Software Factory.

BƯỚC ĐẦU TIÊN — Đọc các file:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\AGENTS.md
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\GEMINI.md
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\QA_REPORT.md  ← hoặc CODEX_REVIEW.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\IMPLEMENTATION_REPORT.md

NHIỆM VỤ:
- Chỉ sửa đúng các lỗi được liệt kê trong QA_REPORT.md hoặc CODEX_REVIEW.md.
- Chạy lại build/test/lint sau khi sửa.
- Ghi kết quả vào E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\FIX_REPORT.md

FORMAT:
## Source: QA / CODEX
## Fix 1: [Lỗi gốc / File / Solution / Build sau fix: PASS|FAIL]

QUY TẮC: KHÔNG rewrite code không liên quan. Nếu vẫn FAIL → dừng, báo cáo.
```

**Sau khi Fixer xong → Quay lại bước 3.4 (QA) hoặc 3.6 (Codex) để chạy lại.**

---

### Bước 3.6 — Codex Review (Kiểm tra độc lập)

**Mở PowerShell → chạy:**

```powershell
cd E:\AI_SOFTWARE_FACTORY\[PROJECT]
codex /review
```

Codex đọc git diff và trả kết quả.

**Copy kết quả Codex → Paste vào file:**
```
E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\CODEX_REVIEW.md
```

Thêm dòng đầu tiên:
```markdown
## Status: PASS
```
hoặc:
```markdown
## Status: FAIL
```

**Nếu FAIL → Quay lại bước 3.5 (Fixer). Nếu PASS → Tiếp bước 3.7.**

---

### Bước 3.7 — Release Agent (Tổng hợp báo cáo)

**Mở Antigravity → New Conversation → Chọn model: Claude Sonnet 4.6**

Paste prompt sau:

```
Bạn là Release Agent trong AI Software Factory.

KIỂM TRA ĐIỀU KIỆN — Đọc 2 file này trước:
1. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\QA_REPORT.md    → phải có "Status: PASS"
2. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\CODEX_REVIEW.md → phải có "Status: PASS"

Nếu một trong hai chưa PASS → DỪNG và báo lại. KHÔNG tiếp tục.

NHIỆM VỤ (chỉ khi cả hai PASS) — Đọc thêm:
3. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\context\PLAN.md
4. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\IMPLEMENTATION_REPORT.md
5. E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\FIX_REPORT.md

Tạo 3 file:
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\RELEASE_NOTES.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\PR_DESCRIPTION.md
- E:\AI_SOFTWARE_FACTORY\[PROJECT]\.agent\reports\FINAL_REPORT.md

QUY TẮC: KHÔNG push lên main/master. Chờ human review.
```

---

### Bước 3.8 — Human Review & Commit (Bạn tự làm)

1. Đọc `FINAL_REPORT.md` và `PR_DESCRIPTION.md`
2. Kiểm tra code thay đổi trong `source-code/`
3. Nếu OK → Commit:

```powershell
cd E:\AI_SOFTWARE_FACTORY\[PROJECT]\source-code
git add .
git commit -m "feat: [tên tính năng theo PLAN.md]"
```

---

## PHẦN 4 — SƠ ĐỒ TỔNG THỂ

```
TASK MỚI
   │
   ▼
[Bạn] Điền PROJECT_CONTEXT.md
   │
   ▼
[Antigravity/Claude]   → Planner    → PLAN.md, PHASES.md
   │
   ▼
[Antigravity/Claude]   → Architect  → TECHNICAL_DESIGN.md
   │
   ▼
[Antigravity/Gemini]   → Implementer → code + IMPLEMENTATION_REPORT.md
   │
   ▼
[Antigravity/Gemini]   → QA          → QA_REPORT.md
   │
   ├─ FAIL ──► [Gemini Fixer] ──► quay lại QA
   │
   ▼ PASS
[PowerShell/Codex]     → codex /review → CODEX_REVIEW.md
   │
   ├─ FAIL ──► [Gemini Fixer] ──► quay lại Codex
   │
   ▼ PASS
[Antigravity/Claude]   → Release Agent → FINAL_REPORT.md
   │
   ▼
[Bạn] Review → Commit / PR
```

---

## PHẦN 5 — CHECKLIST THEO DÕI TASK

*Copy ra Notepad mỗi khi bắt đầu task mới:*

```
PROJECT: _______________
TASK: _______________
NGÀY: _______________

[ ] 3.0 Điền PROJECT_CONTEXT.md
[ ] 3.1 Claude Planner     → PLAN.md tạo xong
[ ] 3.2 Claude Architect   → TECHNICAL_DESIGN.md tạo xong
[ ] 3.3 Gemini Implementer → code xong + build PASS
[ ] 3.4 Gemini QA          → QA_REPORT.md = PASS
[ ] 3.5 Gemini Fixer       → (nếu cần)
[ ] 3.6 Codex /review      → CODEX_REVIEW.md = PASS
[ ] 3.7 Release Agent      → FINAL_REPORT.md tạo xong
[ ] 3.8 Human Review       → Commit / PR hoàn tất
```
