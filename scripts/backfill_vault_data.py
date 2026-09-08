import sqlite3
import json
import os
import sys

# Đảm bảo import được vault_engine
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from vault_engine.db import DatabaseManager
from vault_engine.pipeline import GeminiReflectivePipeline
from vault_engine.extractors.reference_harvester import extract_references

def backfill():
    db = DatabaseManager("data/vault.db")
    pipeline = GeminiReflectivePipeline()
    cursor = db.conn.cursor()

    cursor.execute("SELECT id, canonical_url, source_type, title, original_md, deep_research_md FROM vault_items WHERE is_deleted = 0;")
    rows = cursor.fetchall()
    print(f"Bắt đầu nâng cấp tri thức & backfill cho {len(rows)} tài liệu...")

    for row in rows:
        item_id = row["id"]
        url = row["canonical_url"]
        stype = row["source_type"]
        old_title = row["title"]
        orig_md = row["original_md"]
        deep_md = row["deep_research_md"]

        # Ưu tiên lấy từ original_md nếu có, hoặc trích từ deep_research_md
        raw_text = orig_md or deep_md
        if "## PHẦN II:" in raw_text:
            raw_text = raw_text.split("## PHẦN II:", 1)[1]
        if "## PHẦN III:" in raw_text:
            raw_text = raw_text.split("## PHẦN III:", 1)[0]

        # Khử các ghi chú hệ thống cũ
        clean_lines = [
            line for line in raw_text.split("\n")
            if not any(k in line for k in ["[!(NOTE|TIP|IMPORTANT)]", "[!NOTE]", "chuyển ngữ sang tiếng Việt", "nguyên tác của tác giả", "giải mã tại chỗ", "(Original English)"])
        ]
        raw_text = "\n".join(clean_lines).strip()

        # Chạy pipeline phản biện nâng cấp (kèm AI Translation và Reference Harvester)
        schema = pipeline.process_content(raw_text, canonical_url=url, source_type=stype, title_hint=old_title)
        
        # Cập nhật DB
        ref_docs_json = json.dumps(schema.referenced_docs, ensure_ascii=False)
        cursor.execute("""
            UPDATE vault_items 
            SET deep_research_md = ?,
                original_md = ?,
                referenced_docs = ?,
                tech_stack = ?,
                updated_at = strftime('%s', 'now')
            WHERE id = ?;
        """, (schema.deep_research_md, schema.original_md, ref_docs_json, json.dumps(schema.tech_stack, ensure_ascii=False), item_id))
        
        ref_count = len(schema.referenced_docs)
        print(f" -> Đã nâng cấp Item #{item_id} [{old_title[:30]}...] | References tìm thấy: {ref_count}")

    db.conn.commit()
    print("Hoàn tất backfill toàn bộ kho dữ liệu!")

if __name__ == "__main__":
    backfill()
