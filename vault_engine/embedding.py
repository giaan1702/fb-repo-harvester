import os
import json
import math
import struct
import logging
import urllib.request
from typing import List, Dict, Optional, Tuple
from vault_engine.config import GEMINI_API_KEY

logger = logging.getLogger("vault_embedding")

EMBEDDING_MODELS = [
    "gemini-embedding-001",
    "gemini-embedding-2",
    "gemini-embedding-2-preview"
]

def get_embedding(text: str, model: str = "gemini-embedding-001", api_key: Optional[str] = None) -> Optional[List[float]]:
    """Sinh vector embedding từ Google AI Studio REST API."""
    key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not key or os.getenv("TESTING"):
        if os.getenv("TESTING"):
            import hashlib
            h = hashlib.sha256(text.encode()).digest()
            return [b / 255.0 for b in h[:32]]
        return None

    clean_text = text.strip()[:6000]
    if not clean_text:
        return None

    for m in [model] + [x for x in EMBEDDING_MODELS if x != model]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:embedContent?key={key}"
        payload = json.dumps({
            "model": f"models/{m}",
            "content": {"parts": [{"text": clean_text}]}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embedding", {}).get("values")
        except Exception as e:
            logger.warning(f"Lỗi gọi embedding model {m}: {e}")
            continue

    return None

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Tính độ tương đồng Cosine giữa 2 vector số thực."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec_a, vec_b):
        dot_product += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))

def serialize_vector(vector: List[float]) -> bytes:
    """Chuyển đổi vector số thực float sang chuỗi byte nhị phân để lưu trữ tối ưu trong SQLite."""
    return struct.pack(f"{len(vector)}f", *vector)

def deserialize_vector(blob: bytes) -> List[float]:
    """Khôi phục vector số thực float từ chuỗi byte nhị phân của SQLite."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))

def reciprocal_rank_fusion(
    bm25_ranks: Dict[int, int],
    vector_ranks: Dict[int, int],
    k: int = 60
) -> List[Tuple[int, float]]:
    """
    Thuật toán hợp nhất xếp hạng RRF (Reciprocal Rank Fusion):
    Score(d) = 1 / (k + rank_bm25(d)) + 1 / (k + rank_vector(d))
    """
    all_doc_ids = set(bm25_ranks.keys()).union(set(vector_ranks.keys()))
    scores = []

    for doc_id in all_doc_ids:
        r_bm25 = bm25_ranks.get(doc_id, 9999)
        r_vec = vector_ranks.get(doc_id, 9999)

        score = (1.0 / (k + r_bm25)) + (1.0 / (k + r_vec))
        scores.append((doc_id, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores
