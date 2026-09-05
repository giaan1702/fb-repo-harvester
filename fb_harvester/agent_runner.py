"""
agent_runner.py
Autonomous AI Agent Loop sử dụng FreeLLMAPI Gateway + AgentBridge
Mô hình AI tự động nhận thức, tự chọn công cụ, tự thực thi và trả lời người dùng.
"""

import sys
import io
import json
import logging
import requests
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fb_harvester.agent_bridge import AgentBridge

logger = logging.getLogger("agent_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

GATEWAY_URL = "https://freellmapi-gateway.onrender.com/v1/chat/completions"
API_KEY = "freellmapi-85740b8f1f5ae3aa3c1f43eab41e55fa04f8027443e09ac4"

SYSTEM_PROMPT = """Bạn là Tech Repo Navigator & Knowledge Architect - trợ lý AI chuyên gia quản lý kho mã nguồn và tri thức kỹ thuật.

BỘ CÔNG CỤ CỦA BẠN:
1. `lookup_catalog`: Tra cứu nhanh kho chỉ mục 29+ repository theo từ khóa hoặc danh mục.
2. `sync_to_cloud`: Đóng gói tài liệu chuyên sâu của một repo và đẩy lên Google NotebookLM.

NGUYÊN TẮC HOẠT ĐỘNG:
- Khi người dùng hỏi tìm kiếm, so sánh hoặc gợi ý công nghệ: Hãy gọi `lookup_catalog` 1 LẦN để lấy dữ liệu.
- Ngay sau khi nhận kết quả từ công cụ: Hãy phân tích kỹ lưỡng và viết câu trả lời hoàn chỉnh, mạch lạc bằng tiếng Việt cho người dùng (nêu rõ tên repo, số sao ⭐, ưu điểm cốt lõi và use case). ĐỪNG gọi lại công cụ nếu đã có kết quả.
- Nếu repo chưa được nạp lên NotebookLM, bạn có thể thông báo và đề xuất người dùng sử dụng `sync_to_cloud` khi cần nghiên cứu sâu."""

class AutonomousAgent:
    def __init__(self, api_key: str = API_KEY, gateway_url: str = GATEWAY_URL):
        self.api_key = api_key
        self.gateway_url = gateway_url
        self.bridge = AgentBridge()
        self.tools = AgentBridge.get_tool_definitions()
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Thực thi công cụ mà AI quyết định gọi."""
        logger.info(f"⚙️ Agent thực thi công cụ: [{tool_name}] với tham số: {args}")
        if tool_name == "lookup_catalog":
            res = self.bridge.lookup_catalog(
                query=args.get("query", ""),
                category=args.get("category", ""),
                limit=args.get("limit", 5)
            )
            return json.dumps(res, ensure_ascii=False, indent=2)
        elif tool_name == "sync_to_cloud":
            res = self.bridge.sync_to_cloud(
                repo_full_name=args.get("repo_full_name", "")
            )
            return json.dumps(res, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": f"Công cụ {tool_name} không tồn tại."}, ensure_ascii=False)

    def chat(self, user_message: str) -> str:
        """Một lượt tương tác hoàn chỉnh: Phân tích -> Gọi tool -> Nhận kết quả -> Phản hồi cuối."""
        self.messages.append({"role": "user", "content": user_message})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Vòng lặp ReAct tối đa 5 lượt gọi tool
        for turn in range(5):
            body = {
                "model": "auto",
                "messages": self.messages,
                "tools": self.tools,
                "temperature": 0.3
            }

            try:
                res = requests.post(self.gateway_url, headers=headers, json=body, timeout=60)
                if res.status_code != 200:
                    return f"Lỗi API Gateway ({res.status_code}): {res.text}"

                data = res.json()
                choice = data["choices"][0]
                msg = choice["message"]
                self.messages.append(msg)

                tool_calls = msg.get("tool_calls")
                if not tool_calls:
                    # Model đã có câu trả lời cuối cùng
                    return msg.get("content", "")

                # Nếu Model yêu cầu gọi tool
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except Exception:
                        fn_args = {}

                    tool_output = self._execute_tool(fn_name, fn_args)

                    # Trả kết quả tool về cho Model
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn_name,
                        "content": tool_output
                    })

            except Exception as e:
                logger.error(f"Lỗi kết nối Agent Gateway: {e}")
                return f"Lỗi thực thi Agent: {e}"

        return "Agent đạt giới hạn số lượt gọi công cụ."
