# AGENTS.md — RevitAddinSolution

## Project Overview

**Project:** RevitAddinSolution — Revit Addin tự động hóa vẽ cột, dầm, vách, xuất dữ liệu BIM.  
**Stack:** C# .NET Framework 4.8, Revit API 2024/2025, Visual Studio 2022.  
**MCP tích hợp:** rvt-mcp, zfenix-revit.  
**Source code:** `source-code/` (mirror từ `e:\Antigravity\RevitAddinSolution`)

## Build / Test / Lint

- Build: `msbuild source-code\RevitAddinSolution.sln /p:Configuration=Release`
- Test: `dotnet test source-code\RevitAddinSolution.Tests\` (nếu có)
- Lint: Visual Studio Code Analysis hoặc Roslyn Analyzer

## General Rules

- Không sửa file ngoài phạm vi phase hiện tại.
- Không xóa code cũ khi chưa có lý do rõ ràng.
- Không push trực tiếp lên main/master.
- Không báo "done" nếu chưa build thành công.
- Mọi thay đổi phải ánh xạ tới acceptance criteria trong `.agent/context/ACCEPTANCE_CRITERIA.md`.
- Khi dùng Revit API: tham chiếu đúng phiên bản DLL trong `source-code/References/`.

## Definition of Done

- [ ] Build Release thành công.
- [ ] Addin load được trong Revit (kiểm tra thủ công qua External Command).
- [ ] QA_REPORT.md trả PASS.
- [ ] CODEX_REVIEW.md trả PASS.
- [ ] FINAL_REPORT.md đã được tạo.
- [ ] Human review đồng ý trước khi commit.
