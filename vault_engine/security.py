import socket
import ipaddress
import time
import logging
from urllib.parse import urlparse
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger("vault_security")

# Danh sách hostname cấm tuyệt đối
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "instance-data",
}

def validate_safe_public_url(url: str) -> bool:
    """
    Xác minh URL an toàn, ngăn chặn tấn công SSRF (Server-Side Request Forgery).
    Từ chối toàn bộ IP nội bộ, loopback, link-local (Cloud metadata) và non-HTTP schemes.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL không hợp lệ hoặc bị rỗng")

    clean = url.strip()
    parsed = urlparse(clean)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Giao thức '{parsed.scheme}' không được phép. Chỉ chấp nhận HTTP/HTTPS.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL thiếu hostname hợp lệ")

    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith((".local", ".internal", ".lan")):
        raise ValueError(f"Hostname '{hostname}' nằm trong danh sách cấm truy cập nội bộ (SSRF)")

    # Kiểm tra nếu hostname là một địa chỉ IP trực tiếp
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        if _is_restricted_ip(ip_obj):
            raise ValueError(f"Địa chỉ IP '{ip_obj}' thuộc dải mạng nội bộ/hạn chế (SSRF)")
        return True
    except ValueError as e:
        # Nếu không phải IP string trực tiếp, phân giải DNS
        if "thuộc dải mạng nội bộ" in str(e):
            raise

    # Phân giải DNS và kiểm tra tất cả các IP trả về
    try:
        addr_info = socket.getaddrinfo(hostname_lower, None)
        if not addr_info:
            raise ValueError(f"Không thể phân giải tên miền: {hostname}")

        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if _is_restricted_ip(ip_obj):
                raise ValueError(f"Tên miền '{hostname}' phân giải về IP nội bộ '{ip_str}' bị cấm (SSRF)")
    except socket.gaierror:
        raise ValueError(f"Không thể phân giải tên miền: {hostname}")

    return True

def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Kiểm tra xem IP có thuộc dải mạng hạn chế hay không."""
    return (
        ip.is_private or
        ip.is_loopback or
        ip.is_link_local or
        ip.is_multicast or
        ip.is_reserved or
        ip.is_unspecified
    )

class SlidingWindowRateLimiter:
    """
    In-memory Sliding Window Rate Limiter không cần Redis.
    Tự động giải phóng bộ nhớ khi các window hết hạn.
    """
    def __init__(self, requests_per_minute: int = 20):
        self.rpm = requests_per_minute
        self.records: Dict[str, List[float]] = {}
        self.last_cleanup = time.time()

    def is_allowed(self, client_key: str) -> Tuple[bool, int]:
        """
        Kiểm tra xem client_key có được phép gọi tiếp hay không.
        Trả về: (được phép hay không, số giây cần chờ nếu bị limit)
        """
        now = time.time()
        self._periodic_cleanup(now)

        window_start = now - 60.0
        timestamps = self.records.get(client_key, [])
        # Lọc các timestamp trong vòng 60 giây gần nhất
        valid_ts = [t for t in timestamps if t > window_start]

        if len(valid_ts) >= self.rpm:
            retry_after = int(60.0 - (now - valid_ts[0])) + 1
            self.records[client_key] = valid_ts
            return False, max(1, retry_after)

        valid_ts.append(now)
        self.records[client_key] = valid_ts
        return True, 0

    def _periodic_cleanup(self, now: float):
        if now - self.last_cleanup > 120.0:
            window_start = now - 60.0
            expired_keys = [k for k, v in self.records.items() if not v or v[-1] <= window_start]
            for k in expired_keys:
                del self.records[k]
            self.last_cleanup = now

# Rate limiters riêng biệt cho các endpoint nhạy cảm
ingest_limiter = SlidingWindowRateLimiter(requests_per_minute=15)
explain_limiter = SlidingWindowRateLimiter(requests_per_minute=30)
scout_limiter = SlidingWindowRateLimiter(requests_per_minute=5)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Gắn các HTTP Security Headers chuẩn OWASP vào toàn bộ phản hồi."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
