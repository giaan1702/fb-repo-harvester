import os
import sys
import sqlite3
import logging
from vault_engine.config import DB_PATH, TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
from vault_engine.db import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("turso_sync")

TABLES_TO_SYNC = [
    "vault_items",
    "brain_associations",
    "brain_synthesis_topics",
    "agent_heuristics",
    "vault_embeddings",
    "queue_tasks"
]

def sync_to_turso(local_db_path: str = DB_PATH, turso_url: str = "", turso_token: str = ""):
    url = turso_url or TURSO_DATABASE_URL or os.getenv("TURSO_DATABASE_URL", "")
    token = turso_token or TURSO_AUTH_TOKEN or os.getenv("TURSO_AUTH_TOKEN", "")

    if not url or not token:
        logger.error("Thiếu cấu hình Turso! Vui lòng cung cấp TURSO_DATABASE_URL và TURSO_AUTH_TOKEN.")
        logger.info("Ví dụ: python -m vault_engine.turso_sync --url libsql://... --token ...")
        return False

    if not os.path.exists(local_db_path):
        logger.error(f"Không tìm thấy database cục bộ tại: {local_db_path}")
        return False

    logger.info("======================================================================")
    logger.info("BAT DAU DONG BO TRI THUC LEN TURSO CLOUD SQLITE")
    logger.info(f"Nguon Local : {local_db_path}")
    logger.info(f"Dich Turso  : {url}")
    logger.info("======================================================================")

    src_conn = sqlite3.connect(local_db_path)
    src_conn.row_factory = sqlite3.Row

    target_db = DatabaseManager(turso_url=url, turso_token=token)
    target_conn = target_db.conn

    total_migrated = 0
    for table in TABLES_TO_SYNC:
        try:
            chk = src_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
            ).fetchone()
            if not chk:
                continue

            rows = src_conn.execute(f"SELECT * FROM {table};").fetchall()
            if not rows:
                logger.info(f"Bang '{table}': Trong, bo qua.")
                continue

            cols = [col[0] for col in src_conn.execute(f"SELECT * FROM {table} LIMIT 1;").description]
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)

            insert_sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders});"

            count = 0
            for r in rows:
                vals = [r[c] for c in cols]
                target_conn.execute(insert_sql, vals)
                count += 1

            target_conn.commit()
            total_migrated += count
            logger.info(f"Bang '{table}': Da dong bo thanh cong {count} ban ghi.")
        except Exception as e:
            logger.error(f"Loi khi dong bo bang '{table}': {e}")

    try:
        logger.info("Dang tai tao chi muc toan van FTS5 tren Turso...")
        target_conn.execute("INSERT INTO vault_fts(vault_fts) VALUES('rebuild');")
        target_conn.commit()
        logger.info("Chi muc FTS5 tren Turso da san sang cho Hybrid Search.")
    except Exception as fts_err:
        logger.warning(f"Canh bao FTS5 rebuild: {fts_err}")

    src_conn.close()
    logger.info("======================================================================")
    logger.info(f"HOAN TAT DONG BO: {total_migrated} ban ghi tri thuc da an toan tren Turso Cloud!")
    logger.info("======================================================================")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate local SQLite to Turso Cloud")
    parser.add_argument("--url", help="Turso Database URL", default="")
    parser.add_argument("--token", help="Turso Auth Token", default="")
    parser.add_argument("--src", help="Local SQLite file path", default=DB_PATH)
    args = parser.parse_args()

    success = sync_to_turso(local_db_path=args.src, turso_url=args.url, turso_token=args.token)
    sys.exit(0 if success else 1)
