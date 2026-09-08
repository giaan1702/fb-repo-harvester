import os
import re
import requests
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

logger = logging.getLogger("github_engine")

BADGE_KEYWORDS = {
    "shields.io", "badge.fury.io", "badgen.net", "travis-ci", "codecov.io",
    "workflows", "actions", "pepy.tech", "hits.seeyoufarm", "license",
    "pypi.org", "discord.gg", "twitter.com", "slack.com", "buymeacoffee"
}

class GitHubExtractor:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")

    def extract(self, url: str) -> Optional[Dict[str, Any]]:
        owner, repo = self._parse_repo_slug(url)
        if not owner or not repo:
            return None

        # 1. Thử lấy metadata từ GitHub API
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "VaultEngine/3.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_data = {}
        default_branch = "main"
        try:
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                repo_data = resp.json()
                default_branch = repo_data.get("default_branch", "main")
            elif resp.status_code == 404:
                return {"error": "REPO_NOT_FOUND", "status_code": 404}
        except Exception as e:
            logger.warning(f"GitHub API error: {e}")

        # 2. Lấy README qua Raw CDN
        readme_content = self._fetch_raw_readme(owner, repo)

        # 3. Trích xuất tài liệu kiến trúc bổ sung (nếu có)
        extra_docs = self._fetch_extra_docs(owner, repo, default_branch)

        # 4. Bóc tách ảnh kiến trúc và biểu đồ benchmark thật
        visual_assets = self.extract_visual_assets(readme_content, owner, repo, default_branch)

        stars = repo_data.get("stargazers_count", 0)
        desc = repo_data.get("description", "") or ""
        topics = repo_data.get("topics", [])
        language = repo_data.get("language", "") or "Markdown"

        clean_text = f"# {owner}/{repo}\n\n"
        if desc:
            clean_text += f"> {desc}\n\n"
        clean_text += f"* **Stars:** {stars:,} | **Language:** {language}\n"
        if topics:
            clean_text += f"* **Topics:** {', '.join(topics)}\n\n"
        clean_text += f"\n## README\n\n{readme_content}\n"
        if extra_docs:
            clean_text += f"\n## TÀI LIỆU KIẾN TRÚC BỔ SUNG\n\n{extra_docs}"

        return {
            "title": f"{owner}/{repo}",
            "description": desc,
            "stars": stars,
            "topics": topics,
            "language": language,
            "content": clean_text[:35000],
            "raw_readme": readme_content[:25000],
            "visual_assets": visual_assets,
            "github_repo": f"https://github.com/{owner}/{repo}",
            "default_branch": default_branch
        }

    def _parse_repo_slug(self, url: str) -> tuple[Optional[str], Optional[str]]:
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            return None, None
        owner = match.group(1)
        repo = match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    _parse_repo_info = _parse_repo_slug

    def _fetch_raw_readme(self, owner: str, repo: str) -> str:
        for branch in ["main", "master", "develop"]:
            cdn_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                r = requests.get(cdn_url, timeout=6)
                if r.status_code == 200 and len(r.text.strip()) > 50:
                    return r.text.strip()
            except Exception:
                continue
        return "Không thể tải README tự động."

    def _fetch_extra_docs(self, owner: str, repo: str, branch: str = "main") -> str:
        """Thử kéo các file tài liệu kiến trúc chuyên sâu trong repo."""
        candidates = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/ARCHITECTURE.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/docs/architecture.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/docs/overview.md"
        ]
        docs_text = []
        for url in candidates:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200 and len(r.text.strip()) > 80:
                    docs_text.append(r.text.strip())
            except Exception:
                continue
        return "\n\n---\n\n".join(docs_text)

    def extract_visual_assets(self, text: str = "", owner: str = "", repo: str = "", default_branch: str = "main", markdown_text: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Bóc tách các ảnh sơ đồ luồng (architecture diagram), biểu đồ benchmark
        từ Markdown/HTML của repo và chuẩn hóa sang raw GitHub CDN URL.
        Lọc bỏ 100% badges và tracking icons.
        """
        text = markdown_text if markdown_text is not None else text
        if not text:
            return []

        raw_assets: List[Dict[str, str]] = []
        seen_urls = set()

        # Regex Markdown: ![alt](url)
        md_img_re = re.compile(r'!\[(.*?)\]\((.*?)\)')
        for m in md_img_re.finditer(text):
            alt = m.group(1).strip()
            src = m.group(2).strip().split(" ")[0].strip("\"'")
            raw_assets.append({"alt": alt, "src": src})

        # Regex HTML: <img ... src="..." ...>
        html_img_re = re.compile(r'<img[^>]+src=["\'](.*?)["\'][^>]*>', re.IGNORECASE)
        for m in html_img_re.finditer(text):
            src = m.group(1).strip()
            raw_assets.append({"alt": "Repo Asset", "src": src})

        valid_assets = []
        base_cdn = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/"

        for item in raw_assets:
            src = item["src"]
            alt = item.get("alt", "")
            src_lower = src.lower()

            # Lọc badge rác
            if any(bad in src_lower for bad in BADGE_KEYWORDS):
                continue
            if not any(ext in src_lower for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"]):
                continue

            # Chuẩn hóa URL sang absolute CDN
            if src.startswith("http://") or src.startswith("https://"):
                # Nếu là github.com/.../blob/... -> chuyển thành raw.githubusercontent.com
                if "github.com" in src and "/blob/" in src:
                    final_url = src.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                else:
                    final_url = src
            else:
                # Relative path: ./docs/images/arch.png -> cdn
                clean_rel = src.lstrip("./").lstrip("/")
                final_url = urljoin(base_cdn, clean_rel)

            if final_url in seen_urls:
                continue
            seen_urls.add(final_url)

            # Phân loại asset
            category = "DEMO_VISUAL"
            combined_label = f"{alt} {src}".lower()
            if any(k in combined_label for k in ["arch", "diagram", "flow", "overview", "pipeline", "topology", "structure", "system"]):
                category = "ARCHITECTURE_DIAGRAM"
            elif any(k in combined_label for k in ["benchmark", "eval", "latency", "throughput", "comparison", "speed", "perf"]):
                category = "BENCHMARK_CHART"

            valid_assets.append({
                "url": final_url,
                "caption": alt or "Sơ đồ kiến trúc / Đo lường của dự án",
                "category": category
            })

        return valid_assets

    def search_repo_by_name(self, name: str) -> Optional[str]:
        """Tự động tìm kiếm repo GitHub khi bài viết chỉ nhắc tên (ví dụ: 'vllm', 'crawl4ai')"""
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', ' ', name).strip()
        if not clean_name or len(clean_name) < 2:
            return None

        search_url = f"https://api.github.com/search/repositories?q={clean_name}&sort=stars&order=desc&per_page=1"
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "VaultEngine/3.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            r = requests.get(search_url, headers=headers, timeout=8)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    top_repo = items[0]["full_name"]
                    return f"https://github.com/{top_repo}"
        except Exception as e:
            logger.warning(f"Lỗi tìm kiếm repo '{clean_name}': {e}")
        return None
