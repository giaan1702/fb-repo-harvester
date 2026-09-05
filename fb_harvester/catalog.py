import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("catalog")

class CatalogManager:
    """Quản lý kho dữ liệu cục bộ và bảng danh mục tham chiếu Markdown phân tầng."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.catalog_file = self.base_dir / "catalog.json"
        self.markdown_file = self.base_dir / "CATALOG.md"
        self._ensure_catalog()

    def _ensure_catalog(self):
        if not self.catalog_file.exists():
            self.save_data([])

    def load_data(self) -> List[Dict[str, Any]]:
        try:
            with open(self.catalog_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc catalog.json: {e}")
            return []

    def save_data(self, data: List[Dict[str, Any]]):
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.generate_markdown(data)

    def get_repo(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một repo theo full_name."""
        data = self.load_data()
        for item in data:
            if item.get("full_name", "").lower() == full_name.lower():
                return item
        return None

    def update_notebook_ref(self, full_name: str, notebook_ref: str) -> bool:
        """Cập nhật trạng thái tham chiếu NotebookLM cho một repo."""
        data = self.load_data()
        for item in data:
            if item.get("full_name", "").lower() == full_name.lower():
                item["notebook_ref"] = notebook_ref
                self.save_data(data)
                return True
        return False

    def is_processed(self, source_url: str = "", full_name: str = "") -> bool:
        """Kiểm tra xem link Facebook hoặc Repo đã từng được xử lý chưa."""
        data = self.load_data()
        for item in data:
            if full_name and item.get("full_name", "").lower() == full_name.lower():
                return True
            if source_url and item.get("source_url") and source_url.strip("/") in item.get("source_url", "").strip("/"):
                return True
        return False

    def add_or_update(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load_data()
        full_name = entry.get("full_name")
        
        found = False
        for idx, item in enumerate(data):
            if item.get("full_name", "").lower() == full_name.lower():
                data[idx].update(entry)
                data[idx]["updated_at"] = datetime.now().isoformat()
                found = True
                break
        
        if not found:
            entry["created_at"] = datetime.now().isoformat()
            data.append(entry)

        self.save_data(data)
        return entry

    def generate_markdown(self, data: List[Dict[str, Any]]):
        """Tạo bảng tra cứu CATALOG.md theo từng danh mục phân loại của AI."""
        # Gom nhóm theo Category
        categories = {}
        for item in data:
            cat = item.get("category") or "Developer Tools, CLI & Terminal"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        lines = [
            "# 📚 Kho Tham Chiếu Repository & Chỉ Mục Tri Thức Cho AI-Agent",
            "",
            f"> Cập nhật lần cuối: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> Tổng số repository: **{len(data)}** | Phân loại thành: **{len(categories)} danh mục**  ",
            f"> Kiến trúc: *Thin Local Index (Chỉ mục cục bộ) + Google NotebookLM (Tri thức sâu)*",
            "",
            "## 📌 Mục Lục Danh Mục Phân Loại Của AI:"
        ]

        # Mục lục
        for cat, items in categories.items():
            anchor = cat.lower().replace(" ", "-").replace("&", "").replace(",", "").replace("--", "-")
            lines.append(f"- [{cat}](#{anchor}) ({len(items)} repos)")

        lines.append("\n---")

        # Nội dung từng danh mục
        for cat, items in sorted(categories.items()):
            lines.append(f"\n## 📂 {cat}")
            lines.append(f"*Tổng số: {len(items)} repository*\n")

            for item in sorted(items, key=lambda x: x.get("stars", 0), reverse=True):
                full_name = item.get("full_name", "N/A")
                repo_url = item.get("repo_url") or item.get("html_url") or f"https://github.com/{full_name}"
                lang = item.get("language", "Unknown")
                stars = f"{item.get('stars', 0):,}"
                forks = f"{item.get('forks', 0):,}"
                license_name = item.get("license") or "N/A"
                install_cmd = item.get("install_cmd")
                summary = item.get("summary") or item.get("description") or "Chưa có mô tả tóm tắt."
                tags = " ".join([f"`{t}`" for t in item.get("tags", [])])
                
                # Tham chiếu NotebookLM
                notebook_ref = item.get("notebook_ref")
                if isinstance(notebook_ref, dict):
                    nb_title = notebook_ref.get("notebook_title") or "Facebook Curated Tech Repositories"
                elif isinstance(notebook_ref, str) and notebook_ref:
                    nb_title = notebook_ref
                else:
                    nb_title = item.get("notebook_title") or "Facebook Curated Tech Repositories"
                nb_status = "✅ Đã nạp vào NotebookLM" if item.get("synced_to_notebooklm") or (notebook_ref and notebook_ref != "Chưa nạp") else "⏳ Sẵn sàng nạp"
                
                lines.append(f"### 📦 [{full_name}]({repo_url})")
                lines.append(f"- **Chỉ số**: ⭐ **{stars}** stars | 🍴 **{forks}** forks | Ngôn ngữ: `{lang}` | License: `{license_name}` {f'| Tags: {tags}' if tags else ''}")
                if install_cmd:
                    lines.append(f"- **🚀 Cài đặt nhanh**: `{install_cmd}`")
                lines.append(f"- **Tham chiếu NotebookLM**: `{nb_title}` ({nb_status})")
                lines.append(f"- **🤖 Tóm tắt cho AI-Agent**:")
                lines.append(f"  > {summary}")
                
                use_cases = item.get("use_cases", [])
                if use_cases:
                    lines.append(f"- **Ứng dụng thực tế**:")
                    for uc in use_cases:
                        lines.append(f"  - {uc}")
                lines.append("")

        self.markdown_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Đã cập nhật CATALOG.md phân loại thành công ({len(data)} repos)")
