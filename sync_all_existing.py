"""
sync_all_existing.py
Đồng bộ toàn bộ các repository hiện có trong catalog.json lên Google NotebookLM.
"""

import sys
import time
import logging
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fb_harvester.catalog import CatalogManager
from fb_harvester.packager import RepoPackager
from fb_harvester.notebook_sync import NotebookSyncEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_all")

def main():
    catalog = CatalogManager()
    packager = RepoPackager()
    sync_engine = NotebookSyncEngine()

    print("=" * 60)
    print("🚀 BẮT ĐẦU ĐỒNG BỘ TOÀN BỘ REPOSITORY LÊN GOOGLE NOTEBOOKLM")
    print("=" * 60)

    # 1. Kiểm tra xác thực
    print("🔍 Đang kiểm tra xác thực Google NotebookLM...")
    if not sync_engine.is_authenticated():
        print("❌ Chưa đăng nhập được Google NotebookLM. Vui lòng kiểm tra lại!")
        return

    # 2. Lấy Notebook chung
    target_nb = sync_engine.get_or_create_default_notebook()
    print(f"🎯 Đang đồng bộ vào Sổ Ghi Chú: {target_nb} (Facebook Curated Tech Repositories)\n")

    # 3. Lọc danh sách chưa đồng bộ
    repos = catalog.load_data()
    unsynced = [
        r for r in repos 
        if not r.get("synced_to_notebooklm") and (not r.get("notebook_ref") or r.get("notebook_ref") == "Chưa nạp")
    ]

    print(f"📊 Tổng số repo: {len(repos)} | Đã nạp trước đó: {len(repos) - len(unsynced)} | Cần nạp: {len(unsynced)}\n")

    if not unsynced:
        print("✅ Toàn bộ repository đã được đưa lên Google NotebookLM từ trước!")
        return

    success_count = 0
    failed_count = 0

    for idx, repo in enumerate(unsynced, 1):
        full_name = repo.get("full_name")
        print(f"[{idx}/{len(unsynced)}] Đang xử lý: {full_name} ...")

        try:
            # Tạo file knowledge doc
            doc_path = packager.build_knowledge_document(fb_info={}, repo_info=repo)
            
            # Tải lên NotebookLM
            ok = sync_engine.add_source_file(target_nb, doc_path)
            if ok:
                repo["synced_to_notebooklm"] = True
                repo["notebook_title"] = target_nb
                repo["notebook_ref"] = target_nb
                catalog.add_or_update(repo)
                success_count += 1
                print(f"   -> ✅ Đã nạp thành công: {full_name}")
            else:
                failed_count += 1
                print(f"   -> ⚠️ Thất bại khi nạp: {full_name}")
        except Exception as e:
            failed_count += 1
            print(f"   -> ❌ Lỗi ngoại lệ: {e}")

        # Nghỉ 1s chống rate limit
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"🎉 HOÀN TẤT ĐỒNG BỘ! Thành công: {success_count} | Thất bại: {failed_count}")
    print(f"📚 Bảng danh mục CATALOG.md và catalog.json đã được cập nhật toàn diện.")
    print("=" * 60)

if __name__ == "__main__":
    main()
