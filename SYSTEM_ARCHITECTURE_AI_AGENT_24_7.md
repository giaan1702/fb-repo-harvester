# 🌐 BẢN THIẾT KẾ KIẾN TRÚC HỆ THỐNG: KHO TRI THỨC TỰ ĐỘNG 24/7 (AUTONOMOUS KNOWLEDGE VAULT)

**Mã tài liệu:** `SYSTEM_ARCHITECTURE_VAULT_24_7`  
**Phiên bản:** `v3.0-Production-Enterprise`  
**Mục tiêu:** Hệ thống tự hành thu nạp, phản biện đa tầng, lưu trữ và tra cứu tri thức công nghệ 24/7 từ điện thoại di động mà không phụ thuộc vào PC hay can thiệp thủ công.

---

## 📐 1. TỔNG QUAN KIẾN TRÚC TOÀN HỆ THỐNG (END-TO-END ARCHITECTURE)

```
[ ĐIỆN THOẠI DI ĐỘNG ] (Facebook, GitHub, YouTube, ArXiv, Thread, Web)
           │
           ▼ (Share Link / Text)
┌────────────────────────────────────────────────────────────────────────┐
│ TRỤ CỘT 1: LUỒNG THU NHẬN & HÀNG ĐỢI BỀN VỮNG (INGESTION & QUEUE)      │
│ - Telegram Webhook Handler (Phản hồi HTTP 200 trong < 1.5s)           │
│ - URL Canonicalization & SHA-256 Deduplication (O(1) < 0.5ms)          │
│ - SQLite WAL Mode Transactional Queue (No Locks, Atomic Worker Lease)  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Lease task)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TRỤ CỘT 2: TRÍCH XUẤT ĐA PHƯƠNG TIỆN & DEAD-LETTER QUEUE (EXTRACTION)  │
│ - GitHub Engine: API v3 Token Pool ──(Fallback)──> Raw Readme CDN      │
│ - YouTube Engine: youtube-transcript-api bóc tách phụ đề có timestamp │
│ - ArXiv/PDF Engine: Bóc tách Abstract & Sơ đồ kiến trúc bài báo        │
│ - Web/FB Engine: Trafilatura (F1 ~0.93) ──(Fallback)──> Readability    │
│ - Dead-Letter Queue (DLQ): Tách biệt lỗi vĩnh viễn 404 vs quá độ 429   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Clean Raw Content)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TRỤ CỘT 3: REFLECTIVE PIPELINE 2-PASS (AI STUDIO DUAL-PASS ENGINE)     │
│ - Pass 1 (Foundation): Mental Model, 20/80 Leverage, Core Insight      │
│ - Pass 2 (Critique): Lead Engineer Đối kháng, Gotchas, Điểm thực chiến │
│ - Pydantic v2 Strict Schema: Grammar-guided decoding (100% Valid JSON) │
│ - Exponential Backoff (1.5s->3s->6s) & Fallback (3.5 -> 3.7 -> Groq)   │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼ (Sync & Archive)                ▼ (Bắn thông báo ngay)
┌──────────────────────────────────────┐   ┌─────────────────────────────┐
│ TRỤ CỘT 4: STORAGE & NOTEBOOKLM      │   │ [TELEGRAM NOTIFICATION]     │
│ - Google Drive 5TB: Phân cấp YYYY-MM │   │ - Tóm tắt đúng 30-40 từ     │
│ - NotebookLM Studio: Tự sinh Podcast │   │ - Điểm thực chiến (1-10)    │
│   Audio Overview (2 AI thảo luận)    │   │ - Link mở bài Deep Research │
│ - Bắn file .mp3 Podcast về Telegram  │   │ - File .mp3 Podcast đính kèm│
│ - Snapshot mã nguồn (.tar.gz) dự phòng│  └─────────────────────────────┘
└──────────────────┬───────────────────┘
                   │
                   ▼ (Read API < 30ms)
┌────────────────────────────────────────────────────────────────────────┐
│ TRỤ CỘT 5: GIAO DIỆN THƯ VIỆN BENTO GRID & READER DASHBOARD            │
│ - Bento Box Layout: Ô Card 30 từ -> Click Slide-over Reader tức thì    │
│ - Chế độ đọc tập trung: Thanh tiến độ cuộn trang + Mục lục động (TOC)  │
│ - Phân loại đa chiều: Chưa đọc / Đã đọc / Đánh dấu sao VIP / Điểm >=8  │
│ - Action Hooks: 1-click Copy Code, Tạo Podcast, Tải Snapshot code      │
│ - Mini Knowledge Graph: Sơ đồ trực quan mối liên hệ giữa các repo      │
│ - Tương thích Mobile PWA: Mở thư viện mượt mà trên trình duyệt mobile  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ 2. CHI TIẾT 5 TRỤ CỘT KỸ THUẬT SẢN XUẤT (ENTERPRISE V3.0)

### Trụ cột 1: Thu Nhận Tức Thì & Hàng Đợi Bền Vững (SQLite WAL)
1. **Telegram Webhook Event-Driven:** Webhook handler phản hồi `HTTP 200 OK` cho Telegram trong `< 1.5s` ngay sau khi ghi nhận request vào SQLite Queue. Tránh triệt để hiện tượng Telegram gửi lại dồn dập (Retry Storm) làm nghẽn hệ thống.
2. **SQLite WAL Mode (Write-Ahead Logging):** Bật `PRAGMA journal_mode = WAL;` và `PRAGMA busy_timeout = 5000;`. Reader không block Writer, Writer không block Reader, triệt tiêu lỗi `database is locked`.
3. **Atomic Worker Lease:** Worker chiếm giữ task bằng 1 câu lệnh nguyên tử (`UPDATE queue_tasks SET status='PROCESSING' ... RETURNING id`), chống race condition khi nhiều worker cùng chạy.
4. **Khử trùng lặp tức thì (Deduplication < 0.5ms):** Chuẩn hóa URL (cắt bỏ toàn bộ tracking `fbclid`, `utm_*`) và băm SHA-256 tra cứu qua B-Tree Index trước khi nạp vào hàng đợi.

---

### Trụ cột 2: Xử Lý Đa Phương Tiện (YouTube, ArXiv, Web, Code) & Dead-Letter Queue
1. **YouTube Video Engine:** 
   * Tự động trích xuất `video_id` và phụ đề qua `youtube-transcript-api` (ưu tiên tiếng Việt $\rightarrow$ tiếng Anh).
   * Gom cụm phụ đề theo mốc thời gian (Timestamps). Video dài 45 phút được tóm lược thành 3 phút đọc gồm ý tưởng cốt lõi, sơ đồ kiến trúc và mốc thời gian quan trọng.
2. **ArXiv & Paper Engine:** Nhận diện link `arxiv.org/abs/...`, tự động gọi ArXiv API trích xuất Abstract, tác giả, phương pháp và kéo file PDF về lưu trữ.
3. **GitHub Code Engine:** Gọi API v3 có token $\rightarrow$ Nếu hết quota fallback sang tải trực tiếp từ Raw Readme CDN (`raw.githubusercontent.com/.../README.md`) với tốc độ < 200ms và không giới hạn rate limit.
4. **Web/Facebook Engine:** Dùng **Trafilatura** (F1 score 0.93) bóc tách bài viết sạch, giữ nguyên vẹn code blocks và bảng biểu Markdown.
5. **Dead-Letter Queue (DLQ):** Tách riêng lỗi mạng tạm thời (tự thử lại sau 1.5s $\rightarrow$ 3s $\rightarrow$ 6s) và lỗi vĩnh viễn (link 404, private repo $\rightarrow$ đẩy vào DLQ để báo cáo qua Telegram, không thử lại vô ích).

---

### Trụ cột 3: Pipeline Phản Biện 2-Pass qua Google AI Studio API
1. **Pass 1 (Foundation Pass):** Áp dụng nguyên vẹn khung tư duy của `notebooklm-book-reader`:
   * Trích xuất 20% nguyên lý cốt lõi tạo 80% sức mạnh hệ thống.
   * Lập bảng phân biệt khái niệm dễ nhầm lẫn (Distinction Matrix).
2. **Pass 2 (Critique Pass - Kỹ sư trưởng khó tính):**
   * Gạch bỏ lý thuyết suông, cảnh báo gotchas, rủi ro bảo mật và chi phí ẩn.
   * Chấm điểm thực chiến (1 đến 10).
3. **Chống lỗi JSON 100% bằng Pydantic v2 Strict Schema:** Sử dụng `responseMimeType: "application/json"` và truyền thẳng `responseSchema` vào cấu hình mô hình của Gemini API để kích hoạt Grammar-Guided Decoding ở cấp độ Token Sampler. Đầu ra đảm bảo 100% đúng cấu trúc JSON.
4. **Cơ chế Fallback Mô hình:** `gemini-3.5-flash` (Primary) $\rightarrow$ `gemini-3.7-flash` $\rightarrow$ `Groq Llama-3.3-70b` (Dự phòng khẩn cấp khi Google bảo trì).

---

### Trụ cột 4: Khai Thác Triệt Để Google NotebookLM & Lưu Trữ Drive 5TB
1. **Tự động sinh Audio Overview Podcast (2 AI Hosts thảo luận kỹ thuật):**
   * Gọi `studio_create(artifact_type="audio", audio_format="deep_dive")` với prompt định hướng phản biện rủi ro thực chiến.
   * Worker thăm dò ngầm, khi render xong tự động tải file `.mp3` về lưu tại `/KnowledgeVault/Podcasts/{YYYY-MM}/{slug}.mp3`.
   * **Bắn file âm thanh về Telegram:** Gửi file `.mp3` trực tiếp qua Telegram Bot để bạn có thể nghe trên đường đi làm hoặc tập gym.
2. **Truy vấn chéo đa Notebook (`cross_notebook_query`):** Cho phép đặt câu hỏi kết nối giữa các mảng công nghệ (ví dụ: đối chiếu công cụ Scraping mới với kiến trúc Multi-Agent trong các notebook khác nhau).
3. **Snapshot Mã Nguồn Phòng Ngừa Thất Thoát:**
   * Đóng gói `README.md`, file dependencies (`package.json`, `requirements.txt`), Dockerfile và code entrypoint thành tệp `.tar.gz`.
   * Lưu trữ tại Google Drive `/KnowledgeVault/Snapshots/` phòng trường hợp tác giả xóa repo hoặc đổi sang mã nguồn đóng.
4. **Cơ chế Đồng bộ 3 Chiều (Tri-Sync Topology):**
   * `Local SQLite`: Quản lý trạng thái đọc (`UNREAD`, `READ`, `STARRED`), điểm số, task queue.
   * `Google Drive 5TB`: Lưu file Markdown hoàn chỉnh, Podcast .mp3, Snapshot code .tar.gz.
   * `Google NotebookLM`: Bộ nhớ ngữ cảnh triệu token phục vụ hỏi đáp và nghe podcast.

---

### Trụ cột 5: Giao Diện Thư Viện Bento Grid & Reader Dashboard (Ergonomic UI)
1. **Backend FastAPI + SQLite FTS5:** Tìm kiếm toàn văn Full-Text Search qua FTS5 với tốc độ phản hồi API < 30ms.
2. **Bento Box Layout (< 15KB bundle, Zero-Framework):**
   * Màn hình chính: Hiển thị các ô Card với đoạn tóm tắt đúng 30-40 từ, điểm thực chiến, huy hiệu Tech Stack.
   * Click vào Card: Mở Slide-over Reader đọc toàn bộ Bản nghiên cứu sâu tức thì (độ trễ mở = 0ms).
3. **Chế độ đọc tập trung (Distraction-Free Reader Mode):**
   * **Thanh tiến độ đọc (Reading Progress Bar):** Nằm cố định đỉnh màn hình, tự co giãn theo tỷ lệ cuộn trang.
   * **Mục lục động (Auto TOC & ScrollSpy):** Dùng `IntersectionObserver` tự quét `h2, h3` trong bài, hiển thị mục lục bên lề và tự sáng mục tương ứng khi cuộn tới.
   * **Nút 1-Click Action Hooks:** Copy Code mẫu, Tạo Audio Podcast, Tải Snapshot code, Mở trong NotebookLM.
4. **Đồ thị liên kết tri thức (Mini Knowledge Graph View):**
   * Dùng thư viện đồ họa cực nhẹ Vis.js Network (<30KB) để vẽ trực quan mạng lưới liên kết giữa các bài viết và công nghệ có chung tech stack/kiến trúc.
5. **Tương thích Mobile PWA (Progressive Web App):**
   * Hỗ trợ cài đặt lên màn hình chính điện thoại như một app native, thanh điều hướng đáy (Bottom Navigation), vuốt chạm mượt mà.

---

## 🗄️ 3. SCHEMA CƠ SỞ DỮ LIỆU SẢN XUẤT V3.0 (SQLITE WAL)

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

-- HÀNG ĐỢI TIẾP NHẬN BỀN VỮNG
CREATE TABLE IF NOT EXISTS queue_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT NOT NULL UNIQUE,
    url_hash TEXT NOT NULL,
    raw_url TEXT NOT NULL,
    source_type TEXT NOT NULL,      -- 'GITHUB', 'YOUTUBE', 'ARXIV', 'WEB_ARTICLE'
    status TEXT NOT NULL DEFAULT 'PENDING',
    priority INTEGER NOT NULL DEFAULT 1,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    locked_at INTEGER DEFAULT NULL,
    locked_by TEXT DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- KHO TRI THỨC ĐÍCH (VAULT ITEMS V3.0)
CREATE TABLE IF NOT EXISTS vault_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT NOT NULL UNIQUE,
    canonical_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    short_summary TEXT NOT NULL,
    practical_score INTEGER NOT NULL,
    score_reason TEXT NOT NULL,
    tech_stack TEXT NOT NULL,           -- JSON Array: ["Python", "FastAPI"]
    gotchas_and_risks TEXT NOT NULL,    -- JSON Array: ["RCE Risk", "Lock Risk"]
    deep_research_md TEXT NOT NULL,
    github_repo TEXT,
    drive_path TEXT,                    -- Đường dẫn trên Drive 5TB
    notebook_ref TEXT,                  -- ID NotebookLM
    audio_podcast_path TEXT,            -- Đường dẫn file .mp3 Podcast
    snapshot_archive_path TEXT,         -- Đường dẫn file .tar.gz snapshot
    reading_status TEXT NOT NULL DEFAULT 'UNREAD', -- 'UNREAD', 'READ', 'STARRED'
    is_starred INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL DEFAULT '',
    topic_group_id TEXT DEFAULT NULL,   -- Dành cho chuỗi bài viết liên hoàn
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- HÀNG ĐỢI LỖI VĨNH VIỄN (DLQ)
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT NOT NULL,
    raw_url TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    payload_snapshot TEXT,
    resolved INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- TÌM KIẾM TOÀN VĂN FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
    title, short_summary, tech_stack, deep_research_md, content='vault_items', content_rowid='id'
);

-- CHỈ MỤC TỐI ƯU
CREATE INDEX IF NOT EXISTS idx_vault_cat ON vault_items (category);
CREATE INDEX IF NOT EXISTS idx_vault_score ON vault_items (practical_score DESC);
CREATE INDEX IF NOT EXISTS idx_vault_status ON vault_items (reading_status);
CREATE INDEX IF NOT EXISTS idx_vault_starred ON vault_items (is_starred);
```
