import hashlib
import uuid
import time
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Dict, Any, Optional

STRIP_PARAMS = {
    "fbclid", "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "ref", "ref_src", "si", "s", "igsh", "feature", "context"
}

def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    # Xử lý chuẩn hoá riêng cho GitHub
    if "github.com" in netloc:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[0].lower(), parts[1].lower()
            if repo.endswith(".git"):
                repo = repo[:-4]
            return f"https://github.com/{owner}/{repo}"

    # Lọc bỏ tham số theo dõi
    query_params = parse_qsl(parsed.query, keep_blank_values=False)
    filtered = sorted([(k, v) for k, v in query_params if k.lower() not in STRIP_PARAMS])
    clean_query = urlencode(filtered)

    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    return urlunparse((scheme, netloc, path, "", clean_query, ""))

def generate_url_hash(url: str) -> str:
    canon = canonicalize_url(url)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()

def detect_source_type(url: str) -> str:
    u = url.lower()
    if "github.com" in u:
        return "GITHUB"
    elif "youtube.com" in u or "youtu.be" in u:
        return "YOUTUBE"
    elif "arxiv.org" in u:
        return "ARXIV"
    elif "facebook.com" in u or "fb.watch" in u:
        return "FACEBOOK"
    return "WEB_ARTICLE"

class IngestManager:
    def __init__(self, db):
        self.db = db

    def enqueue_url(self, raw_url: str, source_type: Optional[str] = None, priority: int = 1) -> Optional[Dict[str, Any]]:
        canon_url = canonicalize_url(raw_url)
        url_hash = generate_url_hash(canon_url)
        stype = source_type or detect_source_type(canon_url)
        task_uuid = str(uuid.uuid4())

        cursor = self.db.conn.cursor()
        # Kiểm tra trùng lặp trong kho đã xử lý
        cursor.execute("SELECT id, title FROM vault_items WHERE url_hash = ?;", (url_hash,))
        existing_vault = cursor.fetchone()
        if existing_vault:
            return {"status": "ALREADY_IN_VAULT", "item_id": existing_vault["id"], "title": existing_vault["title"]}

        # Kiểm tra trùng lặp trong hàng đợi đang chờ/đang chạy
        cursor.execute("SELECT id, task_uuid, status FROM queue_tasks WHERE url_hash = ? AND status IN ('PENDING', 'PROCESSING');", (url_hash,))
        existing_queue = cursor.fetchone()
        if existing_queue:
            return {"status": "ALREADY_QUEUED", "task_uuid": existing_queue["task_uuid"]}

        # Thêm mới vào queue
        sql = """INSERT INTO queue_tasks (
            task_uuid, url_hash, raw_url, source_type, status, priority
        ) VALUES (?, ?, ?, ?, 'PENDING', ?);"""
        cursor.execute(sql, (task_uuid, url_hash, canon_url, stype, priority))
        self.db.conn.commit()

        return {
            "task_id": cursor.lastrowid,
            "task_uuid": task_uuid,
            "url_hash": url_hash,
            "canonical_url": canon_url,
            "source_type": stype,
            "status": "PENDING"
        }

    def lease_next_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.conn.cursor()
        now = int(time.time())

        # Transaction an toàn: Chọn task khả dụng và lock
        cursor.execute("""
            SELECT id, task_uuid, url_hash, raw_url, source_type, status, locked_by, locked_at, retry_count
            FROM queue_tasks
            WHERE status = 'PENDING'
               OR (status = 'PROCESSING' AND locked_at < ? - 300)
            ORDER BY priority DESC, created_at ASC
            LIMIT 1;
        """, (now,))
        task_row = cursor.fetchone()
        if not task_row:
            return None

        task_id = task_row["id"]
        # Update trạng thái
        cursor.execute("""
            UPDATE queue_tasks
            SET status = 'PROCESSING',
                locked_at = ?,
                locked_by = ?,
                updated_at = ?
            WHERE id = ? AND (status = 'PENDING' OR (status = 'PROCESSING' AND locked_at < ? - 300));
        """, (now, worker_id, now, task_id, now))
        self.db.conn.commit()

        if cursor.rowcount == 0:
            # Race condition: Task vừa bị worker khác nhận
            return None

        result = dict(task_row)
        result["status"] = "PROCESSING"
        result["locked_by"] = worker_id
        result["locked_at"] = now
        return result

    def complete_task(self, task_id: int):
        cursor = self.db.conn.cursor()
        cursor.execute("UPDATE queue_tasks SET status = 'COMPLETED', updated_at = strftime('%s', 'now') WHERE id = ?;", (task_id,))
        self.db.conn.commit()

    def fail_task(self, task_id: int, error_message: str, is_permanent: bool = False):
        cursor = self.db.conn.cursor()
        if is_permanent:
            cursor.execute("UPDATE queue_tasks SET status = 'DLQ', error_message = ?, updated_at = strftime('%s', 'now') WHERE id = ?;", (error_message, task_id))
        else:
            cursor.execute("""
                UPDATE queue_tasks
                SET retry_count = retry_count + 1,
                    status = CASE WHEN retry_count + 1 >= max_retries THEN 'FAILED' ELSE 'PENDING' END,
                    error_message = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = strftime('%s', 'now')
                WHERE id = ?;
            """, (error_message, task_id))
        self.db.conn.commit()
