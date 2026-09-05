# 🚀 Facebook Page Repo Crawler & NotebookLM Knowledge Sync

Hệ thống tự động theo dõi các **Fanpage / Tài khoản Facebook** chuyên review mã nguồn mở, cào các video/reels mới nhất, trích xuất repository GitHub, đóng gói codebase bằng `repomix` và đồng bộ lên Google NotebookLM qua MCP.

---

## 📌 Cách Hoạt Động

Thay vì phải lưu từng video thủ công, bạn chỉ cần cung cấp link của các Fanpage/Kênh Facebook uy tín chuyên giới thiệu repo. Hệ thống sẽ:
1. **Tự động vào trang của kênh** (bằng Playwright Chromium ngầm).
2. **Quét N video / reels mới nhất** kèm tiêu đề và caption.
3. **Phân tích & Thẩm định GitHub Repo** (stars, tech stack, README, đóng gói repomix).
4. **Lọc trùng lặp thông minh**: Video hoặc repo nào đã cào rồi sẽ tự động bỏ qua.
5. **Đồng bộ hóa lên NotebookLM** để bạn tra cứu và hỏi đáp.

---

## 🛠️ Hướng Dẫn Sử Dụng

### 1. Cào ngay một Fanpage / Kênh Facebook
```bash
python -m fb_harvester.cli crawl-page --url "https://www.facebook.com/Aixamxi" --limit 5
```

### 2. Thêm Fanpage vào danh sách theo dõi
```bash
python -m fb_harvester.cli add-channel --url "https://www.facebook.com/GiaiPhapAi" --name "Giải Pháp AI"
```

### 3. Xem các kênh đang theo dõi
```bash
python -m fb_harvester.cli channels
```

### 4. Quét định kỳ toàn bộ các kênh theo dõi
```bash
python -m fb_harvester.cli crawl-all --limit 3
```

### 5. Cào một video hoặc bài viết lẻ
```bash
python -m fb_harvester.cli harvest --url "https://www.facebook.com/watch/?v=123456789"
```
