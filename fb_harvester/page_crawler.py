import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("page_crawler")

def normalize_fb_page_url(url: str) -> Tuple[str, List[str], str]:
    """
    Chuẩn hóa URL Facebook thành URL gốc và danh sách target_urls để quét (reels, videos, main).
    Xử lý thông minh cả 2 loại:
    1. Dạng Profile ID: https://www.facebook.com/profile.php?id=61591295115405
    2. Dạng Page Username: https://www.facebook.com/lachcachai
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    parsed = urlparse(url)
    base_origin = f"{parsed.scheme or 'https'}://{parsed.netloc or 'www.facebook.com'}"

    # Trường hợp 1: Dạng Profile ID (profile.php?id=...)
    if "profile.php" in parsed.path:
        qs = parse_qs(parsed.query)
        user_id = qs.get("id", [""])[0]
        if user_id:
            clean_url = f"{base_origin}/profile.php?id={user_id}"
            target_urls = [
                f"{clean_url}&sk=reels_tab",
                f"{clean_url}&sk=videos",
                clean_url
            ]
            return clean_url, target_urls, f"Profile {user_id}"

    # Trường hợp 2: Dạng Page/User chuẩn (facebook.com/username)
    clean_path = parsed.path.rstrip("/")
    for sub in ["/reels", "/videos", "/photos", "/about", "/posts"]:
        if clean_path.endswith(sub):
            clean_path = clean_path[:-len(sub)]
            break

    clean_url = f"{base_origin}{clean_path}"
    target_urls = [
        f"{clean_url}/reels",
        f"{clean_url}/videos",
        clean_url
    ]
    name_slug = clean_path.strip("/").split("/")[-1] or "Facebook Page"
    return clean_url, target_urls, name_slug

class PageCrawler:
    """Tự động cào danh sách video/reels mới nhất từ các Fanpage hoặc Profile Facebook."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.channels_file = self.base_dir / "channels.json"
        self._ensure_channels()

    def _ensure_channels(self):
        if not self.channels_file.exists():
            self.save_channels([])

    def load_channels(self) -> List[Dict[str, Any]]:
        try:
            with open(self.channels_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return []

    def save_channels(self, channels: List[Dict[str, Any]]):
        with open(self.channels_file, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)

    def add_channel(self, url: str, name: str = "", category: str = "General") -> bool:
        channels = self.load_channels()
        clean_url, _, default_name = normalize_fb_page_url(url)

        for ch in channels:
            if ch.get("url", "").rstrip("/").lower() == clean_url.lower():
                logger.info(f"Kênh đã tồn tại trong danh sách: {clean_url}")
                return False

        display_name = name.strip() if name.strip() else default_name

        channels.append({
            "name": display_name,
            "url": clean_url,
            "category": category
        })
        self.save_channels(channels)
        logger.info(f"Đã thêm kênh theo dõi mới: {display_name} ({clean_url})")
        return True

    def update_channel_name(self, url: str, new_name: str):
        """Cập nhật tên hiển thị thực tế sau khi cào thành công."""
        if not new_name or new_name.lower().startswith("profile"):
            return
        channels = self.load_channels()
        changed = False
        for ch in channels:
            if ch.get("url", "").rstrip("/").lower() == url.rstrip("/").lower():
                if ch.get("name") != new_name:
                    ch["name"] = new_name
                    changed = True
        if changed:
            self.save_channels(channels)
            logger.info(f"Đã tự động cập nhật tên kênh thành: {new_name}")

    def delete_channel(self, url: str) -> bool:
        """Xóa một kênh khỏi danh sách theo dõi."""
        channels = self.load_channels()
        clean_url, _, _ = normalize_fb_page_url(url)
        new_channels = [ch for ch in channels if ch.get("url", "").rstrip("/").lower() != clean_url.lower()]
        if len(new_channels) < len(channels):
            self.save_channels(new_channels)
            logger.info(f"Đã xóa kênh: {url}")
            return True
        return False

    def dismiss_popups(self, page):
        """Tự động phát hiện và dọn dẹp các popup đăng nhập/chặn cuộn của Facebook."""
        selectors = [
            "div[aria-label='Đóng']", "div[aria-label='Close']",
            "[aria-label='Not now']", "div[role='button']:has-text('Không phải bây giờ')",
            "div[role='button']:has-text('Đóng')", "div[role='dialog'] [aria-label='Close']"
        ]
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

    def fetch_videos_from_page(self, page_url: str, limit: int = 10, headless: bool = True) -> List[Dict[str, str]]:
        """Sử dụng Playwright để mở trang video của Page/Profile và lấy danh sách video/reels."""
        from playwright.sync_api import sync_playwright

        clean_url, target_urls, default_name = normalize_fb_page_url(page_url)

        found_videos = []
        seen_links = set()

        logger.info(f"Bắt đầu quét video từ Page/Profile: {clean_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            detected_name = ""

            for target in target_urls:
                try:
                    logger.info(f"Đang truy cập: {target}")
                    page.goto(target, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    # Tự động dọn dẹp popup nếu có
                    self.dismiss_popups(page)

                    # Đọc tên thực tế của Profile/Page từ Title trang
                    if not detected_name:
                        try:
                            title_text = page.title()
                            if title_text and "Facebook" in title_text:
                                real_name = title_text.split("|")[0].split("-")[0].strip()
                                if real_name and len(real_name) > 1 and real_name != "Facebook":
                                    detected_name = real_name
                                    self.update_channel_name(clean_url, real_name)
                        except Exception:
                            pass

                    # Cuộn trang thông minh (Smart Infinite Scroll)
                    scroll_attempts = 0
                    max_scrolls = 6

                    while len(found_videos) < limit and scroll_attempts < max_scrolls:
                        self.dismiss_popups(page)
                        page.mouse.wheel(0, 1200)
                        page.wait_for_timeout(1200)
                        scroll_attempts += 1

                        # Quét tất cả thẻ <a> trên trang sau mỗi nhịp cuộn
                        links = page.query_selector_all("a[href]")
                        for a in links:
                            try:
                                href = a.get_attribute("href") or ""
                                if not href:
                                    continue

                                # Bắt link video / reel / watch / post
                                if ("/reel/" in href or "/watch" in href or "/videos/" in href):
                                    full_url = href
                                    if full_url.startswith("/"):
                                        full_url = "https://www.facebook.com" + full_url

                                    parsed = urlparse(full_url)
                                    clean_path = parsed.path.rstrip("/")
                                    
                                    clean_item_url = ""
                                    if "/reel/" in clean_path:
                                        clean_item_url = f"https://www.facebook.com{clean_path}"
                                    elif "/watch" in clean_path:
                                        if "v=" in parsed.query:
                                            v_id = [q.split("=")[1] for q in parsed.query.split("&") if q.startswith("v=")]
                                            if v_id:
                                                clean_item_url = f"https://www.facebook.com/watch/?v={v_id[0]}"
                                    elif "/videos/" in clean_path:
                                        clean_item_url = f"https://www.facebook.com{clean_path}"

                                    if clean_item_url and clean_item_url not in seen_links:
                                        seen_links.add(clean_item_url)
                                        title = (a.inner_text() or "").strip().replace("\n", " ")
                                        found_videos.append({
                                            "url": clean_item_url,
                                            "title": title,
                                            "page_url": clean_url,
                                            "creator_name": detected_name or default_name
                                        })

                                        if len(found_videos) >= limit:
                                            break
                            except Exception:
                                pass

                    if found_videos:
                        break

                except Exception as e:
                    logger.warning(f"Lỗi khi quét {target}: {e}")

            browser.close()

        logger.info(f"Tìm thấy {len(found_videos)} video từ page {clean_url}")
        return found_videos
