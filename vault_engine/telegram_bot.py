import re
import json
import time
import logging
import threading
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List
from vault_engine.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH, DASHBOARD_BASE_URL
)
from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, canonicalize_url, detect_source_type
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.youtube_engine import YouTubeExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.extractors.context_scout import ContextScout
from vault_engine.pipeline import GeminiReflectivePipeline

logger = logging.getLogger("telegram_bot")

URL_REGEX = re.compile(r"https?://[^\s<>\"']+")

class TelegramBot:
    def __init__(self, token: Optional[str] = None, default_chat_id: Optional[str] = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.default_chat_id = str(default_chat_id or TELEGRAM_CHAT_ID or "")
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.db = DatabaseManager(db_path=DB_PATH)
        self.ingest = IngestManager(db=self.db)
        self.pipeline = GeminiReflectivePipeline()
        self.github_ext = GitHubExtractor()
        self.youtube_ext = YouTubeExtractor()
        self.web_ext = WebExtractor()
        self.context_scout = ContextScout(github_ext=self.github_ext, web_ext=self.web_ext, youtube_ext=self.youtube_ext)
        self._running = False
        self._poll_thread = None

    def send_message(self, text: str, chat_id: Optional[str] = None, reply_to_message_id: Optional[int] = None, parse_mode: str = "HTML", reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        cid = chat_id or self.default_chat_id
        if not self.token or not cid:
            logger.warning("Không thể gửi tin nhắn Telegram: Thiếu token hoặc chat_id")
            return False

        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return bool(res.get("ok"))
        except Exception as e:
            if parse_mode:
                try:
                    payload.pop("parse_mode", None)
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        return bool(res.get("ok"))
                except Exception:
                    pass
            logger.error(f"Lỗi gửi tin nhắn Telegram: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> bool:
        if not self.token:
            return False
        url = f"{self.api_base}/answerCallbackQuery"
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return bool(res.get("ok"))
        except Exception as e:
            logger.warning(f"Lỗi answerCallbackQuery: {e}")
            return False

    def get_updates(self, offset: Optional[int] = None, timeout: int = 15) -> List[Dict[str, Any]]:
        if not self.token:
            return []
        url = f"{self.api_base}/getUpdates?timeout={timeout}"
        if offset is not None:
            url += f"&offset={offset}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VaultTelegramBot/3.0"})
            with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            # Timeout bình thường khi long-polling không có tin mới
            if "timed out" not in str(e).lower():
                logger.warning(f"Lỗi khi getUpdates Telegram: {e}")
        return []

    def format_completion_message(self, item: Dict[str, Any], item_id: int) -> tuple:
        title = item.get("title", "Bài viết mới")
        cat = item.get("category", "Tech")
        arch = item.get("archetype", "KNOWLEDGE")
        score = item.get("practical_score", 8)
        reason = item.get("score_reason", "Giá trị kỹ thuật cao.")
        summary = item.get("short_summary", "")
        tech_list = item.get("tech_stack", [])
        tech_str = ", ".join(f"<code>{t}</code>" for t in tech_list[:5]) if tech_list else "<i>Đang cập nhật</i>"
        
        gotchas = item.get("gotchas_and_risks", [])
        gotchas_str = ""
        if gotchas:
            gotchas_str = "\n⚠️ <b>Gotchas & Rủi ro:</b>\n" + "\n".join(f"• {g}" for g in gotchas[:3])

        link = f"{DASHBOARD_BASE_URL}/?id={item_id}"

        msg = (
            f"📥 <b>PHÂN TÍCH HOÀN TẤT (CHỜ DUYỆT SƠ KHẢO)</b>\n\n"
            f"📌 <b>{title}</b>\n"
            f"🏷️ #{cat} | 🏛️ #{arch}\n"
            f"⭐ Điểm thực chiến: <b>{score}/10</b>\n"
            f"💬 <i>{reason}</i>\n\n"
            f"🛠️ <b>Tech Stack:</b> {tech_str}\n"
            f"{gotchas_str}\n\n"
            f"📝 <b>Tóm tắt đòn bẩy 20/80:</b>\n{summary}\n\n"
            f"<i>Bấm nút bên dưới để Đưa vào Não Bộ (tự động hợp nhất & sinh quy tắc) hoặc Loại Bỏ:</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "🧠 Duyệt Vào Não", "callback_data": f"brain:approve:{item_id}"},
                    {"text": "🗑️ Loại Bỏ", "callback_data": f"brain:reject:{item_id}"}
                ],
                [
                    {"text": "📖 Đọc trên Dashboard", "url": link}
                ]
            ]
        }
        return msg, reply_markup

    def _is_authorized(self, chat_id: str) -> bool:
        """Kiểm tra quyền truy cập của người gửi tin nhắn Telegram."""
        if not self.default_chat_id:
            return True
        return str(chat_id) == str(self.default_chat_id)

    def process_url_task(self, raw_url: str, chat_id: str, reply_to_message_id: Optional[int] = None):
        clean_url = canonicalize_url(raw_url)
        stype = detect_source_type(clean_url)

        # 0. Phòng thủ SSRF (Server-Side Request Forgery)
        try:
            from vault_engine.security import validate_safe_public_url
            validate_safe_public_url(clean_url)
        except ValueError as ssrf_err:
            logger.warning(f"Chặn liên kết nguy hiểm (SSRF) từ Telegram chat {chat_id}: {clean_url} - {ssrf_err}")
            self.send_message(
                f"🛡️ <b>Từ chối xử lý liên kết (Bảo Mật SSRF):</b>\n<code>{clean_url}</code>\n<i>{ssrf_err}</i>",
                chat_id=chat_id,
                reply_to_message_id=reply_to_message_id
            )
            return

        try:
            # 1. Trinh sát & Khai phá bối cảnh đa tầng (Context Scout Agent)
            dossier = self.context_scout.build_unified_dossier(clean_url, stype)
            if dossier.error:
                self.send_message(
                    f"❌ <b>Lỗi bóc tách nội dung:</b>\nURL: <code>{clean_url}</code>\nChi tiết: {dossier.error}",
                    chat_id=chat_id,
                    reply_to_message_id=reply_to_message_id
                )
                return

            # 2. Chạy Gemini Pipeline
            item_schema = self.pipeline.process_content(
                clean_content=dossier,
                canonical_url=clean_url,
                source_type=stype,
                title_hint=dossier.title
            )

            # 3. Lưu DB với trạng thái INBOX sơ khảo
            vault_payload = item_schema.model_dump()
            from vault_engine.ingest import generate_url_hash
            vault_payload["url_hash"] = generate_url_hash(clean_url)
            vault_payload["canonical_url"] = getattr(dossier, "identified_repo_url", None) or clean_url
            vault_payload["source_type"] = stype
            vault_payload["curation_status"] = "INBOX"

            item_id = self.db.insert_vault_item(vault_payload)

            # 4. Sinh vector embedding cho Hybrid Search
            try:
                from vault_engine.embedding import get_embedding
                content_to_embed = f"{item_schema.title}. {item_schema.short_summary}. Tech: {' '.join(item_schema.tech_stack)}"
                vec = get_embedding(content_to_embed)
                if vec:
                    self.db.save_embedding(item_id, vec)
            except Exception as emb_err:
                logger.warning(f"Không thể sinh embedding cho item {item_id}: {emb_err}")

            # 5. Gửi kết quả về Telegram kèm nút Duyệt 1-chạm
            success_msg, reply_markup = self.format_completion_message(vault_payload, item_id)
            self.send_message(success_msg, chat_id=chat_id, reply_to_message_id=reply_to_message_id, reply_markup=reply_markup)
            logger.info(f"Đã xử lý và thông báo thành công item {item_id} (INBOX) về Telegram chat {chat_id}")

        except Exception as e:
            logger.error(f"Lỗi khi xử lý URL {clean_url}: {e}", exc_info=True)
            self.send_message(
                f"❌ <b>Lỗi phân tích bài viết:</b>\nURL: <code>{clean_url}</code>\nLỗi: <i>{str(e)}</i>",
                chat_id=chat_id,
                reply_to_message_id=reply_to_message_id
            )

    def handle_callback_query(self, cb: Dict[str, Any]):
        """Xử lý sự kiện bấm nút Inline Keyboard từ người dùng trên Telegram."""
        cb_id = cb.get("id")
        data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        from_id = str(cb.get("from", {}).get("id", ""))
        msg_id = message.get("message_id")

        # Kiểm tra phân quyền truy cập
        if not self._is_authorized(chat_id) and not self._is_authorized(from_id):
            logger.warning(f"Từ chối callback query từ người dùng chưa cấp quyền: chat_id={chat_id}, from_id={from_id}")
            self.answer_callback_query(cb_id, text="⛔ Bạn không có quyền thực hiện thao tác này.")
            return

        if data.startswith("brain:approve:"):
            try:
                item_id = int(data.split(":")[-1])
                self.answer_callback_query(cb_id, text="Đang duyệt và hợp nhất vào Não Bộ...")
                self.db.curate_vault_item(item_id, "APPROVED")

                from vault_engine.consolidation import ConsolidationEngine
                consolidation = ConsolidationEngine(db=self.db, pipeline=self.pipeline)
                res = consolidation.consolidate_item(item_id)

                reply_text = (
                    f"🧠 <b>ĐÃ DUYỆT THÀNH CÔNG VÀO NÃO BỘ (ITEM #{item_id})!</b>\n\n"
                    f"📌 <b>Tiêu đề:</b> {res['title']}\n"
                    f"🔗 <b>Đối chiếu nơ-ron:</b> Đã liên kết với <b>{res['associations_count']}</b> tài liệu liên quan.\n"
                    f"🏛️ <b>Hồ sơ chuyên đề sống:</b> Cập nhật <code>{res['synthesis_topic']}</code> (v{res['synthesis_version']}).\n"
                    f"⚡ <b>Procedural Memory:</b> Nạp <b>{res['heuristics_count']}</b> quy tắc hành động vào bộ nhớ Agent.\n\n"
                    f"<i>Tri thức đã được củng cố và sẵn sàng cho Agent khai thác qua MCP!</i>"
                )
                self.send_message(reply_text, chat_id=chat_id, reply_to_message_id=msg_id)
            except Exception as e:
                logger.error(f"Lỗi khi duyệt item qua Telegram callback: {e}", exc_info=True)
                self.send_message(f"❌ Lỗi khi duyệt tài liệu: {e}", chat_id=chat_id)

        elif data.startswith("brain:reject:"):
            try:
                item_id = int(data.split(":")[-1])
                self.answer_callback_query(cb_id, text="Đã loại bỏ tài liệu.")
                self.db.curate_vault_item(item_id, "REJECTED")
                self.send_message(f"🗑️ <b>Đã loại bỏ tài liệu #{item_id} khỏi Não Bộ.</b>", chat_id=chat_id, reply_to_message_id=msg_id)
            except Exception as e:
                self.send_message(f"❌ Lỗi khi loại bỏ: {e}", chat_id=chat_id)

    def handle_message(self, message: Dict[str, Any]):
        chat_id = str(message.get("chat", {}).get("id", ""))
        from_id = str(message.get("from", {}).get("id", ""))
        text = message.get("text") or message.get("caption") or ""
        msg_id = message.get("message_id")

        if not text:
            return

        # Kiểm tra phân quyền truy cập
        if not self._is_authorized(chat_id) and not self._is_authorized(from_id):
            logger.warning(f"Từ chối tin nhắn từ người dùng chưa cấp quyền: chat_id={chat_id}, from_id={from_id}")
            self.send_message("⛔ <b>Truy cập bị từ chối.</b> Bạn không có quyền điều khiển Bộ Não Tự Hành này.", chat_id=chat_id, reply_to_message_id=msg_id)
            return

        text_strip = text.strip()

        # Lệnh /start hoặc /help
        if text_strip.startswith(("/start", "/help")):
            help_text = (
                "👋 <b>Chào mừng bạn đến với Autonomous Cognitive Brain Vault v5.0!</b>\n\n"
                "🤖 <b>Cách sử dụng:</b>\n"
                "• Chia sẻ hoặc dán liên kết (GitHub, YouTube, ArXiv, Tech Blog) vào đây.\n"
                "• Bot sẽ phân tích đa tầng sơ khảo (20% cốt lõi, Gotchas, Điểm thực chiến) và gửi báo cáo về cho bạn.\n"
                "• Bạn nhấn <b>[🧠 Duyệt Vào Não]</b> để kích hoạt hợp nhất nơ-ron, cập nhật Hồ sơ chuyên đề sống và sinh Quy tắc cho Agent.\n\n"
                "📊 <b>Lệnh điều khiển:</b>\n"
                "• <code>/approve &lt;id&gt;</code>: Duyệt nhanh tài liệu vào Não Bộ.\n"
                "• <code>/reject &lt;id&gt;</code>: Loại bỏ tài liệu khỏi Não Bộ.\n"
                "• <code>/brain_stats</code>: Xem trạng thái Bộ Não Tự Học."
            )
            self.send_message(help_text, chat_id=chat_id, reply_to_message_id=msg_id)
            return

        # Lệnh /approve <id>
        if text_strip.startswith("/approve"):
            parts = text_strip.split()
            if len(parts) >= 2 and parts[1].isdigit():
                item_id = int(parts[1])
                try:
                    self.db.curate_vault_item(item_id, "APPROVED")
                    from vault_engine.consolidation import ConsolidationEngine
                    consolidation = ConsolidationEngine(db=self.db, pipeline=self.pipeline)
                    res = consolidation.consolidate_item(item_id)
                    reply_text = (
                        f"🧠 <b>ĐÃ DUYỆT THÀNH CÔNG VÀO NÃO BỘ (ITEM #{item_id})!</b>\n\n"
                        f"📌 <b>{res['title']}</b>\n"
                        f"🔗 Liên kết nơ-ron: <b>{res['associations_count']}</b> tài liệu.\n"
                        f"🏛️ Cập nhật chuyên đề: <code>{res['synthesis_topic']}</code> (v{res['synthesis_version']}).\n"
                        f"⚡ Sinh <b>{res['heuristics_count']}</b> quy tắc hành động cho Agent."
                    )
                    self.send_message(reply_text, chat_id=chat_id, reply_to_message_id=msg_id)
                except Exception as e:
                    self.send_message(f"❌ Lỗi khi duyệt: {e}", chat_id=chat_id)
            else:
                self.send_message("💡 Cách dùng: <code>/approve &lt;item_id&gt;</code>", chat_id=chat_id)
            return

        # Lệnh /reject <id>
        if text_strip.startswith("/reject"):
            parts = text_strip.split()
            if len(parts) >= 2 and parts[1].isdigit():
                item_id = int(parts[1])
                self.db.curate_vault_item(item_id, "REJECTED")
                self.send_message(f"🗑️ Đã loại bỏ tài liệu #{item_id}.", chat_id=chat_id, reply_to_message_id=msg_id)
            else:
                self.send_message("💡 Cách dùng: <code>/reject &lt;item_id&gt;</code>", chat_id=chat_id)
            return

        # Lệnh /brain_stats hoặc /stats
        if text_strip.startswith(("/brain_stats", "/stats")):
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM vault_items WHERE curation_status = 'APPROVED' AND is_deleted = 0;")
                approved_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM vault_items WHERE curation_status = 'INBOX' AND is_deleted = 0;")
                inbox_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM brain_associations;")
                assoc_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM brain_synthesis_topics;")
                topic_cnt = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM agent_heuristics;")
                heuristics_cnt = cursor.fetchone()[0]

                stats_msg = (
                    f"🧠 <b>TRẠNG THÁI BỘ NÃO TỰ HỌC (BRAIN VAULT v5.0):</b>\n\n"
                    f"💎 Tri thức Tinh hoa (Approved): <b>{approved_cnt}</b> tài liệu\n"
                    f"📥 Hộp thư chờ duyệt (Inbox): <b>{inbox_cnt}</b> tài liệu\n"
                    f"🔗 Liên kết nơ-ron (Associations): <b>{assoc_cnt}</b> liên kết\n"
                    f"🏛️ Hồ sơ Chuyên đề Sống: <b>{topic_cnt}</b> chuyên đề\n"
                    f"⚡ Quy tắc hành động Agent: <b>{heuristics_cnt}</b> rules\n\n"
                    f"🌐 Dashboard: <a href=\"{DASHBOARD_BASE_URL}/\">{DASHBOARD_BASE_URL}</a>"
                )
                self.send_message(stats_msg, chat_id=chat_id, reply_to_message_id=msg_id)
            except Exception as e:
                self.send_message(f"Lỗi lấy thống kê: {e}", chat_id=chat_id)
            return

        # Trích xuất URLs
        urls = URL_REGEX.findall(text)
        if not urls:
            self.send_message(
                "💡 Vui lòng gửi một liên kết hợp lệ (GitHub, YouTube, ArXiv, Tech Article) để tôi phân tích sơ khảo!",
                chat_id=chat_id,
                reply_to_message_id=msg_id
            )
            return

        for raw_u in urls:
            clean_u = canonicalize_url(raw_u)
            stype = detect_source_type(clean_u)
            res = self.ingest.enqueue_url(clean_u, source_type=stype)

            if res.get("status") == "ALREADY_IN_VAULT":
                self.send_message(
                    f"ℹ️ <b>Liên kết đã có trong kho tri thức!</b>\n📌 Tiêu đề: <b>{res.get('title')}</b>\n🔗 <a href=\"{DASHBOARD_BASE_URL}/\">Mở trên Dashboard</a>",
                    chat_id=chat_id,
                    reply_to_message_id=msg_id
                )
                continue

            if res.get("status") == "ALREADY_QUEUED":
                self.send_message(
                    f"⏳ <b>Liên kết này đang được xử lý trong hàng đợi.</b> Vui lòng chờ trong giây lát!",
                    chat_id=chat_id,
                    reply_to_message_id=msg_id
                )
                continue

            self.send_message(
                f"📥 <b>Đã tiếp nhận liên kết ({stype})!</b>\n<code>{clean_u}</code>\n🔄 <i>Đang trinh sát và phân tích sơ khảo qua Gemini Dual-Pass...</i>",
                chat_id=chat_id,
                reply_to_message_id=msg_id
            )

            t = threading.Thread(
                target=self.process_url_task,
                args=(clean_u, chat_id, msg_id),
                daemon=True
            )
            t.start()

    def process_raw_update(self, update: Dict[str, Any]):
        """Xử lý update nhận từ webhook hoặc polling"""
        cb = update.get("callback_query")
        if cb:
            self.handle_callback_query(cb)
            return

        message = update.get("message") or update.get("channel_post")
        if message:
            self.handle_message(message)

    def start_polling(self):
        """Vòng lặp Long-polling chạy nền liên tục 24/7"""
        self._running = True
        logger.info("Khởi động Telegram Long-polling Worker...")
        last_update_id = None

        while self._running:
            try:
                updates = self.get_updates(offset=last_update_id, timeout=10)
                for update in updates:
                    update_id = update.get("update_id")
                    if update_id is not None:
                        last_update_id = update_id + 1

                    self.process_raw_update(update)

            except Exception as e:
                err_str = str(e)
                if "409" in err_str or "Conflict" in err_str:
                    logger.info("Telegram Bot: Webhook đang hoạt động (409 Conflict), dừng long-polling worker.")
                    self._running = False
                    break
                else:
                    logger.error(f"Lỗi trong vòng lặp polling: {e}")
                    time.sleep(2)

    def start_background(self):
        """Bắt đầu chạy polling trong một thread riêng"""
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_thread = threading.Thread(target=self.start_polling, daemon=True)
        self._poll_thread.start()
        logger.info("Telegram Bot background thread started.")

    def stop(self):
        self._running = False
