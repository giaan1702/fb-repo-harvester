# PROJECT RULES & GUIDELINES (GEMINI.md)

## 1. Nguyên Tắc Cốt Lõi: Đề Xuất Giải Pháp & Xác Minh Thực Nghiệm
* **KIỂM CHỨNG NGẦM BẰNG TEST-CASE (HIDDEN VERIFICATION):** Khi đề xuất bất kỳ giải pháp kỹ thuật nào chưa kiểm chứng, Agent tự kiểm thử, benchmark hoặc rà soát qua các kịch bản test-case ở chế độ nền/suy luận để đảm bảo độ chính xác tuyệt đối.
* **PHẢN HỒI GỌN GÀNG, TIÊU CHUẨN BÌNH THƯỜNG:** Không bày biện các khối test-case, kịch bản rườm rà hay phân vai tranh luận vào câu trả lời trực tiếp trừ khi người dùng yêu cầu xem chi tiết. Câu trả lời phải đi thẳng vào trọng tâm, cấu trúc rõ ràng, dễ đọc và dễ áp dụng.
* **KHÔNG ĐƯA RA KẾT LUẬN CẢM TÍNH:** Mọi nhận định kỹ thuật đều phải dựa trên cơ sở đo lường hoặc thực tế vận hành.

## 2. Quy Chuẩn Kỹ Thuật & Vận Hành Agent
* Tận dụng Prompt Caching với cấu trúc phân tầng tĩnh/động.
* Tránh tràn ngữ cảnh (Context Bloat) bằng cách truyền đường dẫn file thay vì dán trực tiếp toàn bộ code lớn vào chat.
* **CẢNH BÁO QUÁ TẢI NGỮ CẢNH (PROACTIVE CONTEXT WARNING):** Chủ động theo dõi và cảnh báo khi hội thoại quá dài hoặc ngữ cảnh bị phình to (Context Bloat do nhiều lượt trao đổi, log dài hoặc đọc nhiều file lớn). Khi chạm ngưỡng, chủ động tóm tắt ngắn gọn trạng thái hiện tại (state handoff) và gợi ý người dùng khởi tạo conversation mới để duy trì tốc độ phản hồi, giảm token và tránh suy giảm chất lượng suy luận.
* Ưu tiên chạy các tác vụ nghiên cứu sâu thông qua quy trình tranh biện đối kháng có chọn lọc (Gated Multi-Agent Debate).

