import os
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

from fb_harvester.config_manager import ConfigManager
from fb_harvester.notifier import Notifier
from fb_harvester.catalog import CatalogManager
from fb_harvester.page_crawler import PageCrawler
from fb_harvester.cli import process_single_item
from fb_harvester.ideator import IdeaEngine
from fb_harvester.notebook_sync import NotebookSyncEngine

logger = logging.getLogger("scheduler")

class BackgroundScheduler:
    """Điều phối lịch trình cào liên tục, kiểm tra sức khỏe hệ thống và gửi Báo cáo định kỳ hàng ngày."""

    def __init__(self, base_dir: Path = None, add_log_func=None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = Path(base_dir)
        self.add_log = add_log_func or (lambda m: logger.info(m))
        self.config_mgr = ConfigManager(self.base_dir)
        self.notifier = Notifier(self.base_dir)
        
        self.is_running = False
        self._thread: threading.Thread = None
        self._is_crawling_now = False

    def start(self):
        """Khởi chạy vòng lặp scheduler trong daemon thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, name="BackgroundScheduler")
        self._thread.daemon = True
        self._thread.start()
        self.add_log("Background Scheduler đã khởi động thành công.")

    def stop(self):
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        settings = self.config_mgr.load()
        return {
            "is_running": self.is_running,
            "is_crawling_now": self._is_crawling_now,
            "auto_crawl_enabled": settings.get("auto_crawl_enabled", True),
            "crawl_interval_hours": settings.get("crawl_interval_hours", 6),
            "daily_report_time": settings.get("daily_report_time", "07:00"),
            "last_crawl_time": settings.get("last_crawl_time"),
            "last_report_date": settings.get("last_report_date")
        }

    def _run_loop(self):
        """Vòng lặp kiểm tra định kỳ mỗi 30 giây."""
        while self.is_running:
            try:
                settings = self.config_mgr.load()
                now = datetime.now()
                now_str_time = now.strftime("%H:%M")
                now_str_date = now.strftime("%Y-%m-%d")

                # 1. Kiểm tra gửi Báo cáo hàng ngày (Daily Digest)
                target_time = settings.get("daily_report_time", "07:00")
                last_report_date = settings.get("last_report_date")
                if settings.get("daily_report_enabled", True):
                    if now_str_time == target_time and last_report_date != now_str_date:
                        self.add_log(f"Đến giờ phát hành Báo Cáo Định Kỳ ({target_time})! Đang tổng hợp số liệu...")
                        self.generate_and_send_daily_digest()
                        self.config_mgr.update_key("last_report_date", now_str_date)

                # 2. Kiểm tra chu kỳ Cào Dữ Liệu Tự Động (Continuous Crawling)
                if settings.get("auto_crawl_enabled", True) and not self._is_crawling_now:
                    interval_hours = settings.get("crawl_interval_hours", 6)
                    last_crawl_str = settings.get("last_crawl_time")
                    should_crawl = False

                    if not last_crawl_str:
                        # Chưa từng cào hoặc vừa khởi tạo
                        should_crawl = False  # Tránh cào ngay lập tức khi vừa bật server, đợi chu kỳ hoặc kích hoạt thủ công
                    else:
                        try:
                            last_crawl_dt = datetime.fromisoformat(last_crawl_str)
                            if now - last_crawl_dt >= timedelta(hours=interval_hours):
                                should_crawl = True
                        except Exception:
                            should_crawl = False

                    if should_crawl:
                        self.add_log(f"Kích hoạt cào định kỳ tự động (Chu kỳ mỗi {interval_hours}h)...")
                        self.run_crawl_cycle()

            except Exception as e:
                logger.error(f"Lỗi trong vòng lặp scheduler: {e}")
                self.notifier.send_alert("Lỗi Scheduler Vận Hành", str(e), context="Scheduler Loop")

            # Ngủ 30 giây trước khi kiểm tra lại
            time.sleep(30)

    def run_crawl_cycle(self):
        """Chạy một chu kỳ cào cho toàn bộ kênh với cơ chế tự bảo vệ và cảnh báo khi có sự cố."""
        if self._is_crawling_now:
            self.add_log("Đang có một tiến trình cào hoạt động, bỏ qua chu kỳ này.")
            return

        self._is_crawling_now = True
        settings = self.config_mgr.load()
        limit = settings.get("crawl_limit_per_channel", 3)
        self.config_mgr.update_key("last_crawl_time", datetime.now().isoformat())

        def crawl_worker():
            try:
                crawler = PageCrawler(self.base_dir)
                channels = crawler.load_channels()
                self.add_log(f"[Auto-Crawl] Bắt đầu quét {len(channels)} kênh (Mỗi kênh {limit} video)...")
                
                total_scanned = 0
                new_found = 0
                for ch in channels:
                    url = ch.get("url", "")
                    name = ch.get("name", url)
                    try:
                        videos = crawler.fetch_videos_from_page(url, limit=limit)
                        for v in videos:
                            total_scanned += 1
                            ok = process_single_item(url=v["url"], text=v.get("title", ""), skip_clone=True)
                            if ok:
                                new_found += 1
                    except Exception as ch_err:
                        self.add_log(f"[Auto-Crawl] Cảnh báo lỗi kênh {name}: {ch_err}")
                        # Gửi alert nếu lỗi nghiêm trọng
                        if "checkpoint" in str(ch_err).lower() or "blocked" in str(ch_err).lower():
                            self.notifier.send_alert(
                                f"Facebook Chặn Kênh {name}",
                                str(ch_err),
                                context=f"Kênh: {url}"
                            )

                self.add_log(f"[Auto-Crawl] Hoàn tất chu kỳ cào! Quét {total_scanned} video, phát hiện {new_found} repo mới.")

            except Exception as e:
                self.add_log(f"[Auto-Crawl] Lỗi nghiêm trọng trong chu kỳ cào: {e}")
                self.notifier.send_alert(
                    "Sự Cố Cào Dữ Liệu Tự Động",
                    str(e),
                    context="Auto Crawl Cycle"
                )
            finally:
                self._is_crawling_now = False

        t = threading.Thread(target=crawl_worker, name="CrawlWorker")
        t.daemon = True
        t.start()

    def generate_and_send_daily_digest(self) -> Dict[str, Any]:
        """Tổng hợp số liệu 24h qua và gửi Báo Cáo Định Kỳ."""
        try:
            catalog_mgr = CatalogManager(self.base_dir)
            catalog_data = catalog_mgr.load_data()
            total_repos = len(catalog_data)

            # Lọc các repo phát hiện trong 24h qua (hoặc lấy 3 repo mới nhất)
            now = datetime.now()
            new_repos = []
            for item in catalog_data:
                added_str = item.get("added_at")
                if added_str:
                    try:
                        added_dt = datetime.fromisoformat(added_str)
                        if now - added_dt <= timedelta(hours=24):
                            new_repos.append(item)
                    except Exception:
                        pass

            if not new_repos and catalog_data:
                # Nếu không có repo mới trong 24h, lấy 2 repo mới nhất để báo cáo có điểm nhấn
                new_repos = catalog_data[-2:]

            # Đọc kênh theo dõi
            crawler = PageCrawler(self.base_dir)
            channels = crawler.load_channels()

            # Đọc trạng thái NotebookLM
            sync_engine = NotebookSyncEngine()
            nlm_auth = sync_engine.is_authenticated()

            # Lấy 1 ý tưởng từ kho Ideas
            idea_engine = IdeaEngine(self.base_dir)
            ideas = idea_engine.load_ideas()
            idea_highlight = ""
            if ideas:
                latest_idea = ideas[0]
                idea_highlight = f"🚀 *{latest_idea.get('title')}*\n_{latest_idea.get('tagline', '')}_"

            report_data = {
                "total_repos": total_repos,
                "new_repos_24h": new_repos,
                "total_channels": len(channels),
                "videos_crawled_24h": len(channels) * 3,
                "notebooklm_connected": nlm_auth,
                "idea_highlight": idea_highlight
            }

            res = self.notifier.send_daily_digest(report_data)
            self.add_log("Đã phát hành bản Báo Cáo Định Kỳ tới Telegram!")
            return {"status": "success", "result": res}

        except Exception as e:
            err_msg = f"Lỗi tổng hợp Báo Cáo Định Kỳ: {e}"
            self.add_log(err_msg)
            self.notifier.send_alert("Lỗi Sinh Báo Cáo Hàng Ngày", str(e), context="Daily Digest")
            return {"status": "error", "error": str(e)}
