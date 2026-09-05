import re
import logging
from typing import Optional, List
from urllib.parse import urlparse, parse_qs, unquote
import requests

logger = logging.getLogger("unshortener")

SHORTER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd", "rb.gy",
    "shorturl.at", "ow.ly", "buff.ly", "lnkd.in", "linktr.ee", "beacons.ai"
}

URL_REGEX = re.compile(r"https?://[^\s<>\"')]+")

def unwrap_facebook_redirect(url: str) -> str:
    """Bóc tách link thật từ link chuyển tiếp của Facebook (l.facebook.com/l.php?u=...)."""
    try:
        parsed = urlparse(url)
        if "facebook.com" in parsed.netloc and "/l.php" in parsed.path:
            qs = parse_qs(parsed.query)
            if "u" in qs:
                raw_target = qs["u"][0]
                return unquote(raw_target)
    except Exception as e:
        logger.debug(f"Không thể unwrap link Facebook: {e}")
    return url

def expand_short_url(url: str, timeout: int = 6) -> str:
    """Lần theo chuyển hướng (Follow HTTP redirects) để lấy URL đích cuối cùng."""
    # Xử lý link Facebook redirect trước
    url = unwrap_facebook_redirect(url)

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Nếu là domain rút gọn hoặc link cần follow
        is_shortener = any(domain.endswith(s) or domain == s for s in SHORTER_DOMAINS)
        if not is_shortener and "github.com" in domain:
            # Vẫn kiểm tra redirect nếu repo đã đổi tên
            pass

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }

        # Gửi HEAD request để theo dõi chuyển hướng nhanh chóng
        res = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if res.status_code < 400 and res.url:
            return res.url
        
        # Nếu HEAD bị chặn (405 hoặc 403), thử GET nhẹ với stream=True
        if res.status_code in (403, 405):
            res_get = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers, stream=True)
            return res_get.url

    except Exception as e:
        logger.debug(f"Không thể mở rộng link {url}: {e}")

    return url

def find_all_urls(text: str) -> List[str]:
    """Tìm tất cả các URL có trong văn bản."""
    if not text:
        return []
    matches = URL_REGEX.findall(text)
    # Làm sạch dấu câu ở đuôi URL
    cleaned = []
    for u in matches:
        u_clean = u.rstrip(".,;:!?)'\">")
        if u_clean not in cleaned:
            cleaned.append(u_clean)
    return cleaned
