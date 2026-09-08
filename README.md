# 🌐 Autonomous Knowledge Vault v3.0

Hệ thống tự hành thu nạp, phản biện đa tầng, lưu trữ và tra cứu tri thức công nghệ (GitHub, ArXiv, YouTube, Web Tech Articles) hỗ trợ giao diện Bento Grid hiện đại và khả năng nạp dữ liệu từ xa 24/7.

---

## 📐 Kiến Trúc Cốt Lõi

1. **Hàng Đợi & Cơ Sở Dữ Liệu Bền Vững (SQLite WAL + FTS5):**
   - Chế độ Write-Ahead Logging (`WAL`), chống lock, atomic worker lease.
   - Băm SHA-256 canonical URL khử trùng lặp tức thì (<0.5ms).
   - Tìm kiếm toàn văn Full-Text Search qua SQLite FTS5 (<10ms).
2. **Bộ Trích Xuất Đa Kênh (`vault_engine/extractors/`):**
   - **GitHub Engine:** Kéo README, release và star qua Raw CDN / API v3.
   - **YouTube Engine:** Trích xuất transcript có mốc thời gian (Timestamps).
   - **Web Engine:** Bóc tách bài viết sạch qua Trafilatura (F1 ~0.93).
   - **Reference Harvester:** Tự động khai thác các bài báo ArXiv và GitHub Repo được nhắc tới trong nội dung.
3. **Reflective Pipeline 2-Pass (Gemini AI Studio):**
   - **Pass 1 (Foundation):** Mental Model cốt lõi, đòn bẩy 20/80, quét điểm nghẽn nhận thức.
   - **Pass 2 (Critique):** Lead Engineer đối kháng, Gotchas & Rủi ro thực chiến, chấm điểm 1-10.
   - **Bản Dịch Kỹ Thuật Song Ngữ (`🇻🇳 / 🇺🇸`):** Bảo tồn 100% cấu trúc bảng Markdown, code block, công thức và hình ảnh.
4. **Giao Diện Thư Viện Bento Grid & Smart Reader Drawer:**
   - Dark mode chuẩn mực, tải siêu nhanh (<15KB bundle).
   - Reader Drawer trượt mượt mà, hỗ trợ Mục lục động (TOC), Thanh tiến độ cuộn (Progress bar).
   - Mạng lưới tri thức tương tác (Network Tab) với nút `[+ Nạp Vào Kho]` 1-click.

---

## 🚀 Khởi Chạy Nhanh

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình môi trường (`.env`)
```env
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Chạy giao diện Web
* Trên Windows: Nhấp đúp vào `start_ui.bat` hoặc chạy:
```bash
python -m uvicorn vault_engine.server:app --host 127.0.0.1 --port 7860 --reload
```
* Truy cập Dashboard tại: **`http://127.0.0.1:7860`**

---

## 🧪 Kiểm Thử Hệ Thống

Chạy toàn bộ test suite khép kín:
```bash
pytest tests/test_vault_system.py -v
```

---

## 📁 Cấu Trúc Thư Mục

```
.
├── vault_engine/               # Mã nguồn lõi Knowledge Vault v3.0
│   ├── config.py              # Cấu hình biến môi trường & paths
│   ├── db.py                  # SQLite WAL & FTS5 search engine
│   ├── ingest.py              # Ingest queue manager & deduplication
│   ├── pipeline.py            # Gemini Reflective Dual-Pass Pipeline
│   ├── server.py              # FastAPI / Starlette backend & Webhook
│   ├── extractors/            # GitHub, YouTube, Web, Reference miners
│   └── static/                # Giao diện Bento Grid, Reader Drawer, CSS/JS
├── data/
│   └── vault.db               # SQLite database (WAL mode)
├── tests/
│   └── test_vault_system.py   # Test suite tự động hóa
├── archive/                   # Thư mục lưu trữ module cũ (legacy)
│   └── legacy_fb_harvester/   # Module cào Facebook trước đây
├── start_ui.bat               # Script khởi chạy nhanh trên Windows
├── Dockerfile                 # Container deployment
└── requirements.txt           # Thư viện phụ thuộc
```
