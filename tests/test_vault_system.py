import os
os.environ["TESTING"] = "1"
import sys
import time
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vault_engine.ingest import canonicalize_url, generate_url_hash, detect_source_type, IngestManager
from vault_engine.db import DatabaseManager
from vault_engine.pipeline import VaultItemSchema, GeminiReflectivePipeline
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.youtube_engine import YouTubeExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.server import app, db as server_db, ingest as server_ingest

class TestVaultSystemComprehensive(unittest.TestCase):

    def setUp(self):
        # Create isolated temporary SQLite database for each test run
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = DatabaseManager(db_path=self.temp_db.name)
        self.ingest = IngestManager(db=self.db)
        self.pipeline = GeminiReflectivePipeline()
        self.github_ext = GitHubExtractor()
        self.youtube_ext = YouTubeExtractor()
        self.web_ext = WebExtractor()

        # Connect FastAPI testclient to temporary test database
        server_db.conn = self.db.conn
        server_db.db_path = self.db.db_path
        server_ingest.db = self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass
        for ext in ["-wal", "-shm"]:
            f = self.temp_db.name + ext
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass

    # =========================================================================
    # GROUP 1: URL CANONICALIZATION, DEDUPLICATION & SOURCE TYPE DETECTION
    # =========================================================================
    def test_strip_tracking_parameters(self):
        dirty_url = "https://example.com/article?utm_source=facebook&utm_medium=cpc&fbclid=IwAR123&id=42&ref=share"
        clean = canonicalize_url(dirty_url)
        self.assertEqual(clean, "https://example.com/article?id=42")

    def test_github_url_normalization(self):
        dirty_github = "https://github.com/UncleCode/Crawl4AI.git/?utm_source=twitter"
        clean = canonicalize_url(dirty_github)
        self.assertEqual(clean, "https://github.com/unclecode/crawl4ai")

    def test_sha256_hash_speed(self):
        url = "https://github.com/unclecode/crawl4ai"
        start = time.perf_counter()
        for _ in range(100):
            h = generate_url_hash(url)
        duration_ms = (time.perf_counter() - start) * 1000 / 100
        self.assertEqual(len(h), 64)
        self.assertLess(duration_ms, 0.2, f"Hash speed must be < 0.2ms, got {duration_ms:.4f}ms")

    def test_source_type_detection(self):
        self.assertEqual(detect_source_type("https://github.com/psf/black"), "GITHUB")
        self.assertEqual(detect_source_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "YOUTUBE")
        self.assertEqual(detect_source_type("https://youtu.be/dQw4w9WgXcQ"), "YOUTUBE")
        self.assertEqual(detect_source_type("https://facebook.com/groups/12345/posts/67890"), "FACEBOOK")
        self.assertEqual(detect_source_type("https://engineering.atspotify.com/2023/04/paged-attention/"), "WEB_ARTICLE")
        self.assertEqual(detect_source_type("https://arxiv.org/abs/2309.06180"), "ARXIV")
        self.assertEqual(detect_source_type("https://lilianweng.github.io/posts/2023-06-23-agent/"), "WEB_ARTICLE")

    # =========================================================================
    # GROUP 2: SQLITE WAL MODE, ATOMIC LEASE & DEAD-LETTER QUEUE
    # =========================================================================
    def test_wal_mode_enabled(self):
        journal_mode = self.db.execute_scalar("PRAGMA journal_mode;")
        self.assertEqual(journal_mode.lower(), "wal", "Database phai bat che do WAL")

    def test_atomic_worker_lease(self):
        task = self.ingest.enqueue_url("https://github.com/unclecode/crawl4ai", source_type="GITHUB")
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "PENDING")

        leased_task = self.ingest.lease_next_task(worker_id="worker_alpha")
        self.assertIsNotNone(leased_task)
        self.assertEqual(leased_task["status"], "PROCESSING")
        self.assertEqual(leased_task["locked_by"], "worker_alpha")

        # Worker thứ 2 không được phép nhận cùng một task đang PROCESSING
        second_lease = self.ingest.lease_next_task(worker_id="worker_beta")
        self.assertIsNone(second_lease, "Atomic lease phai ngan chan 2 worker nhan cung 1 task")

    def test_task_completion_and_failure(self):
        task = self.ingest.enqueue_url("https://github.com/user/repo-temp", source_type="GITHUB")
        task_id = task["task_id"]

        # Thử fail retry: status reset về PENDING để worker lease lại, retry_count tăng 1
        self.ingest.fail_task(task_id, error_message="Transient timeout", is_permanent=False)
        retry_status = self.db.execute_scalar("SELECT status FROM queue_tasks WHERE id = ?", (task_id,))
        retry_count = self.db.execute_scalar("SELECT retry_count FROM queue_tasks WHERE id = ?", (task_id,))
        self.assertEqual(retry_status, "PENDING")
        self.assertEqual(retry_count, 1)

        # Hoàn tất task
        self.ingest.complete_task(task_id)
        completed_status = self.db.execute_scalar("SELECT status FROM queue_tasks WHERE id = ?", (task_id,))
        self.assertEqual(completed_status, "COMPLETED")

    def test_dead_letter_queue_isolation(self):
        task_uuid = "test-uuid-404"
        self.db.record_dlq(
            task_uuid=task_uuid,
            raw_url="https://github.com/invalid/repo404",
            error_type="HTTP_404",
            error_message="Repository not found on GitHub",
            stack_trace="Traceback ... 404"
        )
        dlq_items = self.db.get_dlq_items()
        self.assertEqual(len(dlq_items), 1)
        self.assertEqual(dlq_items[0]["error_type"], "HTTP_404")
        self.assertEqual(dlq_items[0]["raw_url"], "https://github.com/invalid/repo404")

    # =========================================================================
    # GROUP 3: PYDANTIC V2 STRICT SCHEMA & REFLECTIVE PIPELINE FALLBACK
    # =========================================================================
    def test_pydantic_schema_strict_validation(self):
        valid_payload = {
            "title": "Crawl4AI: Asynchronous LLM Crawler",
            "category": "AI-Agents",
            "short_summary": "Crawl4AI la bo cao du lieu toi uu cho LLM ho tro async va bop tach sach se.",
            "practical_score": 9,
            "score_reason": "Hieu nang async vuot troi, giam 90% thoi gian cao web cho AI pipeline.",
            "tech_stack": ["Python", "Playwright", "AsyncIO"],
            "github_repo": "https://github.com/unclecode/crawl4ai",
            "gotchas_and_risks": [
                "Ton RAM khi chay nhieu instance Chromium",
                "Can proxy khi cao cac trang web co Cloudflare Turnstile"
            ],
            "deep_research_md": "# Deep Research Crawl4AI\n\n## Mental Model\nAsynchronous event-loop scraping..."
        }
        item = VaultItemSchema(**valid_payload)
        self.assertEqual(item.practical_score, 9)
        self.assertEqual(item.category, "AI-Agents")
        self.assertEqual(len(item.gotchas_and_risks), 2)

    def test_pydantic_rejects_invalid_score(self):
        invalid_payload = {
            "title": "Invalid Score Test",
            "category": "AI-Agents",
            "short_summary": "Tom tat hop le dai du ky tu.",
            "practical_score": 15,  # Must be <= 10
            "score_reason": "Diem qua cao",
            "tech_stack": ["Python"],
            "gotchas_and_risks": ["Risk 1", "Risk 2"],
            "deep_research_md": "# Test noi dung dai hop le de thoa man schema..."
        }
        with self.assertRaises(Exception):
            VaultItemSchema(**invalid_payload)

    def test_heuristic_fallback_pipeline(self):
        # Test pipeline khi LLM offline: fallback phải sinh ra VaultItemSchema 100% hợp lệ
        raw_text = "Crawl4AI is an open-source asynchronous web crawler specifically designed for LLMs."
        schema_out = self.pipeline._build_heuristic_fallback(
            clean_content=raw_text,
            canonical_url="https://github.com/unclecode/crawl4ai",
            source_type="GITHUB"
        )
        self.assertIsInstance(schema_out, VaultItemSchema)
        self.assertGreaterEqual(schema_out.practical_score, 1)
        self.assertLessEqual(schema_out.practical_score, 10)
        self.assertTrue(len(schema_out.deep_research_md) > 50)

    # =========================================================================
    # GROUP 4: EXTRACTOR ENGINES (GITHUB, YOUTUBE, WEB)
    # =========================================================================
    def test_github_extractor_parsing(self):
        owner, repo = self.github_ext._parse_repo_info("https://github.com/facebook/react")
        self.assertEqual(owner, "facebook")
        self.assertEqual(repo, "react")

        owner_invalid, repo_invalid = self.github_ext._parse_repo_info("https://example.com/not-github")
        self.assertIsNone(owner_invalid)
        self.assertIsNone(repo_invalid)

    @patch("vault_engine.extractors.github_engine.requests.get")
    def test_github_extractor_fallback_raw_readme(self, mock_requests_get):
        # Mocking raw README & GitHub API
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# React\nA JavaScript library for building user interfaces with high performance."
        mock_resp.json.return_value = {
            "stargazers_count": 220000,
            "description": "The library for web and native user interfaces",
            "topics": ["javascript", "react", "ui"],
            "language": "JavaScript"
        }
        mock_requests_get.return_value = mock_resp

        data = self.github_ext.extract("https://github.com/facebook/react")
        self.assertIsNotNone(data)
        self.assertEqual(data["title"], "facebook/react")
        self.assertIn("React", data["content"])

    def test_youtube_video_id_extraction(self):
        self.assertEqual(self.youtube_ext._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(self.youtube_ext._extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(self.youtube_ext._extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_youtube_timestamp_formatting(self):
        formatted = self.youtube_ext._format_time(125)
        self.assertEqual(formatted, "02:05")
        formatted_hour = self.youtube_ext._format_time(3665)
        self.assertEqual(formatted_hour, "01:01:05")

    # =========================================================================
    # GROUP 5: FTS5 FULL-TEXT SEARCH & VAULT RETRIEVAL (<20ms)
    # =========================================================================
    def test_fts5_indexing_and_fast_search(self):
        self.db.insert_vault_item({
            "url_hash": "hash_crawl4ai",
            "canonical_url": "https://github.com/unclecode/crawl4ai",
            "source_type": "GITHUB",
            "title": "Crawl4AI Scraper Engine",
            "category": "AI-Agents",
            "short_summary": "Asynchronous high-speed web crawler for LLM data ingestion.",
            "practical_score": 9,
            "score_reason": "Toc do vuot troi.",
            "tech_stack": ["Python", "Playwright"],
            "gotchas_and_risks": ["RAM usage"],
            "deep_research_md": "# Crawl4AI\n\nFull markdown analysis on Crawl4AI architecture...",
            "github_repo": "https://github.com/unclecode/crawl4ai"
        })
        self.db.insert_vault_item({
            "url_hash": "hash_vllm",
            "canonical_url": "https://github.com/vllm-project/vllm",
            "source_type": "GITHUB",
            "title": "vLLM PagedAttention Inference",
            "category": "LLM-Infra",
            "short_summary": "High-throughput and memory-efficient inference engine for LLMs.",
            "practical_score": 10,
            "score_reason": "Dot pha quan ly bo nho KV cache.",
            "tech_stack": ["CUDA", "C++", "Python"],
            "gotchas_and_risks": ["Can GPU manh"],
            "deep_research_md": "# vLLM\n\nFull markdown analysis on PagedAttention memory kernel...",
            "github_repo": "https://github.com/vllm-project/vllm"
        })

        start = time.perf_counter()
        results = self.db.search_vault(query="crawler", category="AI-Agents", min_score=8)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Crawl4AI Scraper Engine")
        self.assertLess(duration_ms, 20.0, f"FTS5 query phai < 20ms, thuc te: {duration_ms:.2f}ms")

        item_id = results[0]["id"]
        self.db.update_item_status(item_id, reading_status="READ", is_starred=1)
        updated = self.db.get_vault_item_by_id(item_id)
        self.assertEqual(updated["reading_status"], "READ")
        self.assertEqual(updated["is_starred"], 1)

    # =========================================================================
    # GROUP 6: FASTAPI SERVER ENDPOINTS INTEGRATION (<1.5s WEBHOOK, BENTO API)
    # =========================================================================
    @patch("vault_engine.server.process_task_background")
    def test_api_telegram_webhook_queuing(self, mock_background_process):
        # 1. Gửi tin nhắn chứa 2 URL
        payload = {
            "update_id": 1001,
            "message": {
                "message_id": 42,
                "text": "Xem thu 2 repo nay rat hay: https://github.com/unclecode/crawl4ai va https://github.com/vllm-project/vllm",
                "chat": {"id": 12345678}
            }
        }
        start = time.perf_counter()
        resp = self.client.post("/api/v1/webhook/telegram", json=payload)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["count"], 2)
        self.assertLess(duration_ms, 1500.0, f"Telegram webhook phai phan hoi duoi 1.5s, thuc te: {duration_ms:.2f}ms")

    def test_api_telegram_webhook_ignores_no_url(self):
        payload = {
            "update_id": 1002,
            "message": {"message_id": 43, "text": "Tin nhan binh thuong khong co link"}
        }
        resp = self.client.post("/api/v1/webhook/telegram", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["message"], "no_url_found")

    def test_api_vault_search_and_filtering(self):
        # Insert test item
        item_id = self.db.insert_vault_item({
            "url_hash": "hash_agent",
            "canonical_url": "https://github.com/langchain-ai/langgraph",
            "source_type": "GITHUB",
            "title": "LangGraph Stateful Multi-Agent Architecture",
            "category": "AI-Agents",
            "short_summary": "Framework xay dung multi-agent cyclic graph bang Python.",
            "practical_score": 8,
            "score_reason": "Kien truc StateGraph ro rang de mo rong.",
            "tech_stack": ["Python", "AsyncIO"],
            "gotchas_and_risks": ["De sinh deadlock neu chu trinh khong co diem dung"],
            "deep_research_md": "# LangGraph Deep Research\n\n## Mental Model\nGraph execution...",
            "curation_status": "APPROVED"
        })

        # Test search API
        resp = self.client.get("/api/v1/vault?q=Stateful&category=AI-Agents&min_score=7")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["title"], "LangGraph Stateful Multi-Agent Architecture")

        # Test get detail API
        detail_resp = self.client.get(f"/api/v1/vault/{item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["category"], "AI-Agents")

        # Test get non-existing item
        not_found = self.client.get("/api/v1/vault/999999")
        self.assertEqual(not_found.status_code, 404)

    def test_api_update_status_and_stats(self):
        item_id = self.db.insert_vault_item({
            "url_hash": "hash_status_test",
            "canonical_url": "https://github.com/user/test-status",
            "source_type": "GITHUB",
            "title": "Test Status Item",
            "category": "DevOps-Cloud",
            "short_summary": "Item dung de test cap nhat trang thai.",
            "practical_score": 7,
            "score_reason": "Thuc chien tot.",
            "tech_stack": ["Docker"],
            "gotchas_and_risks": ["Khong co"],
            "deep_research_md": "# Test Status"
        })

        # Cập nhật thành READ và gắn sao VIP
        update_resp = self.client.put(f"/api/v1/vault/{item_id}/status?reading_status=read&is_starred=true")
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["reading_status"], "READ")
        self.assertEqual(update_resp.json()["is_starred"], 1)

        # Kiểm tra Stats API
        stats_resp = self.client.get("/api/v1/stats")
        self.assertEqual(stats_resp.status_code, 200)
        s = stats_resp.json()
        self.assertEqual(s["total_items"], 1)
        self.assertEqual(s["unread_count"], 0)
        self.assertEqual(s["starred_count"], 1)

    def test_api_serves_dashboard_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Knowledge Vault", resp.text)
        self.assertIn("bento-grid", resp.text)

    def test_api_explain_inline(self):
        resp = self.client.post("/api/v1/explain-inline", json={
            "selected_text": "PagedAttention splits KV cache into virtual pages.",
            "article_title": "vLLM Inference"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("explanation", resp.json())
        self.assertGreater(len(resp.json()["explanation"]), 10)

    def test_graph_generation_api(self):
        # Insert 2 related items
        id1 = self.db.insert_vault_item({
            "url_hash": "hash_graph_1",
            "canonical_url": "https://github.com/vllm/vllm",
            "source_type": "GITHUB",
            "title": "vLLM High Throughput",
            "category": "LLM-Infra",
            "short_summary": "High speed LLM serving with [[PagedAttention]] concept.",
            "practical_score": 9,
            "score_reason": "Excellent",
            "tech_stack": ["Python", "CUDA", "C++"],
            "gotchas_and_risks": [],
            "deep_research_md": "Deep dive into [[PagedAttention]] and memory blocks.",
            "referenced_docs": [{"doc_type": "PAPER", "title": "vLLM Paper", "url": "https://arxiv.org/abs/2309.06180"}]
        })
        id2 = self.db.insert_vault_item({
            "url_hash": "hash_graph_2",
            "canonical_url": "https://github.com/sgl-project/sglang",
            "source_type": "GITHUB",
            "title": "SGLang Serving Engine",
            "category": "LLM-Infra",
            "short_summary": "RadixAttention framework for LLM serving.",
            "practical_score": 9,
            "score_reason": "High performance",
            "tech_stack": ["Python", "CUDA"],
            "gotchas_and_risks": [],
            "deep_research_md": "Extends [[PagedAttention]] with Radix trees.",
            "referenced_docs": []
        })

        # Test local item graph
        resp = self.client.get(f"/api/v1/vault/{id1}/graph")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        node_labels = [n["label"] for n in data["nodes"]]
        self.assertIn("vLLM High Throughput", node_labels)
        self.assertIn("LLM-Infra", node_labels)
        self.assertIn("Python", node_labels)
        self.assertIn("[[PagedAttention]]", node_labels)
        self.assertIn("vLLM Paper", node_labels)
        self.assertIn("SGLang Serving Engine", node_labels)

        # Test global graph
        glob_resp = self.client.get("/api/v1/vault-graph")
        self.assertEqual(glob_resp.status_code, 200)
        glob_data = glob_resp.json()
        self.assertGreaterEqual(len(glob_data["nodes"]), 2)

    def test_embedding_serialization_and_cosine_similarity(self):
        from vault_engine.embedding import serialize_vector, deserialize_vector, cosine_similarity
        vec_a = [1.0, 0.0, 0.5, 0.2]
        blob = serialize_vector(vec_a)
        restored = deserialize_vector(blob)
        self.assertEqual(len(restored), len(vec_a))
        for x, y in zip(vec_a, restored):
            self.assertAlmostEqual(x, y, places=5)

        vec_b = [1.0, 0.0, 0.5, 0.2]
        sim_ident = cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(sim_ident, 1.0, places=4)

        vec_c = [-1.0, 0.0, -0.5, -0.2]
        sim_opp = cosine_similarity(vec_a, vec_c)
        self.assertAlmostEqual(sim_opp, -1.0, places=4)

    def test_hybrid_search_rrf_ranking(self):
        from vault_engine.embedding import reciprocal_rank_fusion
        # Document 1 has high BM25 rank (1) but lower vector rank (10)
        # Document 2 has medium in both (3, 2)
        bm25_ranks = {1: 1, 2: 3, 3: 15}
        vector_ranks = {1: 10, 2: 2, 3: 1}
        fused = reciprocal_rank_fusion(bm25_ranks, vector_ranks, k=60)
        
        self.assertEqual(len(fused), 3)
        top_doc_id = fused[0][0]
        # Doc 2: 1/(60+3) + 1/(60+2) = 1/63 + 1/62 = 0.01587 + 0.01612 = 0.0320
        # Doc 1: 1/(60+1) + 1/(60+10) = 1/61 + 1/70 = 0.01639 + 0.01428 = 0.0306
        self.assertEqual(top_doc_id, 2, "Doc 2 must rank higher due to balanced strong signals")

    def test_mcp_server_protocol(self):
        from vault_engine.mcp_server import VaultMCPServer
        server = VaultMCPServer(db_path=self.temp_db.name)

        # 1. Initialize
        init_resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "knowledge-vault-mcp")

        # 2. Tools list
        tools_resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
        self.assertIn("search_vault", tool_names)
        self.assertIn("get_vault_document", tool_names)
        self.assertIn("get_vault_stats", tool_names)
        self.assertIn("ingest_url", tool_names)

        # 3. Call get_vault_stats
        call_resp = server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_vault_stats", "arguments": {}}
        })
        self.assertIn("result", call_resp)
        self.assertIn("content", call_resp["result"])

    def test_telegram_message_formatting(self):
        from vault_engine.telegram_bot import TelegramBot
        bot = TelegramBot(token="TEST_TOKEN", default_chat_id="123456")
        dummy_item = {
            "title": "FastAPI Masterclass",
            "category": "Web-Systems",
            "archetype": "TECH_DEEPDIVE",
            "practical_score": 9,
            "score_reason": "Kien truc cuc ky chuan muc.",
            "short_summary": "Huong dan thiet ke FastAPI chuan Production.",
            "tech_stack": ["Python", "FastAPI", "Uvicorn"],
            "gotchas_and_risks": ["Can chu y connection pool", "Chong memory leak"]
        }
        msg_out = bot.format_completion_message(dummy_item, 99)
        if isinstance(msg_out, tuple):
            msg, markup = msg_out
            self.assertIn("inline_keyboard", markup)
        else:
            msg = msg_out
        self.assertIn("FastAPI Masterclass", msg)
        self.assertIn("9/10", msg)
        self.assertIn("Python", msg)
        self.assertIn("Gotchas & Rủi ro", msg)

    def test_github_visual_asset_extractor(self):
        from vault_engine.extractors.github_engine import GitHubExtractor
        extractor = GitHubExtractor()

        sample_markdown = """
        # Sample Project
        [![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://travis-ci.org)
        [![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

        Here is the high-level architecture:
        ![Architecture Diagram](docs/images/arch_diagram.png)

        And here is our benchmark vs legacy systems:
        <img src="https://raw.githubusercontent.com/test-org/test-repo/main/benchmarks/benchmark_qps.png" alt="Benchmark Results" />

        Demo preview:
        ![Demo UI](assets/demo.gif)
        """
        assets = extractor.extract_visual_assets(
            markdown_text=sample_markdown,
            owner="test-org",
            repo="test-repo",
            default_branch="main"
        )

        # Kiểm tra lọc badge thành công (không chứa shields.io)
        badge_urls = [a["url"] for a in assets if "shields.io" in a["url"]]
        self.assertEqual(len(badge_urls), 0)

        # Kiểm tra chuyển đổi đường dẫn tương đối thành Raw CDN GitHub
        arch_asset = next((a for a in assets if a["category"] == "ARCHITECTURE_DIAGRAM"), None)
        self.assertIsNotNone(arch_asset)
        self.assertEqual(
            arch_asset["url"],
            "https://raw.githubusercontent.com/test-org/test-repo/main/docs/images/arch_diagram.png"
        )

        # Kiểm tra phân loại Benchmark Chart
        bench_asset = next((a for a in assets if a["category"] == "BENCHMARK_CHART"), None)
        self.assertIsNotNone(bench_asset)
        self.assertIn("benchmark_qps.png", bench_asset["url"])

        # Kiểm tra phân loại Demo Visual
        demo_asset = next((a for a in assets if a["category"] == "DEMO_VISUAL"), None)
        self.assertIsNotNone(demo_asset)
        self.assertEqual(
            demo_asset["url"],
            "https://raw.githubusercontent.com/test-org/test-repo/main/assets/demo.gif"
        )

    def test_context_scout_entity_inference(self):
        from vault_engine.extractors.context_scout import ContextScout
        scout = ContextScout()

        # Test case 1: Caption nhắc "thư viện crawl4ai"
        text1 = "Hôm nay chia sẻ mọi người thư viện crawl4ai cào web cực mạnh bằng LLM."
        inferred1 = scout.infer_repo_name_from_text(text1)
        self.assertEqual(inferred1, "crawl4ai")

        # Test case 2: Caption nhắc "framework LangGraph"
        text2 = "Anh em nào đang build multi-agent thì xem framework LangGraph này nhé."
        inferred2 = scout.infer_repo_name_from_text(text2)
        self.assertEqual(inferred2, "LangGraph")

        # Test case 3: Slug owner/repo viết trực tiếp
        text3 = "Tham khảo repo vllm-project/vllm để xem cơ chế PagedAttention."
        inferred3 = scout.infer_repo_name_from_text(text3)
        self.assertEqual(inferred3, "vllm-project/vllm")

    def test_unified_dossier_pipeline_integration(self):
        from vault_engine.extractors.context_scout import UnifiedContextDossier
        from vault_engine.pipeline import GeminiReflectivePipeline

        pipeline = GeminiReflectivePipeline()

        # Giả lập 1 dossier đầy đủ từ Context Scout
        dossier = UnifiedContextDossier(
            canonical_url="https://facebook.com/post/12345",
            source_type="FACEBOOK",
            title="Kỹ thuật cào web hiện đại với crawl4ai",
            primary_content="Chia sẻ thư viện crawl4ai cào dữ liệu Markdown cho LLM siêu nhanh.",
            comments=[
                "Link repo ở đây anh em: https://github.com/unclecode/crawl4ai",
                "Dùng hay lắm, tiết kiệm 90% token!"
            ],
            identified_repo_url="https://github.com/unclecode/crawl4ai",
            repo_metadata={
                "name": "crawl4ai",
                "stars": 24500,
                "language": "Python"
            },
            repo_readme="Crawl4AI is the open-source LLM-friendly web crawler.",
            visual_assets=[
                {
                    "url": "https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/architecture.png",
                    "caption": "Crawl4AI Architecture",
                    "category": "ARCHITECTURE_DIAGRAM"
                },
                {
                    "url": "https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/speed_benchmark.png",
                    "caption": "Speed Benchmark vs Selenium",
                    "category": "BENCHMARK_CHART"
                }
            ],
            referenced_docs=[
                {
                    "title": "Crawl4AI GitHub Repo",
                    "url": "https://github.com/unclecode/crawl4ai",
                    "doc_type": "REPO",
                    "context": "Mã nguồn chính thức"
                }
            ]
        )

        schema = pipeline.process_content(dossier)

        # 1. Kiểm tra tiêu đề và repo
        self.assertIn("crawl4ai", schema.title.lower())
        self.assertEqual(schema.github_repo, "https://github.com/unclecode/crawl4ai")

        # 2. Kiểm tra nhúng hình ảnh kiến trúc & benchmark vào deep_research_md
        self.assertIn("https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/architecture.png", schema.deep_research_md)
        self.assertIn("https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/speed_benchmark.png", schema.deep_research_md)

        # 3. Kiểm tra banner repository được render
        self.assertIn("Kho Mã Nguồn Cốt Lõi:", schema.deep_research_md)
        self.assertIn("24,500", schema.deep_research_md)

        # 4. Kiểm tra mạng lưới tham chiếu (Referenced Docs)
        self.assertTrue(any(r["url"] == "https://github.com/unclecode/crawl4ai" for r in schema.referenced_docs))

    # =========================================================================
    # GROUP 10: COGNITIVE BRAIN VAULT, CURATION GATE & CONSOLIDATION
    # =========================================================================
    def test_curation_lifecycle_and_filtering(self):
        # 1. Insert 1 item ở trạng thái INBOX
        id1 = self.db.insert_vault_item({
            "url_hash": "hash_inbox_1",
            "canonical_url": "https://example.com/draft",
            "source_type": "WEB_ARTICLE",
            "title": "Draft Inbox Item",
            "category": "Architecture",
            "short_summary": "Tài liệu sơ thảo đang chờ duyệt.",
            "practical_score": 7,
            "curation_status": "INBOX"
        })
        # 2. Insert 1 item ở trạng thái APPROVED
        id2 = self.db.insert_vault_item({
            "url_hash": "hash_appr_1",
            "canonical_url": "https://example.com/master",
            "source_type": "WEB_ARTICLE",
            "title": "Master Knowledge Item",
            "category": "Architecture",
            "short_summary": "Tài liệu chuẩn đã duyệt vào Não.",
            "practical_score": 9,
            "curation_status": "APPROVED"
        })

        # Mặc định search chỉ lấy APPROVED
        approved_items = self.db.search_vault("", curation_status="APPROVED")
        self.assertTrue(any(i["id"] == id2 for i in approved_items))
        self.assertFalse(any(i["id"] == id1 for i in approved_items))

        # Query INBOX
        inbox_items = self.db.search_vault("", curation_status="INBOX")
        self.assertTrue(any(i["id"] == id1 for i in inbox_items))
        self.assertFalse(any(i["id"] == id2 for i in inbox_items))

        # Thực hiện duyệt id1 -> APPROVED
        ok = self.db.curate_vault_item(id1, "APPROVE")
        self.assertTrue(ok)
        item1_updated = self.db.get_vault_item(id1)
        self.assertEqual(item1_updated["curation_status"], "APPROVED")
        self.assertIsNotNone(item1_updated["curated_at"])

        # Thực hiện reject id1 -> REJECTED
        ok_rej = self.db.curate_vault_item(id1, "REJECT")
        self.assertTrue(ok_rej)
        item1_rej = self.db.get_vault_item(id1)
        self.assertEqual(item1_rej["curation_status"], "REJECTED")

    def test_brain_associations_and_heuristics(self):
        id_src = self.db.insert_vault_item({
            "url_hash": "hash_src",
            "canonical_url": "https://example.com/src",
            "source_type": "WEB_ARTICLE",
            "title": "Source Paper",
            "curation_status": "APPROVED"
        })
        id_tgt = self.db.insert_vault_item({
            "url_hash": "hash_tgt",
            "canonical_url": "https://example.com/tgt",
            "source_type": "WEB_ARTICLE",
            "title": "Target Paper",
            "curation_status": "APPROVED"
        })

        # Lưu liên kết nơ-ron
        assoc_id = self.db.add_brain_association(
            source_item_id=id_src,
            target_item_id=id_tgt,
            relation_type="REINFORCES",
            reasoning="Cùng củng cố luận điểm tối ưu hóa bộ nhớ đệm Cache-Aware.",
            confidence_score=0.92
        )
        self.assertIsNotNone(assoc_id)
        assocs = self.db.get_brain_associations(id_src)
        self.assertEqual(len(assocs), 1)
        self.assertEqual(assocs[0]["relation_type"], "REINFORCES")
        self.assertEqual(assocs[0]["target_title"], "Target Paper")

        # Lưu hồ sơ chuyên đề sống (Living Synthesis Topic)
        topic_id = self.db.upsert_synthesis_topic(
            topic_name="Memory Architecture",
            topic_slug="memory-architecture",
            category="AI-Engineering",
            synthesis_markdown="# Memory Architecture\n\nTổng hợp các cơ chế bộ nhớ LLM...",
            source_item_ids=[id_src, id_tgt],
            core_principles=["Zero-Copy Streaming", "PagedAttention"]
        )
        self.assertIsNotNone(topic_id)
        topic = self.db.get_synthesis_topic("memory-architecture")
        self.assertIsNotNone(topic)
        self.assertEqual(topic["version"], 1)
        self.assertIn("PagedAttention", topic["core_principles"])

        # Cập nhật topic phiên bản 2
        self.db.upsert_synthesis_topic(
            topic_name="Memory Architecture",
            topic_slug="memory-architecture",
            category="AI-Engineering",
            synthesis_markdown="# Memory Architecture v2\n\nNâng cấp thêm FlashAttention...",
            source_item_ids=[id_src, id_tgt],
            core_principles=["Zero-Copy Streaming", "PagedAttention", "FlashAttention"]
        )
        topic_v2 = self.db.get_synthesis_topic("memory-architecture")
        self.assertEqual(topic_v2["version"], 2)
        self.assertIn("FlashAttention", topic_v2["core_principles"])

        # Lưu quy tắc Agent (Procedural Heuristics)
        h_id = self.db.add_agent_heuristic(
            rule_type="MUST_DO",
            category="Performance",
            trigger_context="Khi triển khai crawler đa luồng",
            action_directive="Luôn tái sử dụng session HTTP để tránh TLS handshake overhead",
            rationale="Tiết kiệm 80% RTT",
            confidence_score=0.85,
            source_item_id=id_src
        )
        self.assertIsNotNone(h_id)
        heuristics = self.db.get_agent_heuristics(rule_type="MUST_DO")
        self.assertEqual(len(heuristics), 1)
        self.assertEqual(heuristics[0]["confidence_score"], 0.85)

        # Ghi nhận phản hồi (Feedback Loop)
        self.db.record_heuristic_feedback(h_id, is_positive=True)
        self.db.record_heuristic_feedback(h_id, is_positive=True)
        updated_h = self.db.get_agent_heuristics()[0]
        self.assertGreater(updated_h["confidence_score"], 0.85)
        self.assertEqual(updated_h["success_count"], 2)

    def test_curation_api_endpoints(self):
        # Tạo 1 item INBOX
        item_id = self.db.insert_vault_item({
            "url_hash": "hash_api_curate",
            "canonical_url": "https://example.com/api-test",
            "source_type": "WEB_ARTICLE",
            "title": "API Test Item",
            "curation_status": "INBOX"
        })

        # Test GET /api/v1/vault?curation_status=INBOX
        resp = self.client.get("/api/v1/vault?curation_status=INBOX")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        inbox_items = data.get("items", []) if isinstance(data, dict) else data
        self.assertTrue(any(i["id"] == item_id for i in inbox_items))

        # Test POST /api/v1/vault/{id}/curate APPROVE
        resp_curate = self.client.post(f"/api/v1/vault/{item_id}/curate", json={"action": "APPROVE"})
        self.assertEqual(resp_curate.status_code, 200)
        self.assertEqual(resp_curate.json()["curation_status"], "APPROVED")

        # Kiểm tra item đã chuyển sang APPROVED
        check_item = self.db.get_vault_item(item_id)
        self.assertEqual(check_item["curation_status"], "APPROVED")

        # Test GET /api/v1/vault/{id}/associations
        resp_assocs = self.client.get(f"/api/v1/vault/{item_id}/associations")
        self.assertEqual(resp_assocs.status_code, 200)
        self.assertIn("associations", resp_assocs.json())

        # Test GET /api/v1/brain/topics
        resp_topics = self.client.get("/api/v1/brain/topics")
        self.assertEqual(resp_topics.status_code, 200)

        # Test GET /api/v1/brain/heuristics
        resp_heuristics = self.client.get("/api/v1/brain/heuristics")
        self.assertEqual(resp_heuristics.status_code, 200)

    def test_mcp_cognitive_tools(self):
        from vault_engine.mcp_server import VaultMCPServer
        mcp = VaultMCPServer()
        mcp.db = self.db

        # Tạo rule
        h_id = self.db.add_agent_heuristic(
            rule_type="NEVER_DO",
            category="Security",
            trigger_context="Khi nhận token từ người dùng",
            action_directive="Không log plaintext token ra console",
            rationale="Chống rò rỉ credential",
            confidence_score=0.9
        )

        # 1. Test get_agent_heuristics
        res_h = mcp.execute_tool("get_agent_heuristics", {"category": "Security"})
        self.assertEqual(res_h["count"], 1)
        self.assertEqual(res_h["heuristics"][0]["rule_type"], "NEVER_DO")

        # 2. Test record_agent_feedback
        res_fb = mcp.execute_tool("record_agent_feedback", {"heuristic_id": h_id, "success": True, "note": "Đã áp dụng tốt"})
        self.assertEqual(res_fb["status"], "success")

        # 3. Test get_master_synthesis
        self.db.upsert_synthesis_topic(
            topic_name="Security Standards",
            topic_slug="security-standards",
            category="Security",
            synthesis_markdown="# Security Master Guidelines",
            core_principles=["Least Privilege"]
        )
        res_syn = mcp.execute_tool("get_master_synthesis", {"topic_slug": "security-standards"})
        self.assertEqual(res_syn["topic_slug"], "security-standards")
        self.assertEqual(res_syn["version"], 1)

    def test_ssrf_validator_blocks_private_ips_and_schemes(self):
        from vault_engine.security import validate_safe_public_url

        # Invalid schemes
        with self.assertRaises(ValueError):
            validate_safe_public_url("ftp://example.com/file")
        with self.assertRaises(ValueError):
            validate_safe_public_url("file:///etc/passwd")

        # Localhost / Private IPs
        with self.assertRaises(ValueError):
            validate_safe_public_url("http://127.0.0.1:8000/secret")
        with self.assertRaises(ValueError):
            validate_safe_public_url("http://localhost:3000")
        with self.assertRaises(ValueError):
            validate_safe_public_url("http://169.254.169.254/latest/meta-data")
        with self.assertRaises(ValueError):
            validate_safe_public_url("http://10.0.0.1/admin")
        with self.assertRaises(ValueError):
            validate_safe_public_url("http://192.168.1.1/router")

        # Valid public URLs
        self.assertTrue(validate_safe_public_url("https://github.com/openai/skills"))
        self.assertTrue(validate_safe_public_url("http://example.com"))

    def test_rate_limiter_sliding_window(self):
        from vault_engine.security import SlidingWindowRateLimiter
        import time

        # Rate limiter với 2 req / min
        limiter = SlidingWindowRateLimiter(requests_per_minute=2)
        ip = "192.0.2.1" # TEST-NET-1 public test IP

        # Lần 1 và 2 hợp lệ
        allowed1, _ = limiter.is_allowed(ip)
        self.assertTrue(allowed1)
        allowed2, _ = limiter.is_allowed(ip)
        self.assertTrue(allowed2)

        # Lần 3 bị chặn
        allowed3, retry_after = limiter.is_allowed(ip)
        self.assertFalse(allowed3)
        self.assertGreater(retry_after, 0)

        # Khác client IP vẫn được đi qua
        allowed_other, _ = limiter.is_allowed("192.0.2.2")
        self.assertTrue(allowed_other)

    def test_security_headers_middleware(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(resp.headers.get("x-frame-options"), "SAMEORIGIN")
        self.assertEqual(resp.headers.get("x-xss-protection"), "1; mode=block")
        self.assertIn("strict-transport-security", resp.headers)

    def test_telegram_bot_unauthorized_access_control(self):
        from vault_engine.telegram_bot import TelegramBot
        bot = TelegramBot(token="dummy_token", default_chat_id="123456789")

        # Test user trái phép gửi tin nhắn
        unauthorized_message = {
            "chat": {"id": 999999999},
            "from": {"id": 999999999},
            "text": "https://github.com/test/repo",
            "message_id": 123
        }
        with unittest.mock.patch.object(bot, "send_message") as mock_send:
            bot.handle_message(unauthorized_message)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("Truy cập bị từ chối", args[0])

        # Test callback query trái phép
        unauthorized_cb = {
            "id": "cb_1",
            "from": {"id": 888888888},
            "message": {"chat": {"id": 888888888}, "message_id": 10},
            "data": "brain:approve:1"
        }
        with unittest.mock.patch.object(bot, "answer_callback_query") as mock_answer:
            bot.handle_callback_query(unauthorized_cb)
            mock_answer.assert_called_once_with("cb_1", text="⛔ Bạn không có quyền thực hiện thao tác này.")

    def test_mermaid_diagram_sanitizer(self):
        from vault_engine.consolidation import sanitize_mermaid_diagram
        raw_md = """# Architecture
```mermaid
flowchart TD
    A["[[Superpowers Framework]]"] --> B[LangGraph (Multi-Agent)]
    B --> C["PostgreSQL (Vector DB)"]
```
Some other text."""
        sanitized = sanitize_mermaid_diagram(raw_md)
        self.assertIn('A["Superpowers Framework"]', sanitized)
        self.assertIn('B["LangGraph (Multi-Agent)"]', sanitized)
        self.assertIn('C["PostgreSQL (Vector DB)"]', sanitized)
        self.assertNotIn('[[', sanitized)

    def test_heuristics_deduplication_via_cosine_similarity(self):
        from vault_engine.consolidation import ConsolidationEngine
        engine = ConsolidationEngine(db=self.db)

        topic_info = {
            "slug": "ai-agents",
            "title": "Kiến Trúc Multi-Agent & RAG Nhận Thức Tự Hành",
            "description": "Test Topic"
        }

        # Item 1 với gotcha tràn context
        item_id1 = self.db.insert_vault_item({
            "url_hash": "hash_rag_1",
            "canonical_url": "https://github.com/rag/framework-a",
            "source_type": "GITHUB",
            "title": "Framework RAG A",
            "category": "AI-Agents",
            "short_summary": "RAG framework",
            "practical_score": 9,
            "score_reason": "Good",
            "tech_stack": ["Python"],
            "gotchas_and_risks": ["Context window overflow khi nạp dữ liệu lớn"]
        })
        item1 = self.db.get_vault_item_by_id(item_id1)
        res1 = engine._extract_procedural_heuristics(item1, topic_info)
        self.assertEqual(len(res1), 1)
        self.assertFalse(res1[0].get("deduplicated"))
        hid1 = res1[0]["id"]

        # Item 2 với gotcha tương đương
        item_id2 = self.db.insert_vault_item({
            "url_hash": "hash_rag_2",
            "canonical_url": "https://github.com/rag/framework-b",
            "source_type": "GITHUB",
            "title": "Framework RAG B",
            "category": "AI-Agents",
            "short_summary": "RAG framework",
            "practical_score": 9,
            "score_reason": "Good",
            "tech_stack": ["Python"],
            "gotchas_and_risks": ["Context window overflow khi nạp dữ liệu lớn"]
        })
        item2 = self.db.get_vault_item_by_id(item_id2)
        res2 = engine._extract_procedural_heuristics(item2, topic_info)
        self.assertEqual(len(res2), 1)
        # Kiểm tra item 2 đã được khử trùng lặp và củng cố rule cũ
        self.assertTrue(res2[0].get("deduplicated"))
        self.assertEqual(res2[0]["id"], hid1)

        # Kiểm tra điểm confidence_score của rule 1 đã được boost
        heuristics = self.db.get_agent_heuristics(topic=topic_info["title"])
        matched = next(h for h in heuristics if h["id"] == hid1)
        self.assertGreater(matched["confidence_score"], 1.0)

    def test_sanitize_mermaid_double_brackets(self):
        from vault_engine.consolidation import sanitize_mermaid_diagram
        raw_md = """```mermaid
flowchart TD
    D1[Start] --> D2[[HydraFusion: Tối Ưu Hóa]]
    D2 --> D3["Final Node"]
```"""
        sanitized = sanitize_mermaid_diagram(raw_md)
        self.assertIn('D1["Start"]', sanitized)
        self.assertIn('D2["HydraFusion: Tối Ưu Hóa"]', sanitized)
        self.assertIn('D3["Final Node"]', sanitized)
        self.assertNotIn('[[', sanitized)

    def test_export_rules_api(self):
        # Tạo test heuristic
        self.db.add_agent_heuristic(
            rule_type="MUST_DO",
            category="AI-Agents",
            trigger_context="Khi gọi LLM streaming",
            action_directive="Luôn bắt GeneratorExit để giải phóng SSE connection",
            anti_pattern="Nuốt GeneratorExit gây rò rỉ socket connection",
            confidence_score=1.5
        )
        self.db.add_agent_heuristic(
            rule_type="NEVER_DO",
            category="AI-Agents",
            trigger_context="Khi lưu trữ sensitive keys",
            action_directive="Không hardcode secret token trong codebase",
            anti_pattern="Lộ secret key lên GitHub công khai",
            confidence_score=1.8
        )

        # 1. Test format GEMINI.md
        resp_g = self.client.get("/api/v1/brain/export-rules?format=gemini")
        self.assertEqual(resp_g.status_code, 200)
        self.assertIn("PROJECT RULES & GUIDELINES (GEMINI.md)", resp_g.text)
        self.assertIn("MUST DO", resp_g.text)
        self.assertIn("GeneratorExit", resp_g.text)
        self.assertIn("NEVER DO", resp_g.text)

        # 2. Test format .cursorrules
        resp_c = self.client.get("/api/v1/brain/export-rules?format=cursorrules")
        self.assertEqual(resp_c.status_code, 200)
        self.assertIn("Cursor Rules", resp_c.text)
        self.assertIn("GeneratorExit", resp_c.text)

        # 3. Test format as JSON for clipboard
        resp_j = self.client.get("/api/v1/brain/export-rules?format=gemini&as_json=true")
        self.assertEqual(resp_j.status_code, 200)
        data = resp_j.json()
        self.assertIn("rules_markdown", data)
        self.assertGreaterEqual(data["count"], 2)

    def test_curate_api_async_status(self):
        item_id = self.db.insert_vault_item({
            "url_hash": "hash_async_curate_test",
            "canonical_url": "https://example.com/async-curate",
            "source_type": "WEB_ARTICLE",
            "title": "Async Curate Item",
            "curation_status": "INBOX"
        })
        resp = self.client.post(f"/api/v1/vault/{item_id}/curate", json={"action": "APPROVE"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["curation_status"], "APPROVED")
        self.assertEqual(data["consolidation"], "in_progress")

        # Xác nhận DB đã cập nhật trạng thái APPROVED
        item = self.db.get_vault_item(item_id)
        self.assertEqual(item["curation_status"], "APPROVED")

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestVaultSystemComprehensive)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

