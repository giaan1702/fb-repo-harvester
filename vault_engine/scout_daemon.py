import os
import sys
import re
import time
import json
import logging
import urllib.request
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import threading
from vault_engine.config import DB_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, canonicalize_url, generate_url_hash, detect_source_type
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.pipeline import GeminiReflectivePipeline
from vault_engine.consolidation import ConsolidationEngine
from vault_engine.telegram_bot import TelegramBot

logger = logging.getLogger("vault_scout")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Ngưỡng điểm tự động duyệt vào Thư Viện Não Bộ (Strict Rubric)
AUTO_APPROVE_THRESHOLD = 8.5
MIN_INGEST_THRESHOLD = 7.0

class AutonomousScout:
    """
    Đặc vụ Săn lùng Tri thức Tự hành (Autonomous Continuous Knowledge Harvester).
    Tự động quét các nguồn kỹ thuật tinh tuyển, gửi qua RMKO Gateway thẩm định khắt khe
    và tự động củng cố vào Cognitive Brain Vault.
    """
    def __init__(self, db_path: Optional[str] = None):
        target_db = db_path or DB_PATH
        db_existed = os.path.exists(target_db) and os.path.getsize(target_db) > 0
        self.db = DatabaseManager(target_db)
        if not db_existed:
            dump_file = os.path.join(os.path.dirname(os.path.abspath(target_db)), "vault_dump.sql")
            if os.path.exists(dump_file):
                logger.info(f"🔄 Khởi tạo cơ sở dữ liệu từ {dump_file}...")
                self.db.restore_sql(dump_file)
        self.ingest = IngestManager(db=self.db)
        self.pipeline = GeminiReflectivePipeline()
        self.github_ext = GitHubExtractor()
        self.web_ext = WebExtractor()
        self.consolidation = ConsolidationEngine(db=self.db, pipeline=self.pipeline)
        self.bot = TelegramBot()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def fetch_github_trending(self, since: str = "daily") -> List[Dict[str, Any]]:
        """Cào danh sách repository đang thịnh hành trên GitHub (Trending)."""
        url = f"https://github.com/trending?since={since}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        items = []
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")

            # Regex trích xuất các bài trending: /owner/repo
            matches = re.findall(r'href="/([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)"\s+data-view-component', html)
            for clean_path in matches[:10]: # Top 10 repositories
                clean_path = clean_path.strip().strip("/")
                parts = clean_path.split("/")
                if len(parts) == 2:
                    repo_url = f"https://github.com/{clean_path}"
                    items.append({
                        "url": repo_url,
                        "source": "GITHUB_TRENDING",
                        "title": clean_path
                    })
            logger.info(f"✓ Scout phát hiện {len(items)} repositories trending trên GitHub")
        except Exception as err:
            logger.warning(f"Lỗi cào GitHub Trending: {err}")
        return items

    def fetch_hackernews_best(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lấy danh sách các bài viết kỹ thuật hay nhất từ Hacker News (Best Stories)."""
        items = []
        try:
            best_url = "https://hacker-news.firebaseio.com/v0/beststories.json"
            req = urllib.request.Request(best_url, headers={"User-Agent": "CognitiveScout/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                story_ids = json.loads(resp.read().decode("utf-8"))[:limit]

            for sid in story_ids:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                req_item = urllib.request.Request(item_url, headers={"User-Agent": "CognitiveScout/1.0"})
                with urllib.request.urlopen(req_item, timeout=8) as r_item:
                    story = json.loads(r_item.read().decode("utf-8"))
                    url = story.get("url")
                    title = story.get("title", "")
                    score = story.get("score", 0)
                    # Chỉ lấy bài có URL ngoài và điểm cộng đồng cao (>50 points)
                    if url and score >= 40:
                        items.append({
                            "url": url,
                            "source": "HACKER_NEWS",
                            "title": title,
                            "community_score": score
                        })
            logger.info(f"✓ Scout phát hiện {len(items)} bài viết kỹ thuật từ Hacker News")
        except Exception as err:
            logger.warning(f"Lỗi truy vấn Hacker News API: {err}")
        return items

    def harvest_and_evaluate(self, target_url: str, source_label: str = "SCOUT") -> Optional[Dict[str, Any]]:
        """Quy trình thẩm định khắt khe qua RMKO Gateway và tự động học."""
        clean_url = canonicalize_url(target_url)
        url_hash = generate_url_hash(clean_url)

        # 1. Kiểm tra xem bài đã tồn tại trong Vault chưa
        existing = self.db.execute_scalar("SELECT id FROM vault_items WHERE url_hash = ? AND is_deleted = 0;", (url_hash,))
        if existing:
            logger.info(f"⏩ Đã tồn tại trong Vault (ID: {existing}) -> Bỏ qua: {clean_url}")
            return None

        source_type = detect_source_type(clean_url)
        logger.info(f"\n🔍 [SCOUT AUDIT] Đang phân tích: {clean_url} ({source_type})")

        # 2. Trích xuất nội dung
        content = ""
        title_hint = ""
        dossier = None
        if source_type == "GITHUB":
            data = self.github_ext.extract(clean_url)
            content = data.get("content", "")
            title_hint = data.get("title", "")
        else:
            data = self.web_ext.extract(clean_url)
            content = data.get("clean_text", "")
            title_hint = data.get("title", "")

        if len(content) < 300:
            logger.info(f"❌ Nội dung quá ngắn ({len(content)} ký tự), không đạt tiêu chuẩn sơ cấp -> Loại bỏ")
            return None

        # 3. Thẩm định 2 vòng qua RMKO Gateway (Pass 1 Planner -> Pass 2 Reviewer)
        t0 = time.perf_counter()
        schema_item = self.pipeline.process_content(content, clean_url, source_type, title_hint=title_hint)
        eval_time = time.perf_counter() - t0

        score = schema_item.practical_score
        logger.info(f"⚖️ Phán quyết RMKO Gateway ({eval_time:.2f}s): Điểm {score}/10 | Tiêu đề: '{schema_item.title}'")

        # 4. Phân loại theo Rubric nghiêm ngặt
        if score < MIN_INGEST_THRESHOLD:
            logger.info(f"❌ Điểm thực chiến {score}/10 < {MIN_INGEST_THRESHOLD} -> Tự động loại bỏ (Auto-Rejected)")
            return None

        # Đóng gói lưu trữ
        is_auto_approved = (score >= AUTO_APPROVE_THRESHOLD)
        curation_status = "APPROVED" if is_auto_approved else "INBOX"

        payload = schema_item.model_dump()
        payload["url_hash"] = url_hash
        payload["canonical_url"] = clean_url
        payload["source_type"] = source_type
        payload["curation_status"] = curation_status

        item_id = self.db.insert_vault_item(payload)
        logger.info(f"💾 Đã lưu vào Vault Item #{item_id} (Trạng thái: {curation_status})")

        # 5. Nếu đạt chuẩn Auto-Approve -> Kích hoạt Memory Consolidation
        if is_auto_approved:
            logger.info(f"🧠 Điểm xuất sắc {score}/10 >= {AUTO_APPROVE_THRESHOLD} -> KÍCH HOẠT TỰ ĐỘNG DUYỆT VÀO NÃO BỘ!")
            con_res = self.consolidation.consolidate_item(item_id)
            logger.info(f"✓ Củng cố nơ-ron hoàn tất: {con_res.get('new_associations', 0)} liên kết mới, {con_res.get('new_heuristics', 0)} quy tắc Agent")

            # Thông báo Telegram thành công
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                msg = (
                    f"🤖 <b>[TỰ HỌC THÀNH CÔNG - AUTO-APPROVED]</b>\n\n"
                    f"📌 <b>{schema_item.title}</b>\n"
                    f"⭐ Điểm thực chiến: <b>{score}/10</b> (Vượt ngưỡng {AUTO_APPROVE_THRESHOLD})\n"
                    f"🏷️ #{schema_item.category} | Nguồn: {source_label}\n"
                    f"🛠️ <b>Tech:</b> {', '.join(schema_item.tech_stack[:4])}\n\n"
                    f"🧠 <i>Hệ thống đã tự động đối chiếu nơ-ron & cập nhật quy tắc cho AI Agent!</i>"
                )
                self.bot.send_message(TELEGRAM_CHAT_ID, msg)
        else:
            # Gửi thông báo chờ duyệt về Telegram
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                saved_item = self.db.get_vault_item_by_id(item_id)
                msg_out = self.bot.format_completion_message(saved_item, item_id)
                if isinstance(msg_out, tuple):
                    msg, markup = msg_out
                    self.bot.send_message(TELEGRAM_CHAT_ID, msg, reply_markup=markup)
                else:
                    self.bot.send_message(TELEGRAM_CHAT_ID, msg_out)

        return {
            "item_id": item_id,
            "title": schema_item.title,
            "score": score,
            "curation_status": curation_status,
            "auto_approved": is_auto_approved
        }

    def run_scout_cycle(self) -> Dict[str, Any]:
        """Thực thi một chu kỳ săn lùng toàn diện."""
        logger.info("=" * 70)
        logger.info("🚀 BẮT ĐẦU CHU KỲ SĂN LÙNG TRI THỨC TỰ HÀNH (AUTONOMOUS SCOUT)")
        logger.info("=" * 70)

        candidates = []
        candidates.extend(self.fetch_github_trending(since="daily"))
        candidates.extend(self.fetch_hackernews_best(limit=8))

        stats = {
            "total_scanned": len(candidates),
            "auto_approved": 0,
            "sent_to_inbox": 0,
            "rejected": 0
        }

        for c in candidates:
            try:
                res = self.harvest_and_evaluate(c["url"], source_label=c.get("source", "SCOUT"))
                if not res:
                    stats["rejected"] += 1
                elif res.get("auto_approved"):
                    stats["auto_approved"] += 1
                else:
                    stats["sent_to_inbox"] += 1
            except Exception as e:
                logger.error(f"Lỗi xử lý candidate {c['url']}: {e}")

        logger.info("\n" + "=" * 70)
        logger.info(f"🏁 KẾT THÚC CHU KỲ: Quét {stats['total_scanned']} bài | Duyệt Não: {stats['auto_approved']} | Inbox: {stats['sent_to_inbox']} | Loại: {stats['rejected']}")
        logger.info("=" * 70)

        # Flush toàn bộ dữ liệu WAL vào file vault.db chính
        try:
            self.db.checkpoint()
            logger.info("✓ Đã checkpoint WAL vào vault.db")
        except Exception as e:
            logger.warning(f"Không thể checkpoint DB: {e}")

        return stats


    def run_forever(self, interval_seconds: Optional[int] = None):
        """Vòng lặp tự hành vĩnh cửu quét định kỳ (mặc định 4 tiếng hoặc đọc từ biến môi trường SCOUT_INTERVAL_SECONDS)."""
        if interval_seconds is None:
            interval_seconds = int(os.getenv("SCOUT_INTERVAL_SECONDS", "14400"))
        
        self._running = True
        logger.info(f"🔄 Kích hoạt chế độ Autonomous Scout 24/7. Chu kỳ lặp: {interval_seconds}s (~{interval_seconds/3600:.1f}h)")
        
        while self._running:
            try:
                self.run_scout_cycle()
            except Exception as e:
                logger.error(f"Lỗi không mong muốn trong chu kỳ Scout: {e}")
            
            # Chia nhỏ sleep để có thể shutdown nhẹ nhàng khi nhận signal
            logger.info(f"⏳ Scout đang ngủ {interval_seconds}s trước chu kỳ tiếp theo...")
            slept = 0
            while self._running and slept < interval_seconds:
                sleep_step = min(5, interval_seconds - slept)
                time.sleep(sleep_step)
                slept += sleep_step

        logger.info("Autonomous Scout đã dừng.")

    def start_background(self, interval_seconds: Optional[int] = None):
        """Khởi chạy Scout trong background daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Scout background thread đã đang chạy.")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self.run_forever, args=(interval_seconds,), daemon=True)
        self._thread.start()
        logger.info("✓ Scout background thread đã được khởi động.")

    def stop(self):
        """Dừng daemon Scout một cách êm ái."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            logger.info("✓ Scout background thread đã dừng.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Scout Daemon")
    parser.add_argument("--loop", action="store_true", help="Chạy vòng lặp vô tận 24/7")
    parser.add_argument("--interval", type=int, default=14400, help="Thời gian nghỉ giữa các chu kỳ tính bằng giây (mặc định: 14400s = 4h)")
    args = parser.parse_args()

    scout = AutonomousScout()
    if args.loop:
        scout.run_forever(interval_seconds=args.interval)
    else:
        scout.run_scout_cycle()

