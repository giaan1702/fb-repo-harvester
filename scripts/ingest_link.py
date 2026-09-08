import os
import sys
import argparse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vault_engine.config import DB_PATH
from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, detect_source_type, canonicalize_url, generate_url_hash
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.youtube_engine import YouTubeExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.pipeline import GeminiReflectivePipeline

def ingest_single_url(raw_url: str, force: bool = False):
    print(f"\n⚡ Đang nạp liên kết: {raw_url}")
    clean_url = canonicalize_url(raw_url)
    url_hash = generate_url_hash(clean_url)
    source_type = detect_source_type(clean_url)
    print(f"-> Chuẩn hóa URL: {clean_url}")
    print(f"-> Băm SHA-256: {url_hash[:16]}... | Nguồn: {source_type}")

    db = DatabaseManager(DB_PATH)
    ingest = IngestManager(db)
    pipeline = GeminiReflectivePipeline()

    # 1. Trinh sát & Khai phá bối cảnh đa tầng (Context Scout Agent)
    print(f"-> Đang kích hoạt Context Scout (Trinh sát đa tầng, truy vết repo, quét visual assets)...")
    from vault_engine.extractors.context_scout import ContextScout
    scout = ContextScout()
    dossier = scout.build_unified_dossier(clean_url, source_type)

    if dossier.error:
        print(f"❌ Trích xuất thất bại: {dossier.error}")
        return

    # 2. Chạy Reflective Pipeline (Senior Staff v4.0 + Smart Article Reader)
    print(f"-> Đang tạo Hồ Sơ Kỹ Sư Trưởng (Mermaid topology, Visual Assets, Pydantic contracts, Gotchas)...")
    schema_item = pipeline.process_content(
        clean_content=dossier,
        canonical_url=clean_url,
        source_type=source_type,
        title_hint=dossier.title
    )

    # 3. Lưu / Ghi đè vào Vault Database
    payload = schema_item.model_dump()
    payload["url_hash"] = url_hash
    payload["canonical_url"] = getattr(dossier, "identified_repo_url", None) or clean_url
    payload["source_type"] = source_type
    item_id = db.insert_vault_item(payload)

    print(f"\n🎉 HOÀN TẤT ĐÓNG GÓI HỒ SƠ TRI THỨC!")
    print(f"   * ID: #{item_id}")
    print(f"   * Tiêu đề: {schema_item.title}")
    print(f"   * Chuyên mục: {schema_item.category} | Điểm thực chiến: {schema_item.practical_score}/10")
    print(f"   * Tóm tắt: {schema_item.short_summary}")
    print(f"   * Sơ đồ kiến trúc: Đã tích hợp Mermaid Vector Diagram")
    print(f"   * Xem ngay tại: http://localhost:7860\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nạp link vào Kho Tri Thức Knowledge Vault")
    parser.add_argument("url", nargs="?", default="https://github.com/unclecode/crawl4ai", help="Đường link bài viết, GitHub hoặc YouTube")
    parser.add_argument("--force", action="store_true", help="Ghi đè nếu đã tồn tại")
    args = parser.parse_args()
    ingest_single_url(args.url, force=args.force)
