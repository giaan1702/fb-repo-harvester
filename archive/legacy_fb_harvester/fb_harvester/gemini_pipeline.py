"""
Module: gemini_pipeline.py
Kiến trúc Pipeline 2-Pass phản biện đa tầng sử dụng Google Gemini API
Đảm bảo độ bền bỉ, chống lỗi 429/503 và nâng chất lượng phân tích lên chuẩn Kỹ sư trưởng.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("gemini_pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PRIMARY_MODEL = "gemini-3.5-flash"
FALLBACK_MODEL = "gemini-3.7-flash"

class GeminiPipeline:
    def __init__(self, api_key: str = "", primary_model: str = PRIMARY_MODEL, fallback_model: str = FALLBACK_MODEL):
        self.api_key = os.environ.get("GEMINI_API_KEY", api_key or DEFAULT_API_KEY)
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    def _call_api(self, prompt: str, model: str, temperature: float = 0.2, max_tokens: int = 2500, json_mode: bool = False, max_retries: int = 3) -> Tuple[str, Dict[str, Any]]:
        """
        Gọi Google Gemini API với cơ chế Exponential Backoff chống lỗi 429/503.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        gen_config = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        backoff = 1.5
        last_exception = None

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                with urllib.request.urlopen(req, timeout=30) as resp:
                    elapsed = time.time() - start_time
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    usage = data.get("usageMetadata", {})
                    logger.info(f"✅ [{model}] Thành công trong {elapsed:.2f}s (In: {usage.get('promptTokenCount')}, Out: {usage.get('candidatesTokenCount')})")
                    return text, usage
            except urllib.error.HTTPError as e:
                last_exception = e
                err_content = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
                logger.warning(f"⚠️ [{model}] Lỗi HTTP {e.code} lần thử {attempt+1}/{max_retries}: {err_content[:150]}")
                
                # Xử lý quá tải hoặc rate limit
                if e.code in [429, 503]:
                    time.sleep(backoff)
                    backoff *= 2.0  # 1.5s -> 3.0s -> 6.0s
                    continue
                else:
                    raise e
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ [{model}] Lỗi kết nối lần {attempt+1}/{max_retries}: {e}")
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(f"Hết lượt thử lại ({max_retries} lần) với model {model}: {last_exception}")

    def execute_robust_call(self, prompt: str, temperature: float = 0.2, max_tokens: int = 2500, json_mode: bool = False) -> Tuple[str, Dict[str, Any]]:
        """
        Thực thi với cơ chế Dynamic Model Fallback: Nếu primary model lỗi, chuyển sang fallback model.
        """
        try:
            return self._call_api(prompt, self.primary_model, temperature, max_tokens, json_mode)
        except Exception as e:
            logger.warning(f"🔄 Primary model [{self.primary_model}] thất bại, chuyển sang Fallback [{self.fallback_model}]: {e}")
            return self._call_api(prompt, self.fallback_model, temperature, max_tokens, json_mode)

    def process_knowledge_pipeline(self, raw_content: str, source_url: str = "") -> Dict[str, Any]:
        """
        PIPELINE 2-PASS ĐẠT CHUẨN KỸ SƯ TRƯỞNG & SKILL ĐỌC SÁCH:
        Pass 1: Trích xuất nền tảng theo khung Mental Model & 20% đòn bẩy
        Pass 2: Phản biện Kỹ sư trưởng, loại bỏ lý thuyết sáo rỗng, tạo bản nghiên cứu chuyên sâu
        """
        logger.info("🚀 BẮT ĐẦU PIPELINE XỬ LÝ TRI THỨC 2 TẦNG...")

        # =====================================================================
        # PASS 1: TRÍCH XUẤT NỀN TẢNG (FOUNDATION EXTRACTION)
        # =====================================================================
        prompt_pass1 = f"""
Bạn là chuyên gia phân tích công nghệ AI. Hãy phân tích nội dung sau theo BỘ KHUNG TƯ DUY SKILL ĐỌC SÁCH:
---
{raw_content}
---

Yêu cầu cấu trúc:
1. Đòn bẩy 20/80: Đâu là 20% ý tưởng/công nghệ tạo ra 80% giá trị cốt lõi?
2. Khái niệm dễ nhầm: So sánh và làm rõ các khái niệm hoặc công nghệ tương đồng.
3. Framework đánh giá: Vấn đề giải quyết là gì? Khi nào NÊN dùng? Khi nào KHÔNG NÊN dùng?
4. Định danh: Tên repo/dự án chính, các thư viện/tech stack liên quan, và link GitHub (nếu có).

Hãy phân tích mạch lạc, logic, súc tích.
"""
        pass1_text, usage1 = self.execute_robust_call(prompt_pass1, temperature=0.2, max_tokens=1500)

        # =====================================================================
        # PASS 2: PHẢN BIỆN KỸ SƯ TRƯỞNG & ĐÓNG GÓI CHUẨN (CRITIQUE & JSON EXPORT)
        # =====================================================================
        prompt_pass2 = f"""
Bạn là Kỹ sư Trưởng (Lead Principal Engineer). Dưới đây là bản phân tích sơ bộ từ nội dung:
---
{pass1_text}
---
Nguồn gốc tài liệu: {source_url}

Hãy thực hiện 2 nhiệm vụ:
1. PHẢN BIỆN KHẮT KHE: Loại bỏ hoàn toàn những lời khen ngợi sáo rỗng. Chỉ ra rủi ro kỹ thuật, góc khuất bảo mật, hoặc cạm bẫy vận hành (gotchas) trong thực tế.
2. ĐÓNG GÓI THÀNH ĐỊNH DẠNG JSON CHÍNH XÁC với các trường sau:

{{
  "title": "Tiêu đề kỹ thuật cô đọng (dưới 15 từ)",
  "short_summary": "Tóm tắt ngắn gọn 30-40 từ, đủ thông tin để đọc nhanh trên thông báo điện thoại",
  "practical_score": "Điểm giá trị thực chiến từ 1 đến 10 (kèm 1 câu giải thích ngắn)",
  "tech_stack": ["danh", "sách", "công", "nghệ"],
  "github_repo": "link repo nếu có hoặc để trống",
  "deep_research_md": "Bản nghiên cứu hoàn chỉnh định dạng Markdown chuẩn mực (gồm: Mental Model cốt lõi, Phân tích kỹ thuật chuyên sâu, Gotchas & Rủi ro, Kịch bản áp dụng thực chiến, và Lời khuyên của Kỹ sư trưởng)"
}}

Chỉ trả về JSON hợp lệ.
"""
        pass2_json_str, usage2 = self.execute_robust_call(prompt_pass2, temperature=0.1, max_tokens=2500, json_mode=True)

        try:
            result = json.loads(pass2_json_str)
        except Exception:
            # Fallback nếu model vô tình bọc markdown
            clean_str = pass2_json_str.strip().strip("```json").strip("```").strip()
            result = json.loads(clean_str)

        result["metadata"] = {
            "source_url": source_url,
            "tokens_in": usage1.get("promptTokenCount", 0) + usage2.get("promptTokenCount", 0),
            "tokens_out": usage1.get("candidatesTokenCount", 0) + usage2.get("candidatesTokenCount", 0),
            "model_used": self.primary_model
        }

        logger.info(f"🏁 PIPELINE HOÀN TẤT: '{result.get('title')}' | Điểm: {result.get('practical_score')}")
        return result
