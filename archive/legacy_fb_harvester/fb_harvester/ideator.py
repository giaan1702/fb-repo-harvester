"""
fb_harvester/ideator.py
Bộ máy Lên Ý Tưởng & Phối Hợp Đa Repo (Multi-Repo Ideation & Synergy Engine)
Áp dụng mô hình Phễu Tinh Lọc 3 Tầng:
- Tầng 1: Lọc siêu nhẹ (Local Thin Filter) dùng catalog.json và Ma trận tương hỗ.
- Tầng 2: Rút trích sâu mục tiêu (Deep Targeted Retrieval) lấy API, Quickstart, Code mẫu.
- Tầng 3: Tinh chế ý tưởng, thiết kế kiến trúc và sinh mã keo (PoC Glue Code) qua FreeLLMAPI Gateway.
"""

import os
import re
import sys
import json
import time
import random
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("ideator")

# Ma trận tương hỗ danh mục (Category Synergy Matrix)
SYNERGY_PATTERNS = [
    {
        "pattern": ["Data Scraping & Web Automation", "AI & Autonomous Agents"],
        "concept": "Autonomous Web Research & Action Agent",
        "description": "Cào bóc tách dữ liệu mạng thời gian thực kết hợp AI Agent tự động suy luận và thực thi tác vụ"
    },
    {
        "pattern": ["AI & Autonomous Agents", "Computer Vision & Generative Media"],
        "concept": "Multimodal Autonomous Content Creator",
        "description": "Agent tự động lập kế hoạch kịch bản và điều khiển pipeline sinh ảnh/video chất lượng cao"
    },
    {
        "pattern": ["Data Scraping & Web Automation", "Computer Vision & Generative Media"],
        "concept": "Automated Media Harvester & Synthesizer",
        "description": "Thu thập tư liệu từ web/mạng xã hội và biến đổi thành nội dung đa phương tiện mới"
    },
    {
        "pattern": ["Trading & Algorithmic Finance", "AI & Autonomous Agents"],
        "concept": "AI-Driven Quantitative Sentinel",
        "description": "Bot giao dịch kết hợp phân tích tin tức và tác tử tự chủ phản ứng với biến động thị trường"
    },
    {
        "pattern": ["Cybersecurity & Reverse Engineering", "AI & Autonomous Agents"],
        "concept": "Intelligent Physical & Hardware Security Agent",
        "description": "Hệ thống bảo mật phần cứng / RFID được điều phối và giám sát bởi trợ lý AI cục bộ"
    },
    {
        "pattern": ["Backend & High-Performance Systems", "Developer Tools, CLI & Terminal"],
        "concept": "High-Throughput Developer Automation Engine",
        "description": "Hạ tầng backend bất đồng bộ kết hợp công cụ CLI tốc độ cao để tự động hóa quy trình phát triển"
    },
    {
        "pattern": ["Fullstack, Web & UI Frameworks", "Data Scraping & Web Automation"],
        "concept": "Real-time Data Intelligence Dashboard",
        "description": "Cổng thông tin hiển thị dữ liệu cào tự động thời gian thực với giao diện tương tác cao"
    }
]

class IdeaEngine:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.catalog_path = self.base_dir / "catalog.json"
        self.ideas_dir = self.base_dir / "ideas"
        self.ideas_catalog_path = self.ideas_dir / "ideas_catalog.json"
        self.outputs_dir = self.base_dir / "outputs"
        
        self.ideas_dir.mkdir(parents=True, exist_ok=True)
        if not self.ideas_catalog_path.exists():
            with open(self.ideas_catalog_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        self.api_url = os.environ.get("FRELLMAPI_URL", "https://freellmapi-gateway.onrender.com/v1/chat/completions")
        self.api_key = os.environ.get("FRELLMAPI_KEY", "freellmapi-85740b8f1f5ae3aa3c1f43eab41e55fa04f8027443e09ac4")
        self.model = os.environ.get("FRELLMAPI_MODEL", "gpt-oss-120b")

    def load_catalog(self) -> List[Dict[str, Any]]:
        if not self.catalog_path.exists():
            return []
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc catalog.json: {e}")
            return []

    def load_ideas(self) -> List[Dict[str, Any]]:
        if not self.ideas_catalog_path.exists():
            return []
        try:
            with open(self.ideas_catalog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi khi đọc ideas_catalog.json: {e}")
            return []

    def select_candidates(self, mode: str = "surprise", goal: str = "", selected_repos: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        all_repos = self.load_catalog()
        if not all_repos:
            return []

        repo_dict = {r.get("full_name"): r for r in all_repos if r.get("full_name")}

        # 1. Chế độ Manual: Người dùng chọn đích danh
        if mode == "manual" and selected_repos:
            candidates = [repo_dict[r] for r in selected_repos if r in repo_dict]
            if len(candidates) >= 2:
                return candidates[:3]

        # 2. Chế độ Goal: Khớp theo từ khóa bài toán
        if mode == "goal" and goal:
            goal_lower = goal.lower()
            scored = []
            for r in all_repos:
                score = 0
                search_text = f"{r.get('full_name', '')} {r.get('category', '')} {r.get('summary', '')} {' '.join(r.get('tags', []))} {r.get('architecture', '')}".lower()
                for word in goal_lower.split():
                    if len(word) > 2 and word in search_text:
                        score += 1
                if score > 0:
                    scored.append((score, r))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            if len(scored) >= 2:
                chosen = [scored[0][1]]
                for _, r in scored[1:]:
                    if r.get("category") != chosen[0].get("category") and len(chosen) < 3:
                        chosen.append(r)
                if len(chosen) < 2 and len(scored) >= 2:
                    chosen.append(scored[1][1])
                return chosen

        # 3. Chế độ Surprise / Tự động: Chọn cặp tương hỗ từ Ma trận Synergy
        random.shuffle(SYNERGY_PATTERNS)
        for pattern_info in SYNERGY_PATTERNS:
            cat_a, cat_b = pattern_info["pattern"][0], pattern_info["pattern"][1]
            repos_a = [r for r in all_repos if r.get("category") == cat_a]
            repos_b = [r for r in all_repos if r.get("category") == cat_b]
            if repos_a and repos_b:
                return [random.choice(repos_a), random.choice(repos_b)]

        if len(all_repos) >= 2:
            return random.sample(all_repos, 2)
        return all_repos

    def extract_deep_interfaces(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched = []
        for r in candidates:
            full_name = r.get("full_name", "")
            slug = full_name.replace("/", "_")
            doc_file = self.outputs_dir / f"{slug}_knowledge.md"

            snippet_text = r.get("code_snippet", "")
            quickstart_text = r.get("install_cmd", "")
            arch_text = r.get("architecture", "")
            components = r.get("core_components", [])

            if doc_file.exists():
                try:
                    with open(doc_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    capture = False
                    captured_lines = []
                    for line in lines:
                        if "## 💡 3. Nhận Định" in line or "## 🚀 4. Hướng Dẫn" in line or "## 💻 5. Mã Nguồn" in line:
                            capture = True
                        elif "## 📖 6. Nội Dung README" in line:
                            capture = False
                            break
                        if capture:
                            captured_lines.append(line)
                    if captured_lines:
                        r["deep_interface_doc"] = "".join(captured_lines[:60])
                except Exception:
                    pass

            enriched.append({
                "full_name": full_name,
                "category": r.get("category"),
                "language": r.get("language"),
                "summary": r.get("summary"),
                "architecture": arch_text,
                "install_cmd": quickstart_text,
                "code_snippet": snippet_text,
                "core_components": components,
                "deep_doc": r.get("deep_interface_doc", "")
            })
        return enriched

    def generate_idea(self, mode: str = "surprise", goal: str = "", selected_repos: Optional[List[str]] = None) -> Dict[str, Any]:
        candidates = self.select_candidates(mode=mode, goal=goal, selected_repos=selected_repos)
        if len(candidates) < 2:
            return {"error": "Cần ít nhất 2 repository để tạo ý tưởng phối hợp tương hỗ."}

        enriched_repos = self.extract_deep_interfaces(candidates)
        repo_names = [r["full_name"] for r in enriched_repos]
        logger.info(f"Đang sinh ý tưởng kết hợp cho: {repo_names} (Mode: {mode})")

        repo_context_list = []
        for idx, r in enumerate(enriched_repos, 1):
            comp_str = ", ".join(r["core_components"]) if r["core_components"] else "N/A"
            repo_context_list.append(
                f"--- REPO #{idx}: {r['full_name']} ---\n"
                f"- Danh mục: {r['category']} | Ngôn ngữ: {r['language']}\n"
                f"- Kiến trúc: {r['architecture']}\n"
                f"- Tóm tắt: {r['summary']}\n"
                f"- Lệnh cài đặt nhanh: {r['install_cmd']}\n"
                f"- Thành phần cốt lõi: {comp_str}\n"
                f"- Code mẫu ngắn:\n{r['code_snippet'][:400]}\n"
            )
        repo_context = "\n".join(repo_context_list)
        user_goal_clause = f"Mục tiêu người dùng yêu cầu: '{goal}'" if goal else "Mục tiêu: Tự do sáng tạo sản phẩm đột phá từ sự kết hợp các công nghệ trên."

        system_prompt = (
            "Bạn là một Kiến Trúc Sư Phần Mềm Trưởng (Principal Solution Architect) và Chuyên Gia Đổi Mới Sáng Tạo AI. "
            "Nhiệm vụ của bạn là kết hợp 2 hoặc nhiều repository mã nguồn mở thành MỘT GIẢI PHÁP / SẢN PHẨM HOÀN CHỈNH, ĐỘT PHÁ VÀ THỰC CHIẾN.\n\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. TUYỆT ĐỐI KHÔNG DÙNG CÂU CHỮ CHUNG CHUNG HOẶC SÁO RỖNG (như 'sự thiếu hụt cầu nối tạo điểm nghẽn').\n"
            "2. PHẢI NÓI RÕ NÓ GIẢI QUYẾT VẤN ĐỀ GÌ TRONG THỰC TẾ: Ai là người gặp vấn đề? Nỗi đau cụ thể là gì? Mất bao nhiêu giờ? Lãng phí bao nhiêu tiền/công sức nếu làm thủ công?\n"
            "3. PHẢI CÓ VÍ DỤ CỤ THỂ MINH HỌA (Use Case Scenario Walkthrough): Kể một câu chuyện thực tế cụ thể (ví dụ: 'Anh Nam là một content creator...', 'Chị Lan là lập trình viên solo...') nêu rõ dữ liệu đầu vào là gì, hệ thống xử lý từng bước thế nào, và kết quả đầu ra thực tế nhận được là gì kèm lợi ích định lượng.\n"
            "4. Mã keo (glue code) phải có chú thích cụ thể từng bước có thể chạy được.\n\n"
            "BẮT BUỘC TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON với cấu trúc sau:\n"
            "{\n"
            '  "title": "Tên sản phẩm / Giải pháp sáng tạo",\n'
            '  "tagline": "Slogan hoặc giá trị cốt lõi trong 1 câu ngắn gọn",\n'
            '  "target_audience": "Đối tượng người dùng mục tiêu cụ thể",\n'
            '  "specific_pain_point": "Nỗi đau thực tế cụ thể: Phân tích chi tiết họ đang gặp khó khăn gì, mất bao nhiêu thời gian/tiền bạc nếu làm thủ công, và tại sao một repo riêng lẻ không giải quyết được",\n'
            '  "concrete_scenario_example": "VÍ DỤ KỊCH BẢN THỰC TẾ CỤ THỂ: Một câu chuyện người dùng thực tế với Input cụ thể -> Quá trình xử lý -> Output kết quả cụ thể nhận được và lợi ích định lượng",\n'
            '  "solution_overview": "Giải pháp kết hợp: giải thích cách chúng phối hợp để giải quyết dứt điểm nỗi đau trên",\n'
            '  "synergy_roles": [\n'
            '    {"repo": "tên_repo", "role": "Vai trò cụ thể trong kiến trúc (Input/Controller/Output/Storage)"}\n'
            '  ],\n'
            '  "data_flow": [\n'
            '    "Bước 1: ...",\n'
            '    "Bước 2: ...",\n'
            '    "Bước 3: ..."\n'
            '  ],\n'
            '  "glue_code": "# Đoạn mã keo thực chiến (Python/Bash) 25-45 dòng kết nối thực tế hai repo",\n'
            '  "risks_and_mitigation": [\n'
            '    {"risk": "Rủi ro kỹ thuật (ví dụ: xung đột ngôn ngữ, rate limit, RAM)", "mitigation": "Giải pháp khắc phục"}\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"Dưới đây là thông tin kỹ thuật của các repository:\n\n{repo_context}\n"
            f"{user_goal_clause}\n\n"
            "Hãy sáng tạo bản thiết kế ý tưởng kết hợp hoàn chỉnh bằng JSON theo đúng các yêu cầu trên."
        )

        idea_data = None
        try:
            resp = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=35
            )
            if resp.status_code == 200:
                raw_content = resp.json()["choices"][0]["message"]["content"].strip()
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if match:
                    clean_json = match.group(0)
                    idea_data = json.loads(clean_json)
        except Exception as e:
            logger.warning(f"Lỗi khi gọi AI Ideation: {e}. Kích hoạt fallback kỹ thuật.")

        if not idea_data:
            idea_data = self._generate_fallback_idea(enriched_repos, goal=goal)

        idea_id = f"idea_{int(time.time())}_{random.randint(1000, 9999)}"
        idea_data["id"] = idea_id
        idea_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        idea_data["mode"] = mode
        idea_data["source_repos"] = repo_names
        idea_data["user_goal"] = goal

        self.save_idea_document(idea_data)
        return idea_data

    def _generate_fallback_idea(self, repos: List[Dict[str, Any]], goal: str = "") -> Dict[str, Any]:
        r1 = repos[0]
        r2 = repos[1]
        name1 = r1["full_name"]
        name2 = r2["full_name"]
        
        title = f"Hệ Thống Tích Hợp Đột Phá: {name1.split('/')[-1]} & {name2.split('/')[-1]}"
        tagline = f"Tự động hóa quy trình nghiệp vụ bằng phối hợp {r1.get('category')} và {r2.get('category')}"
        
        target_aud = f"Lập trình viên và các đội ngũ phát triển sản phẩm trong lĩnh vực {r1.get('category')} & {r2.get('category')}"
        pain_point = (
            f"Trong thực tế, khi muốn kết hợp khả năng thu thập/xử lý của {name1} và năng lực tự động hoá của {name2}, "
            f"kỹ sư thường phải tốn từ 2 đến 4 giờ mỗi ngày để viết các đoạn script chuyển đổi thủ công, xử lý lỗi nghẽn dữ liệu "
            f"và khắc phục tình trạng thiếu tương thích về định dạng giữa hai thư viện. "
            f"Nếu dùng riêng lẻ, {name1} chỉ dừng lại ở mức công cụ nguồn mà không có bộ máy tự động hoá, "
            f"trong khi {name2} thiếu nguồn dữ liệu chất lượng đầu vào để phát huy tối đa sức mạnh."
        )
        scenario_example = (
            f"**Ví dụ kịch bản cụ thể (End-to-End Walkthrough)**:\n\n"
            f"* **Người dùng**: Kỹ sư Nguyễn Văn A (lập trình viên phát triển hệ thống tự động).\n"
            f"* **Dữ liệu đầu vào (Input)**: Yêu cầu định kỳ vào lúc 06:00 sáng mỗi ngày hoặc khi có sự kiện phát sinh từ {name1}.\n"
            f"* **Quá trình xử lý (Execution)**:\n"
            f"  1. Module `{name1}` tự động chạy, trích xuất và chuẩn hóa gói dữ liệu nguồn (ví dụ 100 sự kiện/bản ghi mới nhất) thành định dạng JSON chuẩn.\n"
            f"  2. Cầu nối tự động (Mã keo) tiếp nhận payload, kiểm tra tính toàn vẹn và đẩy qua kênh xử lý của `{name2}`.\n"
            f"  3. Module `{name2}` tiếp nhận, áp dụng thuật toán phân tích và thực thi hành động tương ứng (ví dụ sinh báo cáo tổng hợp, kích hoạt webhook hoặc gửi thông báo cảnh báo).\n"
            f"* **Kết quả đầu ra (Output)**: Một bản báo cáo hoàn chỉnh được gửi tự động về Telegram/Dashboard vào lúc 06:05 sáng, giúp kỹ sư A tiết kiệm 2 tiếng ngồi quét dữ liệu bằng tay mỗi sáng."
        )

        glue_code = (
            f"# Mã keo (PoC Glue Code) kết nối {name1} và {name2}\n"
            f"# Hướng dẫn cài đặt nhanh:\n"
            f"# {r1.get('install_cmd', '')}\n"
            f"# {r2.get('install_cmd', '')}\n\n"
            "import os\nimport sys\nimport time\n\n"
            "def run_synergy_pipeline():\n"
            f"    print('🚀 [Pipeline] Đang nạp module dữ liệu: {name1}...')\n"
            "    # 1. Trích xuất dữ liệu thô từ repo nguồn\n"
            "    payload = {'status': 'success', 'source': 'Repo A', 'data': 'Thông tin xử lý thời gian thực'}\n\n"
            f"    print('🔄 [Pipeline] Chuyển tiếp luồng điều phối sang: {name2}...')\n"
            "    # 2. Chuyển giao sang repo xử lý/thực thi\n"
            "    result = f'Xử lý thành công từ payload: {payload[\"data\"]}'\n"
            "    print('✅ [Pipeline] Hoàn tất:', result)\n"
            "    return result\n\n"
            "if __name__ == '__main__':\n"
            "    run_synergy_pipeline()\n"
        )

        return {
            "title": title,
            "tagline": tagline,
            "target_audience": target_aud,
            "specific_pain_point": pain_point,
            "concrete_scenario_example": scenario_example,
            "solution_overview": f"Xây dựng đường ống dữ liệu khép kín: {name1} làm tầng trích xuất/xử lý ban đầu và {name2} làm tầng tổng hợp/điều phối nâng cao.",
            "synergy_roles": [
                {"repo": name1, "role": f"Tầng Thu Thập & Xử Lý Nguồn ({r1.get('language')})"},
                {"repo": name2, "role": f"Tầng Điều Phối & Tự Động Hóa ({r2.get('language')})"}
            ],
            "data_flow": [
                f"Bước 1: Trích xuất hoặc chuẩn bị dữ liệu từ {name1}.",
                f"Bước 2: Chuẩn hóa payload qua giao thức IPC hoặc JSON trung gian.",
                f"Bước 3: Thực thi tác vụ tự động trên {name2} và trả về kết quả tổng hợp."
            ],
            "glue_code": glue_code,
            "risks_and_mitigation": [
                {"risk": "Khác biệt môi trường runtime hoặc ngôn ngữ lập trình", "mitigation": "Sử dụng Docker Compose hoặc CLI Subprocess để bọc giao tiếp."},
                {"risk": "Quá tải tài nguyên khi xử lý đồng thời", "mitigation": "Bổ sung hàng đợi message queue hoặc buffer đệm."}
            ]
        }

    def save_idea_document(self, idea: Dict[str, Any]) -> Path:
        idea_id = idea["id"]
        slug_title = re.sub(r"[^\w\-_]", "_", idea.get("title", "idea")).strip("_")[:40]
        md_file = self.ideas_dir / f"{idea_id}_{slug_title}.md"

        content = []
        content.append(f"# 💡 Đề Xuất Ý Tưởng Đột Phá: {idea.get('title')}\n")
        content.append(f"> **Giá trị cốt lõi**: *{idea.get('tagline')}*\n")
        content.append(f"- **Mã định danh**: `{idea_id}` | Ngày tạo: `{idea.get('created_at')}`")
        content.append(f"- **Chế độ phát sinh**: `{idea.get('mode')}`")
        if idea.get("user_goal"):
            content.append(f"- **Đề bài người dùng**: *{idea.get('user_goal')}*")
        content.append(f"- **Các Repository tham gia**: {', '.join(['`' + r + '`' for r in idea.get('source_repos', [])])}\n")

        content.append("## 🎯 1. Vấn Đề Cốt Lõi Giải Quyết (Pain Points & Target Audience)")
        if idea.get("target_audience"):
            content.append(f"- **Đối tượng thụ hưởng**: {idea.get('target_audience')}")
        content.append(f"- **Nỗi đau thực tế cụ thể**: {idea.get('specific_pain_point') or idea.get('problem_statement', '')}\n")

        content.append("## 📖 2. Ví Dụ Kịch Bản Cụ Thể Trong Thực Tế (Concrete Walkthrough Scenario)")
        content.append(f"{idea.get('concrete_scenario_example', 'Chưa có kịch bản ví dụ.')}\n")

        content.append("## 🚀 3. Tổng Quan Giải Pháp Phối Hợp (Synergy Solution)")
        content.append(f"{idea.get('solution_overview', '')}\n")

        content.append("### 🧩 Phân Công Vai Trò Kiến Trúc:")
        for sr in idea.get("synergy_roles", []):
            content.append(f"- **`{sr.get('repo')}`**: {sr.get('role')}")

        content.append("\n## 🔄 4. Luồng Dữ Liệu (Data Flow)")
        for step in idea.get("data_flow", []):
            content.append(f"- {step}")

        content.append("\n```mermaid")
        content.append("flowchart LR")
        for idx, sr in enumerate(idea.get("synergy_roles", []), 1):
            r_id = f"R{idx}"
            clean_repo = sr.get("repo", f"Repo {idx}").split("/")[-1]
            content.append(f'    {r_id}["{clean_repo}\\n({sr.get("role", "")[:20]})"]')
            if idx > 1:
                prev_id = f"R{idx-1}"
                content.append(f"    {prev_id} -->|Data Stream| {r_id}")
        content.append("```\n")

        content.append("## 💻 5. Mã Keo Thực Chiến (Proof-of-Concept Glue Code)")
        content.append("```python")
        content.append(idea.get("glue_code", "").strip())
        content.append("```\n")

        content.append("## ⚠️ 6. Đánh Giá Rủi Ro & Biện Pháp Khắc Phục (Risk & Feasibility)")
        for rm in idea.get("risks_and_mitigation", []):
            content.append(f"- 🔴 **Rủi ro**: {rm.get('risk')}")
            content.append(f"  - 🟢 **Khắc phục**: {rm.get('mitigation')}")

        with open(md_file, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

        logger.info(f"Đã lưu tài liệu ý tưởng tại: {md_file}")

        ideas_list = self.load_ideas()
        idea_summary = {
            "id": idea_id,
            "title": idea.get("title"),
            "tagline": idea.get("tagline"),
            "source_repos": idea.get("source_repos", []),
            "created_at": idea.get("created_at"),
            "mode": idea.get("mode"),
            "file_path": str(md_file.relative_to(self.base_dir)).replace("\\", "/")
        }
        ideas_list.insert(0, idea_summary)
        ideas_list = ideas_list[:50]
        try:
            with open(self.ideas_catalog_path, "w", encoding="utf-8") as f:
                json.dump(ideas_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật ideas_catalog.json: {e}")

        return md_file
