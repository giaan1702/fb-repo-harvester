import os
import re
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from vault_engine.config import DB_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, BASE_DIR, SCOUT_ENABLED, SCOUT_INTERVAL_SECONDS
from vault_engine.db import DatabaseManager
from vault_engine.ingest import IngestManager, detect_source_type, canonicalize_url
from vault_engine.pipeline import GeminiReflectivePipeline
from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.youtube_engine import YouTubeExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.extractors.context_scout import ContextScout
from vault_engine.scout_daemon import AutonomousScout

logger = logging.getLogger("vault_server")

# Database & Ingest instances
db = DatabaseManager(db_path=DB_PATH)
ingest = IngestManager(db=db)
pipeline = GeminiReflectivePipeline()

github_ext = GitHubExtractor()
youtube_ext = YouTubeExtractor()
web_ext = WebExtractor()
context_scout = ContextScout(github_ext=github_ext, web_ext=web_ext, youtube_ext=youtube_ext)

telegram_bot = None
if TELEGRAM_BOT_TOKEN:
    try:
        from vault_engine.telegram_bot import TelegramBot
        telegram_bot = TelegramBot()
    except Exception as e:
        logger.warning(f"Không thể khởi tạo TelegramBot: {e}")

scout_daemon = None
if SCOUT_ENABLED:
    try:
        scout_daemon = AutonomousScout(db_path=DB_PATH)
    except Exception as e:
        logger.warning(f"Không thể khởi tạo AutonomousScout: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    is_cloud_webhook = bool(os.getenv("RENDER") or os.getenv("TELEGRAM_USE_WEBHOOK", "").lower() in ("true", "1"))
    if telegram_bot and not os.getenv("TESTING"):
        if is_cloud_webhook:
            logger.info("Môi trường Cloud/Webhook phát hiện: Bỏ qua long-polling, sử dụng Webhook tiếp nhận tin nhắn.")
        else:
            telegram_bot.start_background()
            logger.info("Telegram Bot 24/7 Long-polling Worker started.")
    if scout_daemon and not os.getenv("TESTING"):
        scout_daemon.start_background(interval_seconds=SCOUT_INTERVAL_SECONDS)
        logger.info(f"Autonomous Scout 24/7 Daemon started (interval: {SCOUT_INTERVAL_SECONDS}s).")
    yield
    if scout_daemon and not os.getenv("TESTING"):
        scout_daemon.stop()
        logger.info("Autonomous Scout Daemon stopped.")
    if telegram_bot and not os.getenv("TESTING"):
        telegram_bot.stop()
        logger.info("Telegram Bot stopped.")

app = FastAPI(title="Autonomous Knowledge Vault", version="3.0.0", lifespan=lifespan)

STATIC_DIR = BASE_DIR / "vault_engine" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Autonomous Knowledge Vault v3.0"}

URL_REGEX = re.compile(r"https?://[^\s<>\"']+")

def process_task_background(task_id: int, task_uuid: str, raw_url: str, source_type: str):
    """Background worker xử lý toàn diện 1 task mà không chặn webhook."""
    logger.info(f"Bắt đầu xử lý task {task_uuid}: {raw_url} ({source_type})")
    clean_url = canonicalize_url(raw_url)

    try:
        # 1. Trinh sát & Khai phá bối cảnh đa tầng (Context Scout Agent)
        dossier = context_scout.build_unified_dossier(clean_url, source_type)
        if dossier.error:
            db.record_dlq(task_uuid, clean_url, "EXTRACTION_ERROR", dossier.error)
            ingest.fail_task(task_id, dossier.error, is_permanent=True)
            return

        # 2. Pipeline Phản biện 2-Pass qua Gemini (Senior Staff v4.0 + Smart Article Reader)
        item_schema = pipeline.process_content(
            clean_content=dossier,
            canonical_url=clean_url,
            source_type=source_type,
            title_hint=dossier.title
        )

        # 3. Lưu vào Vault Database
        vault_payload = item_schema.model_dump()
        vault_payload["url_hash"] = ingest.db.execute_scalar("SELECT url_hash FROM queue_tasks WHERE id = ?", (task_id,)) or ""
        vault_payload["canonical_url"] = getattr(dossier, "identified_repo_url", None) or clean_url
        vault_payload["source_type"] = source_type
        vault_payload["curation_status"] = "INBOX"

        item_id = db.insert_vault_item(vault_payload)

        # 4. Sinh vector embedding cho Hybrid Search
        try:
            from vault_engine.embedding import get_embedding
            content_to_embed = f"{item_schema.title}. {item_schema.short_summary}. Tech: {' '.join(item_schema.tech_stack)}"
            vec = get_embedding(content_to_embed)
            if vec:
                db.save_embedding(item_id, vec)
        except Exception as emb_err:
            logger.warning(f"Khong the sinh embedding cho item {item_id}: {emb_err}")

        ingest.complete_task(task_id)
        logger.info(f"Hoàn tất xử lý task {task_uuid} -> Vault Item ID {item_id} (INBOX)")

        if telegram_bot:
            try:
                msg, reply_markup = telegram_bot.format_completion_message(vault_payload, item_id)
                telegram_bot.send_message(msg, reply_markup=reply_markup)
            except Exception as notify_err:
                logger.warning(f"Không thể gửi thông báo Telegram: {notify_err}")

    except Exception as e:
        logger.error(f"Lỗi xử lý task {task_uuid}: {e}", exc_info=True)
        db.record_dlq(task_uuid, clean_url, "PIPELINE_ERROR", str(e))
        ingest.fail_task(task_id, str(e), is_permanent=False)

@app.post("/api/v1/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook tiếp nhận từ Telegram phản hồi <1.5s"""
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # 1. Hỗ trợ Callback Query từ nút bấm Inline Keyboard
    if "callback_query" in data and telegram_bot:
        background_tasks.add_task(telegram_bot.handle_callback_query, data["callback_query"])
        return {"status": "ok", "action": "callback_handled"}

    message = data.get("message") or data.get("channel_post") or {}
    text = message.get("text") or message.get("caption") or ""

    # 2. Hỗ trợ các lệnh điều khiển bot (/start, /stats, /brain_stats, /approve, /reject)
    if telegram_bot and text.strip().startswith("/"):
        background_tasks.add_task(telegram_bot.handle_message, message)
        return {"status": "ok", "action": "command_handled"}

    # 3. Trích xuất URL và nạp hàng đợi
    urls = URL_REGEX.findall(text)
    if not urls:
        return {"status": "ok", "message": "no_url_found"}

    queued = []
    for u in urls:
        stype = detect_source_type(u)
        res = ingest.enqueue_url(u, source_type=stype)
        if res and "task_id" in res:
            queued.append(res)
            background_tasks.add_task(
                process_task_background,
                res["task_id"], res["task_uuid"], res["canonical_url"], res["source_type"]
            )

    return {"status": "queued", "count": len(queued), "tasks": queued}

class ExplainInlineRequest(BaseModel):
    selected_text: str
    article_title: Optional[str] = ""

@app.post("/api/v1/explain-inline")
def explain_inline(payload: ExplainInlineRequest):
    """Giải thích siêu cô đọng 2-3 câu đoạn trích kỹ thuật được bôi đen"""
    text = payload.selected_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    if os.getenv("TESTING"):
        return {"explanation": "Khái niệm này đề cập đến cơ chế kỹ thuật cốt lõi giúp tối ưu hóa hiệu năng và độ ổn định."}

    prompt = f"""Bạn là Kỹ sư trưởng cấp cao. Người dùng vừa bôi đen đoạn văn/mã nguồn sau trong bài viết "{payload.article_title}":
\"\"\"{text[:2000]}\"\"\"

Nhiệm vụ: Hãy giải thích ngắn gọn, súc tích trong đúng 2-3 câu bằng tiếng Việt:
1. Bản chất kỹ thuật hoặc ý nghĩa cốt lõi của đoạn này là gì?
2. Tại sao nó quan trọng hoặc lưu ý thực chiến cần nhớ.
Không dài dòng, trả lời trực diện ngay vào bản chất."""

    try:
        explanation = pipeline._call_gemini_api(prompt, is_json=False)
        return {"explanation": explanation.strip()}
    except Exception as e:
        logger.warning(f"Lỗi explain inline: {e}")
        return {"explanation": "Khái niệm này đề cập đến cơ chế vận hành cốt lõi của hệ thống, giúp tối ưu hóa hiệu năng và độ ổn định."}

class IngestRequest(BaseModel):
    url: str

@app.post("/api/v1/ingest")
async def direct_ingest(payload: IngestRequest, background_tasks: BackgroundTasks):
    """API nạp trực tiếp URL từ Web UI"""
    raw_url = payload.url.strip()
    if not raw_url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL không hợp lệ. Phải bắt đầu bằng http:// hoặc https://")

    clean_url = canonicalize_url(raw_url)
    stype = detect_source_type(clean_url)
    res = ingest.enqueue_url(clean_url, source_type=stype)
    
    if res.get("status") == "ALREADY_IN_VAULT":
        return {"status": "already_in_vault", "item_id": res.get("item_id"), "message": "Liên kết đã tồn tại trong kho"}

    if res and "task_id" in res:
        background_tasks.add_task(
            process_task_background,
            res["task_id"], res["task_uuid"], res["canonical_url"], res["source_type"]
        )
        return {"status": "queued", "task": res, "message": "Đang phân tích bài viết trong nền"}

    return {"status": "already_queued", "message": "Liên kết đang chờ xử lý trong hàng đợi"}

class CuratePayload(BaseModel):
    action: str

class HeuristicFeedbackPayload(BaseModel):
    heuristic_id: int
    success: bool
    note: Optional[str] = ""

@app.get("/api/v1/vault")
def get_vault_items(q: str = "", category: str = "", min_score: int = 1,
                    reading_status: str = "", is_starred: Optional[int] = None,
                    curation_status: Optional[str] = "APPROVED",
                    mode: str = "hybrid",
                    limit: int = 50, offset: int = 0):
    """API tra cứu kho tri thức toàn văn FTS5 hoặc Hybrid RRF có bộ lọc tuyển chọn"""
    start = time.perf_counter()
    if mode == "hybrid" and q.strip():
        results = db.hybrid_search_vault(
            query=q, category=category, min_score=min_score,
            reading_status=reading_status, is_starred=is_starred,
            curation_status=curation_status,
            limit=limit, offset=offset
        )
    else:
        results = db.search_vault(
            query=q, category=category, min_score=min_score,
            reading_status=reading_status, is_starred=is_starred,
            curation_status=curation_status,
            limit=limit, offset=offset
        )
    duration_ms = (time.perf_counter() - start) * 1000
    return {
        "total": len(results),
        "duration_ms": round(duration_ms, 2),
        "mode": mode if q.strip() else "fts",
        "curation_status": curation_status,
        "items": results
    }

@app.post("/api/v1/vault/{item_id}/curate")
def curate_item(item_id: int, payload: CuratePayload):
    """Duyệt hoặc loại bỏ bài viết. Nếu duyệt (APPROVE) -> kích hoạt ConsolidationEngine tự học."""
    act = payload.action.upper()
    if act not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Action must be APPROVE or REJECT")

    item = db.get_vault_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if act == "REJECT":
        db.curate_vault_item(item_id, "REJECTED")
        return {"status": "rejected", "curation_status": "REJECTED", "item_id": item_id}

    db.curate_vault_item(item_id, "APPROVED")
    from vault_engine.consolidation import ConsolidationEngine
    consolidation = ConsolidationEngine(db=db, pipeline=pipeline)
    res = consolidation.consolidate_item(item_id)
    return {"status": "approved", "curation_status": "APPROVED", "item_id": item_id, "consolidation": res}

@app.get("/api/v1/vault/{item_id}/associations")
def get_item_associations(item_id: int):
    """Lấy danh sách các liên kết nơ-ron đối chiếu của bài viết trong Não"""
    assocs = db.get_brain_associations(item_id)
    return {"item_id": item_id, "associations": assocs}

@app.get("/api/v1/brain/topics")
def get_brain_topics():
    """Lấy danh sách các Hồ Sơ Chuyên Đề Sống (Living Master Synthesis)"""
    return db.get_all_synthesis_topics()

@app.get("/api/v1/brain/topics/{slug}")
def get_brain_topic_detail(slug: str):
    """Lấy chi tiết bản tổng luận sống của một chuyên đề"""
    topic = db.get_synthesis_topic(slug)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic

@app.get("/api/v1/brain/heuristics")
def get_agent_heuristics(topic: Optional[str] = None, limit: int = 50):
    """Lấy danh sách quy tắc hành động (Procedural Memory) của Agent"""
    return db.get_agent_heuristics(topic=topic, limit=limit)

@app.post("/api/v1/brain/feedback")
def record_agent_feedback(payload: HeuristicFeedbackPayload):
    """Ghi nhận phản hồi thực chiến từ Agent để tự động tiến hóa điểm tin cậy"""
    ok = db.record_heuristic_feedback(payload.heuristic_id, payload.success, payload.note or "")
    if not ok:
        raise HTTPException(status_code=404, detail="Heuristic not found")
    return {"status": "success", "heuristic_id": payload.heuristic_id, "recorded": True}

@app.get("/api/v1/vault/stats")
async def get_vault_stats_alias():
    return await get_vault_stats()

@app.get("/api/v1/vault/{item_id}")
async def get_vault_detail(item_id: int):
    """Lấy chi tiết bản nghiên cứu sâu Markdown (<10ms)"""
    item = db.get_vault_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/v1/vault/{item_id}/graph")
def get_vault_item_graph(item_id: int):
    """Lấy dữ liệu đồ thị tri thức (Knowledge Graph) tương tác cho bài viết"""
    graph_data = db.get_item_graph(item_id)
    if not graph_data.get("nodes"):
        raise HTTPException(status_code=404, detail="Item not found or empty graph")
    return graph_data

@app.get("/api/v1/vault-graph")
def get_vault_global_graph(limit: int = 60):
    """Lấy dữ liệu đồ thị tri thức toàn cảnh (Global Knowledge Graph)"""
    return db.get_global_graph(limit=limit)

class StatusUpdatePayload(BaseModel):
    reading_status: Optional[str] = None
    is_starred: Optional[Any] = None

@app.api_route("/api/v1/vault/{item_id}/status", methods=["PUT", "PATCH"])
async def update_status(
    item_id: int,
    request: Request,
    reading_status: Optional[str] = None,
    read_status: Optional[str] = None,
    is_starred: Optional[Any] = None
):
    """Cập nhật trạng thái đọc hoặc gắn sao VIP hỗ trợ cả Query Params và JSON Body"""
    status_val = reading_status or read_status
    star_val = is_starred

    # Đọc thêm từ JSON body nếu có
    try:
        body = await request.json()
        if isinstance(body, dict):
            status_val = body.get("reading_status") or body.get("read_status") or status_val
            if "is_starred" in body:
                star_val = body.get("is_starred")
    except Exception:
        pass

    clean_status = status_val.upper() if isinstance(status_val, str) else None
    clean_star = None
    if star_val is not None:
        if isinstance(star_val, str):
            clean_star = 1 if star_val.lower() in ("true", "1") else 0
        elif isinstance(star_val, bool):
            clean_star = 1 if star_val else 0
        else:
            clean_star = int(star_val)

    db.update_item_status(item_id, reading_status=clean_status, is_starred=clean_star)
    return {"status": "success", "item_id": item_id, "reading_status": clean_status, "is_starred": clean_star}

@app.get("/api/v1/stats")
async def get_vault_stats():
    """Thống kê kho tri thức và bộ não nhận thức"""
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_deleted = 0;")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vault_items WHERE curation_status = 'APPROVED' AND is_deleted = 0;")
    approved = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vault_items WHERE curation_status = 'INBOX' AND is_deleted = 0;")
    inbox = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vault_items WHERE reading_status = 'UNREAD' AND is_deleted = 0;")
    unread = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vault_items WHERE is_starred = 1 AND is_deleted = 0;")
    starred = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM brain_associations;")
    assoc_cnt = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM brain_synthesis_topics;")
    topics_cnt = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM agent_heuristics;")
    heuristics_cnt = cursor.fetchone()[0]

    cursor.execute("SELECT category, COUNT(*) FROM vault_items WHERE is_deleted = 0 GROUP BY category;")
    cats = {r[0]: r[1] for r in cursor.fetchall()}

    return {
        "total_items": total,
        "total_vault_items": total,
        "approved_count": approved,
        "inbox_count": inbox,
        "associations_count": assoc_cnt,
        "synthesis_topics_count": topics_cnt,
        "heuristics_count": heuristics_cnt,
        "unread_count": unread,
        "unread_items": unread,
        "starred_count": starred,
        "starred_items": starred,
        "categories": cats
    }

@app.post("/api/v1/scout/trigger")
async def trigger_scout_cycle(background_tasks: BackgroundTasks):
    """Kích hoạt một chu kỳ săn lùng tri thức tự hành ngay lập tức"""
    if not scout_daemon:
        raise HTTPException(status_code=503, detail="Autonomous Scout chưa được khởi tạo")
    
    background_tasks.add_task(scout_daemon.run_scout_cycle)
    return {
        "status": "triggered",
        "message": "Đã kích hoạt chu kỳ săn lùng tri thức tự hành trong background worker"
    }

@app.get("/api/v1/scout/status")
async def get_scout_status():
    """Lấy trạng thái vận hành của Autonomous Scout Daemon"""
    is_running = scout_daemon._running if scout_daemon else False
    is_thread_alive = scout_daemon._thread.is_alive() if (scout_daemon and scout_daemon._thread) else False
    return {
        "enabled": SCOUT_ENABLED,
        "is_running": is_running,
        "is_thread_alive": is_thread_alive,
        "interval_seconds": SCOUT_INTERVAL_SECONDS,
        "interval_hours": round(SCOUT_INTERVAL_SECONDS / 3600, 2)
    }

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Giao diện Bento Grid Dashboard"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Autonomous Knowledge Vault v3.0</h1><p>Dashboard UI is loading...</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("vault_engine.server:app", host="127.0.0.1", port=7860, reload=True)
