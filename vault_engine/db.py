import sqlite3
import json
import os
import time
import re
from typing import List, Dict, Any, Optional

DDL_STATEMENTS = [
    "PRAGMA journal_mode = WAL;",
    "PRAGMA busy_timeout = 5000;",
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA foreign_keys = ON;",

    """CREATE TABLE IF NOT EXISTS queue_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_uuid TEXT NOT NULL UNIQUE,
        url_hash TEXT NOT NULL,
        raw_url TEXT NOT NULL,
        source_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        priority INTEGER NOT NULL DEFAULT 1,
        retry_count INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        locked_at INTEGER DEFAULT NULL,
        locked_by TEXT DEFAULT NULL,
        error_message TEXT DEFAULT NULL,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
    );""",

    """CREATE TABLE IF NOT EXISTS vault_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url_hash TEXT NOT NULL UNIQUE,
        canonical_url TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'WEB_ARTICLE',
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        short_summary TEXT NOT NULL,
        practical_score INTEGER NOT NULL,
        score_reason TEXT NOT NULL,
        tech_stack TEXT NOT NULL,
        gotchas_and_risks TEXT NOT NULL,
        deep_research_md TEXT NOT NULL,
        original_md TEXT DEFAULT '',
        referenced_docs TEXT DEFAULT '[]',
        github_repo TEXT DEFAULT NULL,
        drive_path TEXT DEFAULT NULL,
        notebook_ref TEXT DEFAULT NULL,
        audio_podcast_path TEXT DEFAULT NULL,
        reading_status TEXT NOT NULL DEFAULT 'UNREAD',
        is_starred INTEGER NOT NULL DEFAULT 0,
        curation_status TEXT NOT NULL DEFAULT 'INBOX',
        curated_at INTEGER DEFAULT NULL,
        content_hash TEXT NOT NULL DEFAULT '',
        topic_group_id TEXT DEFAULT NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
    );""",

    """CREATE TABLE IF NOT EXISTS dead_letter_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_uuid TEXT NOT NULL,
        raw_url TEXT NOT NULL,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        stack_trace TEXT,
        payload_snapshot TEXT,
        resolved INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
    );""",

    """CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
        title, short_summary, tech_stack, deep_research_md, content='vault_items', content_rowid='id'
    );""",

    """CREATE TRIGGER IF NOT EXISTS vault_ai AFTER INSERT ON vault_items BEGIN
      INSERT INTO vault_fts(rowid, title, short_summary, tech_stack, deep_research_md)
      VALUES (new.id, new.title, new.short_summary, new.tech_stack, new.deep_research_md);
    END;""",

    """CREATE TRIGGER IF NOT EXISTS vault_ad AFTER DELETE ON vault_items BEGIN
      INSERT INTO vault_fts(vault_fts, rowid, title, short_summary, tech_stack, deep_research_md)
      VALUES('delete', old.id, old.title, old.short_summary, old.tech_stack, old.deep_research_md);
    END;""",

    """CREATE TRIGGER IF NOT EXISTS vault_au AFTER UPDATE ON vault_items BEGIN
      INSERT INTO vault_fts(vault_fts, rowid, title, short_summary, tech_stack, deep_research_md)
      VALUES('delete', old.id, old.title, old.short_summary, old.tech_stack, old.deep_research_md);
      INSERT INTO vault_fts(rowid, title, short_summary, tech_stack, deep_research_md)
      VALUES (new.id, new.title, new.short_summary, new.tech_stack, new.deep_research_md);
    END;""",

    """CREATE TABLE IF NOT EXISTS vault_embeddings (
        vault_id INTEGER PRIMARY KEY,
        vector_blob BLOB NOT NULL,
        model_name TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (vault_id) REFERENCES vault_items (id) ON DELETE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS brain_associations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_item_id INTEGER NOT NULL,
        target_item_id INTEGER NOT NULL,
        relation_type TEXT NOT NULL DEFAULT 'EXTENDS',
        insight_notes TEXT NOT NULL,
        confidence_score REAL NOT NULL DEFAULT 1.0,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (source_item_id) REFERENCES vault_items (id) ON DELETE CASCADE,
        FOREIGN KEY (target_item_id) REFERENCES vault_items (id) ON DELETE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS brain_synthesis_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_slug TEXT NOT NULL UNIQUE,
        topic_title TEXT NOT NULL,
        master_synthesis_md TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        included_item_ids TEXT NOT NULL DEFAULT '[]',
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
    );""",

    """CREATE TABLE IF NOT EXISTS agent_heuristics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        rule_statement TEXT NOT NULL,
        anti_pattern TEXT DEFAULT '',
        evidence_item_id INTEGER DEFAULT NULL,
        confidence_score REAL NOT NULL DEFAULT 1.0,
        execution_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (evidence_item_id) REFERENCES vault_items (id) ON DELETE SET NULL
    );""",

    "CREATE INDEX IF NOT EXISTS idx_queue_status_prio ON queue_tasks (status, priority DESC, created_at ASC);",
    "CREATE INDEX IF NOT EXISTS idx_queue_url_hash ON queue_tasks (url_hash);",
    "CREATE INDEX IF NOT EXISTS idx_vault_cat ON vault_items (category);",
    "CREATE INDEX IF NOT EXISTS idx_vault_score ON vault_items (practical_score DESC);",
    "CREATE INDEX IF NOT EXISTS idx_vault_status ON vault_items (reading_status);",
    "CREATE INDEX IF NOT EXISTS idx_vault_starred ON vault_items (is_starred);",
    "CREATE INDEX IF NOT EXISTS idx_vault_curation ON vault_items (curation_status);",
    "CREATE INDEX IF NOT EXISTS idx_assoc_source ON brain_associations (source_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_assoc_target ON brain_associations (target_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_topic_slug ON brain_synthesis_topics (topic_slug);",
    "CREATE INDEX IF NOT EXISTS idx_heuristics_topic ON agent_heuristics (topic);"
]

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        for stmt in DDL_STATEMENTS:
            try:
                cursor.execute(stmt)
            except Exception:
                pass
        self.conn.commit()
        self._run_migrations()

    def _run_migrations(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(vault_items);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "original_md" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE vault_items ADD COLUMN original_md TEXT DEFAULT '';")
            except Exception:
                pass
        if "referenced_docs" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE vault_items ADD COLUMN referenced_docs TEXT DEFAULT '[]';")
            except Exception:
                pass
        if "curation_status" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE vault_items ADD COLUMN curation_status TEXT NOT NULL DEFAULT 'INBOX';")
                cursor.execute("UPDATE vault_items SET curation_status = 'APPROVED' WHERE curation_status = 'INBOX';")
            except Exception:
                pass
        if "curated_at" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE vault_items ADD COLUMN curated_at INTEGER DEFAULT NULL;")
                cursor.execute("UPDATE vault_items SET curated_at = strftime('%s', 'now') WHERE curation_status = 'APPROVED';")
            except Exception:
                pass

        cursor.execute("PRAGMA table_info(brain_synthesis_topics);")
        topic_cols = {row["name"] for row in cursor.fetchall()}
        if "core_principles" not in topic_cols:
            try:
                cursor.execute("ALTER TABLE brain_synthesis_topics ADD COLUMN core_principles TEXT DEFAULT '[]';")
            except Exception:
                pass

        cursor.execute("PRAGMA table_info(agent_heuristics);")
        h_cols = {row["name"] for row in cursor.fetchall()}
        if "rule_type" not in h_cols:
            try:
                cursor.execute("ALTER TABLE agent_heuristics ADD COLUMN rule_type TEXT DEFAULT 'MUST_DO';")
            except Exception:
                pass

        self.conn.commit()

    def checkpoint(self):
        """Flush toàn bộ dữ liệu WAL vào file sqlite .db chính để đồng bộ Git trọn vẹn."""
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            self.conn.commit()
            return True
        except Exception:
            return False

    def dump_sql(self, sql_path: str):
        """Xuất toàn bộ cơ sở dữ liệu thành file SQL sạch, tự động lọc shadow tables của FTS5."""
        os.makedirs(os.path.dirname(os.path.abspath(sql_path)), exist_ok=True)
        with open(sql_path, "w", encoding="utf-8") as f:
            for line in self.conn.iterdump():
                # Lọc bỏ các bảng ảo/bảng bóng FTS5 để tránh xung đột sqlite_master
                if any(x in line for x in ["vault_fts_data", "vault_fts_idx", "vault_fts_docsize", "vault_fts_config", "sqlite_master"]):
                    continue
                if line.startswith('INSERT INTO "vault_fts"') or line.startswith("INSERT INTO vault_fts"):
                    continue
                f.write(f"{line}\n")
            # Tự động thêm lệnh rebuild FTS5 vào cuối dump
            f.write("\n-- Rebuild FTS5 Search Index\n")
            f.write("CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(title, short_summary, tech_stack, deep_research_md, content='vault_items', content_rowid='id');\n")
            f.write("INSERT INTO vault_fts(vault_fts) VALUES('rebuild');\n")

    def restore_sql(self, sql_path: str) -> bool:
        """Khôi phục dữ liệu từ file SQL vào cơ sở dữ liệu một cách idempotent và an toàn tuyệt đối."""
        if not os.path.exists(sql_path):
            return False

        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        self.conn.commit()

        # Xóa các bảng cũ trước khi nạp lại dump để đảm bảo tính Idempotent
        cursor.executescript("""
            DROP TABLE IF EXISTS dead_letter_queue;
            DROP TABLE IF EXISTS brain_associations;
            DROP TABLE IF EXISTS vault_embeddings;
            DROP TABLE IF EXISTS brain_synthesis_topics;
            DROP TABLE IF EXISTS agent_heuristics;
            DROP TABLE IF EXISTS vault_items;
            DROP TABLE IF EXISTS queue_tasks;
            DROP TABLE IF EXISTS vault_fts;
            DROP TABLE IF EXISTS vault_fts_data;
            DROP TABLE IF EXISTS vault_fts_idx;
            DROP TABLE IF EXISTS vault_fts_docsize;
            DROP TABLE IF EXISTS vault_fts_config;
            DROP TRIGGER IF EXISTS vault_ai;
            DROP TRIGGER IF EXISTS vault_ad;
            DROP TRIGGER IF EXISTS vault_au;
        """)
        self.conn.commit()

        cursor.executescript(sql_script)
        self.conn.commit()

        # Đảm bảo FTS5 được khởi tạo và rebuild hoàn chỉnh
        try:
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(title, short_summary, tech_stack, deep_research_md, content='vault_items', content_rowid='id');")
            cursor.execute("INSERT INTO vault_fts(vault_fts) VALUES('rebuild');")
            self.conn.commit()
        except Exception:
            pass

        cursor.execute("PRAGMA foreign_keys = ON;")
        self.conn.commit()
        self._run_migrations()
        return True




    def execute_scalar(self, query: str, params: tuple = ()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row[0] if row else None

    def insert_vault_item(self, item: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        sql = """INSERT OR REPLACE INTO vault_items (
            url_hash, canonical_url, source_type, title, category,
            short_summary, practical_score, score_reason, tech_stack,
            gotchas_and_risks, deep_research_md, original_md, referenced_docs,
            github_repo, drive_path, notebook_ref, audio_podcast_path, reading_status, is_starred,
            curation_status, curated_at
        ) VALUES (
            :url_hash, :canonical_url, :source_type, :title, :category,
            :short_summary, :practical_score, :score_reason, :tech_stack,
            :gotchas_and_risks, :deep_research_md, :original_md, :referenced_docs,
            :github_repo, :drive_path, :notebook_ref, :audio_podcast_path, :reading_status, :is_starred,
            :curation_status, :curated_at
        );"""

        ref_docs = item.get("referenced_docs", [])
        if isinstance(ref_docs, str):
            try: ref_docs = json.loads(ref_docs)
            except Exception: ref_docs = []

        payload = {
            "url_hash": item["url_hash"],
            "canonical_url": item["canonical_url"],
            "source_type": item.get("source_type", "WEB_ARTICLE"),
            "title": item.get("title", "Untitled"),
            "category": item.get("category", "AI-Agents"),
            "short_summary": item.get("short_summary", ""),
            "practical_score": int(item.get("practical_score", 8)),
            "score_reason": item.get("score_reason", ""),
            "tech_stack": json.dumps(item.get("tech_stack", []), ensure_ascii=False) if isinstance(item.get("tech_stack"), list) else item.get("tech_stack", "[]"),
            "gotchas_and_risks": json.dumps(item.get("gotchas_and_risks", []), ensure_ascii=False) if isinstance(item.get("gotchas_and_risks"), list) else item.get("gotchas_and_risks", "[]"),
            "deep_research_md": item.get("deep_research_md", ""),
            "original_md": item.get("original_md", ""),
            "referenced_docs": json.dumps(ref_docs, ensure_ascii=False),
            "github_repo": item.get("github_repo", None),
            "drive_path": item.get("drive_path", None),
            "notebook_ref": item.get("notebook_ref", None),
            "audio_podcast_path": item.get("audio_podcast_path", None),
            "reading_status": item.get("reading_status", "UNREAD"),
            "is_starred": int(item.get("is_starred", 0)),
            "curation_status": item.get("curation_status", "INBOX"),
            "curated_at": item.get("curated_at", None)
        }
        cursor.execute(sql, payload)
        self.conn.commit()
        return cursor.lastrowid

    def get_vault_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        return self.get_vault_item_by_id(item_id)

    def get_vault_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM vault_items WHERE id = ? AND is_deleted = 0;", (item_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try: d["tech_stack"] = json.loads(d["tech_stack"])
        except Exception: pass
        try: d["gotchas_and_risks"] = json.loads(d["gotchas_and_risks"])
        except Exception: pass
        try: d["referenced_docs"] = json.loads(d.get("referenced_docs") or "[]")
        except Exception: d["referenced_docs"] = []
        return d

    def search_vault(self, query: str = "", category: str = "", min_score: int = 1,
                     reading_status: str = "", is_starred: Optional[int] = None,
                     curation_status: Optional[str] = None,
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        conditions = ["v.is_deleted = 0", "v.practical_score >= ?"]
        params: List[Any] = [min_score]

        if category:
            conditions.append("v.category = ?")
            params.append(category)
        if reading_status:
            conditions.append("v.reading_status = ?")
            params.append(reading_status)
        if is_starred is not None:
            conditions.append("v.is_starred = ?")
            params.append(is_starred)
        if curation_status and curation_status.upper() != "ALL":
            conditions.append("v.curation_status = ?")
            params.append(curation_status.upper())

        if query:
            clean_q = re.sub(r'["\'*^~:;{}[\]!@#$%()+\-/<>=?]', ' ', query)
            tokens = [t for t in clean_q.strip().split() if t.upper() not in ("AND", "OR", "NOT")]
            safe_match_query = " ".join(f'"{t}"*' for t in tokens) if tokens else ""

            if safe_match_query:
                sql = f"""SELECT v.* FROM vault_items v
                          JOIN vault_fts f ON v.id = f.rowid
                          WHERE vault_fts MATCH ? AND {' AND '.join(conditions)}
                          ORDER BY v.practical_score DESC, v.created_at DESC
                          LIMIT ? OFFSET ?;"""
                params = [safe_match_query] + params + [limit, offset]
            else:
                # Fallback to LIKE if query was composed entirely of special characters
                like_pattern = f"%{query.strip()}%"
                conditions.append("(v.title LIKE ? OR v.short_summary LIKE ?)")
                sql = f"""SELECT v.* FROM vault_items v
                          WHERE {' AND '.join(conditions)}
                          ORDER BY v.practical_score DESC, v.created_at DESC
                          LIMIT ? OFFSET ?;"""
                params = params + [like_pattern, like_pattern, limit, offset]
        else:
            sql = f"""SELECT v.* FROM vault_items v
                      WHERE {' AND '.join(conditions)}
                      ORDER BY v.practical_score DESC, v.created_at DESC
                      LIMIT ? OFFSET ?;"""
            params = params + [limit, offset]

        try:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # Absolute fallback to standard LIKE query
            fallback_conditions = ["v.is_deleted = 0", "v.practical_score >= ?"]
            fallback_params = [min_score]
            if category:
                fallback_conditions.append("v.category = ?")
                fallback_params.append(category)
            if reading_status:
                fallback_conditions.append("v.reading_status = ?")
                fallback_params.append(reading_status)
            if is_starred is not None:
                fallback_conditions.append("v.is_starred = ?")
                fallback_params.append(is_starred)
            if curation_status and curation_status.upper() != "ALL":
                fallback_conditions.append("v.curation_status = ?")
                fallback_params.append(curation_status.upper())
            fallback_conditions.append("(v.title LIKE ? OR v.short_summary LIKE ?)")
            fallback_sql = f"""SELECT v.* FROM vault_items v
                              WHERE {' AND '.join(fallback_conditions)}
                              ORDER BY v.practical_score DESC, v.created_at DESC
                              LIMIT ? OFFSET ?;"""
            cursor.execute(fallback_sql, tuple(fallback_params + [f"%{query}%", f"%{query}%", limit, offset]))
            rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try: d["tech_stack"] = json.loads(d["tech_stack"])
            except Exception: pass
            try: d["gotchas_and_risks"] = json.loads(d["gotchas_and_risks"])
            except Exception: pass
            try: d["referenced_docs"] = json.loads(d.get("referenced_docs") or "[]")
            except Exception: d["referenced_docs"] = []
            results.append(d)
        return results

    def update_item_status(self, item_id: int, reading_status: Optional[str] = None, is_starred: Optional[int] = None):
        cursor = self.conn.cursor()
        updates = []
        params = []
        if reading_status:
            updates.append("reading_status = ?")
            params.append(reading_status)
        if is_starred is not None:
            updates.append("is_starred = ?")
            params.append(is_starred)
        if updates:
            updates.append("updated_at = strftime('%s', 'now')")
            params.append(item_id)
            sql = f"UPDATE vault_items SET {', '.join(updates)} WHERE id = ?;"
            cursor.execute(sql, tuple(params))
            self.conn.commit()

    def curate_vault_item(self, item_id: int, status: str) -> bool:
        """Cập nhật trạng thái duyệt tuyển chọn: 'APPROVED', 'REJECTED', 'INBOX'."""
        st_upper = status.strip().upper()
        if st_upper in ("APPROVE", "APPROVED"):
            normalized_status = "APPROVED"
        elif st_upper in ("REJECT", "REJECTED"):
            normalized_status = "REJECTED"
        else:
            normalized_status = st_upper

        cursor = self.conn.cursor()
        curated_at = int(time.time()) if normalized_status == "APPROVED" else None
        cursor.execute(
            "UPDATE vault_items SET curation_status = ?, curated_at = ?, updated_at = strftime('%s', 'now') WHERE id = ?;",
            (normalized_status, curated_at, item_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def add_brain_association(self, source_id: Optional[int] = None, target_id: Optional[int] = None,
                              relation_type: str = "EXTENDS", insight_notes: str = "", confidence: float = 1.0,
                              source_item_id: Optional[int] = None, target_item_id: Optional[int] = None,
                              reasoning: str = "", confidence_score: Optional[float] = None) -> int:
        """Tạo liên kết nơ-ron ngữ nghĩa giữa 2 tài liệu trong Não bộ."""
        s_id = source_id if source_id is not None else source_item_id
        t_id = target_id if target_id is not None else target_item_id
        notes = insight_notes if insight_notes else reasoning
        conf = confidence_score if confidence_score is not None else confidence

        if s_id is None or t_id is None:
            raise ValueError("source_id and target_id are required")

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO brain_associations (source_item_id, target_item_id, relation_type, insight_notes, confidence_score)
            VALUES (?, ?, ?, ?, ?);
        """, (s_id, t_id, relation_type, notes, conf))
        self.conn.commit()
        return cursor.lastrowid

    def get_brain_associations(self, item_id: int) -> List[Dict[str, Any]]:
        """Lấy toàn bộ các liên kết đối chiếu nơ-ron của một tài liệu."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.*, 
                   s.title AS source_title, 
                   t.title AS target_title,
                   t.canonical_url AS target_url
            FROM brain_associations a
            JOIN vault_items s ON a.source_item_id = s.id
            JOIN vault_items t ON a.target_item_id = t.id
            WHERE a.source_item_id = ? OR a.target_item_id = ?
            ORDER BY a.created_at DESC;
        """, (item_id, item_id))
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if "insight_notes" in r and "reasoning" not in r:
                r["reasoning"] = r["insight_notes"]
        return rows

    def upsert_synthesis_topic(self, topic_slug: str, topic_title: str = "", master_synthesis_md: str = "",
                               included_item_ids: Optional[List[int]] = None,
                               topic_name: str = "", synthesis_markdown: str = "",
                               source_item_ids: Optional[List[int]] = None,
                               core_principles: Optional[List[str]] = None, **kwargs) -> int:
        """Khởi tạo hoặc cập nhật (tiến hóa) một Hồ Sơ Chuyên Đề Sống (Living Synthesis Doc)."""
        title = topic_title if topic_title else topic_name
        md = master_synthesis_md if master_synthesis_md else synthesis_markdown
        items = included_item_ids if included_item_ids is not None else (source_item_ids or [])
        principles = core_principles or []
        principles_json = json.dumps(principles, ensure_ascii=False)

        cursor = self.conn.cursor()
        item_ids_json = json.dumps(list(set(items)))
        cursor.execute("SELECT id, version FROM brain_synthesis_topics WHERE topic_slug = ?;", (topic_slug,))
        row = cursor.fetchone()
        if row:
            tid, cur_ver = row[0], row[1]
            cursor.execute("""
                UPDATE brain_synthesis_topics 
                SET topic_title = ?, master_synthesis_md = ?, version = ?, included_item_ids = ?, core_principles = ?, updated_at = strftime('%s', 'now')
                WHERE id = ?;
            """, (title, md, cur_ver + 1, item_ids_json, principles_json, tid))
            self.conn.commit()
            return tid
        else:
            cursor.execute("""
                INSERT INTO brain_synthesis_topics (topic_slug, topic_title, master_synthesis_md, version, included_item_ids, core_principles)
                VALUES (?, ?, ?, 1, ?, ?);
            """, (topic_slug, title, md, item_ids_json, principles_json))
            self.conn.commit()
            return cursor.lastrowid

    def get_synthesis_topic(self, topic_slug: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết một Hồ Sơ Chuyên Đề Sống theo slug."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM brain_synthesis_topics WHERE topic_slug = ?;", (topic_slug,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try: d["included_item_ids"] = json.loads(d["included_item_ids"])
        except Exception: d["included_item_ids"] = []
        d["source_item_ids"] = d["included_item_ids"]
        d["synthesis_markdown"] = d.get("master_synthesis_md", "")
        raw_principles = d.get("core_principles", "[]")
        if isinstance(raw_principles, str):
            try: d["core_principles"] = json.loads(raw_principles)
            except Exception: d["core_principles"] = []
        else:
            d["core_principles"] = raw_principles or []
        return d

    def get_all_synthesis_topics(self) -> List[Dict[str, Any]]:
        """Danh sách tất cả các Hồ Sơ Chuyên Đề Sống."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM brain_synthesis_topics ORDER BY updated_at DESC;")
        res = []
        for r in cursor.fetchall():
            d = dict(r)
            try: d["included_item_ids"] = json.loads(d["included_item_ids"])
            except Exception: d["included_item_ids"] = []
            d["source_item_ids"] = d["included_item_ids"]
            d["synthesis_markdown"] = d.get("master_synthesis_md", "")
            raw_principles = d.get("core_principles", "[]")
            if isinstance(raw_principles, str):
                try: d["core_principles"] = json.loads(raw_principles)
                except Exception: d["core_principles"] = []
            else:
                d["core_principles"] = raw_principles or []
            res.append(d)
        return res

    def add_agent_heuristic(self, topic: str = "", rule_statement: str = "", anti_pattern: str = "",
                            evidence_item_id: Optional[int] = None, confidence_score: float = 1.0,
                            category: str = "", trigger_context: str = "", action_directive: str = "",
                            rationale: str = "", source_item_id: Optional[int] = None,
                            rule_type: str = "MUST_DO", **kwargs) -> int:
        """Thêm một quy tắc hành động thực chiến vào Procedural Memory của Agent."""
        t = topic if topic else category
        statement = rule_statement if rule_statement else action_directive
        ev_id = evidence_item_id if evidence_item_id is not None else source_item_id
        r_type = rule_type or kwargs.get("rule_type", "MUST_DO")

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO agent_heuristics (topic, rule_statement, anti_pattern, evidence_item_id, confidence_score, rule_type)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (t, statement, anti_pattern, ev_id, confidence_score, r_type))
        self.conn.commit()
        return cursor.lastrowid

    def get_agent_heuristics(self, topic: Optional[str] = None, rule_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách quy tắc hành động của Agent, sắp xếp theo điểm tin cậy cao nhất."""
        cursor = self.conn.cursor()
        query = """
            SELECT h.*, v.title AS evidence_title, v.canonical_url AS evidence_url
            FROM agent_heuristics h
            LEFT JOIN vault_items v ON h.evidence_item_id = v.id
        """
        conditions = []
        params = []
        if topic:
            conditions.append("h.topic LIKE ?")
            params.append(f"%{topic}%")
        if rule_type:
            conditions.append("h.rule_type = ?")
            params.append(rule_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY h.confidence_score DESC, h.updated_at DESC LIMIT ?;"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if "rule_type" not in r or not r["rule_type"]:
                r["rule_type"] = "MUST_DO"
        return rows

    def record_heuristic_feedback(self, heuristic_id: int, success: bool = True, note: str = "", is_positive: Optional[bool] = None, **kwargs) -> bool:
        """Ghi nhận phản hồi thực nghiệm từ Agent để tự động điều chỉnh điểm tin cậy."""
        succ = success if is_positive is None else is_positive
        cursor = self.conn.cursor()
        cursor.execute("SELECT confidence_score, execution_count, success_count FROM agent_heuristics WHERE id = ?;", (heuristic_id,))
        row = cursor.fetchone()
        if not row:
            return False
        cur_score, exec_cnt, succ_cnt = row[0], row[1], row[2]
        new_exec = exec_cnt + 1
        new_succ = succ_cnt + (1 if succ else 0)
        delta = 0.05 if succ else -0.15
        new_score = max(0.1, min(2.0, round(cur_score + delta, 2)))
        cursor.execute("""
            UPDATE agent_heuristics
            SET execution_count = ?, success_count = ?, confidence_score = ?, updated_at = strftime('%s', 'now')
            WHERE id = ?;
        """, (new_exec, new_succ, new_score, heuristic_id))
        self.conn.commit()
        return True

    def record_dlq(self, task_uuid: str, raw_url: str, error_type: str,
                   error_message: str, stack_trace: str = "", payload_snapshot: str = ""):
        cursor = self.conn.cursor()
        sql = """INSERT INTO dead_letter_queue (
            task_uuid, raw_url, error_type, error_message, stack_trace, payload_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?);"""
        cursor.execute(sql, (task_uuid, raw_url, error_type, error_message, stack_trace, payload_snapshot))
        self.conn.commit()

    def get_dlq_items(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM dead_letter_queue WHERE resolved = 0 ORDER BY created_at DESC;")
        return [dict(r) for r in cursor.fetchall()]

    def get_item_graph(self, item_id: int) -> Dict[str, Any]:
        """
        Xây dựng mạng lưới tri thức đồ thị (Knowledge Graph) cho một bài viết cụ thể:
        - Nốt trung tâm: Bài viết hiện tại (current)
        - Nốt phân loại: Category (category)
        - Nốt công nghệ: Tech Stack tags (tech)
        - Nốt trích dẫn: Referenced docs (ref_repo, ref_paper, ref_web)
        - Nốt khái niệm WikiLinks: [[Concept]] được trích xuất từ deep_research_md (concept)
        - Nốt bài viết liên quan trong Vault: Chia sẻ tech stack hoặc category (vault_item)
        """
        target = self.get_vault_item_by_id(item_id)
        if not target:
            return {"nodes": [], "edges": []}

        nodes = []
        edges = []
        node_ids = set()

        def add_node(nid, label, group, **kwargs):
            if nid not in node_ids:
                node = {
                    "id": nid,
                    "label": label,
                    "group": group,
                    **kwargs
                }
                nodes.append(node)
                node_ids.add(nid)

        def add_edge(src, dst, label="", **kwargs):
            edges.append({
                "from": src,
                "to": dst,
                "label": label,
                **kwargs
            })

        # 1. Target node (Trung tâm)
        target_nid = f"vault_{target['id']}"
        add_node(
            target_nid,
            target["title"],
            "current",
            shape="dot",
            size=28,
            color="#38bdf8",
            font={"color": "#f8fafc", "size": 13, "bold": True},
            item_id=target["id"],
            summary=target["short_summary"]
        )

        # 2. Category node
        cat = target.get("category")
        if cat:
            cat_nid = f"cat_{cat}"
            add_node(
                cat_nid,
                cat,
                "category",
                shape="hexagon",
                size=22,
                color="#a855f7",
                font={"color": "#e9d5ff", "size": 12}
            )
            add_edge(target_nid, cat_nid, label="DANH MỤC", color={"color": "#a855f7", "opacity": 0.6})

        # 3. Tech stack nodes
        raw_tech = target.get("tech_stack", [])
        if isinstance(raw_tech, str):
            try: raw_tech = json.loads(raw_tech)
            except Exception: raw_tech = []
        
        target_tech_set = set(t.lower() for t in raw_tech)
        for t in raw_tech:
            tech_nid = f"tech_{t.lower()}"
            add_node(
                tech_nid,
                t,
                "tech",
                shape="box",
                margin=7,
                color="#10b981",
                font={"color": "#ecfdf5", "size": 11}
            )
            add_edge(target_nid, tech_nid, label="CÔNG NGHỆ", color={"color": "#10b981", "opacity": 0.5})

        # 4. Referenced Docs (Papers, Repos, URLs)
        raw_refs = target.get("referenced_docs", [])
        if isinstance(raw_refs, str):
            try: raw_refs = json.loads(raw_refs)
            except Exception: raw_refs = []
        
        for idx, ref in enumerate(raw_refs):
            ref_nid = f"ref_{target['id']}_{idx}"
            dtype = ref.get("doc_type", "LINK").upper()
            color = "#f59e0b" if dtype == "REPO" else ("#ec4899" if dtype == "PAPER" else "#6366f1")
            shape = "diamond" if dtype == "REPO" else ("star" if dtype == "PAPER" else "triangle")
            add_node(
                ref_nid,
                ref.get("title", f"Ref #{idx+1}"),
                f"ref_{dtype.lower()}",
                shape=shape,
                size=18,
                color=color,
                url=ref.get("url", ""),
                font={"color": "#fef3c7", "size": 10}
            )
            add_edge(target_nid, ref_nid, label=f"TRÍCH DẪN ({dtype})", color={"color": color, "opacity": 0.6})

        # 5. WikiLinks [[Concept]] trong markdown
        deep_md = target.get("deep_research_md", "")
        wikilink_matches = re.findall(r"\[\[(.*?)\]\]", deep_md)
        seen_concepts = set()
        for concept in wikilink_matches:
            c_clean = concept.strip()
            if not c_clean or c_clean.lower() in seen_concepts:
                continue
            seen_concepts.add(c_clean.lower())
            concept_nid = f"concept_{c_clean.lower()}"
            add_node(
                concept_nid,
                f"[[{c_clean}]]",
                "concept",
                shape="ellipse",
                size=18,
                color="#06b6d4",
                font={"color": "#cffafe", "size": 11}
            )
            add_edge(target_nid, concept_nid, label="KHÁI NIỆM", color={"color": "#06b6d4", "opacity": 0.5})

        # 6. Related Vault Items (chia sẻ category hoặc tech stack)
        all_items = self.search_vault(limit=100)
        for other in all_items:
            if other["id"] == target["id"]:
                continue
            
            other_tech = set(t.lower() for t in (other.get("tech_stack") or []))
            common_tech = target_tech_set.intersection(other_tech)
            same_cat = (other.get("category") == cat)

            if common_tech or same_cat:
                other_nid = f"vault_{other['id']}"
                add_node(
                    other_nid,
                    other["title"],
                    "vault_item",
                    shape="dot",
                    size=20,
                    color="#475569",
                    item_id=other["id"],
                    summary=other["short_summary"],
                    font={"color": "#cbd5e1", "size": 11}
                )

                if same_cat:
                    add_edge(other_nid, f"cat_{cat}", color={"color": "#64748b", "opacity": 0.3})
                for ct in common_tech:
                    add_edge(other_nid, f"tech_{ct}", color={"color": "#10b981", "opacity": 0.3})

                if len(common_tech) >= 2 or (same_cat and common_tech):
                    add_edge(target_nid, other_nid, label="LIÊN ĐỚI", dashes=True, color={"color": "#38bdf8", "opacity": 0.4})

        return {"nodes": nodes, "edges": edges}

    def get_global_graph(self, limit: int = 60) -> Dict[str, Any]:
        """Xây dựng đồ thị tri thức toàn cảnh cho tất cả tài liệu trong Vault"""
        all_items = self.search_vault(limit=limit)
        nodes = []
        edges = []
        node_ids = set()

        def add_node(nid, label, group, **kwargs):
            if nid not in node_ids:
                nodes.append({"id": nid, "label": label, "group": group, **kwargs})
                node_ids.add(nid)

        def add_edge(src, dst, **kwargs):
            edges.append({"from": src, "to": dst, **kwargs})

        # Danh mục
        categories = set(i.get("category") for i in all_items if i.get("category"))
        for c in categories:
            add_node(f"cat_{c}", c, "category", shape="hexagon", size=24, color="#a855f7", font={"color": "#e9d5ff", "size": 12, "bold": True})

        # Toàn bộ bài viết và tech stack
        for item in all_items:
            vnid = f"vault_{item['id']}"
            score = item.get("practical_score", 0)
            arch = item.get("archetype", "CODE_REPO")
            color = "#38bdf8" if arch == "CODE_REPO" else ("#f43f5e" if arch == "CONCEPT_THOUGHT" else "#8b5cf6")

            add_node(
                vnid,
                item["title"],
                "vault_item",
                shape="dot",
                size=18 + int(score),
                color=color,
                item_id=item["id"],
                summary=item["short_summary"],
                font={"color": "#f1f5f9", "size": 11}
            )

            # Nối Category
            if item.get("category"):
                add_edge(vnid, f"cat_{item['category']}", color={"color": "#a855f7", "opacity": 0.4})

            # Nối Tech Stack
            raw_tech = item.get("tech_stack", [])
            if isinstance(raw_tech, str):
                try: raw_tech = json.loads(raw_tech)
                except Exception: raw_tech = []
            for t in raw_tech:
                tnid = f"tech_{t.lower()}"
                add_node(tnid, t, "tech", shape="box", margin=6, color="#10b981", font={"color": "#ecfdf5", "size": 10})
                add_edge(vnid, tnid, color={"color": "#10b981", "opacity": 0.3})

        return {"nodes": nodes, "edges": edges}

    def save_embedding(self, vault_id: int, vector: List[float], model_name: str = "gemini-embedding-001"):
        from vault_engine.embedding import serialize_vector
        cursor = self.conn.cursor()
        blob = serialize_vector(vector)
        sql = """INSERT INTO vault_embeddings (vault_id, vector_blob, model_name, updated_at)
                 VALUES (?, ?, ?, strftime('%s', 'now'))
                 ON CONFLICT(vault_id) DO UPDATE SET
                 vector_blob = excluded.vector_blob,
                 model_name = excluded.model_name,
                 updated_at = excluded.updated_at;"""
        cursor.execute(sql, (vault_id, blob, model_name))
        self.conn.commit()

    def get_embedding(self, vault_id: int) -> Optional[List[float]]:
        from vault_engine.embedding import deserialize_vector
        cursor = self.conn.cursor()
        cursor.execute("SELECT vector_blob FROM vault_embeddings WHERE vault_id = ?;", (vault_id,))
        row = cursor.fetchone()
        if not row or not row["vector_blob"]:
            return None
        return deserialize_vector(row["vector_blob"])

    def get_all_embeddings(self) -> Dict[int, List[float]]:
        from vault_engine.embedding import deserialize_vector
        cursor = self.conn.cursor()
        cursor.execute("SELECT vault_id, vector_blob FROM vault_embeddings;")
        rows = cursor.fetchall()
        result = {}
        for r in rows:
            try:
                result[r["vault_id"]] = deserialize_vector(r["vector_blob"])
            except Exception:
                pass
        return result

    def hybrid_search_vault(self, query: str = "", category: str = "", min_score: int = 1,
                            reading_status: str = "", is_starred: Optional[int] = None,
                            curation_status: Optional[str] = None,
                            limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Tìm kiếm kết hợp (Hybrid Search: FTS5 BM25 + Gemini Vector Embedding) qua thuật toán RRF.
        """
        bm25_items = self.search_vault(
            query=query, category=category, min_score=min_score,
            reading_status=reading_status, is_starred=is_starred,
            curation_status=curation_status,
            limit=max(50, limit), offset=0
        )
        if not query.strip():
            return bm25_items[:limit]

        bm25_ranks = {item["id"]: rank for rank, item in enumerate(bm25_items, 1)}

        from vault_engine.embedding import get_embedding, cosine_similarity, reciprocal_rank_fusion
        q_vec = get_embedding(query)
        all_vecs = self.get_all_embeddings()

        if not q_vec or not all_vecs:
            return bm25_items[:limit]

        sim_scores = []
        for vid, vec in all_vecs.items():
            sim = cosine_similarity(q_vec, vec)
            sim_scores.append((vid, sim))

        sim_scores.sort(key=lambda x: x[1], reverse=True)
        vector_ranks = {vid: rank for rank, (vid, sim) in enumerate(sim_scores[:50], 1)}

        fused = reciprocal_rank_fusion(bm25_ranks, vector_ranks, k=60)
        top_ids = [vid for vid, score in fused[:limit]]

        item_map = {item["id"]: item for item in bm25_items}
        missing_ids = [vid for vid in top_ids if vid not in item_map]
        for mid in missing_ids:
            it = self.get_vault_item_by_id(mid)
            if it:
                cat_match = not category or it.get("category") == category
                score_match = it.get("practical_score", 0) >= min_score
                curation_match = not curation_status or curation_status.upper() == "ALL" or it.get("curation_status") == curation_status.upper()
                if cat_match and score_match and curation_match:
                    item_map[mid] = it

        results = []
        for vid in top_ids:
            if vid in item_map:
                results.append(item_map[vid])
                if len(results) >= limit:
                    break

        return results if results else bm25_items[:limit]

    # Alias for convenience
    search_hybrid = hybrid_search_vault

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
