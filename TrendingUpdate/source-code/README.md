# BIM-AI Academic News Auto-Scanner

Hệ thống tự động tìm kiếm, dịch thuật và tóm tắt các bài báo khoa học Q1/Q2 mới nhất về lĩnh vực **BIM & Trí tuệ nhân tạo (AI)** từ các nguồn uy tín (Semantic Scholar, arXiv) sử dụng **Ollama** cục bộ.

## 🛠️ Hướng dẫn thiết lập & Sử dụng nhanh

### Bước 1: Khởi động Ollama (Nếu muốn dịch/tóm tắt bằng AI)
1. Đảm bảo bạn đã cài đặt và khởi động Ollama trên máy tính.
2. Tải về model mặc định là `llama3` (hoặc bạn có thể sửa model trong file `scan_news.py` thành model bạn đang có như `qwen2.5`, `mistral`...):
   ```bash
   ollama run llama3
   ```
*(Lưu ý: Nếu Ollama không chạy, công cụ vẫn hoạt động bình thường nhưng sẽ lấy tóm tắt tiếng Anh gốc thay vì dịch bằng AI).*

### Bước 2: Chạy kiểm tra thủ công (Manual Run)
1. Mở PowerShell trong thư mục này.
2. Chạy file script PowerShell bằng lệnh sau:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\run.ps1
   ```
   *Script sẽ tự động:*
   - Cài đặt các thư viện cần thiết (`requests`, `arxiv`...).
   - Thực hiện quét bài báo từ các nguồn.
   - Gọi Ollama dịch/tóm tắt sang tiếng Việt.
   - Xuất file báo cáo dạng Markdown vào thư mục `newsletters/`.
   - Tự động mở file báo cáo mới nhất cho bạn đọc.

---

## ⏰ Hướng dẫn cài đặt tự động hàng tuần (Scheduled Task)

Để hệ thống tự chạy ngầm vào **9:00 sáng Thứ Hai hàng tuần**:

1. Click chuột phải vào nút Start của Windows, chọn **Terminal (Admin)** hoặc **PowerShell (Admin)**.
2. Di chuyển đến thư mục này:
   ```powershell
   cd "E:\Antigravity\TrendingUpdate"
   ```
3. Chạy script cấu hình tác vụ tự động:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup_task.ps1
   ```

### Cách kiểm tra hoặc xóa tác vụ tự động:
- **Kiểm tra:** Nhấn `Windows + R`, gõ `taskschd.msc` để mở **Task Scheduler**. Tìm tác vụ tên là `BIM-AI_Academic_Scanner`.
- **Chạy thử ngay:** Click chuột phải vào tác vụ đó trong Task Scheduler -> Chọn `Run`.
- **Xóa:** Click chuột phải vào tác vụ đó -> Chọn `Delete`.
