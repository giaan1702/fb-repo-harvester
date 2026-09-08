import os
import sys
import json
import time
import logging

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from vault_engine.db import DatabaseManager
from vault_engine.config import DB_PATH
from vault_engine.pipeline import GeminiReflectivePipeline
from vault_engine.extractors.context_scout import ContextScout, UnifiedContextDossier
from vault_engine.embedding import get_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reprocess_all")

def reprocess_all():
    db = DatabaseManager(DB_PATH)
    pipeline = GeminiReflectivePipeline()
    scout = ContextScout()

    cursor = db.conn.cursor()
    cursor.execute("SELECT id, canonical_url, source_type, title, original_md, deep_research_md FROM vault_items WHERE is_deleted = 0 ORDER BY id ASC;")
    items = cursor.fetchall()
    total = len(items)

    print(f"\n🚀 BẮT ĐẦU CHẠY LẠI TOÀN BỘ {total} TÀI LIỆU TRONG VAULT QUA PIPELINE HỢP NHẤT v4.0\n")

    for idx, item in enumerate(items, 1):
        item_id = item["id"]
        url = item["canonical_url"]
        stype = item["source_type"]
        old_title = item["title"]
        stored_orig = item["original_md"] or ""
        stored_deep = item["deep_research_md"] or ""

        print(f"[{idx}/{total}] Đang xử lý Item #{item_id}: {old_title} ({stype})")
        print(f"    URL: {url}")

        # 1. Trinh sát bối cảnh qua ContextScout
        dossier = scout.build_unified_dossier(url, stype)

        # Fallback an toàn: Nếu live extraction bị rỗng/lỗi (ví dụ Facebook anti-bot chặn IP), 
        # tận dụng lại nội dung đã thu thập trước đó trong DB
        if dossier.error or not dossier.primary_content:
            logger.info(f"    -> Live fetch không có dữ liệu mới, kích hoạt nội dung lưu trữ...")
            existing_text = stored_orig
            if "## PHẦN II:" in existing_text:
                existing_text = existing_text.split("## PHẦN II:", 1)[1]
            if not existing_text.strip():
                existing_text = stored_deep
                if "## PHẦN II:" in existing_text:
                    existing_text = existing_text.split("## PHẦN II:", 1)[1]
                if "## PHẦN III:" in existing_text:
                    existing_text = existing_text.split("## PHẦN III:", 1)[0]

            clean_lines = [
                line for line in existing_text.split("\n")
                if not any(k in line for k in ["[!(NOTE|TIP|IMPORTANT)]", "[!NOTE]", "chuyển ngữ sang tiếng Việt", "nguyên tác của tác giả", "(Original English)"])
            ]
            primary_text = "\n".join(clean_lines).strip()
            if not primary_text:
                primary_text = stored_orig or stored_deep

            # Tự động suy luận repo từ nội dung đã có nếu chưa tìm thấy
            inferred_repo = dossier.identified_repo_url or scout.infer_repo_name_from_text(primary_text)
            repo_meta = dossier.repo_metadata
            repo_readme = dossier.repo_readme
            visuals = dossier.visual_assets

            if inferred_repo and not repo_readme:
                if not inferred_repo.startswith("http"):
                    found = scout.github_ext.search_repo_by_name(inferred_repo)
                    if found:
                        inferred_repo = found
                if inferred_repo.startswith("http"):
                    gh_deep = scout.github_ext.extract(inferred_repo)
                    if gh_deep and "error" not in gh_deep:
                        repo_readme = gh_deep.get("raw_readme", "")
                        visuals = gh_deep.get("visual_assets", [])
                        repo_meta = {
                            "name": gh_deep.get("title"),
                            "stars": gh_deep.get("stars", 0),
                            "language": gh_deep.get("language", ""),
                            "topics": gh_deep.get("topics", [])
                        }

            dossier = UnifiedContextDossier(
                canonical_url=url,
                source_type=stype,
                title=old_title,
                primary_content=primary_text,
                comments=dossier.comments,
                identified_repo_url=inferred_repo if inferred_repo and inferred_repo.startswith("http") else None,
                repo_metadata=repo_meta,
                repo_readme=repo_readme,
                visual_assets=visuals,
                referenced_docs=dossier.referenced_docs,
                video_transcript=dossier.video_transcript
            )

        # 2. Xử lý qua Content Engine Senior Staff v4.0
        schema = pipeline.process_content(dossier, canonical_url=url, source_type=stype, title_hint=old_title)

        # 3. Cập nhật vào DB
        resolved_repo = getattr(dossier, "identified_repo_url", None) or schema.github_repo
        ref_docs_json = json.dumps(schema.referenced_docs, ensure_ascii=False)
        tech_stack_json = json.dumps(schema.tech_stack, ensure_ascii=False)
        gotchas_json = json.dumps(schema.gotchas_and_risks, ensure_ascii=False)

        cursor.execute("""
            UPDATE vault_items 
            SET title = ?,
                category = ?,
                short_summary = ?,
                practical_score = ?,
                score_reason = ?,
                tech_stack = ?,
                github_repo = ?,
                gotchas_and_risks = ?,
                deep_research_md = ?,
                original_md = ?,
                referenced_docs = ?,
                updated_at = strftime('%s', 'now')
            WHERE id = ?;
        """, (
            schema.title,
            schema.category,
            schema.short_summary,
            schema.practical_score,
            schema.score_reason,
            tech_stack_json,
            resolved_repo,
            gotchas_json,
            schema.deep_research_md,
            schema.original_md or stored_orig,
            ref_docs_json,
            item_id
        ))
        db.conn.commit()

        # 4. Tái sinh Vector Embedding
        try:
            content_to_embed = f"{schema.title}. {schema.short_summary}. Tech: {' '.join(schema.tech_stack)}"
            vec = get_embedding(content_to_embed)
            if vec:
                db.save_embedding(item_id, vec)
        except Exception as emb_err:
            logger.warning(f"Lỗi embedding item #{item_id}: {emb_err}")

        print(f"    -> Hoàn tất: '{schema.title}' | Repo: {resolved_repo or 'None'} | Điểm: {schema.practical_score}/10\n")
        time.sleep(1.0)

    print("✅ ĐÃ HOÀN TẤT CHẠY LẠI 100% CÁC LIÊN KẾT TRONG VAULT!")

if __name__ == "__main__":
    reprocess_all()
