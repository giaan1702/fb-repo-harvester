import sys
import json
import logging
from typing import Dict, Any, List, Optional
from vault_engine.config import DB_PATH
from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, canonicalize_url, detect_source_type

# Set utf-8 stdout/stdin
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("vault_mcp")

SERVER_NAME = "knowledge-vault-mcp"
SERVER_VERSION = "3.0.0"

# Tool Definitions (MCP Schema)
TOOLS = [
    {
        "name": "search_vault",
        "description": "Tìm kiếm tri thức chuyên sâu trong Knowledge Vault bằng Hybrid Retrieval (FTS5 BM25 + Gemini Vector Embedding). Trả về danh sách tài liệu khớp nhất kèm tóm tắt, điểm thực chiến và rủi ro.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa hoặc câu hỏi cần tra cứu (ví dụ: 'PagedAttention', 'Async web scraping', 'Multi-Agent architecture')"},
                "category": {"type": "string", "description": "Lọc theo danh mục: AI-Agents, LLM-Infra, DevOps-Cloud, Web-Systems, Data-Eng"},
                "min_score": {"type": "integer", "description": "Điểm thực chiến tối thiểu (1-10)", "default": 1},
                "curation_status": {"type": "string", "description": "Trạng thái duyệt: 'APPROVED' (Não bộ tinh hoa), 'INBOX' (Chờ duyệt), 'ALL'", "default": "APPROVED"},
                "limit": {"type": "integer", "description": "Số lượng kết quả tối đa cần lấy", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_vault_document",
        "description": "Trích xuất toàn văn bản phân tích kỹ thuật chuyên sâu (Executive Brief + Smart Article Reader + References) của một tài liệu trong Vault theo ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer", "description": "ID định danh của tài liệu trong Vault"}
            },
            "required": ["item_id"]
        }
    },
    {
        "name": "get_agent_heuristics",
        "description": "Lấy danh sách các Quy tắc hành động thực chiến (Procedural Rules) và Cạm bẫy (Anti-patterns) được đúc kết từ Bộ Não Tự Học để Agent tuân thủ khi viết code/kiến trúc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Lọc theo chủ đề kỹ thuật (ví dụ: 'AI-Agents', 'Web-Systems', 'Concurrency')"},
                "limit": {"type": "integer", "description": "Số lượng quy tắc cần lấy", "default": 20}
            }
        }
    },
    {
        "name": "get_master_synthesis",
        "description": "Lấy tài liệu Hồ Sơ Chuyên Đề Sống (Living Master Synthesis) cấp cao tổng hợp toàn bộ các mô hình tư duy, nguyên lý bất biến theo chủ đề.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_slug": {"type": "string", "description": "Slug chuyên đề (ví dụ: 'ai-agents', 'llm-infra', 'web-systems', 'devops-cloud', 'data-eng')"}
            },
            "required": ["topic_slug"]
        }
    },
    {
        "name": "record_agent_feedback",
        "description": "Ghi nhận phản hồi thực chiến sau khi Agent áp dụng một quy tắc vào code (Thành công -> củng cố nơ-ron; Thất bại -> hạ điểm & ghi chú gotcha).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "heuristic_id": {"type": "integer", "description": "ID định danh của quy tắc trong Agent Heuristics"},
                "success": {"type": "boolean", "description": "Kết quả áp dụng: true nếu thành công, false nếu gặp lỗi/thất bại"},
                "note": {"type": "string", "description": "Ghi chú bài học kinh nghiệm hoặc gotcha phát sinh trong thực tế"}
            },
            "required": ["heuristic_id", "success"]
        }
    },
    {
        "name": "get_vault_stats",
        "description": "Lấy thông tin tổng quan về số lượng tài liệu, bài viết nổi bật và phân loại danh mục trong Knowledge Vault.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "ingest_url",
        "description": "Nạp một liên kết mới (GitHub Repo, YouTube Video, ArXiv Paper hoặc Tech Blog) vào hàng đợi bóc tách của Knowledge Vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Địa chỉ URL cần nạp vào kho"}
            },
            "required": ["url"]
        }
    }
]

class VaultMCPServer:
    def __init__(self, db_path: Optional[str] = None):
        self.db = DatabaseManager(db_path=db_path or DB_PATH)
        self.ingest = IngestManager(db=self.db)

    def handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION
                    }
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                content = self.execute_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(content, ensure_ascii=False, indent=2)}
                        ]
                    }
                }
            except Exception as err:
                logger.error(f"Error executing tool {tool_name}: {err}", exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(err)}
                }

        elif method == "notifications/initialized":
            return None

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if name == "search_vault":
            query = args.get("query", "")
            category = args.get("category", "")
            min_score = args.get("min_score", 1)
            curation_status = args.get("curation_status", "APPROVED")
            limit = args.get("limit", 5)

            items = self.db.hybrid_search_vault(
                query=query,
                category=category,
                min_score=min_score,
                curation_status=curation_status,
                limit=limit
            )
            compact_results = []
            for it in items:
                compact_results.append({
                    "id": it["id"],
                    "title": it["title"],
                    "category": it["category"],
                    "practical_score": it["practical_score"],
                    "short_summary": it["short_summary"],
                    "curation_status": it.get("curation_status", "APPROVED"),
                    "tech_stack": it.get("tech_stack", []),
                    "gotchas_and_risks": it.get("gotchas_and_risks", []),
                    "url": it.get("canonical_url", "")
                })
            return {"total": len(compact_results), "items": compact_results}

        elif name == "get_vault_document":
            item_id = args.get("item_id")
            if not item_id:
                raise ValueError("item_id is required")
            item = self.db.get_vault_item_by_id(int(item_id))
            if not item:
                return {"status": "not_found", "message": f"Document {item_id} not found in Vault"}
            return {
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "practical_score": item["practical_score"],
                "canonical_url": item["canonical_url"],
                "curation_status": item.get("curation_status", "APPROVED"),
                "deep_research_md": item.get("deep_research_md", "")
            }

        elif name == "get_agent_heuristics":
            topic = args.get("topic") or args.get("category")
            limit = args.get("limit", 20)
            heuristics = self.db.get_agent_heuristics(topic=topic, limit=limit)
            return {"total": len(heuristics), "count": len(heuristics), "heuristics": heuristics}

        elif name == "get_master_synthesis":
            slug = args.get("topic_slug", "").strip()
            topic = self.db.get_synthesis_topic(slug)
            if not topic:
                return {"status": "not_found", "message": f"Synthesis topic '{slug}' not found"}
            return topic

        elif name == "record_agent_feedback":
            hid = args.get("heuristic_id")
            success = args.get("success", True)
            note = args.get("note", "")
            if not hid:
                raise ValueError("heuristic_id is required")
            ok = self.db.record_heuristic_feedback(int(hid), bool(success), note)
            return {"status": "success" if ok else "error", "heuristic_id": hid, "updated": ok}

        elif name == "get_vault_stats":
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0;")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0 AND curation_status = 'APPROVED';")
            approved = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0 AND curation_status = 'INBOX';")
            inbox = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0 AND reading_status = 'UNREAD';")
            unread = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0 AND is_starred = 1;")
            starred = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM brain_associations;")
            assoc_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM brain_synthesis_topics;")
            topics_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM agent_heuristics;")
            heuristics_cnt = cursor.fetchone()[0]

            cursor.execute("SELECT category, COUNT(*) FROM vault_items WHERE is_deleted = 0 GROUP BY category;")
            categories = {r[0]: r[1] for r in cursor.fetchall()}
            return {
                "total_items": total,
                "approved_items": approved,
                "inbox_items": inbox,
                "associations_count": assoc_cnt,
                "synthesis_topics_count": topics_cnt,
                "heuristics_count": heuristics_cnt,
                "unread_items": unread,
                "starred_items": starred,
                "categories": categories
            }

        elif name == "ingest_url":
            url = args.get("url", "").strip()
            if not url:
                raise ValueError("url is required")
            clean_url = canonicalize_url(url)
            stype = detect_source_type(clean_url)
            res = self.ingest.enqueue_url(clean_url, source_type=stype)
            return res

        else:
            raise ValueError(f"Unknown tool: {name}")

def run_stdio_server():
    server = VaultMCPServer()
    logger.info("Knowledge Vault MCP Server started on StdIO.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = server.handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            logger.error(f"Failed to process line: {e}")

if __name__ == "__main__":
    run_stdio_server()
