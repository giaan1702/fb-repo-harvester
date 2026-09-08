import re
import json
import time
import logging
from typing import Dict, Any, List, Optional
from vault_engine.db import DatabaseManager

logger = logging.getLogger("vault_consolidation")

TOPIC_CATALOG = {
    "AI-Agents": {
        "slug": "ai-agents",
        "title": "Kiến Trúc Multi-Agent & RAG Nhận Thức Tự Hành",
        "description": "Các mô hình tư duy, giao thức giao tiếp và cơ chế tự học cho hệ thống đa tác tử thông minh."
    },
    "LLM-Infra": {
        "slug": "llm-infra",
        "title": "Hạ Tầng Suy Luận & Tối Ưu Bộ Nhớ LLM",
        "description": "Tối ưu hóa KV Cache, PagedAttention, lượng tử hóa và thông lượng phục vụ mô hình ngôn ngữ lớn."
    },
    "Web-Systems": {
        "slug": "web-systems",
        "title": "Hệ Thống Phân Tán, Backend & API Hiệu Năng Cao",
        "description": "Kiến trúc bất đồng bộ, concurrency, chống nghẽn I/O và độ tin cậy của dịch vụ phân tán."
    },
    "DevOps-Cloud": {
        "slug": "devops-cloud",
        "title": "Hạ Tầng Cloud-Native, Docker & Tự Động Hóa Vận Hành",
        "description": "Tự động hóa CI/CD, đóng gói container, quản trị tài nguyên và zero-downtime deployment."
    },
    "Data-Eng": {
        "slug": "data-eng",
        "title": "Kỹ Thuật Xử Lý Dữ Liệu & Vector Search Quy Mô Lớn",
        "description": "Lưu trữ phân tán, xử lý dòng, đánh chỉ mục vector và tối ưu hóa truy vấn thời gian thực."
    }
}

class ConsolidationEngine:
    def __init__(self, db: DatabaseManager, pipeline: Optional[Any] = None):
        self.db = db
        self.pipeline = pipeline

    def _resolve_topic(self, category: str) -> Dict[str, str]:
        for cat_key, info in TOPIC_CATALOG.items():
            if cat_key.lower() == category.lower() or cat_key.lower() in category.lower():
                return info
        clean_slug = re.sub(r'[^a-zA-Z0-9]+', '-', category.lower()).strip('-') or "general-tech"
        return {
            "slug": clean_slug,
            "title": f"Chuyên Đề Tổng Hợp: {category}",
            "description": f"Kho tri thức tổng hợp chuyên sâu về lĩnh vực {category}."
        }

    def consolidate_item(self, item_id: int) -> Dict[str, Any]:
        """Thực hiện toàn bộ chu trình Hợp Nhất Trí Nhớ (Memory Consolidation) cho tài liệu được duyệt."""
        item = self.db.get_vault_item_by_id(item_id)
        if not item:
            raise ValueError(f"Không tìm thấy tài liệu ID #{item_id}")

        logger.info(f"Bắt đầu chu trình Hợp Nhất Não Bộ cho Item #{item_id}: '{item['title']}'")

        # 1. Tìm các nốt lân cận ngữ nghĩa trong Brain Vault (chỉ tìm trong các bài đã APPROVED)
        neighbors = []
        try:
            query = f"{item['title']} {item['short_summary']}"
            candidates = self.db.search_hybrid(
                query=query,
                category="",
                min_score=1,
                reading_status="",
                is_starred=None,
                curation_status="APPROVED",
                limit=6
            )
            neighbors = [n for n in candidates if n["id"] != item_id][:3]
        except Exception as e:
            logger.warning(f"Lỗi khi tìm nốt lân cận qua search_hybrid: {e}")

        # 2. Đối chiếu nơ-ron (Associative Cross-Referencing)
        created_associations = []
        for neighbor in neighbors:
            try:
                assoc = self._cross_synthesize_pair(item, neighbor)
                if assoc:
                    assoc_id = self.db.add_brain_association(
                        source_id=item_id,
                        target_id=neighbor["id"],
                        relation_type=assoc["relation_type"],
                        insight_notes=assoc["insight_notes"],
                        confidence_score=assoc.get("confidence_score", 1.0)
                    )
                    created_associations.append({"id": assoc_id, **assoc})
            except Exception as assoc_err:
                logger.warning(f"Lỗi khi liên kết nơ-ron #{item_id} <-> #{neighbor['id']}: {assoc_err}")

        # 3. Cập nhật / Tiến hóa Hồ Sơ Chuyên Đề Sống (Living Synthesis Topic)
        topic_info = self._resolve_topic(item.get("category", "Tech"))
        topic_record = self._evolve_synthesis_topic(topic_info, item)

        # 4. Trích xuất Bộ nhớ thủ tục (Procedural Memory / Heuristics)
        created_heuristics = self._extract_procedural_heuristics(item, topic_info)

        return {
            "item_id": item_id,
            "title": item["title"],
            "curation_status": "APPROVED",
            "associations_count": len(created_associations),
            "associations": created_associations,
            "synthesis_topic": topic_info["slug"],
            "synthesis_version": topic_record.get("version", 1),
            "heuristics_count": len(created_heuristics),
            "heuristics": created_heuristics
        }

    def _cross_synthesize_pair(self, current: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        """Phân tích quan hệ kỹ thuật giữa 2 tài liệu trong Não."""
        curr_tech = set([t.lower() for t in current.get("tech_stack", [])])
        target_tech = set([t.lower() for t in target.get("tech_stack", [])])
        common_tech = curr_tech.intersection(target_tech)

        relation_type = "EXTENDS"
        insight_notes = ""

        if self.pipeline and hasattr(self.pipeline, "_call_gemini_api") and not getattr(self.pipeline, "api_key", "").startswith("mock_"):
            prompt = f"""Bạn là Kỹ sư trưởng chuyên đối chiếu kiến trúc hệ thống.
Hãy so sánh hai giải pháp/tài liệu sau trong kho tri thức của bộ não:
Tài liệu A (Mới duyệt): "{current['title']}"
- Tóm tắt: {current['short_summary']}
- Gotchas: {current.get('gotchas_and_risks')}

Tài liệu B (Đã có trong não): "{target['title']}"
- Tóm tắt: {target['short_summary']}
- Gotchas: {target.get('gotchas_and_risks')}

Nhiệm vụ: Trả về JSON đúng cấu trúc:
{{
  "relation_type": "REINFORCES" | "CONTRADICTS" | "EXTENDS" | "ALTERNATIVE",
  "insight_notes": "1-2 câu tiếng Việt sắc bén chỉ ra điểm giao thoa kỹ thuật, đánh đổi hoặc sự bổ sung giữa A và B."
}}"""
            try:
                res = self.pipeline._call_gemini_api(prompt, is_json=True)
                data = json.loads(res.strip().replace("```json", "").replace("```", ""))
                return {
                    "relation_type": data.get("relation_type", "EXTENDS"),
                    "insight_notes": data.get("insight_notes", f"Mở rộng kiến trúc liên đới với [[{target['title']}]]."),
                    "confidence_score": 0.95
                }
            except Exception:
                pass

        if common_tech:
            tech_str = ", ".join(list(common_tech)[:3])
            relation_type = "REINFORCES"
            insight_notes = f"Củng cố mô hình thiết kế chung về công nghệ ({tech_str}). Bổ sung giải pháp thực chiến cho [[{target['title']}]]."
        else:
            relation_type = "EXTENDS"
            insight_notes = f"Mở rộng biên độ kiến thức cho [[{target['title']}]], kết hợp nguyên lý tư duy và giải pháp bổ trợ."

        return {
            "relation_type": relation_type,
            "insight_notes": insight_notes,
            "confidence_score": 0.85
        }

    def _evolve_synthesis_topic(self, topic_info: Dict[str, str], new_item: Dict[str, Any]) -> Dict[str, Any]:
        """Tự động tiến hóa tài liệu tổng luận sống khi có kiến thức mới được duyệt."""
        slug = topic_info["slug"]
        existing = self.db.get_synthesis_topic(slug)

        tech_badge = ", ".join([f"`{t}`" for t in new_item.get("tech_stack", [])[:4]])
        gotchas = new_item.get("gotchas_and_risks", [])
        gotcha_item = f"- ⚠️ **{gotchas[0]}**" if gotchas else "- ⚠️ *Lưu ý ràng buộc tài nguyên và giới hạn tải.*"

        item_entry = f"""
### ✦ [[{new_item['title']}]] *(Score: {new_item.get('practical_score', 8)}/10)*
- **Bản chất đòn bẩy:** {new_item['short_summary']}
- **Tech Stack Cốt Lõi:** {tech_badge}
- **Thực chiến Gotcha:**
  {gotcha_item}
"""

        if existing:
            included_ids = existing.get("included_item_ids", [])
            if new_item["id"] not in included_ids:
                included_ids.append(new_item["id"])
            
            cur_md = existing["master_synthesis_md"]
            if new_item['title'] not in cur_md:
                updated_md = cur_md + "\n" + item_entry
            else:
                updated_md = cur_md

            self.db.upsert_synthesis_topic(
                topic_slug=slug,
                topic_title=topic_info["title"],
                master_synthesis_md=updated_md,
                included_item_ids=included_ids
            )
            return {"version": existing["version"] + 1, "topic_slug": slug}
        else:
            initial_md = f"""# 🏛️ Hồ Sơ Chuyên Đề Sống: {topic_info['title']}

> {topic_info['description']}

---

## 1. Bản Đồ Nguyên Lý Cốt Lõi (Core Mental Models)
Tập hợp các giải pháp công nghệ đã qua kiểm duyệt thực tế bởi Kỹ sư Trưởng và nạp vào Bộ Não Tự Hành.

---

## 2. Các Nút Tri Thức Thành Phần
{item_entry}
"""
            self.db.upsert_synthesis_topic(
                topic_slug=slug,
                topic_title=topic_info["title"],
                master_synthesis_md=initial_md,
                included_item_ids=[new_item["id"]]
            )
            return {"version": 1, "topic_slug": slug}

    def _extract_procedural_heuristics(self, item: Dict[str, Any], topic_info: Dict[str, str]) -> List[Dict[str, Any]]:
        """Rút trích các quy tắc hành động (Actionable Rules) và Anti-patterns cho Agent."""
        gotchas = item.get("gotchas_and_risks", [])
        topic = topic_info["title"]
        extracted = []

        if gotchas:
            for g in gotchas[:2]:
                rule = f"Khi thiết kế {item.get('category', 'hệ thống')}, phải chủ động xử lý: {g}."
                anti = f"Bỏ qua kiểm soát hoặc cấu hình mặc định dẫn đến nguy cơ: {g}."
                hid = self.db.add_agent_heuristic(
                    topic=topic,
                    rule_statement=rule,
                    anti_pattern=anti,
                    evidence_item_id=item["id"],
                    confidence_score=1.0
                )
                extracted.append({"id": hid, "rule": rule, "anti_pattern": anti})
        else:
            rule = f"Áp dụng triệt để kiến trúc cốt lõi từ [[{item['title']}]] để tối ưu hóa hiệu năng."
            anti = "Thiết kế monolithic phân tán không có cơ chế timeout và retry lũy kế."
            hid = self.db.add_agent_heuristic(
                topic=topic,
                rule_statement=rule,
                anti_pattern=anti,
                evidence_item_id=item["id"],
                confidence_score=1.0
            )
            extracted.append({"id": hid, "rule": rule, "anti_pattern": anti})

        return extracted
