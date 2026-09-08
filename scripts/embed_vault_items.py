import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("embed_migration")

from vault_engine.config import DB_PATH
from vault_engine.db import DatabaseManager
from vault_engine.embedding import get_embedding

def main():
    db = DatabaseManager(db_path=DB_PATH)
    items = db.search_vault(limit=100)
    logger.info(f"Bat dau nhung vector cho {len(items)} tai lieu trong Vault...")

    success = 0
    for it in items:
        vid = it["id"]
        title = it.get("title", "")
        summary = it.get("short_summary", "")
        tech = " ".join(it.get("tech_stack", []))
        concept = it.get("mental_model", "")
        content = f"{title}. {summary}. Tech stack: {tech}. Mental model: {concept}"
        
        vec = get_embedding(content)
        if vec:
            db.save_embedding(vid, vec)
            success += 1
            logger.info(f"[{success}/{len(items)}] Da nhung ID {vid}: {title[:40]}... (dims: {len(vec)})")
        else:
            logger.warning(f"That bai khi nhung ID {vid}")

    total = len(db.get_all_embeddings())
    logger.info(f"Hoan tat! Tong so vector embeddings trong database: {total}")

if __name__ == "__main__":
    main()
