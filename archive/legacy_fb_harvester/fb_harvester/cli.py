import sys
import io
import os
import argparse
import logging
from pathlib import Path
from typing import List

# Fix Unicode output on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fb_harvester.extractor import FacebookExtractor
from fb_harvester.github_resolver import GitHubResolver
from fb_harvester.packager import RepoPackager
from fb_harvester.catalog import CatalogManager
from fb_harvester.notebook_sync import NotebookSyncEngine
from fb_harvester.page_crawler import PageCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fb_harvester_cli")

def process_single_item(
    url: str = "",
    text: str = "",
    query: str = "",
    skip_clone: bool = False,
    notebook_id: str = "",
    catalog: CatalogManager = None,
    extractor: FacebookExtractor = None,
    resolver: GitHubResolver = None,
    packager: RepoPackager = None,
    sync_engine: NotebookSyncEngine = None
) -> bool:
    catalog = catalog or CatalogManager()
    extractor = extractor or FacebookExtractor()
    resolver = resolver or GitHubResolver()
    packager = packager or RepoPackager()
    sync_engine = sync_engine or NotebookSyncEngine()

    if url and catalog.is_processed(source_url=url):
        print(f"⏩ Đã bỏ qua (URL đã được thu thập trước đó): {url}")
        return True

    fb_info = {}
    github_targets = []

    # 1. Bóc tách từ URL hoặc Text
    if url:
        print(f"\n🔍 Đang phân tích từ URL: {url} ...")
        fb_info = extractor.extract_from_url(url)
        github_targets = fb_info.get("github_links", [])
        if text:
            if not fb_info.get("title"):
                fb_info["title"] = text
            extra_kw = extractor.extract_keywords(text)
            fb_info["keywords"] = list(set(fb_info.get("keywords", []) + extra_kw))
            extra_links = extractor.extract_github_links(text)
            for el in extra_links:
                if el["full_name"] not in [g["full_name"] for g in github_targets]:
                    github_targets.append(el)
    elif text:
        print(f"\n🔍 Đang phân tích văn bản ...")
        fb_info = extractor.extract_from_text(text)
        github_targets = fb_info.get("github_links", [])

    # 2. Tìm kiếm nếu không có link trực tiếp
    if not github_targets:
        candidates = []
        if query:
            candidates.append(query)
        elif fb_info.get("keywords"):
            candidates.extend(fb_info["keywords"])

        for cand in candidates:
            print(f"🔎 Tìm kiếm GitHub với từ khóa: '{cand}'...")
            search_results = resolver.search_repo(cand, limit=1)
            if search_results:
                top = search_results[0]
                print(f"🎯 Đã tìm thấy: {top['full_name']} (⭐ {top['stars']:,})")
                github_targets.append({
                    "owner": top["owner"],
                    "repo": top["name"],
                    "full_name": top["full_name"],
                    "url": top["html_url"]
                })
                break

    if not github_targets:
        print("⚠️ Không tìm thấy repo nào từ mục này.")
        return False

    success_any = False
    for target in github_targets:
        owner = target["owner"]
        repo_name = target["repo"]
        full_name = f"{owner}/{repo_name}"

        if catalog.is_processed(full_name=full_name):
            print(f"⏩ Đã bỏ qua (Repo '{full_name}' đã có trong kho lưu trữ).")
            continue

        print(f"📦 Đang lấy chi tiết: {full_name} ...")
        repo_details = resolver.get_repo_details(owner, repo_name)
        if not repo_details:
            continue

        print(f"🤖 Đang gửi FreeLLMAPI phân loại & tóm tắt ngữ nghĩa ...")
        from fb_harvester.classifier import AIClassifier
        classifier = AIClassifier()
        ai_res = classifier.classify_and_summarize(repo_details, repo_details.get("readme", ""))
        repo_details["category"] = ai_res.get("category", "Developer Tools, CLI & Terminal")
        repo_details["tags"] = ai_res.get("tags", [])
        repo_details["summary"] = ai_res.get("summary", repo_details.get("description", ""))
        repo_details["use_cases"] = ai_res.get("use_cases", [])

        repo_path = None
        if not skip_clone:
            print(f"🚀 Đang clone mã nguồn repo ...")
            safe_name = f"{owner}_{repo_name}"
            repo_path = packager.clone_repo(repo_details["clone_url"], safe_name)

        print(f"📝 Đang tạo tài liệu tri thức (Knowledge Doc & Repomix) ...")
        doc_path = packager.build_knowledge_document(fb_info, repo_details, repo_path)

        catalog_entry = {
            "full_name": repo_details["full_name"],
            "category": repo_details["category"],
            "tags": repo_details["tags"],
            "summary": repo_details["summary"],
            "use_cases": repo_details["use_cases"],
            "repo_url": repo_details["html_url"],
            "stars": repo_details["stars"],
            "language": repo_details["language"],
            "description": repo_details["description"],
            "source_url": fb_info.get("source_url", ""),
            "knowledge_doc": str(doc_path),
            "synced_to_notebooklm": False,
            "notebook_title": "",
            "notebook_ref": ""
        }

        # Tự động đồng bộ ngay lên Google NotebookLM
        print(f"☁️ Đang tự động nạp tri thức repo '{repo_details['full_name']}' lên Google NotebookLM...")
        if sync_engine.is_authenticated():
            target_nb = notebook_id or sync_engine.get_or_create_default_notebook()
            if target_nb:
                ok = sync_engine.add_source_file(target_nb, doc_path)
                if ok:
                    catalog_entry["synced_to_notebooklm"] = True
                    catalog_entry["notebook_title"] = target_nb
                    catalog_entry["notebook_ref"] = target_nb
                    print(f"🎉 Đã nạp thành công lên NotebookLM (Notebook ID: {target_nb})!")
                else:
                    print("⚠️ Tải file lên NotebookLM không thành công.")
            else:
                print("⚠️ Không lấy được Notebook ID.")
        else:
            print("ℹ️ Đã lưu kho cục bộ (Phiên NotebookLM không sẵn sàng).")

        catalog.add_or_update(catalog_entry)
        print(f"✅ Hoàn tất: {repo_details['full_name']}")
        success_any = True

    return success_any

def crawl_and_process_page(page_url: str, limit: int = 5, skip_clone: bool = False, notebook_id: str = ""):
    """Cào danh sách video từ một Fanpage/Profile và xử lý từng video."""
    crawler = PageCrawler()
    print(f"\n🌐 Đang cào các video mới nhất từ Facebook Page: {page_url} (Giới hạn {limit} video) ...")
    videos = crawler.fetch_videos_from_page(page_url, limit=limit)

    if not videos:
        print(f"❌ Không tìm thấy video nào từ trang này hoặc trang cần đăng nhập.")
        return

    print(f"\n🎯 Tìm thấy {len(videos)} video từ page. Bắt đầu phân tích từng video...")
    for idx, v in enumerate(videos, 1):
        print(f"\n--- [{idx}/{len(videos)}] Xử lý: {v['url']} ({v.get('title', '')[:50]}) ---")
        process_single_item(
            url=v["url"],
            text=v.get("title", ""),
            skip_clone=skip_clone,
            notebook_id=notebook_id
        )

def main():
    parser = argparse.ArgumentParser(description="FB Repo Harvester - Thu thập repo từ Facebook và sync NotebookLM")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh thực hiện")

    # Command: harvest
    harvest_parser = subparsers.add_parser("harvest", help="Cào và xử lý video/bài đăng Facebook")
    harvest_parser.add_argument("--url", "-u", type=str, default="", help="URL video/post Facebook")
    harvest_parser.add_argument("--text", "-t", type=str, default="", help="Nội dung caption copy từ Facebook")
    harvest_parser.add_argument("--query", "-q", type=str, default="", help="Từ khóa hoặc tên repo tìm kiếm")
    harvest_parser.add_argument("--skip-clone", action="store_true", help="Chỉ lấy README và metadata, không clone toàn bộ code")
    harvest_parser.add_argument("--notebook-id", type=str, default="", help="ID Notebook trên NotebookLM")

    # Command: crawl-page
    page_parser = subparsers.add_parser("crawl-page", help="Cào danh sách video từ một Fanpage/Profile cụ thể")
    page_parser.add_argument("--url", "-u", type=str, required=True, help="URL Fanpage hoặc Profile Facebook")
    page_parser.add_argument("--limit", "-l", type=int, default=5, help="Số lượng video mới nhất cần quét (mặc định 5)")
    page_parser.add_argument("--skip-clone", action="store_true", help="Chỉ lấy README và metadata, không clone toàn bộ code")
    page_parser.add_argument("--notebook-id", type=str, default="", help="ID Notebook trên NotebookLM")

    # Command: add-channel
    add_ch_parser = subparsers.add_parser("add-channel", help="Thêm một Fanpage vào danh sách theo dõi")
    add_ch_parser.add_argument("--url", "-u", type=str, required=True, help="URL Fanpage hoặc Profile")
    add_ch_parser.add_argument("--name", "-n", type=str, default="", help="Tên kênh/page")
    add_ch_parser.add_argument("--category", "-c", type=str, default="AI & Tech Repos", help="Chủ đề của page")

    # Command: channels
    subparsers.add_parser("channels", help="Xem danh sách các kênh đang theo dõi")

    # Command: crawl-all
    crawl_all_parser = subparsers.add_parser("crawl-all", help="Quét tất cả các kênh đang theo dõi")
    crawl_all_parser.add_argument("--limit", "-l", type=int, default=3, help="Số video mỗi kênh (mặc định 3)")
    crawl_all_parser.add_argument("--skip-clone", action="store_true", help="Chỉ lấy README và metadata, không clone toàn bộ code")
    crawl_all_parser.add_argument("--notebook-id", type=str, default="", help="ID Notebook trên NotebookLM")

    # Command: list
    subparsers.add_parser("list", help="Xem danh sách các repo đã lưu trong kho")

    args = parser.parse_args()

    if args.command == "harvest":
        if args.url or args.text or args.query:
            process_single_item(url=args.url, text=args.text, query=args.query, skip_clone=args.skip_clone, notebook_id=args.notebook_id)
        else:
            print("Vui lòng cung cấp ít nhất một tham số: --url, --text hoặc --query")
            sys.exit(1)

    elif args.command == "crawl-page":
        crawl_and_process_page(args.url, limit=args.limit, skip_clone=args.skip_clone, notebook_id=args.notebook_id)

    elif args.command == "add-channel":
        crawler = PageCrawler()
        crawler.add_channel(args.url, name=args.name, category=args.category)
        print(f"✅ Đã thêm kênh: {args.url}")

    elif args.command == "channels":
        crawler = PageCrawler()
        channels = crawler.load_channels()
        print(f"\n📡 Danh sách {len(channels)} Fanpage / Kênh đang theo dõi:")
        for idx, ch in enumerate(channels, 1):
            print(f"{idx}. {ch['name']} - {ch['url']} [{ch.get('category', '')}]")

    elif args.command == "crawl-all":
        crawler = PageCrawler()
        channels = crawler.load_channels()
        print(f"\n🚀 Bắt đầu quét tất cả {len(channels)} kênh theo dõi...")
        for ch in channels:
            print(f"\n==========================================")
            print(f"📡 Đang quét kênh: {ch['name']} ({ch['url']})")
            print(f"==========================================")
            crawl_and_process_page(ch['url'], limit=args.limit, skip_clone=args.skip_clone, notebook_id=args.notebook_id)

    elif args.command == "list":
        catalog = CatalogManager()
        data = catalog.load_data()
        print(f"\n📚 Danh sách {len(data)} repositories trong kho lưu trữ:")
        for item in data:
            synced = "✅" if item.get("synced_to_notebooklm") else "⏳"
            print(f"- {synced} {item.get('full_name')} (⭐ {item.get('stars', 0):,}) - {item.get('repo_url')}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
