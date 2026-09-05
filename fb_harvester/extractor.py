import re
import json
import logging
from typing import Optional, Dict, Any, List
import yt_dlp

from fb_harvester.unshortener import expand_short_url, find_all_urls, unwrap_facebook_redirect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fb_extractor")

GITHUB_URL_REGEX = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)",
    re.IGNORECASE
)

CLEANUP_CHARS = ".,;:!?)'\">"

class FacebookExtractor:
    """Trích xuất thông tin video/post từ Facebook, giải mã link rút gọn và quét bình luận."""

    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

    def extract_github_links(self, text: str) -> List[Dict[str, str]]:
        """Tìm tất cả các link GitHub trong text, bao gồm cả giải mã link rút gọn & chuyển tiếp."""
        if not text:
            return []

        results = []
        seen = set()

        # 1. Tìm các link GitHub trực tiếp
        direct_matches = GITHUB_URL_REGEX.findall(text)
        for owner, repo in direct_matches:
            owner = owner.strip(CLEANUP_CHARS)
            repo = repo.strip(CLEANUP_CHARS)
            if repo.endswith(".git"):
                repo = repo[:-4]

            if owner.lower() in ("topics", "features", "explore", "trending", "about", "site"):
                continue

            full_name = f"{owner}/{repo}".lower()
            if full_name not in seen:
                seen.add(full_name)
                results.append({
                    "owner": owner,
                    "repo": repo,
                    "full_name": f"{owner}/{repo}",
                    "url": f"https://github.com/{owner}/{repo}"
                })

        # 2. Tìm tất cả các URL khác để giải mã link rút gọn / link l.facebook.com
        all_urls = find_all_urls(text)
        for u in all_urls:
            # Bỏ qua nếu đã là link github trực tiếp
            if "github.com" in u.lower() and "/l.php" not in u.lower():
                continue

            # Mở rộng link rút gọn
            expanded = expand_short_url(u)
            if "github.com" in expanded.lower():
                gh_matches = GITHUB_URL_REGEX.findall(expanded)
                for owner, repo in gh_matches:
                    owner = owner.strip(CLEANUP_CHARS)
                    repo = repo.strip(CLEANUP_CHARS)
                    if repo.endswith(".git"):
                        repo = repo[:-4]

                    if owner.lower() in ("topics", "features", "explore", "trending", "about", "site"):
                        continue

                    full_name = f"{owner}/{repo}".lower()
                    if full_name not in seen:
                        seen.add(full_name)
                        logger.info(f"🎯 Đã giải mã link rút gọn: {u} -> https://github.com/{owner}/{repo}")
                        results.append({
                            "owner": owner,
                            "repo": repo,
                            "full_name": f"{owner}/{repo}",
                            "url": f"https://github.com/{owner}/{repo}"
                        })

        return results

    def fetch_video_comments_with_playwright(self, video_url: str) -> List[str]:
        """Sử dụng Playwright để lấy nội dung bình luận ghim / top comments của video."""
        comments = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                page.goto(video_url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                # Bấm tắt popup nếu có
                self._dismiss_popups(page)

                # Cuộn nhẹ để load khung bình luận
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1500)

                # Tìm các thẻ comment
                comment_nodes = page.query_selector_all("div[role='article'], div[dir='auto']")
                for node in comment_nodes[:15]:
                    try:
                        txt = (node.inner_text() or "").strip()
                        if txt and len(txt) > 5 and txt not in comments:
                            # Ưu tiên các comment có link hoặc nhắc đến repo
                            if "http" in txt or "github" in txt or "link" in txt.lower():
                                comments.append(txt)
                    except Exception:
                        pass
                browser.close()
        except Exception as e:
            logger.debug(f"Không thể lấy comment qua Playwright: {e}")
        return comments

    def _dismiss_popups(self, page):
        """Tắt các popup phiền toái trên Facebook."""
        selectors = [
            "div[aria-label='Đóng']", "div[aria-label='Close']",
            "[aria-label='Not now']", "div[role='button']:has-text('Không phải bây giờ')",
            "div[role='button']:has-text('Đóng')"
        ]
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

    def extract_from_url(self, url: str) -> Dict[str, Any]:
        """Lấy thông tin từ URL (Hỗ trợ cả Facebook URL lẫn link GitHub trực tiếp)."""
        # Nếu là link GitHub trực tiếp
        direct_github = self.extract_github_links(url)
        if direct_github:
            logger.info(f"Phát hiện liên kết GitHub trực tiếp: {url}")
            return {
                "source_url": url,
                "title": f"Direct GitHub: {direct_github[0]['full_name']}",
                "description": "",
                "uploader": "Direct Link",
                "upload_date": "",
                "github_links": direct_github,
                "keywords": []
            }

        logger.info(f"Đang bóc tách thông tin từ Facebook URL: {url}")
        data = {
            "source_url": url,
            "title": "",
            "description": "",
            "uploader": "",
            "upload_date": "",
            "duration": 0,
            "thumbnail": "",
            "github_links": [],
            "keywords": []
        }

        # 1. Dùng yt-dlp bóc tách caption & video info
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    data["title"] = info.get("title") or ""
                    data["description"] = info.get("description") or ""
                    data["uploader"] = info.get("uploader") or info.get("channel") or ""
                    data["upload_date"] = info.get("upload_date") or ""
                    data["duration"] = info.get("duration") or 0
                    data["thumbnail"] = info.get("thumbnail") or ""

                    combined_text = f"{data['title']}\n{data['description']}"
                    data["github_links"] = self.extract_github_links(combined_text)
                    data["keywords"] = self.extract_keywords(combined_text)
                    logger.info(f"Tìm thấy {len(data['github_links'])} link GitHub trong nội dung video.")

        except Exception as e:
            logger.warning(f"yt-dlp không thể tải trực tiếp video Facebook: {e}")
            data["github_links"] = self.extract_github_links(url)

        # 2. Nếu caption chưa có link GitHub, quét thêm bình luận ghim / top comments!
        if not data["github_links"] and ("/watch" in url or "/reel/" in url or "/videos/" in url):
            logger.info("Không thấy link GitHub trong caption. Đang quét bình luận ghim của video...")
            top_comments = self.fetch_video_comments_with_playwright(url)
            for c in top_comments:
                links = self.extract_github_links(c)
                for l in links:
                    if l["full_name"] not in [x["full_name"] for x in data["github_links"]]:
                        logger.info(f"🎉 TÌM THẤY LINK REPO TRONG BÌNH LUẬN: {l['url']}")
                        data["github_links"].append(l)

        return data

    def extract_from_text(self, text: str, source_url: str = "") -> Dict[str, Any]:
        """Trích xuất khi người dùng cung cấp trực tiếp text/caption copy từ FB."""
        github_links = self.extract_github_links(text)
        keywords = self.extract_keywords(text)
        return {
            "source_url": source_url,
            "title": text.split("\n")[0][:80] if text else "Manual Note",
            "description": text,
            "uploader": "Manual Input",
            "github_links": github_links,
            "keywords": keywords
        }

    def extract_keywords(self, text: str) -> List[str]:
        """Trích xuất các từ khóa công nghệ, ưu tiên tên riêng của tool."""
        if not text:
            return []

        priority_candidates = []
        secondary_candidates = []

        hashtags = re.findall(r"#([a-zA-Z0-9_\-]+)", text)
        priority_candidates.extend(hashtags)

        named_tools = re.findall(r"\b[A-Za-z]+[A-Z0-9]+[A-Za-z0-9]*\b", text)
        priority_candidates.extend(named_tools)

        tool_patterns = [
            r"(?:tool|công cụ|repo|thư viện|dự án|project|mã nguồn mở|framework)\s+([A-Za-z0-9_\-\.]+)",
            r"([A-Za-z0-9_\-\.]+)\s+(?:tool|framework|library)"
        ]
        for pattern in tool_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            secondary_candidates.extend(matches)

        stopwords = {"facebook", "youtube", "tiktok", "video", "link", "github", "https", "http", "backend", "frontend", "web"}
        cleaned = []
        for c in priority_candidates + secondary_candidates:
            c_clean = c.strip(CLEANUP_CHARS)
            if len(c_clean) > 2 and c_clean.lower() not in stopwords:
                if c_clean not in cleaned:
                    cleaned.append(c_clean)

        return cleaned
