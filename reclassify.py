import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import time
import json
import logging
from fb_harvester.catalog import CatalogManager
from fb_harvester.classifier import AIClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reclassify")

def run():
    catalog = CatalogManager()
    classifier = AIClassifier()
    data = catalog.load_data()
    total = len(data)
    
    print(f"\n🚀 BẮT ĐẦU PHÂN LOẠI & TÓM TẮT BẰNG AI CHO {total} REPO TRONG KHO...")
    
    for idx, item in enumerate(data, 1):
        name = item.get("full_name")
        print(f"\n[{idx}/{total}] Đang phân loại: {name} ...")
        
        # Nếu chưa có summary hoặc category chưa được gán chuẩn
        ai_res = classifier.classify_and_summarize(item)
        item["category"] = ai_res.get("category", "Developer Tools, CLI & Terminal")
        item["tags"] = ai_res.get("tags", [])
        item["summary"] = ai_res.get("summary", item.get("description", ""))
        item["use_cases"] = ai_res.get("use_cases", [])
        
        print(f"   -> Danh mục: [{item['category']}]")
        print(f"   -> Tóm tắt: {item['summary'][:80]}...")
        
        # Cập nhật từng bước
        catalog.add_or_update(item)
        time.sleep(1) # Tránh nghẽn request

    print(f"\n🎉 HOÀN THÀNH PHÂN LOẠI TOÀN BỘ {total} REPOSITORY!")
    print("📚 Đã cập nhật lại file CATALOG.md và catalog.json với đầy đủ phân mục và tóm tắt ngữ nghĩa.")

if __name__ == "__main__":
    run()
