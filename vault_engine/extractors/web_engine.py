import html
import re
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("web_engine")

class WebExtractor:
    def extract(self, url: str) -> Optional[Dict[str, Any]]:
        is_fb = "facebook.com" in url.lower() or "fb.watch" in url.lower()
        if is_fb:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

        try:
            resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            if resp.status_code == 404:
                return {"error": "HTTP_404", "status_code": 404}
            elif resp.status_code != 200:
                return {"error": f"HTTP_{resp.status_code}", "status_code": resp.status_code}
            
            # Ép chuẩn UTF-8 chống lỗi ký tự rác â (Mojibake)
            resp.encoding = resp.apparent_encoding or "utf-8"
            html_text = resp.text
        except Exception as e:
            logger.warning(f"Lỗi tải URL {url}: {e}")
            return {"error": str(e)}

        if is_fb:
            title = self._extract_fb_title(html_text)
            clean_content = self._extract_fb_content(html_text, url)
            comments = self._extract_fb_comments(html_text)
            return {
                "title": title,
                "content": clean_content[:25000],
                "comments": comments,
                "url": url
            }

        clean_content = self._extract_clean_text(html_text, url)
        title = self._extract_title(html_text)

        return {
            "title": title,
            "content": clean_content[:25000],
            "comments": [],
            "url": url
        }

    def _extract_clean_text(self, html: str, url: str) -> str:
        # Bước 1: Thử Trafilatura
        try:
            import trafilatura
            extracted = trafilatura.extract(
                html,
                url=url,
                include_links=True,
                include_images=False,
                include_tables=True,
                output_format="markdown"
            )
            if extracted and len(extracted.strip()) > 150:
                return extracted.strip()
        except Exception:
            pass

        # Bước 2: Fallback tách thô
        lines = []
        for line in html.splitlines():
            line = line.strip()
            if line and not line.startswith("<script") and not line.startswith("<style") and not line.startswith("<path"):
                clean = ""
                in_tag = False
                for char in line:
                    if char == "<":
                        in_tag = True
                    elif char == ">":
                        in_tag = False
                    elif not in_tag:
                        clean += char
                clean = clean.strip()
                if len(clean) > 20:
                    lines.append(clean)
        return "\n\n".join(lines[:100])

    def _extract_title(self, html: str) -> str:
        try:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return "Bài viết công nghệ"

    def _extract_fb_title(self, html_str: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.IGNORECASE | re.DOTALL)
        if m:
            raw_title = html.unescape(m.group(1).strip())
            clean_title = re.sub(r"\s*-\s*[^|]+(?:\s*\|\s*Facebook)?$", "", raw_title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r"\s*\|\s*Facebook$", "", clean_title, flags=re.IGNORECASE).strip()
            if clean_title:
                return clean_title
        og_t = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_str, re.IGNORECASE)
        if og_t:
            return html.unescape(og_t.group(1).strip())
        return "Bài viết Facebook công nghệ"

    def _extract_fb_content(self, html_str: str, url: str) -> str:
        desc = ""
        og_d = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', html_str, re.IGNORECASE)
        if og_d:
            desc = html.unescape(og_d.group(1).strip())
        else:
            m_d = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_str, re.IGNORECASE)
            if m_d:
                desc = html.unescape(m_d.group(1).strip())

        canon_m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', html_str, re.IGNORECASE)
        canon_post_url = canon_m.group(1).strip() if canon_m else url

        gh_links = re.findall(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+', html_str)
        gh_info = ""
        if gh_links:
            gh_info = f"\n\n**Mã nguồn / GitHub Repository:** {list(set(gh_links))[0]}"

        body = (
            f"**Nguồn bài đăng:** Facebook ({canon_post_url})\n\n"
            f"### Nội dung tóm tắt & Giới thiệu từ bài viết:\n\n"
            f"{desc}"
            f"{gh_info}"
        )
        return body

    def _extract_fb_comments(self, html_str: str) -> list[str]:
        """Trích xuất các bình luận tiềm năng hoặc link được ghim dưới bài viết Facebook"""
        comments = []
        # Tìm các link được nhắc trong body nhưng không nằm trong header
        comment_links = re.findall(r'https?://(?:github\.com|arxiv\.org|drive\.google\.com|t\.me)/[^\s"\'<>]+', html_str)
        for cl in list(set(comment_links)):
            comments.append(f"Liên kết chia sẻ trong bình luận: {cl}")
        return comments
