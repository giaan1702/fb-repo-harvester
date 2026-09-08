import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("config_manager")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    "discord_webhook_url": "",
    "auto_crawl_enabled": True,
    "crawl_interval_hours": 6,
    "crawl_limit_per_channel": 3,
    "daily_report_enabled": True,
    "daily_report_time": "07:00",
    "last_crawl_time": None,
    "last_report_date": None,
    "github_token": ""
}

class ConfigManager:
    """Quản lý đọc/ghi cài đặt vận hành từ settings.json kết hợp biến môi trường."""

    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = Path(base_dir)
        self.settings_path = self.base_dir / "settings.json"
        self._ensure_file()

    def _ensure_file(self):
        if not self.settings_path.exists():
            self.save(DEFAULT_SETTINGS)

    def load(self) -> Dict[str, Any]:
        """Tải cài đặt kết hợp ưu tiên biến môi trường."""
        data = dict(DEFAULT_SETTINGS)
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    data.update(file_data)
            except Exception as e:
                logger.warning(f"Không thể đọc settings.json, dùng mặc định: {e}")

        # Ghi đè bằng biến môi trường nếu có
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            data["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
            data["telegram_enabled"] = True
        if os.getenv("TELEGRAM_CHAT_ID"):
            data["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
        if os.getenv("DISCORD_WEBHOOK_URL"):
            data["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL")
        if os.getenv("AUTO_CRAWL_ENABLED") is not None:
            data["auto_crawl_enabled"] = os.getenv("AUTO_CRAWL_ENABLED").lower() in ("true", "1", "yes")
        if os.getenv("CRAWL_INTERVAL_HOURS"):
            try:
                data["crawl_interval_hours"] = int(os.getenv("CRAWL_INTERVAL_HOURS"))
            except ValueError:
                pass
        if os.getenv("DAILY_REPORT_TIME"):
            data["daily_report_time"] = os.getenv("DAILY_REPORT_TIME")

        return data

    def save(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Lưu cài đặt mới vào settings.json."""
        current = self.load()
        current.update(new_settings)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            logger.info("Đã lưu thành công settings.json")
        except Exception as e:
            logger.error(f"Lỗi khi lưu settings.json: {e}")
        return current

    def update_key(self, key: str, value: Any):
        current = self.load()
        current[key] = value
        self.save(current)
