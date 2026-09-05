import os
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fb_harvester.config_manager import ConfigManager

logger = logging.getLogger("notifier")

class Notifier:
    """Module quản lý thông báo, cảnh báo sự cố khẩn cấp (Alerts) và Báo cáo định kỳ (Daily Digest) qua Telegram/Discord."""

    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = Path(base_dir)
        self.config_mgr = ConfigManager(self.base_dir)

    def get_settings(self) -> Dict[str, Any]:
        return self.config_mgr.load()

    def send_telegram(self, text: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
        """Gửi tin nhắn trực tiếp qua Telegram Bot API (không phụ thuộc thư viện bên ngoài)."""
        settings = self.get_settings()
        bot_token = settings.get("telegram_bot_token", "").strip()
        chat_id = settings.get("telegram_chat_id", "").strip()

        if not bot_token or not chat_id:
            logger.warning("Telegram Bot Token hoặc Chat ID chưa được cấu hình.")
            return {"ok": False, "error": "Chưa cấu hình Telegram Bot Token hoặc Chat ID"}

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("ok"):
                    logger.info("Đã gửi tin nhắn Telegram thành công!")
                    return {"ok": True, "result": result}
                else:
                    logger.error(f"Telegram API trả về lỗi: {result}")
                    return {"ok": False, "error": result.get("description", "Unknown error")}
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            logger.error(f"Lỗi HTTP khi gửi Telegram: {e.code} - {err_msg}")
            # Thử gửi lại dạng văn bản thô nếu lỗi parse Markdown
            if parse_mode and "can't parse entities" in err_msg.lower():
                logger.info("Thử gửi lại tin nhắn dưới dạng plain text...")
                return self.send_telegram(text, parse_mode="")
            return {"ok": False, "error": f"HTTP {e.code}: {err_msg}"}
        except Exception as e:
            logger.error(f"Lỗi kết nối khi gửi Telegram: {e}")
            return {"ok": False, "error": str(e)}

    def send_discord(self, text: str) -> Dict[str, Any]:
        """Gửi tin nhắn qua Discord Webhook nếu được cấu hình."""
        settings = self.get_settings()
        webhook_url = settings.get("discord_webhook_url", "").strip()
        if not webhook_url:
            return {"ok": False, "error": "Chưa cấu hình Discord Webhook"}

        payload = {"content": text}
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "FBRepoHarvester/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return {"ok": True, "status": response.status}
        except Exception as e:
            logger.error(f"Lỗi gửi Discord Webhook: {e}")
            return {"ok": False, "error": str(e)}

    def send_alert(self, title: str, error_message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Gửi cảnh báo sự cố khẩn cấp (Incident Alert) tới quản trị viên."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        msg_lines = [
            f"🚨 *[SỰ CỐ VẬN HÀNH]*: {title}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"⏰ *Thời gian:* `{now_str}`",
            f"❌ *Chi tiết lỗi:*",
            f"```text\n{error_message[:500]}\n```"
        ]
        if context:
            msg_lines.append(f"🔍 *Ngữ cảnh tác vụ:* {context}")
        msg_lines.append("⚠️ *Hành động đề xuất:* Kiểm tra logs server hoặc cập nhật token đăng nhập.")

        full_msg = "\n".join(msg_lines)
        # Gửi Telegram
        res = self.send_telegram(full_msg)
        # Gửi Discord nếu có
        self.send_discord(f"🚨 **[SỰ CỐ VẬN HÀNH] {title}**\n{error_message}")
        return res

    def send_daily_digest(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gửi Báo Cáo Định Kỳ Hàng Ngày (Daily Digest) tổng hợp kết quả hoạt động."""
        now_str = datetime.now().strftime("%d/%m/%Y")
        
        total_repos = report_data.get("total_repos", 0)
        new_repos = report_data.get("new_repos_24h", [])
        total_channels = report_data.get("total_channels", 0)
        videos_crawled = report_data.get("videos_crawled_24h", 0)
        nlm_status = "🟢 Đã kết nối" if report_data.get("notebooklm_connected") else "🔴 Chưa đăng nhập"
        idea_highlight = report_data.get("idea_highlight", "")

        msg_lines = [
            f"📊 *[BÁO CÁO HÀNG NGÀY]* FB REPO HARVESTER",
            f"📅 *Ngày:* `{now_str}`",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"🩺 *Trạng thái:* {nlm_status}",
            f"📡 *Kênh theo dõi:* {total_channels} kênh",
            f"🎬 *Video đã duyệt 24h qua:* {videos_crawled} video",
            f"📚 *Tổng kho tri thức:* {total_repos} repositories",
            f"✨ *Repo mới phát hiện hôm nay:* {len(new_repos)} repos",
            f"━━━━━━━━━━━━━━━━━━━━━━"
        ]

        if new_repos:
            msg_lines.append("🌟 *TOP REPOSITORIES MỚI KHÁM PHÁ:*")
            for idx, r in enumerate(new_repos[:5], 1):
                name = r.get("full_name") or r.get("repo_name") or r.get("name") or "Unknown"
                desc = r.get("description", "Không có mô tả")[:90]
                url = r.get("repo_url") or r.get("html_url") or r.get("url") or f"https://github.com/{name}"
                cat = r.get("category", "General")
                msg_lines.append(f"{idx}. 🚀 *[{name}]({url})* `[{cat}]`\n   _{desc}_")
        else:
            msg_lines.append("ℹ️ _Không có repo mới nào được thêm trong 24h qua._")

        if idea_highlight:
            msg_lines.append(f"\n💡 *GỢI Ý TỪ CO-IDEATION PARTNER:*\n{idea_highlight}")

        msg_lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n👉 _Hệ thống tự động vận hành 24/7_")

        full_msg = "\n".join(msg_lines)
        res = self.send_telegram(full_msg)
        self.send_discord(full_msg)
        return res

    def test_connection(self) -> Dict[str, Any]:
        """Kiểm tra cấu hình và gửi tin nhắn kiểm thử."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        test_msg = (
            f"✅ *[KIỂM TRA KẾT NỐI THÀNH CÔNG]*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *FB Repo Harvester Operations Bot* đã sẵn sàng!\n"
            f"⏰ *Thời gian:* `{now_str}`\n"
            f"🔔 Bạn sẽ nhận được cảnh báo tức thời khi có sự cố và Báo cáo định kỳ lúc 07:00 sáng mỗi ngày."
        )
        return self.send_telegram(test_msg)
