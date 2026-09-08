import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:7860"

def log_test(name, passed, detail=""):
    symbol = "[PASS]" if passed else "[FAIL]"
    print(f"{symbol:7} | {name:<42} | {detail}")

def test_fts5_fuzzing():
    """Kiểm tra tìm kiếm FTS5 với các ký tự đặc biệt dễ gây lỗi cú pháp SQLite FTS5."""
    fuzz_queries = [
        ('Ký tự nháy kép "', 'vllm"'),
        ('Ký tự nháy đơn \'', "vllm'"),
        ('Dấu ngoặc đơn ()', '(python) AND (rust)'),
        ('Ký tự sao đứng đầu *', '*vllm'),
        ('Toán tử logic đứng trơ AND', 'vllm AND'),
        ('Toán tử NOT không vế', 'NOT vllm'),
        ('Ký tự đặc biệt lẫn lộn', '^~:;{}[]!@#$%')
    ]
    
    passed_all = True
    for label, q in fuzz_queries:
        encoded_q = urllib.parse.quote(q)
        url = f"{BASE_URL}/api/v1/vault?q={encoded_q}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", data) if isinstance(data, dict) else data
                log_test(f"FTS5: {label}", True, f"HTTP {resp.status} - Kết quả: {len(items)}")
        except urllib.error.HTTPError as e:
            log_test(f"FTS5: {label}", False, f"HTTP {e.code} ({e.reason}) - GÂY SẬP QUERY!")
            passed_all = False
        except Exception as e:
            log_test(f"FTS5: {label}", False, f"Lỗi không mong muốn: {str(e)}")
            passed_all = False
    return passed_all

def test_concurrent_duplicate_ingest():
    """Kiểm tra Race Condition khi nạp đồng thời cùng 1 URL trong tích tắc."""
    test_url = "https://github.com/astral-sh/uv"
    num_requests = 5
    
    def send_ingest(_):
        req_data = json.dumps({"url": test_url}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/api/v1/ingest", data=req_data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")
        except Exception as e:
            return 500, str(e)

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        results = list(executor.map(send_ingest, range(num_requests)))

    statuses = [r[0] for r in results]
    success_count = sum(1 for s in statuses if s == 200)
    log_test("Concurrency Deduplication (5 reqs)", success_count == num_requests, f"Statuses: {statuses}")
    return success_count == num_requests

def test_malformed_urls():
    """Kiểm tra phản ứng của hệ thống với URL không hợp lệ hoặc giao thức nguy hiểm."""
    bad_urls = [
        ("Protocol javascript:", "javascript:alert(1)"),
        ("Protocol file://", "file:///etc/passwd"),
        ("URL rỗng", ""),
        ("Domain không tồn tại", "https://khong-ton-tai-123456789-xyz.org/bai-viet"),
        ("URL quá dài (>2000 ký tự)", "https://example.com/" + "a" * 2500)
    ]
    for label, u in bad_urls:
        req_data = json.dumps({"url": u}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/api/v1/ingest", data=req_data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                log_test(f"Malformed: {label}", True, f"HTTP {resp.status} - {res_data.get('message', '')}")
        except urllib.error.HTTPError as e:
            log_test(f"Malformed: {label}", e.code == 400, f"HTTP {e.code} (Từ chối hợp lệ)")
        except Exception as e:
            log_test(f"Malformed: {label}", False, f"Lỗi: {str(e)}")

def test_ui_static_health():
    """Kiểm tra tính toàn vẹn của các file tĩnh UI."""
    endpoints = [
        ("/", 200, "text/html"),
        ("/static/styles.css", 200, "text/css"),
        ("/static/app.js", 200, "javascript"),
        ("/api/v1/stats", 200, "application/json")
    ]
    for ep, exp_status, exp_type in endpoints:
        try:
            with urllib.request.urlopen(f"{BASE_URL}{ep}", timeout=3) as resp:
                ct = resp.headers.get("Content-Type", "")
                is_ok = (resp.status == exp_status and exp_type in ct)
                log_test(f"Static Asset: {ep}", is_ok, f"HTTP {resp.status} - {ct.split(';')[0]}")
        except Exception as e:
            log_test(f"Static Asset: {ep}", False, f"Lỗi: {str(e)}")

def test_brain_cognitive_endpoints():
    """Kiểm tra các endpoint nhận thức Cognitive Brain Vault mới."""
    endpoints = [
        ("/api/v1/vault?curation_status=APPROVED", "Brain Vault Approved Items"),
        ("/api/v1/vault?curation_status=INBOX", "Staging Inbox Items"),
        ("/api/v1/brain/topics", "Living Synthesis Topics"),
        ("/api/v1/brain/heuristics", "Agent Procedural Heuristics"),
        ("/api/v1/vault/1/associations", "Neural Associations Graph")
    ]
    for ep, desc in endpoints:
        try:
            with urllib.request.urlopen(f"{BASE_URL}{ep}", timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cnt = len(data.get("items", [])) if isinstance(data, dict) and "items" in data else len(data)
                log_test(f"Brain: {desc}", True, f"HTTP {resp.status} - Trả về: {cnt} phần tử")
        except Exception as e:
            log_test(f"Brain: {desc}", False, f"Lỗi: {str(e)}")

if __name__ == "__main__":
    print("=" * 80)
    print("KHỞI ĐỘNG RUN-TIME AUDIT SUITE CHO KNOWLEDGE VAULT V5.0 (COGNITIVE BRAIN)")
    print("=" * 80)
    print("\n--- 1. KIỂM TRA TẦNG STATIC ASSETS & API CƠ BẢN ---")
    test_ui_static_health()
    print("\n--- 2. KIỂM TRA CÁC ENDPOINT NHẬN THỨC NÃO BỘ (COGNITIVE BRAIN) ---")
    test_brain_cognitive_endpoints()
    print("\n--- 3. KIỂM TRA LỖ HỔNG FTS5 QUERY FUZZING ---")
    test_fts5_fuzzing()
    print("\n--- 4. KIỂM TRA ĐỒNG THỜI & RACE CONDITION NẠP LINK ---")
    test_concurrent_duplicate_ingest()
    print("\n--- 5. KIỂM TRA ĐẦU VÀO URL DỊ BIỆT & ĐỘ AN TOÀN ---")
    test_malformed_urls()
    print("=" * 80)

