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

    def _generate_master_synthesis_whitepaper(self, topic_info: Dict[str, str], items: List[Dict[str, Any]]) -> Optional[str]:
        """Gọi LLM (RMKO Gateway hoặc Gemini) để tổng hợp toàn diện các bài viết thành Bản Tổng Luận Kiến Trúc."""
        from vault_engine.config import RMKO_GATEWAY_URL
        import urllib.request

        items_summary = []
        for it in items:
            tech = it.get("tech_stack", [])
            if isinstance(tech, str):
                try: tech = json.loads(tech)
                except Exception: tech = []
            gotchas = it.get("gotchas_and_risks", [])
            if isinstance(gotchas, str):
                try: gotchas = json.loads(gotchas)
                except Exception: gotchas = []
            items_summary.append({
                "title": it["title"],
                "summary": it.get("short_summary", ""),
                "tech_stack": tech[:4] if isinstance(tech, list) else [],
                "gotchas": gotchas[:2] if isinstance(gotchas, list) else [],
                "score": it.get("practical_score", 9)
            })

        prompt = f"""Bạn là Kỹ sư Trưởng (Principal Systems Architect) kiêm Biên tập viên Kỹ thuật Cấp cao.
Nhiệm vụ: TỔNG HỢP VÀ BIÊN TẬP TOÀN DIỆN CÁC TÀI LIỆU DƯỚI ĐÂY THÀNH MỘT BẢN TỔNG LUẬN KIẾN TRÚC SỐNG (LIVING ARCHITECTURE WHITEPAPER).

CHỦ ĐỀ: {topic_info['title']}
MÔ TẢ: {topic_info['description']}

DANH SÁCH {len(items_summary)} GIẢI PHÁP / CÔNG NGHỆ TRONG CHUYÊN ĐỀ:
{json.dumps(items_summary, ensure_ascii=False, indent=2)}

QUY TẮC BẮT BUỘC:
1. TUYỆT ĐỐI KHÔNG làm tóm tắt gạch đầu dòng rời rạc từng bài. Phải tổng hợp thành một bài khảo sát kiến trúc chuyên sâu liền mạch, đẳng cấp kỹ sư trưởng.
2. MỖI KHI NHẮC ĐẾN TÊN BÀI VIẾT, BẮT BUỘC DÙNG ĐÚNG CÚ PHÁP WIKILINK: `[[Tên Bài Viết]]` (ví dụ: `[[{items_summary[0]['title']}]]`).
3. CẤU TRÚC BÀI TỔNG LUẬN PHẢI GỒM ĐÚNG 5 PHẦN:
   # 🏛️ KHẢO SÁT TOÀN CẢNH: {topic_info['title'].upper()}
   > [!IMPORTANT]
   > **Executive Thesis:** [Luận điểm kỹ thuật cốt lõi 35-50 từ về bản chất và xu hướng dịch chuyển]
   
   ---
   ## 1. The Unified Mental Model (Mô hình hợp nhất 20/80)
   [Phân tích các ranh giới kiểm soát cốt lõi, tìm ra mẫu số chung của các công cụ trong chuyên đề]
   
   ---
   ## 2. Sơ Đồ Topology Toàn Cảnh (Unified System Pipeline)
   [Sơ đồ Mermaid flowchart TD kết nối các công nghệ thành một luồng dữ liệu / kiến trúc phân tầng khép kín. Các node trong Mermaid ghi rõ `[[Tên Công Nghệ]]`]
   
   ---
   ## 3. Ma Trận Đánh Đổi Giữa Các Giải Pháp (Architectural Trade-offs Matrix)
   [Bảng Markdown so sánh chi tiết: Giải pháp / Công cụ | Điểm Mạnh Cốt Lõi | Chi Phí Kỹ Thuật (Trade-off) | Điểm Nghẽn / Cạm Bẫy | Khi Nào Nên Dùng]
   
   ---
   ## 4. Cạm Bẫy Hệ Thống Khi Tích Hợp (Systemic Gotchas & Failure Modes)
   [Các rủi ro chỉ xuất hiện khi kết hợp các công cụ lại với nhau: Cascading Context Drift, I/O Bottlenecks, Deadlocks, Token Amplification, Security]
   
   ---
   ## 5. Khung Phán Quyết Kỹ Sư Trưởng & Lộ Trình Triển Khai (Production Blueprint)
   [Cây quyết định hoặc hướng dẫn chọn phối hợp công cụ theo từng quy mô dự án thực tế: Solo Dev, RAG Doanh Nghiệp, Hệ Thống Lớn]

Ngôn ngữ: Tiếng Việt kỹ thuật chuẩn mực, sâu sắc, trực tiếp.
Xuất ra trực tiếp nội dung Markdown."""

        # 1. Thử gọi RMKO Gateway
        if RMKO_GATEWAY_URL:
            try:
                url = f"{RMKO_GATEWAY_URL.rstrip('/')}/v1/chat/completions"
                payload = {
                    "model": "gemini-3.5-flash-lite",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 8192
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-role": "planner"}
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"].strip()
                    if len(content) > 500:
                        logger.info(f"✓ Đã sinh thành công Master Synthesis Whitepaper ({len(content)} ký tự) qua RMKO Gateway")
                        return content
            except Exception as gw_err:
                logger.warning(f"Không thể sinh synthesis qua RMKO Gateway: {gw_err}")

        # 2. Fallback Gemini Direct
        if self.pipeline and hasattr(self.pipeline, "_call_gemini_api") and getattr(self.pipeline, "api_key", None):
            try:
                res = self.pipeline._call_gemini_api(prompt, is_json=False)
                if res and len(res.strip()) > 500:
                    logger.info(f"✓ Đã sinh thành công Master Synthesis Whitepaper ({len(res)} ký tự) qua Gemini Direct")
                    return res.strip()
            except Exception as g_err:
                logger.warning(f"Không thể sinh synthesis qua Gemini Direct: {g_err}")

        return None

    def _evolve_synthesis_topic(self, topic_info: Dict[str, str], new_item: Dict[str, Any]) -> Dict[str, Any]:
        """Tự động tiến hóa tài liệu tổng luận sống khi có kiến thức mới được duyệt."""
        slug = topic_info["slug"]
        existing = self.db.get_synthesis_topic(slug)

        included_ids = existing.get("included_item_ids", []) if existing else []
        if new_item["id"] not in included_ids:
            included_ids.append(new_item["id"])

        # Nạp tất cả các item trong chuyên đề để tiến hành tổng hợp
        topic_items = []
        for i_id in included_ids:
            it = self.db.get_vault_item_by_id(i_id)
            if it:
                topic_items.append(it)

        # Nếu có từ 2 bài trở lên, kích hoạt Meta-Synthesis cấp Kỹ sư Trưởng
        master_md = None
        if len(topic_items) >= 2:
            master_md = self._generate_master_synthesis_whitepaper(topic_info, topic_items)

        # Fallback nếu LLM tạm thời offline hoặc chỉ có 1 bài
        if not master_md:
            entries = []
            for it in topic_items:
                tech_b = ", ".join([f"`{t}`" for t in (json.loads(it["tech_stack"]) if isinstance(it["tech_stack"], str) else it.get("tech_stack", []))[:4]])
                g_list = json.loads(it["gotchas_and_risks"]) if isinstance(it["gotchas_and_risks"], str) else it.get("gotchas_and_risks", [])
                g_item = f"- ⚠️ **{g_list[0]}**" if g_list else "- ⚠️ *Lưu ý ràng buộc tài nguyên.*"
                entries.append(f"""### ✦ [[{it['title']}]] *(Score: {it.get('practical_score', 8)}/10)*\n- **Bản chất đòn bẩy:** {it.get('short_summary', '')}\n- **Tech Stack Cốt Lõi:** {tech_b}\n- **Thực chiến Gotcha:**\n  {g_item}""")

            joined_entries = "\n\n".join(entries)
            master_md = f"""# 🏛️ Hồ Sơ Chuyên Đề Sống: {topic_info['title']}

> {topic_info['description']}

---

## 1. Bản Đồ Nguyên Lý Cốt Lõi (Core Mental Models)
Tập hợp các giải pháp công nghệ đã qua kiểm duyệt thực tế bởi Kỹ sư Trưởng và nạp vào Bộ Não Tự Hành.

---

## 2. Các Nút Tri Thức Thành Phần ({len(topic_items)} Giải Pháp)
{joined_entries}
"""

        cur_version = existing["version"] if existing else 0
        self.db.upsert_synthesis_topic(
            topic_slug=slug,
            topic_title=topic_info["title"],
            master_synthesis_md=master_md,
            included_item_ids=included_ids
        )
        return {"version": cur_version + 1, "topic_slug": slug}

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
