import os
import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("packager")

class RepoPackager:
    """Tải và đóng gói repository thành tài liệu tri thức chuẩn cho LLM và NotebookLM."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.repos_dir = self.base_dir / "repos"
        self.outputs_dir = self.base_dir / "outputs"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def clone_repo(self, clone_url: str, repo_name: str) -> Optional[Path]:
        """Shallow clone repo để tiết kiệm thời gian và băng thông."""
        target_path = self.repos_dir / repo_name
        if target_path.exists() and any(target_path.iterdir()):
            logger.info(f"Repo đã tồn tại ở: {target_path}")
            return target_path

        cmd = ["git", "clone", "--depth", "1", clone_url, str(target_path)]
        logger.info(f"Đang clone repo: {clone_url} -> {target_path}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return target_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Lỗi khi clone repo: {e.stderr}")
            return None

    def pack_with_repomix(self, repo_path: Path, output_file: Path) -> bool:
        """Sử dụng repomix nếu có npx."""
        try:
            # Dùng npx.cmd trên Windows
            cmd = [
                "npx.cmd", "--yes", "repomix",
                "--output", str(output_file),
                "--style", "markdown",
                "--ignore", "node_modules,dist,build,.git,*.lock,package-lock.json,venv,__pycache__"
            ]
            logger.info(f"Đang đóng gói bằng repomix: {' '.join(cmd)}")
            res = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and output_file.exists():
                logger.info(f"Đóng gói repomix thành công: {output_file}")
                return True
            else:
                logger.warning(f"repomix cảnh báo: {res.stderr[:300]}")
        except Exception as e:
            logger.warning(f"Không thể chạy repomix: {e}")
        return False

    def build_knowledge_document(
        self,
        fb_info: Dict[str, Any],
        repo_info: Dict[str, Any],
        repo_path: Optional[Path] = None
    ) -> Path:
        """Tạo file Markdown tổng hợp toàn diện cho NotebookLM."""
        repo_full_name = repo_info.get("full_name", "unknown_repo")
        safe_name = repo_full_name.replace("/", "_")
        doc_path = self.outputs_dir / f"{safe_name}_knowledge.md"

        # Đóng gói code nếu có repo_path
        repomix_file = self.outputs_dir / f"{safe_name}_repomix.md"
        has_repomix = False
        if repo_path and repo_path.exists():
            has_repomix = self.pack_with_repomix(repo_path, repomix_file)

        # Xây dựng cấu trúc tài liệu tri thức chuẩn mực
        content = []
        full_name = repo_info.get("full_name", "unknown_repo")
        github_url = repo_info.get("html_url") or repo_info.get("repo_url") or f"https://github.com/{full_name}"
        source_url = fb_info.get("source_url") or repo_info.get("source_url") or "Không có link bài đăng"
        stars = f"{repo_info.get('stars', 0):,}"
        forks = f"{repo_info.get('forks', 0):,}"
        license_name = repo_info.get("license") or "N/A"
        lang = repo_info.get("language") or "Unknown"
        category = repo_info.get("category") or "Developer Tools, CLI & Terminal"
        summary = repo_info.get("summary") or repo_info.get("description", "Không có mô tả.")
        use_cases = repo_info.get("use_cases", [])
        install_cmd = repo_info.get("install_cmd") or f"git clone {github_url}"
        architecture = repo_info.get("architecture") or f"Hệ thống phần mềm mã nguồn mở ({lang})"
        core_components = repo_info.get("core_components", [])
        code_snippet = repo_info.get("code_snippet", "")
        readme = repo_info.get("readme", "")

        content.append(f"# 📦 Tri Thức Kỹ Thuật Dự Án: {full_name}\n")
        content.append(f"> **Mô tả ngắn**: {repo_info.get('description', 'Không có')}\n")

        # 1. Nguồn Giới Thiệu
        content.append("## 1. Nguồn Giới Thiệu & Video")
        if source_url and source_url != "Không có link bài đăng":
            content.append(f"- **Link bài viết / Video gốc**: [{source_url}]({source_url})")
        else:
            content.append("- **Link bài viết / Video gốc**: *Được thu thập từ mạng xã hội/cộng đồng*")
        content.append(f"- **Kênh / Người chia sẻ**: {fb_info.get('uploader') or repo_info.get('uploader', 'Cộng đồng Công Nghệ')}")
        if fb_info.get('title'):
            content.append(f"- **Tiêu đề video**: {fb_info.get('title')}")
        if fb_info.get('description'):
            content.append(f"\n**Trích đoạn bài viết / Caption**:\n```text\n{fb_info.get('description').strip()[:1000]}\n```\n")

        # 2. Thông Tin GitHub Repository
        content.append("\n## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)")
        content.append(f"- **GitHub URL**: [{github_url}]({github_url})")
        content.append(f"- **Chỉ số cộng đồng**: ⭐ **{stars}** stars | 🍴 **{forks}** forks")
        content.append(f"- **Ngôn ngữ chủ đạo**: `{lang}`")
        content.append(f"- **Giấy phép bản quyền (License)**: `{license_name}`")
        topics = repo_info.get("topics", [])
        if topics:
            content.append(f"- **Chủ đề (Topics)**: {', '.join([f'`{t}`' for t in topics])}")
        content.append(f"- **Cập nhật gần nhất**: {repo_info.get('updated_at', 'N/A')}\n")

        # 3. Phân Loại & Tóm Tắt Của AI
        content.append("## 💡 3. Nhận Định & Phân Loại Của AI")
        content.append(f"- **Phân Loại Lĩnh Vực**: `{category}`")
        content.append(f"- **Kiến Trúc Kỹ Thuật**: `{architecture}`")
        content.append(f"- **Tóm Tắt Cốt Lõi Cho AI-Agent**:\n  > {summary}\n")
        if use_cases:
            content.append("- **Kịch Bản Ứng Dụng Đề Xuất**:")
            for uc in use_cases:
                content.append(f"  * {uc}")

        if core_components:
            content.append("\n- **Các Thành Phần / API Cốt Lõi**:")
            for comp in core_components:
                content.append(f"  * {comp}")

        # 4. Hướng Dẫn Cài Đặt Nhanh
        content.append("\n## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)")
        content.append("```bash")
        content.append(install_cmd.strip())
        content.append("```")

        # 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
        if code_snippet:
            clean_snippet = code_snippet.replace("\\n", "\n")
            code_lang = lang.lower() if lang.lower() in ["python", "javascript", "typescript", "rust", "go", "bash", "shell"] else ""
            content.append(f"\n## 💻 5. Mã Nguồn Mẫu Thực Chiến (\"Hello World\")")
            content.append(f"```{code_lang}")
            content.append(clean_snippet.strip())
            content.append("```")

        # 6. Nội Dung README.md Chính Thức
        content.append("\n## 📖 6. Nội Dung README.md Chính Thức")
        if readme and len(readme.strip()) > 50:
            content.append(readme.strip())
        else:
            content.append(f"*(Chưa có bản tải về của README. Bạn có thể truy cập trực tiếp tại [{github_url}]({github_url}))*")

        # 7. Đính kèm nội dung repomix nếu có
        if has_repomix and repomix_file.exists():
            content.append("\n\n---\n## 🏗️ 7. Cấu Trúc Mã Nguồn & File Quan Trọng (Repomix Snapshot)\n")
            try:
                file_size = repomix_file.stat().st_size
                if file_size > 2 * 1024 * 1024:
                    with open(repomix_file, "r", encoding="utf-8", errors="replace") as rf:
                        truncated = rf.read(1024 * 1024)
                        content.append(truncated)
                        content.append("\n\n*(Nội dung mã nguồn đã được cắt ngắn bớt do vượt quá 1MB)*")
                else:
                    content.append(repomix_file.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                logger.error(f"Lỗi đọc repomix file: {e}")

        # Ghi ra file tổng hợp
        doc_path.write_text("\n".join(content), encoding="utf-8")
        logger.info(f"Đã tạo tài liệu tri thức toàn diện: {doc_path}")
        return doc_path
