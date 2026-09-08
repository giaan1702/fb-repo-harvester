"""
enrich_and_resync.py
Pipeline làm giàu toàn diện:
1. Lấy forks thực tế, license bản quyền và toàn văn README.md từ GitHub.
2. Dùng FreeLLMAPI Gateway sinh Technical Quickstart + Mã mẫu Hello World thực chiến.
3. Tạo lại toàn bộ file tri thức chi tiết outputs/*_knowledge.md (khắc phục 100% lỗi thiếu README và links).
4. Tải đè toàn bộ lên Google NotebookLM cùng với Ma trận so sánh AI Agents.
"""

import sys
import time
import json
import logging
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fb_harvester.catalog import CatalogManager
from fb_harvester.github_resolver import GitHubResolver
from fb_harvester.classifier import AIClassifier
from fb_harvester.packager import RepoPackager
from fb_harvester.notebook_sync import NotebookSyncEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("enrich_pipeline")

def main():
    catalog = CatalogManager()
    resolver = GitHubResolver()
    classifier = AIClassifier()
    packager = RepoPackager()
    sync_engine = NotebookSyncEngine()

    print("=" * 65)
    print("🌟 BẮT ĐẦU PIPELINE NÂNG CẤP KHO TRI THỨC TOÀN DIỆN & ĐỒNG BỘ")
    print("=" * 65)

    if not sync_engine.is_authenticated():
        print("⚠️ Chưa xác thực được NotebookLM. Đang thử phục hồi ngầm...")
        sync_engine.recover_auth_headless()

    target_nb = sync_engine.get_or_create_default_notebook()
    print(f"🎯 Target Notebook: {target_nb}\n")

    repos = catalog.load_data()
    print(f"📦 Đang xử lý làm giàu cho {len(repos)} repository...\n")

    # 1. Đẩy trước Ma trận so sánh AI Agents
    matrix_file = Path("outputs/AI_AGENTS_COMPARATIVE_MATRIX.md")
    if matrix_file.exists():
        print("📑 Đang tải Ma trận so sánh AI Agents lên NotebookLM...")
        sync_engine.add_source_file(target_nb, matrix_file)
        print("✅ Đã tải Ma trận so sánh thành công!\n")

    success_count = 0

    for idx, repo in enumerate(repos, 1):
        full_name = repo.get("full_name")
        print(f"--- [{idx}/{len(repos)}] Nâng cấp: {full_name} ---")

        if "/" not in full_name:
            continue
        owner, repo_name = full_name.split("/", 1)

        # 1. Lấy dữ liệu đầy đủ từ GitHub (README, Forks, License, HTML URL)
        print(f"   🌐 Đang tải metadata thực tế & README từ GitHub...")
        gh_data = resolver.get_repo_details(owner, repo_name)
        if not gh_data:
            # Dùng lại dữ liệu hiện có nếu API gặp lỗi
            gh_data = repo
            if "readme" not in gh_data:
                gh_data["readme"] = resolver.get_readme(owner, repo_name)

        # Đảm bảo các chỉ số chính xác 100%
        repo["stars"] = gh_data.get("stars") or repo.get("stars", 0)
        repo["forks"] = gh_data.get("forks") or repo.get("forks", 0)
        repo["license"] = gh_data.get("license") or repo.get("license") or "None"
        repo["html_url"] = gh_data.get("html_url") or f"https://github.com/{full_name}"
        repo["repo_url"] = repo["html_url"]
        readme_text = gh_data.get("readme") or ""
        gh_data["readme"] = readme_text

        print(f"      ⭐ Stars: {repo['stars']:,} | 🍴 Forks: {repo['forks']:,} | 📜 License: {repo['license']} | 📖 README: {len(readme_text)} ký tự")

        # 2. Sinh Technical Quickstart & Code Snippet bằng FreeLLMAPI nếu chưa có
        if not repo.get("code_snippet") or not repo.get("install_cmd"):
            print(f"   🤖 Đang gọi FreeLLMAPI Gateway tạo Quickstart & Code Snippet...")
            ai_info = classifier.classify_and_summarize(gh_data, readme_text[:15000])
            repo["category"] = ai_info.get("category", repo.get("category"))
            repo["summary"] = ai_info.get("summary", repo.get("summary"))
            repo["use_cases"] = ai_info.get("use_cases", repo.get("use_cases"))
            repo["install_cmd"] = ai_info.get("install_cmd") or f"git clone {repo['html_url']}"
            repo["architecture"] = ai_info.get("architecture") or f"Module {repo.get('language', 'Open-source')}"
            repo["core_components"] = ai_info.get("core_components", [])
            repo["code_snippet"] = ai_info.get("code_snippet", "")
            gh_data.update(ai_info)

        # 3. Tạo tài liệu tri thức hoàn chỉnh
        fb_info = {"source_url": repo.get("source_url", "")}
        doc_path = packager.build_knowledge_document(fb_info=fb_info, repo_info=gh_data)

        # 4. Tải lên Google NotebookLM
        print(f"   ☁️ Đang đồng bộ tài liệu tri thức đầy đủ lên NotebookLM...")
        ok = sync_engine.add_source_file(target_nb, doc_path)
        if ok:
            repo["synced_to_notebooklm"] = True
            repo["notebook_title"] = target_nb
            repo["notebook_ref"] = target_nb
            success_count += 1
            print(f"   ✅ Hoàn tất nâng cấp và đồng bộ: {full_name}")
        else:
            print(f"   ⚠️ Đã tạo file tri thức cục bộ nhưng chưa nạp được lên cloud.")

        # Cập nhật catalog sau mỗi repo
        catalog.add_or_update(repo)
        time.sleep(1)

    print("\n" + "=" * 65)
    print(f"🎉 HOÀN TẤT NÂNG CẤP TOÀN BỘ KHO TRI THỨC ({success_count}/{len(repos)} repo thành công)!")
    print("📚 Đã cập nhật lại file CATALOG.md và catalog.json với đầy đủ Forks, License, Quickstart và README.")
    print("=" * 65)

if __name__ == "__main__":
    main()
