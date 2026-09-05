import os
import re
import json
import base64
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger("github_resolver")

class GitHubResolver:
    """Truy vấn, thẩm định và tải thông tin chi tiết về GitHub Repository."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "FB-Repo-Harvester/1.0"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get_repo_details(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Lấy metadata chi tiết của một repo."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            res = requests.get(url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                readme_content = self.get_readme(owner, repo)
                return {
                    "owner": data.get("owner", {}).get("login", owner),
                    "name": data.get("name", repo),
                    "full_name": data.get("full_name", f"{owner}/{repo}"),
                    "html_url": data.get("html_url"),
                    "description": data.get("description") or "Không có mô tả.",
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "open_issues": data.get("open_issues_count", 0),
                    "language": data.get("language") or "Unknown",
                    "topics": data.get("topics", []),
                    "license": (data.get("license") or {}).get("spdx_id") or "None",
                    "default_branch": data.get("default_branch", "main"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "clone_url": data.get("clone_url"),
                    "readme": readme_content
                }
            elif res.status_code == 404:
                logger.warning(f"Không tìm thấy repo: {owner}/{repo}")
            else:
                logger.error(f"Lỗi GitHub API ({res.status_code}): {res.text[:200]}")
        except Exception as e:
            logger.error(f"Lỗi khi gọi GitHub API: {e}")
        return None

    def search_repo(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Tìm kiếm repo theo từ khóa hoặc tên công cụ (sắp xếp theo số stars cao nhất)."""
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit
        }
        results = []
        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=15)
            if res.status_code == 200:
                items = res.json().get("items", [])
                for item in items:
                    results.append({
                        "owner": item["owner"]["login"],
                        "name": item["name"],
                        "full_name": item["full_name"],
                        "html_url": item["html_url"],
                        "description": item.get("description") or "",
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language") or "Unknown",
                        "topics": item.get("topics", []),
                        "clone_url": item.get("clone_url")
                    })
        except Exception as e:
            logger.error(f"Lỗi tìm kiếm GitHub: {e}")
        return results

    def get_readme(self, owner: str, repo: str) -> str:
        """Tải nội dung file README.md của repo."""
        # Thử lấy từ raw github user content trước (nhanh và không bị rate limit)
        for branch in ["main", "master"]:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                r = requests.get(raw_url, timeout=10)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass

        # Fallback qua API
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                content = res.json().get("content", "")
                return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"Không lấy được README qua API: {e}")
        return ""
