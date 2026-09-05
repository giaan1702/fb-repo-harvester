"""
agent_bridge.py
Module cung cấp Facade Interface tinh gọn (4 Primitives) cho Model AI gọi qua API
(OpenAI Function Calling / Tool Use) mà không phải tiếp xúc với 40 tool MCP phức tạp.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fb_harvester.catalog import CatalogManager
from fb_harvester.notebook_sync import NotebookSyncEngine
from fb_harvester.packager import RepoPackager

logger = logging.getLogger("agent_bridge")

class AgentBridge:
    """Cầu nối tinh gọn giữa LLM Model, Chỉ mục cục bộ và Google NotebookLM."""

    def __init__(self, base_dir: Optional[str] = None):
        self.catalog = CatalogManager(base_dir=base_dir)
        self.sync_engine = NotebookSyncEngine()
        self.packager = RepoPackager()

    def lookup_catalog(self, query: str = "", category: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Primitive 1: Tra cứu nhanh trong chỉ mục cục bộ theo từ khóa hoặc danh mục.
        Chi phí token cực thấp, phản hồi tức thì (0.1s).
        """
        repos = self.catalog.load_data()
        results = []
        q = query.lower().strip()
        cat = category.lower().strip()

        for r in repos:
            match_query = True
            match_cat = True

            if q:
                text_to_search = f"{r.get('full_name', '')} {r.get('description', '')} {r.get('summary', '')} {' '.join(r.get('tags', []))}".lower()
                q_words = q.split()
                match_query = all(w in text_to_search for w in q_words)

            if cat:
                repo_cat = r.get("category", "").lower()
                match_cat = cat in repo_cat

            if match_query and match_cat:
                results.append({
                    "full_name": r.get("full_name"),
                    "stars": r.get("stars", 0),
                    "language": r.get("language", ""),
                    "category": r.get("category", "Chưa phân loại"),
                    "tags": r.get("tags", []),
                    "summary": r.get("summary", r.get("description", "")),
                    "use_cases": r.get("use_cases", []),
                    "notebook_ref": r.get("notebook_ref", "Chưa nạp")
                })
                if len(results) >= limit:
                    break

        return results

    def sync_to_cloud(self, repo_full_name: str, notebook_title: str = "Facebook Curated Tech Repositories") -> Dict[str, Any]:
        """
        Primitive 2: Đóng gói tài liệu chuyên sâu của repo và đẩy lên Google NotebookLM.
        """
        repo_data = self.catalog.get_repo(repo_full_name)
        if not repo_data:
            return {"status": "error", "message": f"Không tìm thấy repo '{repo_full_name}' trong catalog cục bộ."}

        # 1. Lấy hoặc tạo notebook (chống trùng lặp)
        nb_id = self.sync_engine.get_or_create_default_notebook(title=notebook_title)
        if not nb_id:
            return {"status": "error", "message": "Không thể kết nối hoặc tạo Notebook trên Google NotebookLM."}

        # 2. Đóng gói markdown kiến thức
        doc_path = self.packager.build_knowledge_document(fb_info={}, repo_info=repo_data)
        
        # 3. Đẩy file lên NotebookLM
        success = self.sync_engine.add_source_file(notebook_id=nb_id, file_path=doc_path)
        if success:
            self.catalog.update_notebook_ref(repo_full_name, notebook_title)
            return {
                "status": "success",
                "notebook_id": nb_id,
                "repo": repo_full_name,
                "message": f"Đã nạp thành công tri thức repo {repo_full_name} vào NotebookLM."
            }
        else:
            return {
                "status": "warning",
                "notebook_id": nb_id,
                "repo": repo_full_name,
                "message": f"Notebook đã sẵn sàng ({nb_id}), vui lòng kiểm tra đăng nhập nlm."
            }

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """
        Trả về định nghĩa schema chuẩn OpenAPI / JSON Schema cho các LLM API
        (như OpenAI, FreeLLMAPI, Gemini Function Calling).
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_catalog",
                    "description": "Tra cứu nhanh các repository mã nguồn trong kho chỉ mục cục bộ. Dùng để tìm công cụ, thư viện, hoặc xem tóm tắt giải pháp cho người dùng.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Từ khóa tìm kiếm (tên thư viện, bài toán, chức năng...)"},
                            "category": {"type": "string", "description": "Danh mục công nghệ cụ thể (ví dụ: 'AI & Autonomous Agents', 'Data Scraping', ...)"},
                            "limit": {"type": "integer", "description": "Số lượng repo tối đa cần lấy (mặc định 5)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sync_to_cloud",
                    "description": "Đóng gói tài liệu phân tích chuyên sâu của một repo và đẩy lên Google NotebookLM để chuẩn bị cho các câu hỏi đào sâu về code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo_full_name": {"type": "string", "description": "Tên đầy đủ của repository theo định dạng 'owner/repo' (ví dụ: 'unclecode/crawl4ai')"}
                        },
                        "required": ["repo_full_name"]
                    }
                }
            }
        ]
