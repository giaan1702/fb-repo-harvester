import os
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, detect_source_type, canonicalize_url
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.pipeline import GeminiReflectivePipeline
from vault_engine.config import DB_PATH

def run_e2e():
    print("=== [BẮT ĐẦU KIỂM CHỨNG THỰC NGHIỆM E2E] ===")
    db = DatabaseManager(DB_PATH)
    ingest = IngestManager(db)
    pipeline = GeminiReflectivePipeline()
    github_ext = GitHubExtractor()

    # 1. URL Ingestion
    test_url = "https://github.com/unclecode/crawl4ai.git/?utm_source=telegram&ref=vip"
    clean_url = canonicalize_url(test_url)
    source_type = detect_source_type(clean_url)
    print(f"[1] URL Chuẩn hoá: {clean_url} | Nguồn: {source_type}")

    # 2. Hàng đợi SQLite WAL
    task = ingest.enqueue_url(clean_url, source_type=source_type)
    task_id = task.get("task_id")
    print(f"[2] Đã nạp vào Queue Tasks ID: {task_id} (Status: {task.get('status')})")

    # 3. Worker Lease
    leased = ingest.lease_next_task(worker_id="verifier_daemon_01")
    print(f"[3] Worker nhận lease thành công: Task UUID {leased.get('task_uuid')}")

    # 4. Trích xuất GitHub
    print(f"[4] Đang trích xuất nội dung từ GitHub...")
    t0 = time.perf_counter()
    data = github_ext.extract(clean_url)
    ext_time = time.perf_counter() - t0
    print(f"    -> Repo: {data.get('title')} ({data.get('stars')} stars) trong {ext_time:.2f}s")
    print(f"    -> Độ dài nội dung: {len(data.get('content', ''))} ký tự")

    # 5. Phản biện 2-Pass Pipeline
    print(f"[5] Chạy Reflective Pipeline (Pass 1 Foundation -> Pass 2 Critique)...")
    t1 = time.perf_counter()
    schema_item = pipeline.process_content(data["content"], clean_url, source_type)
    pipe_time = time.perf_counter() - t1
    print(f"    -> Hoàn tất trong {pipe_time:.2f}s")
    print(f"    -> Tiêu đề: {schema_item.title}")
    print(f"    -> Phân loại: {schema_item.category} | Điểm thực chiến: {schema_item.practical_score}/10")
    print(f"    -> Tóm tắt ngắn: {schema_item.short_summary}")
    print(f"    -> Cảnh báo rủi ro: {schema_item.gotchas_and_risks}")

    # 6. Lưu trữ vào Vault
    payload = schema_item.model_dump()
    payload["url_hash"] = leased["url_hash"]
    payload["canonical_url"] = clean_url
    payload["source_type"] = source_type
    item_id = db.insert_vault_item(payload)
    ingest.complete_task(leased["id"])
    print(f"[6] Đã lưu vào Kho Tri Thức: Vault Item ID {item_id}")

    # 7. Kiểm tra FTS5 Full-Text Search
    t2 = time.perf_counter()
    fts_results = db.search_vault(query="crawl4ai", category="AI-Agents", min_score=7)
    fts_time = (time.perf_counter() - t2) * 1000
    print(f"[7] FTS5 Search 'crawl4ai': tìm thấy {len(fts_results)} kết quả trong {fts_time:.2f}ms")
    assert len(fts_results) > 0, "FTS5 phải tìm thấy item vừa lưu"

    print("\n>>> KIỂM CHỨNG THỰC NGHIỆM E2E THÀNH CÔNG 100%! <<<")

if __name__ == "__main__":
    run_e2e()
