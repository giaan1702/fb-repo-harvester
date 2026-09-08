import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-3.5-flash"

def call_gemini(prompt, model=MODEL, temperature=0.2, max_tokens=2000, retries=2):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    
    last_err = None
    for attempt in range(retries + 1):
        start = time.time()
        try:
            with urllib.request.urlopen(req) as resp:
                elapsed = time.time() - start
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata", {})
                return elapsed, text, usage
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in [503, 429] and attempt < retries:
                time.sleep(1.5)
                continue
            raise last_err
        except Exception as e:
            last_err = e
            raise last_err

print("=================================================================")
print(f"BẮT ĐẦU KIỂM THỬ KHỐI LƯỢNG MÔ PHỎNG VỚI MODEL: {MODEL}")
print("=================================================================\n")

# Kịch bản 1: Phân tích bài viết Facebook dài + trích xuất JSON chuẩn
fb_post = """
Hôm nay mình chia sẻ về kiến trúc AI Agent chạy ngầm không phụ thuộc vào PC cá nhân. 
Thông thường khi dựng agentic workflow với LangChain hay LlamaIndex, người ta hay chạy local trên laptop. Nhưng nhược điểm lớn nhất là khi tắt máy thì worker ngừng chạy. 
Giải pháp đột phá ở đây là kết hợp: 
1. Serverless Webhook trên Cloudflare Worker hoặc Google Apps Script nhận tin nhắn từ Telegram Bot.
2. Đẩy task vào hàng đợi Cloud Pub/Sub hoặc Redis.
3. Sử dụng Gemini 3.7 Flash làm Inference Engine vì context lớn và chi phí cực thấp, tốc độ sinh 150 token/giây.
4. Đóng gói kiến thức kết xuất vào Google NotebookLM thông qua Drive API để tạo second brain.
Điểm cốt lõi: Bạn chỉ mất $0 chi phí hạ tầng, biến chiếc điện thoại thành remote control điều khiển cả hệ thống tri thức. 
Repo demo mình để tại: https://github.com/example/serverless-knowledge-agent
"""

prompt_1 = f"""
Bạn là chuyên gia phân tích công nghệ. Hãy phân tích bài viết sau:
{fb_post}

Yêu cầu định dạng JSON chính xác:
{{
  "short_summary": "(tóm tắt 30-40 từ súc tích cho thông báo Telegram)",
  "core_insight": "(tư duy cốt lõi tạo đòn bẩy)",
  "tech_stack": ["danh sách công nghệ"],
  "github_repo": "(link repo nếu có)",
  "practical_score": "(điểm thực tiễn thang 10)"
}}
Chỉ trả về JSON thuần túy, không thêm markdown.
"""

print("[Test-case 1] Phân tích bài viết dài + Trích xuất JSON:")
t1, res1, u1 = call_gemini(prompt_1)
print(f"-> Thời gian phản hồi: {t1:.2f}s")
print(f"-> Tokens tiêu thụ: In={u1.get('promptTokenCount')}, Out={u1.get('candidatesTokenCount')}")
print(f"-> Kết quả thực tế:\n{res1.strip()}\n")

# Kịch bản 2: Phân tích Repository & Đề xuất ý tưởng Co-Ideation
prompt_2 = """
Phân tích repository 'unclecode/crawl4ai' (Công cụ cào dữ liệu web tối ưu cho LLM).
Hãy đóng vai trò Kỹ sư AI cấp cao:
1. Nêu 2 ưu điểm kỹ thuật vượt trội so với Selenium/Playwright thông thường.
2. Đề xuất 1 ý tưởng tích hợp (Co-ideation) kết hợp crawl4ai với Google NotebookLM để tự động biến các diễn đàn kỹ thuật thành kho tri thức sống.
Độ dài khoảng 150-200 từ, hành văn sắc sảo, kỹ thuật thực chiến.
"""

print("[Test-case 2] Phân tích Repository & Đề xuất Ý tưởng Co-Ideation:")
t2, res2, u2 = call_gemini(prompt_2)
print(f"-> Thời gian phản hồi: {t2:.2f}s")
print(f"-> Tokens tiêu thụ: In={u2.get('promptTokenCount')}, Out={u2.get('candidatesTokenCount')}")
print(f"-> Kết quả thực tế:\n{res2.strip()}\n")

# Kịch bản 3: Thử tải liên tiếp (Stress test / Concurrency simulation)
print("[Test-case 3] Thử tải 5 request liên tiếp (mô phỏng người dùng gửi dồn link vào bot):")
latencies = []
for i in range(1, 6):
    try:
        t, _, u = call_gemini(f"Mô phỏng tóm tắt link số {i}: Hãy đưa ra 1 lời khuyên bảo mật API trong 1 câu.", max_tokens=100)
        latencies.append(t)
        print(f"  Request {i}/5: Thành công trong {t:.2f}s")
    except Exception as e:
        print(f"  Request {i}/5: Thất bại -> {e}")

avg_latency = sum(latencies) / len(latencies) if latencies else 0
print(f"\n=> Tỷ lệ thành công: {len(latencies)}/5 ({len(latencies)*20}%)")
print(f"=> Độ trễ trung bình: {avg_latency:.2f}s / request")
print("\n=================================================================")
print("HOÀN TẤT KIỂM THỬ MÔ PHỎNG")
print("=================================================================")
