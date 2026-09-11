# SOURCE OF TRUTH & TASK TRACKER: TINH CHỈNH TÍNH NĂNG LÕI COGNITIVE BRAIN VAULT

## 1. Bối Cảnh Dự Án (Context)
Dự án **FB Repo Harvester / Autonomous Cognitive Brain Vault v3.0** (REPOCraw) là hệ thống thu thập, thẩm định tri thức công nghệ đa kênh (Facebook, GitHub, HackerNews, YouTube, Web), bóc tách cạm bẫy thực chiến (Gotchas), quản trị kho tri thức tuyển chọn (Curation Inbox), hợp nhất nơ-ron ngữ nghĩa và cung cấp cổng MCP cho các AI Coding Agent.

## 2. Nguyên Tắc & Lời Dặn Của Người Dùng
- **Xếp các vấn đề stress test và bảo mật ra sau**, tập trung cao độ vào **tính hợp lý, độ hữu dụng thực tế và trải nghiệm người dùng/Agent** của các tính năng cốt lõi.
- **Quy trình bắt buộc:** Tuân thủ quy chuẩn kiểm chứng ngầm bằng test-case (Hidden Verification), phản hồi ngắn gọn, không kết luận cảm tính.
- **Loại bỏ tính năng thừa/gimmick**, giải quyết dứt điểm các điểm nghẽn gây khó chịu (friction) trong luồng nghiệp vụ hàng ngày.

## 3. Bảng Tiến Độ Công Việc (Checklist)

### Giai Đoạn 1: Sửa Lỗi Nghiệp Vụ Trích Xuất & Cú Pháp Kiến Trúc
- [x] Sửa lỗi trích xuất YouTube: Đổi key yt_data.get(raw_transcript) thành yt_data.get(transcript) trong context_scout.py.
- [x] Sửa thuật toán làm sạch sơ đồ Mermaid trong consolidation.py: Chuẩn hóa trực tiếp 
ode_id[[Tên]] và 
ode_id[Tên] thành 
ode_id[Tên] qua negative lookbehind (?<![a-zA-Z0-9_\-])\[\[(.*?)\]\].
- [x] Sửa lỗi Scout Daemon: Lấy chuẩn data.get(content) và chuẩn hóa thứ tự tham số ot.send_message(text=..., chat_id=...), bổ sung sinh vector embedding.

### Giai Đoạn 2: Tối Ưu Hóa & Bất Đồng Bộ Hóa Curation Workflow
- [x] Bất đồng bộ hóa Web API /api/v1/vault/{id}/curate: Chuyển consolidate_item sang BackgroundTasks, phản hồi < 50ms.
- [x] Cập nhật Optimistic UI trong pp.js: Khi bấm Duyệt Vào Não hoặc Loại Bỏ, card fade out ngay lập tức kèm toast, không treo UI 30-60s.

### Giai Đoạn 3: Nâng Cấp Giao Diện Đọc Bài (Smart Reader UX) & Bộ Lọc
- [x] Chuyển Drawer từ 5 Tabs phân mảnh sang **Continuous Single-Page Scroll** liền mạch.
- [x] Tích hợp thanh Mục lục / Quick-Jump bám bên cạnh điều hướng nhanh (Đầu Trang -> Hồ Sơ Kỹ Sư -> Bản Đọc Sâu -> Nơ-ron Não Bộ).
- [x] Sửa contract bộ lọc: data-arch trong index.html khớp CONCEPT_THOUGHT & TECH_DEEPDIVE. Sửa lọc sao is_starred=1.
- [x] Ẩn nút Mạng Lưới Toàn Cảnh trên Header, thay bằng nút Xuất Rules.
- [x] Tích hợp DOMPurify ngăn ngừa triệt để nguy cơ XSS Injection.

### Giai Đoạn 4: Tính Năng Mới - 1-Click Export Workspace Rules
- [x] Tạo endpoint backend: GET /api/v1/brain/export-rules?topic=...&format=gemini|cursorrules xuất các Heuristics thành file chuẩn markdown GEMINI.md hoặc .cursorrules.
- [x] Thêm modal và nút bấm trực quan trên Web UI để tải về hoặc copy 1-chạm vào clipboard.

### Giai Đoạn 5: Kiểm Thử Thực Nghiệm Toàn Diện
- [x] Viết test-cases kiểm chứng cho export-rules, async curate, YouTube transcript, Mermaid sanitizer.
- [x] Đảm bảo 100% test-cases pass (	ests/test_vault_system.py) - 43/43 tests OK.
