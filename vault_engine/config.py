import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# Prioritize IPv4 on Windows to prevent network timeouts when IPv6 routes drop
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_first_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in res if r[0] == socket.AF_INET]
    ipv6 = [r for r in res if r[0] == socket.AF_INET6]
    return (ipv4 + ipv6) if ipv4 else res
socket.getaddrinfo = _ipv4_first_getaddrinfo

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = os.getenv("VAULT_DB_PATH", str(DATA_DIR / "vault.db"))
DRIVE_OUTPUT_DIR = Path(os.getenv("DRIVE_OUTPUT_DIR", str(BASE_DIR / "outputs" / "KnowledgeVault")))
DRIVE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
RMKO_GATEWAY_URL = os.getenv("RMKO_GATEWAY_URL", "https://rmko-gateway.onrender.com")

# Fallback từ settings.json nếu .env chưa có
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    import json
    for p in [BASE_DIR / "settings.json", BASE_DIR / "archive" / "legacy_fb_harvester" / "settings.json"]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN or s_data.get("telegram_bot_token", "")
                    TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID or s_data.get("telegram_chat_id", "")
            except Exception:
                pass

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "7860"))
DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", f"http://{SERVER_HOST}:{SERVER_PORT}")

SCOUT_ENABLED = os.getenv("SCOUT_ENABLED", "true").lower() in ("true", "1", "yes")
SCOUT_INTERVAL_SECONDS = int(os.getenv("SCOUT_INTERVAL_SECONDS", "14400"))