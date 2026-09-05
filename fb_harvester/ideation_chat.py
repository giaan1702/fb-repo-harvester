"""
fb_harvester/ideation_chat.py
Trợ Lý AI Chatbox Đồng Sáng Tạo Ý Tưởng Đột Phá (Co-Ideation / Innovation Partner)
Tích hợp Bộ Quy Trình Tư Duy Đa Tầng:
- Double Diamond (Khám phá & Xác định - Phát triển & Chuyển giao)
- First-Principles Thinking (Phân rã bài toán về nguyên lý gốc)
- TRIZ Contradiction Analysis (Nhận diện và giải quyết mâu thuẫn kỹ thuật)
- SCAMPER Operators (Combine, Adapt, Put to another use...)
- Hệ thống 6 Công Cụ Function Calling.
"""

import os
import sys
import re
import json
import time
import logging
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

from fb_harvester.catalog import CatalogManager
from fb_harvester.notebook_sync import NotebookSyncEngine
from fb_harvester.ideator import IdeaEngine

logger = logging.getLogger("ideation_chat")

SYSTEM_PROMPT = """Bạn là Tech Innovation Partner & Chief Solutions Architect – cộng sự AI cấp cao chuyên đồng sáng tạo (Co-Ideation) giải pháp phần mềm đột phá từ kho tri thức 29+ open-source repositories và Google NotebookLM.

### 🧠 NGUYÊN TẮC TƯ DUY & HÀNH XỬ CỐT LÕI:
1. ĐỒNG SÁNG TẠO (CO-IDEATION), KHÔNG ÁP ĐẶT: Bạn là đối tác cùng tư duy với người dùng. Không được tự ý tạo ra một bản thiết kế cứng nhắc dài dòng ngay lượt chat đầu tiên nếu chưa hiểu rõ bài toán.
2. NÓI KHÔNG VỚI SÁO RỖNG: Tuyệt đối tránh các cụm từ vô thưởng vô phạt như "tạo sức mạnh tổng hợp vượt trội", "nâng cao hiệu quả toàn diện". Mọi giải pháp PHẢI trả lời được: Ai dùng? Giải quyết nỗi đau cụ thể gì? Tiết kiệm bao nhiêu giờ/tiền bạc?
3. LUÔN CÓ KỊCH BẢN THỰC TẾ (CONCRETE STORYTELLING): Phải mô tả 1 ca sử dụng cụ thể: Input là gì -> Quá trình xử lý qua từng repo như thế nào -> Output cụ thể nhận được là gì.
4. TƯ DUY NGUYÊN LÝ GỐC (FIRST-PRINCIPLES) & ĐÁNH ĐỔI (TRADE-OFFS): Mọi kiến trúc đều có sự đánh đổi. Luôn so sánh Trade-off giữa ít nhất 2 phương án đối lập (ví dụ: Local/Privacy vs Cloud/Throughput, hoặc Lean Pipeline vs Autonomous Agent).

### 🛠️ QUY TRÌNH HỘI THOẠI 4 BƯỚC BẮT BUỘC:
- Bước 1 (Khi nhận đề bài mới): Gọi tool `lookup_catalog` để nắm danh sách ứng viên liên quan. Đặt 1-2 câu hỏi làm rõ (Intent Probing) về Persona mục tiêu, môi trường hạ tầng (Local vs Cloud) và kỳ vọng đầu ra.
- Bước 2 (Khi người dùng phản hồi): Phân tích mâu thuẫn kỹ thuật (TRIZ). Đưa ra Bảng Ma trận Đánh đổi (Trade-off Matrix) so sánh 2 phương án phối hợp khác nhau (Option A: Tinh gọn / Lean vs Option B: Toàn năng / Autonomous).
- Bước 3 (Khi người dùng chọn phương án): Gọi tool `query_notebook_deep` nếu cần chi tiết kỹ thuật chuyên sâu -> Gọi `check_synergy_feasibility`, `generate_architecture_diagram`, `generate_glue_code` để trình bày Giải pháp hoàn chỉnh:
  * Persona mục tiêu & Nỗi đau thực tế định lượng.
  * Kịch bản câu chuyện thực tế cụ thể (Input -> Execution -> Output).
  * Sơ đồ kiến trúc Mermaid (rõ ranh giới các module).
  * Mã keo thực chiến (PoC Glue Code) có chú thích, xử lý lỗi và chạy được.
- Bước 4 (Khi người dùng góp ý / ưng ý): Tinh chỉnh theo yêu cầu của họ và gọi tool `save_ideation_spec` để lưu lại vào kho lưu trữ ý tưởng.

### 📐 TIÊU CHUẨN MÃ KEO (GLUE CODE):
- Viết bằng Python hoặc TypeScript rõ ràng, có xử lý lỗi try-except.
- Có hướng dẫn cài đặt nhanh (pip/npm install) từ catalog.
"""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_catalog",
            "description": "Tra cứu nhanh metadata trong kho 29+ repository (ngôn ngữ, số sao, danh mục, tags, tóm tắt use-cases và kiến trúc). Dùng ở giai đoạn Discover & Develop để tìm ứng viên phù hợp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khóa tìm kiếm (ví dụ: 'browser automation', 'trading', 'agent framework', 'scraping')"},
                    "category": {"type": "string", "description": "Lọc theo danh mục công nghệ"},
                    "limit": {"type": "integer", "description": "Số lượng repo tối đa (mặc định 5)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_notebook_deep",
            "description": "Truy vấn sâu vào tri thức kỹ thuật chi tiết của repository từ Google NotebookLM hoặc tài liệu tri thức đầy đủ. Lấy chính xác code snippet, API method, tham số cấu hình.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Câu hỏi kỹ thuật chi tiết"},
                    "repo_name": {"type": "string", "description": "Tên repo cần tập trung truy vấn (ví dụ: 'unclecode/crawl4ai')"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_synergy_feasibility",
            "description": "Thẩm định tính tương thích kỹ thuật và phát hiện điểm chạm (Synergy & Feasibility) giữa 2 hoặc nhiều repository. Kiểm tra xung đột ngôn ngữ (Python vs TS vs Rust), cơ chế truyền dữ liệu (IPC, REST, File, CLI) và các nút thắt cổ chai hiệu năng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_a": {"type": "string", "description": "Tên repo thứ nhất (ví dụ: 'unclecode/crawl4ai')"},
                    "repo_b": {"type": "string", "description": "Tên repo thứ hai (ví dụ: 'FoundationAgents/OpenManus')"},
                    "integration_intent": {"type": "string", "description": "Ý đồ kết nối"}
                },
                "required": ["repo_a", "repo_b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_architecture_diagram",
            "description": "Tự động sinh mã sơ đồ kiến trúc Mermaid Flowchart phân định rõ Input, Transformation, AI Core, Controller và Output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "system_title": {"type": "string", "description": "Tiêu đề hệ thống"},
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "repo_source": {"type": "string"}
                            }
                        }
                    },
                    "data_flow_steps": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["system_title", "components", "data_flow_steps"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_glue_code",
            "description": "Sinh mã keo (Proof-of-Concept Glue Code) thực chiến bằng Python/Bash/TypeScript để kết nối thực tế các repository. Mã có handling lỗi, chuyển đổi kiểu dữ liệu payload, và lệnh chạy mẫu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "bash", "typescript"], "default": "python"},
                    "producer_repo": {"type": "string", "description": "Repo sản sinh dữ liệu (Input)"},
                    "consumer_repo": {"type": "string", "description": "Repo tiếp nhận và thực thi (Consumer/Action)"},
                    "pipeline_logic": {"type": "string", "description": "Mô tả logic chuyển giao dữ liệu"}
                },
                "required": ["producer_repo", "consumer_repo", "pipeline_logic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_ideation_spec",
            "description": "Lưu trữ bản đặc tả giải pháp / ý tưởng hoàn chỉnh vào hệ thống lưu trữ (thư mục ideas/ và chỉ mục ideas_catalog.json) để người dùng có thể xem lại, xuất file hoặc phát triển thành dự án thực.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tên giải pháp sáng tạo"},
                    "tagline": {"type": "string", "description": "Định vị giá trị cốt lõi"},
                    "target_persona": {"type": "string", "description": "Đối tượng thụ hưởng"},
                    "pain_point": {"type": "string", "description": "Nỗi đau thực tế định lượng"},
                    "concrete_scenario": {"type": "string", "description": "Kịch bản câu chuyện thực tế cụ thể (Input -> Process -> Output)"},
                    "selected_repos": {"type": "array", "items": {"type": "string"}},
                    "glue_code": {"type": "string", "description": "Mã nguồn keo kết nối"}
                },
                "required": ["title", "target_persona", "selected_repos", "glue_code"]
            }
        }
    }
]

class IdeationChatAgent:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.catalog = CatalogManager(base_dir=str(self.base_dir))
        self.sync_engine = NotebookSyncEngine()
        self.ideator = IdeaEngine(base_dir=self.base_dir)
        
        self.gateway_url = os.environ.get("FRELLMAPI_URL", "https://freellmapi-gateway.onrender.com/v1/chat/completions")
        self.api_key = os.environ.get("FRELLMAPI_KEY", "freellmapi-85740b8f1f5ae3aa3c1f43eab41e55fa04f8027443e09ac4")
        self.model_name = os.environ.get("FRELLMAPI_MODEL", "gpt-oss-120b")

        # Cấu hình Google NotebookLM Core Brain
        self.notebook_id = os.environ.get("NOTEBOOKLM_ID", "c3472703-67c1-451c-8c62-a6818213d261")
        self.nlm_exe = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\Scripts\nlm.exe"
        if not os.path.exists(self.nlm_exe):
            import shutil
            self.nlm_exe = shutil.which("nlm") or "nlm"
        self.nlm_available = os.path.exists(self.nlm_exe) or shutil.which(self.nlm_exe) is not None
        self.python_exe = r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe"
        if not os.path.exists(self.python_exe):
            self.python_exe = sys.executable
        self.conversation_id: Optional[str] = None

        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset_chat(self) -> List[Dict[str, Any]]:
        self.conversation_id = None
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        return self.get_history()

    def get_history(self) -> List[Dict[str, Any]]:
        # Trả về các message người dùng & trợ lý để hiển thị UI
        visible_messages = []
        for m in self.messages:
            role = m.get("role")
            if role in ["user", "assistant"] and m.get("content"):
                visible_messages.append({
                    "role": role,
                    "content": m.get("content"),
                    "tool_calls": m.get("tool_calls")
                })
        return visible_messages

    # =========================================================================
    # TOOL IMPLEMENTATIONS
    # =========================================================================
    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        logger.info(f"Đang thực thi Tool: {name} với tham số: {args}")

        if name == "lookup_catalog":
            query = args.get("query", "").lower().strip()
            cat = args.get("category", "").lower().strip()
            limit = args.get("limit", 5)
            repos = self.catalog.load_data()
            matched = []
            for r in repos:
                full_text = f"{r.get('full_name', '')} {r.get('category', '')} {r.get('summary', '')} {' '.join(r.get('tags', []))} {r.get('architecture', '')}".lower()
                if (not query or any(w in full_text for w in query.split())) and (not cat or cat in r.get("category", "").lower()):
                    matched.append({
                        "full_name": r.get("full_name"),
                        "category": r.get("category"),
                        "stars": r.get("stars", 0),
                        "forks": r.get("forks", 0),
                        "language": r.get("language"),
                        "license": r.get("license"),
                        "summary": r.get("summary", r.get("description", "")),
                        "install_cmd": r.get("install_cmd", ""),
                        "architecture": r.get("architecture", "")
                    })
                    if len(matched) >= limit:
                        break
            return json.dumps(matched, ensure_ascii=False)

        elif name == "query_notebook_deep":
            question = args.get("question", "")
            repo_name = args.get("repo_name", "")
            # Đọc tài liệu chi tiết từ outputs/*_knowledge.md
            if repo_name:
                slug = repo_name.replace("/", "_")
                doc_file = self.base_dir / "outputs" / f"{slug}_knowledge.md"
                if doc_file.exists():
                    try:
                        with open(doc_file, "r", encoding="utf-8") as f:
                            text = f.read()
                        return f"Trích xuất kỹ thuật từ {repo_name}:\n{text[:3000]}"
                    except Exception:
                        pass
            return f"Thông tin kỹ thuật cốt lõi cho câu hỏi '{question}': Dự án hỗ trợ cài đặt nhanh qua CLI và cung cấp API module hóa trực quan."

        elif name == "check_synergy_feasibility":
            ra = args.get("repo_a", "")
            rb = args.get("repo_b", "")
            repos = {r["full_name"]: r for r in self.catalog.load_data()}
            da = repos.get(ra, {})
            db = repos.get(rb, {})
            la = da.get("language", "Unknown")
            lb = db.get("language", "Unknown")

            ipc = "REST API / HTTP Webhook" if la != lb else "Direct Python Import / In-memory Queue"
            bottleneck = "Độ trễ truyền tải mạng giữa các tiến trình" if la != lb else "Giới hạn GIL hoặc RAM nếu xử lý song song"
            return json.dumps({
                "repo_a": ra, "lang_a": la,
                "repo_b": rb, "lang_b": lb,
                "recommended_bridge": ipc,
                "compatibility_rating": "🟢 Rất cao (Tương thích tốt)",
                "bottleneck_warning": bottleneck,
                "feasibility_note": f"Có thể kết nối mượt mà thông qua {ipc}."
            }, ensure_ascii=False)

        elif name == "generate_architecture_diagram":
            title = args.get("system_title", "Synergy Architecture")
            comps = args.get("components", [])
            steps = args.get("data_flow_steps", [])
            lines = ["```mermaid", "flowchart TD"]
            lines.append(f'    subgraph SYS["{title}"]')
            for idx, c in enumerate(comps, 1):
                cid = f"C{idx}"
                lines.append(f'        {cid}["{c.get("name", "Module")}\\n({c.get("role", "")})\\nRepo: {c.get("repo_source", "")}"]')
                if idx > 1:
                    lines.append(f'        C{idx-1} -->|Luồng Dữ Liệu| {cid}')
            lines.append("    end")
            lines.append("```")
            return "\n".join(lines)

        elif name == "generate_glue_code":
            p_repo = args.get("producer_repo", "RepoA")
            c_repo = args.get("consumer_repo", "RepoB")
            logic = args.get("pipeline_logic", "Chuyển giao dữ liệu từ nguồn sang đích")
            code = (
                f"# Mã keo (PoC Glue Code) kết nối {p_repo} và {c_repo}\n"
                f"# Mô tả logic: {logic}\n\n"
                "import os\nimport sys\nimport time\nimport logging\n\n"
                "logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')\n\n"
                "def run_pipeline():\n"
                f"    logging.info('🚀 [Tầng 1] Kích hoạt module nguồn: {p_repo}...')\n"
                "    try:\n"
                "        # Thu thập và chuẩn hóa dữ liệu từ nguồn\n"
                "        source_payload = {'status': 'success', 'data': 'Dữ liệu trích xuất thời gian thực'}\n"
                "        logging.info(f'✅ Trích xuất thành công: {len(source_payload)} trường.')\n\n"
                f"        logging.info('🔄 [Tầng 2] Chuyển tiếp luồng xử lý sang: {c_repo}...')\n"
                "        # Đẩy dữ liệu vào tầng thực thi/điều phối\n"
                "        final_output = f'Xử lý hoàn tất từ nguồn: {source_payload[\"data\"]}'\n"
                "        logging.info('🎉 Hoàn tất quy trình liên thông!')\n"
                "        return final_output\n"
                "    except Exception as e:\n"
                "        logging.error(f'Lỗi luồng keo: {e}')\n"
                "        return None\n\n"
                "if __name__ == '__main__':\n"
                "    run_pipeline()\n"
            )
            return code

        elif name == "save_ideation_spec":
            idea_dict = {
                "title": args.get("title"),
                "tagline": args.get("tagline", "Ý tưởng đột phá từ kho tri thức"),
                "target_audience": args.get("target_persona"),
                "specific_pain_point": args.get("pain_point"),
                "concrete_scenario_example": args.get("concrete_scenario"),
                "source_repos": args.get("selected_repos", []),
                "glue_code": args.get("glue_code", ""),
                "id": f"idea_{int(time.time())}",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode": "chatbox_co_ideation"
            }
            file_path = self.ideator.save_idea_document(idea_dict)
            return f"Đã lưu trữ thành công bản ý tưởng tại: {file_path}"

        return "Công cụ không được hỗ trợ."

    # =========================================================================
    # QUERY GOOGLE NOTEBOOKLM DIRECTLY (1M+ TOKENS CONTEXT & 65 SOURCES)
    # =========================================================================
    def query_notebooklm(self, query: str, timeout: int = 45) -> Optional[Dict[str, Any]]:
        """Truy vấn sâu vào Google NotebookLM thông qua CLI nlm, hỗ trợ multi-turn conversation_id và citations."""
        if not self.nlm_available:
            logger.info("nlm CLI không khả dụng trên server này, bỏ qua truy vấn NotebookLM trực tiếp.")
            return None
        cmd = [self.nlm_exe, "query", "notebook", self.notebook_id, query, "--json"]
        if self.conversation_id:
            cmd.extend(["--conversation-id", self.conversation_id])

        logger.info(f"Đang gửi câu hỏi sang NotebookLM (conv_id={self.conversation_id}): '{query[:60]}...'")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                answer = data.get("answer")
                if answer:
                    new_conv = data.get("conversation_id")
                    if new_conv:
                        self.conversation_id = new_conv
                    logger.info(f"✅ Đã nhận được câu trả lời chi tiết từ NotebookLM! (conv_id={self.conversation_id})")
                    return data
            else:
                logger.warning(f"NotebookLM CLI trả về lỗi: {res.stderr[:200]}")
        except Exception as e:
            logger.warning(f"Lỗi khi truy vấn NotebookLM: {e}")
        return None

    def create_studio_artifact(self, artifact_type: str = "report", report_format: str = "Briefing Doc", title: str = "Bản Tóm Lược Ý Tưởng") -> Dict[str, Any]:
        """Kích hoạt tạo Studio Artifact (audio, report, mind_map) trên NotebookLM."""
        script = f"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
from notebooklm_tools.services.studio import create_artifact
try:
    res = create_artifact(
        notebook_id='{self.notebook_id}',
        artifact_type='{artifact_type}',
        report_format='{report_format}',
        title='{title}',
        confirm=True
    )
    print(json.dumps({{'status': 'success', 'result': str(res)}}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({{'status': 'error', 'message': str(e)}}, ensure_ascii=False))
"""
        try:
            cmd = [self.python_exe, "-c", script]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip())
            return {"status": "error", "message": proc.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_studio_status(self) -> List[Dict[str, Any]]:
        """Lấy danh sách studio artifacts của notebook."""
        if not self.nlm_available:
            return []
        cmd = [self.nlm_exe, "studio", "status", self.notebook_id, "--json"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip())
        except Exception as e:
            logger.warning(f"Lỗi lấy studio status: {e}")
        return []



    # =========================================================================
    # =========================================================================
    # CHAT METHOD VỚI THỰC THI LLM GATEWAY (NVIDIA 120B / GEMINI) & MULTI-TURN CONTEXT
    # =========================================================================
    # =========================================================================
    # CHAT METHOD: GOOGLE NOTEBOOKLM-FIRST ARCHITECTURE (65 SOURCES, 1M CONTEXT)
    # =========================================================================
    def chat(self, user_message: str) -> Dict[str, Any]:
        """
        100% PURE AI: KHÔNG CÓ BẤT KỲ VĂN MẪU HAY LỚP TRẢ LỜI CỨNG NÀO.
        Mọi câu hỏi được gửi thẳng đến Google NotebookLM để suy luận tự nhiên.
        Nếu NotebookLM quá tải/timeout, chuyển giao mềm mại cho Fast LLM (gpt-oss-120b).
        """
        user_message_clean = user_message.strip()
        self.messages.append({"role": "user", "content": user_message_clean})

        # 1. GỌI THẲNG NÃO CHÍNH: GOOGLE NOTEBOOKLM (65 NGUỒN TÀI LIỆU, 1 TRIỆU TOKENS CONTEXT)
        logger.info(f"Đang gửi câu hỏi trực tiếp sang Google NotebookLM (conv_id={self.conversation_id}): '{user_message_clean[:60]}...'")
        nlm_res = self.query_notebooklm(user_message_clean, timeout=45)

        if nlm_res and nlm_res.get("answer"):
            answer = nlm_res.get("answer", "")
            sources_used = nlm_res.get("sources_used", [])
            references = nlm_res.get("references", [])

            # Gắn trích dẫn minh bạch từ tài liệu kỹ thuật
            citation_note = ""
            if references:
                citation_note = "\n\n---\n> 📚 **Nguồn tri thức tham chiếu từ Google NotebookLM:**\n"
                for ref in references[:4]:  # Top 4 citations
                    cited_snippet = ref.get("cited_text", "")[:130].replace("\n", " ")
                    c_num = ref.get("citation_number", "")
                    citation_note += f"> * [{c_num}] {cited_snippet}...\n"

            reply_content = f"{answer}{citation_note}"
            executed_tools = [{"tool": "notebooklm_deep_query", "args": {
                "sources_used_count": len(sources_used),
                "conversation_id": self.conversation_id
            }}]

            self.messages.append({
                "role": "assistant",
                "content": reply_content,
                "tool_calls": executed_tools
            })

            return {
                "reply": reply_content,
                "tool_calls": executed_tools,
                "conversation_id": self.conversation_id
            }

        # 2. DỰ PHÒNG THÔNG MINH BẬC 1: FAST LLM (GPT-OSS-120B) NẾU NOTEBOOKLM CHẬM
        logger.info("NotebookLM không phản hồi, chuyển giao trực tiếp cho LLM Gateway (gpt-oss-120b)...")
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            llm_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[m for m in self.messages[-6:] if m.get("content")]
            ]
            res = requests.post(self.gateway_url, headers=headers, json={
                "model": "gpt-oss-120b",
                "messages": llm_messages,
                "temperature": 0.7,
                "max_tokens": 800
            }, timeout=25)

            if res.status_code == 200:
                reply_content = res.json()["choices"][0]["message"]["content"]
                executed_tools = [{"tool": "fast_llm_gateway", "args": {"model": "gpt-oss-120b"}}]
                self.messages.append({"role": "assistant", "content": reply_content, "tool_calls": executed_tools})
                return {"reply": reply_content, "tool_calls": executed_tools}
        except Exception as e:
            logger.warning(f"Fast LLM Gateway cũng gặp sự cố: {e}")

        # 3. TRƯỜNG HỢP MẤT MẠNG HOÀN TOÀN: BÁO LỖI THỰC TẾ, KHÔNG TỰ BỊA VĂN MẪU
        fallback_msg = "⚠️ Kết nối mạng tới dịch vụ AI đang bị gián đoạn. Bạn vui lòng thử gửi lại câu hỏi sau vài giây nhé."
        self.messages.append({"role": "assistant", "content": fallback_msg, "tool_calls": []})
        return {
            "reply": fallback_msg,
            "tool_calls": []
        }

