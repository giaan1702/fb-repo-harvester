import os
import sys
import subprocess
import shutil
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("notebook_sync")

DEFAULT_NLM_PATH = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\Scripts\nlm.exe"
DEFAULT_NOTEBOOK_TITLE = "Facebook Curated Tech Repositories"

class NotebookSyncEngine:
    """Quản lý kết nối và đẩy tài liệu tri thức vào Google NotebookLM."""

    def __init__(self, nlm_executable: Optional[str] = None):
        self.nlm_exe = nlm_executable or DEFAULT_NLM_PATH
        if not os.path.exists(self.nlm_exe):
            # Fallback to PATH
            self.nlm_exe = shutil.which("nlm") or "nlm"
        self.nlm_available = os.path.exists(self.nlm_exe) or shutil.which(self.nlm_exe) is not None

    def recover_auth_headless(self) -> bool:
        """Tự động làm mới cookie và CSRF token qua Headless Chrome không cần người dùng thao tác."""
        try:
            logger.info("Đang tự động phục hồi phiên đăng nhập NotebookLM bằng Headless Chrome...")
            python_exe = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            cmd = [python_exe, "-c", "from notebooklm_tools.utils.auth_browser import run_headless_auth; print(bool(run_headless_auth('default')))" ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
            if res.returncode == 0 and "True" in res.stdout:
                logger.info("✅ Phục hồi phiên đăng nhập thành công qua Headless Chrome!")
                return True
        except Exception as e:
            logger.warning(f"Không thể tự động phục hồi headless auth: {e}")
        return False

    def is_authenticated(self) -> bool:
        """Kiểm tra xem nlm đã đăng nhập và sẵn sàng chưa. Tự động phục hồi qua Headless Chrome nếu hết hạn."""
        if not self.nlm_available:
            logger.debug("nlm CLI không khả dụng trên server này, bỏ qua kiểm tra auth.")
            return False
        try:
            cmd = [self.nlm_exe, "login", "--check"]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            if res.returncode == 0:
                return True
        except Exception as e:
            logger.debug(f"Không thể kiểm tra đăng nhập nlm: {e}")

        # Tự động chạy Headless Auth phục hồi phiên đăng nhập
        if self.recover_auth_headless():
            try:
                cmd = [self.nlm_exe, "login", "--check"]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
                return res.returncode == 0
            except Exception:
                pass
        return False

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các notebook hiện có trên tài khoản NotebookLM."""
        try:
            cmd = [self.nlm_exe, "notebook", "list"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                # Phân tích output từ CLI
                logger.info("Lấy danh sách notebook thành công.")
                # nlm in ra bảng hoặc text
                return [{"output": res.stdout}]
        except Exception as e:
            logger.error(f"Lỗi khi list notebook: {e}")
        return []

    def get_or_create_default_notebook(self, title: str = DEFAULT_NOTEBOOK_TITLE) -> Optional[str]:
        """Lấy hoặc tạo Notebook theo tên, chống trùng lặp tuyệt đối."""
        config_path = Path("notebook_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    cached_id = cfg.get("notebook_id")
                    if cached_id:
                        logger.info(f"Sử dụng notebook đã lưu trong cấu hình: {cached_id}")
                        return cached_id
            except Exception as e:
                logger.warning(f"Không thể đọc config notebook: {e}")

        # Kiểm tra danh sách notebook hiện có qua nlm --json
        try:
            cmd = [self.nlm_exe, "notebook", "list", "--json"]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            if res.returncode == 0:
                try:
                    data = json.loads(res.stdout)
                    notebooks = data.get("notebooks", []) if isinstance(data, dict) else data
                    for nb in notebooks:
                        if nb.get("title", "").strip().lower() == title.strip().lower():
                            nb_id = nb.get("id")
                            logger.info(f"Đã tìm thấy notebook trùng khớp: {nb_id} ('{title}')")
                            with open(config_path, "w", encoding="utf-8") as f:
                                json.dump({"notebook_id": nb_id, "title": title}, f, indent=2)
                            return nb_id
                except Exception as je:
                    logger.debug(f"Không thể parse JSON từ nlm notebook list: {je}")
        except Exception as e:
            logger.warning(f"Lỗi khi kiểm tra notebook list: {e}")

        # Nếu chưa có thì mới tạo mới duy nhất 1 lần
        try:
            cmd = [self.nlm_exe, "notebook", "create", title]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if res.returncode == 0:
                stdout = res.stdout.strip()
                # nlm create thường in ID hoặc "Created notebook: <id>"
                import re
                match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", stdout)
                nb_id = match.group(1) if match else stdout
                logger.info(f"Đã tạo mới notebook thành công: {nb_id}")
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"notebook_id": nb_id, "title": title}, f, indent=2)
                return nb_id
            else:
                logger.warning(f"Không thể tạo notebook: {res.stderr}")
        except Exception as e:
            logger.error(f"Lỗi khi tạo notebook: {e}")
        return None

    def add_source_file(self, notebook_id: str, file_path: Path) -> bool:
        """Đẩy file tài liệu markdown vào NotebookLM."""
        if not file_path.exists():
            logger.error(f"File nguồn không tồn tại: {file_path}")
            return False

        try:
            # Lệnh: nlm source add <notebook_id> --file <file_path>
            cmd = [self.nlm_exe, "source", "add", notebook_id, "--file", str(file_path.resolve())]
            logger.info(f"Đang đẩy source lên NotebookLM: {' '.join(cmd)}")
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if res.returncode == 0:
                logger.info("Đẩy source thành công!")
                return True
            else:
                logger.warning(f"nlm trả về lỗi khi add source: {res.stderr}")
        except Exception as e:
            logger.error(f"Lỗi khi add source file: {e}")
        return False
