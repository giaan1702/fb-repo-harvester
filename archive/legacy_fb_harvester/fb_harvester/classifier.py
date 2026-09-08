import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_classifier")

GATEWAY_URL = "https://freellmapi-gateway.onrender.com/v1/chat/completions"
API_KEY = "freellmapi-85740b8f1f5ae3aa3c1f43eab41e55fa04f8027443e09ac4"

STANDARD_CATEGORIES = [
    "AI & Autonomous Agents",
    "Data Scraping & Web Automation",
    "Computer Vision & Generative Media",
    "Developer Tools, CLI & Terminal",
    "Backend & High-Performance Systems",
    "Fullstack, Web & UI Frameworks",
    "Cybersecurity & Reverse Engineering",
    "Education, Cheatsheets & Resource Guides"
]

FALLBACK_RULES = {
    "AI & Autonomous Agents": ["agent", "llm", "gpt", "rag", "langchain", "autogen", "crewai", "chat", "assistant", "claude"],
    "Data Scraping & Web Automation": ["scrape", "crawler", "crawl", "spider", "automation", "feed", "rss", "download", "yt-dlp"],
    "Computer Vision & Generative Media": ["vision", "image", "video", "flux", "diffusion", "comfyui", "animation", "detect", "ocr"],
    "Developer Tools, CLI & Terminal": ["cli", "tool", "terminal", "sdk", "api", "package", "builder", "monitor", "utility"],
    "Backend & High-Performance Systems": ["fastapi", "rust", "database", "redis", "server", "backend", "grpc", "microservice"],
    "Fullstack, Web & UI Frameworks": ["ui", "frontend", "react", "vue", "astro", "web", "android", "animation"],
    "Cybersecurity & Reverse Engineering": ["security", "rfid", "chameleon", "exploit", "hack", "reverse", "auth"],
    "Education, Cheatsheets & Resource Guides": ["learn", "interview", "guide", "cheatsheet", "roadmap", "awesome", "tutorial", "build-your-own"]
}

def fallback_classify(repo_info: Dict[str, Any]) -> Dict[str, Any]:
    """Phân loại bằng từ khóa nếu API không khả dụng."""
    text = f"{repo_info.get('full_name', '')} {repo_info.get('description', '')} {' '.join(repo_info.get('topics', []))}".lower()
    
    assigned_cat = "Developer Tools, CLI & Terminal"
    max_matches = 0

    for cat, keywords in FALLBACK_RULES.items():
        matches = sum(1 for kw in keywords if kw in text)
        if matches > max_matches:
            max_matches = matches
            assigned_cat = cat

    desc = repo_info.get("description", "Không có mô tả.")
    lang = repo_info.get("language", "Python")
    fn = repo_info.get("name", "app")
    return {
        "category": assigned_cat,
        "tags": repo_info.get("topics", [])[:4] or [repo_info.get("language", "Utility")],
        "summary": f"Dự án {repo_info.get('full_name')}: {desc}",
        "use_cases": ["Áp dụng tự động hóa quy trình làm việc.", "Tích hợp vào hệ thống lập trình cá nhân."],
        "install_cmd": f"git clone https://github.com/{repo_info.get('full_name')} && cd {fn}",
        "architecture": f"Open-source {lang} Module",
        "core_components": ["Core Engine", "CLI / Entrypoint"],
        "code_snippet": f"# Khởi chạy nhanh dự án {fn}\nimport sys\nprint('Đang nạp module {fn}...')\n"
    }

class AIClassifier:
    """Sử dụng FreeLLMAPI Gateway để phân loại ngữ nghĩa và tóm tắt repo cho AI Agent."""

    def __init__(self, api_key: str = API_KEY, gateway_url: str = GATEWAY_URL):
        self.api_key = api_key
        self.gateway_url = gateway_url

    def classify_and_summarize(self, repo_info: Dict[str, Any], readme_snippet: str = "") -> Dict[str, Any]:
        full_name = repo_info.get("full_name", "")
        description = repo_info.get("description", "")
        language = repo_info.get("language", "")
        topics = ", ".join(repo_info.get("topics", []))
        
        # Cắt ngắn README để tối ưu token
        readme_short = readme_snippet[:1500] if readme_snippet else ""

        prompt = f"""Bạn là một chuyên gia phân tích công nghệ phần mềm. Hãy đọc thông tin repository sau và phân loại, tóm tắt ngữ nghĩa để lưu vào chỉ mục cho các AI-Agent truy xuất sau này.

THÔNG TIN REPO:
- Tên: {full_name}
- Ngôn ngữ: {language}
- Mô tả tác giả: {description}
- Topics: {topics}
- Trích đoạn README:
{readme_short}

YÊU CẦU PHÂN LOẠI LINH HOẠT (DYNAMIC TAXONOMY):
1. Ưu tiên chọn 1 danh mục phù hợp từ danh sách gợi ý sau nếu tương đồng:
   - "AI & Autonomous Agents"
   - "Data Scraping & Web Automation"
   - "Computer Vision & Generative Media"
   - "Developer Tools, CLI & Terminal"
   - "Backend & High-Performance Systems"
   - "Fullstack, Web & UI Frameworks"
   - "Cybersecurity & Reverse Engineering"
   - "Education, Cheatsheets & Resource Guides"

2. HOẶC NẾU ĐÂY LÀ MỘT LĨNH VỰC HOÀN TOÀN MỚI (ví dụ: "Embedded Systems, IoT & Robotics", "Audio, Speech & Voice AI", "Game Engines & 3D Graphics", "Trading & Algorithmic Finance", "Blockchain & Decentralized Tech", v.v.):
   BẠN ĐƯỢC TOÀN QUYỀN TỰ ĐỘNG TẠO MỘT TÊN DANH MỤC MỚI chuẩn xác, ngắn gọn bằng tiếng Anh (dạng "Topic 1 & Topic 2").

Trả về DUY NHẤT một chuỗi JSON hợp lệ (không kèm markdown ```json) có cấu trúc:
{{
  "category": "Tên danh mục (chọn từ gợi ý hoặc tự sinh mới)",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "Tóm tắt ngữ nghĩa 2-3 câu bằng tiếng Việt cực kỳ cô đọng: nêu rõ bài toán cốt lõi và khi nào nên dùng.",
  "use_cases": ["Kịch bản áp dụng 1", "Kịch bản áp dụng 2"],
  "install_cmd": "Lệnh cài đặt CLI chuẩn (ví dụ: 'pip install ...' hoặc 'npm install ...' hoặc 'git clone ...')",
  "architecture": "Kiến trúc kỹ thuật (ví dụ: 'Autonomous Multi-Agent', 'Async Pipeline', 'CLI Tool', 'Web Framework')",
  "core_components": ["Thành phần/Class/Endpoint chính 1", "Thành phần chính 2"],
  "code_snippet": "Mã nguồn mẫu Hello World ngắn gọn (10-20 dòng) thực chiến có thể copy-paste chạy được, viết bằng ngôn ngữ của repo."
}}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        body = {
            "model": "auto",
            "messages": [
                {"role": "system", "content": "You are a tech taxonomy AI expert. Always output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        try:
            logger.info(f"Đang gửi phân loại AI cho: {full_name} qua FreeLLMAPI...")
            res = requests.post(self.gateway_url, headers=headers, json=body, timeout=20)
            if res.status_code == 200:
                raw_text = res.json()["choices"][0]["message"]["content"].strip()
                # Làm sạch markdown nếu có
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                data = json.loads(raw_text.strip())
                logger.info(f"✅ AI đã phân loại {full_name} -> [{data.get('category')}]")
                return data
            else:
                logger.warning(f"Gateway trả về mã {res.status_code}: {res.text[:100]}. Chuyển sang fallback.")
        except Exception as e:
            logger.warning(f"Lỗi khi gọi AI Classifier: {e}. Chuyển sang fallback.")

        return fallback_classify(repo_info)
