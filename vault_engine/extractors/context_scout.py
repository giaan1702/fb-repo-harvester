import os
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from vault_engine.extractors.github_engine import GitHubExtractor
from vault_engine.extractors.web_engine import WebExtractor
from vault_engine.extractors.youtube_engine import YouTubeExtractor
from vault_engine.extractors.reference_harvester import extract_references
from vault_engine.ingest import canonicalize_url, detect_source_type
from vault_engine.config import GEMINI_API_KEY

logger = logging.getLogger("context_scout")

@dataclass
class UnifiedContextDossier:
    canonical_url: str
    source_type: str
    title: str
    primary_content: str
    comments: List[str] = field(default_factory=list)
    identified_repo_url: Optional[str] = None
    repo_metadata: Optional[Dict[str, Any]] = None
    repo_readme: Optional[str] = None
    visual_assets: List[Dict[str, str]] = field(default_factory=list)
    referenced_docs: List[Dict[str, Any]] = field(default_factory=list)
    video_transcript: Optional[str] = None
    error: Optional[str] = None

    def get_aggregate_text_for_pipeline(self) -> str:
        """Tổng hợp toàn bộ bối cảnh đa tầng thành văn bản đầu vào cho pipeline phân tích."""
        sections = []
        sections.append(f"# {self.title}\n\nURL Nguồn: {self.canonical_url} ({self.source_type})\n")
        
        if self.primary_content:
            sections.append(f"## BÀI VIẾT NGUỒN\n\n{self.primary_content}\n")

        if self.comments:
            sections.append(f"## BÌNH LUẬN & THẢO LUẬN CỘNG ĐỒNG\n\n" + "\n".join(f"- {c}" for c in self.comments) + "\n")

        if self.identified_repo_url and self.repo_metadata:
            stars = self.repo_metadata.get('stars', 0)
            lang = self.repo_metadata.get('language', '')
            topics = ', '.join(self.repo_metadata.get('topics', []))
            sections.append(
                f"## THÔNG TIN KHO MÃ NGUỒN ({self.identified_repo_url})\n"
                f"* Stars: {stars:,} | Ngôn ngữ chính: {lang}\n"
                f"* Topics: {topics}\n"
            )

        if self.repo_readme:
            sections.append(f"## TÀI LIỆU KHO MÃ NGUỒN (README & DOCS)\n\n{self.repo_readme}\n")

        if self.video_transcript:
            sections.append(f"## LỜI THUYẾT MINH VIDEO (TRANSCRIPT)\n\n{self.video_transcript}\n")

        if self.visual_assets:
            sections.append("## HÌNH ẢNH SƠ ĐỒ KIẾN TRÚC & BENCHMARK THẬT TỪ DỰ ÁN\n")
            for idx, asset in enumerate(self.visual_assets[:5], 1):
                sections.append(f"{idx}. ![{asset['caption']}]({asset['url']}) (Loại: {asset['category']})")
            sections.append("")

        return "\n\n".join(sections)

class ContextScout:
    """
    Agent Trinh Sát Suy Luận Bối Cảnh Đa Tầng (Context Scout Agent):
    Đứng giữa khâu thu thập dữ liệu thô và khâu xử lý của LLM:
    - Bóc tách caption và comment từ bài viết mạng xã hội.
    - Tự suy luận tên repo hoặc link giấu trong comment.
    - Tìm kiếm repo GitHub tự động nếu chỉ có tên.
    - Kéo README, tài liệu sâu và bóc tách ảnh sơ đồ kiến trúc thật.
    - Đóng gói toàn bộ thành UnifiedContextDossier.
    """
    def __init__(self, github_ext: Optional[GitHubExtractor] = None,
                 web_ext: Optional[WebExtractor] = None,
                 youtube_ext: Optional[YouTubeExtractor] = None):
        self.github_ext = github_ext or GitHubExtractor()
        self.web_ext = web_ext or WebExtractor()
        self.youtube_ext = youtube_ext or YouTubeExtractor()

    def build_unified_dossier(self, raw_url: str, source_type: Optional[str] = None) -> UnifiedContextDossier:
        clean_url = canonicalize_url(raw_url)
        stype = source_type or detect_source_type(clean_url)
        logger.info(f"ContextScout bắt đầu trinh sát: {clean_url} [{stype}]")

        primary_content = ""
        title = "Tài liệu kỹ thuật"
        visual_assets: List[Dict[str, str]] = []
        comments: List[str] = []
        identified_repo_url: Optional[str] = None
        repo_metadata: Optional[Dict[str, Any]] = None
        repo_readme: Optional[str] = None
        video_transcript: Optional[str] = None

        extraction_error: Optional[str] = None

        # 1. TRÍCH XUẤT SƠ CẤP TÙY THEO SOURCE TYPE
        if stype == "GITHUB":
            gh_data = self.github_ext.extract(clean_url)
            if gh_data and "error" not in gh_data:
                title = gh_data.get("title", title)
                primary_content = gh_data.get("content", "")
                repo_readme = gh_data.get("raw_readme", "")
                visual_assets = gh_data.get("visual_assets", [])
                identified_repo_url = clean_url
                repo_metadata = {
                    "stars": gh_data.get("stars", 0),
                    "language": gh_data.get("language", ""),
                    "topics": gh_data.get("topics", []),
                    "description": gh_data.get("description", "")
                }
            else:
                extraction_error = gh_data.get("error") if gh_data else "GitHub extraction failed"
        elif stype == "YOUTUBE":
            yt_data = self.youtube_ext.extract(clean_url)
            if yt_data and "error" not in yt_data:
                title = yt_data.get("title", title)
                primary_content = yt_data.get("content", "")
                video_transcript = yt_data.get("raw_transcript", "")
            else:
                extraction_error = yt_data.get("error") if yt_data else "YouTube extraction failed"
        else:
            # WEB hoặc FACEBOOK
            web_data = self.web_ext.extract(clean_url)
            if web_data and "error" not in web_data:
                title = web_data.get("title", title)
                primary_content = web_data.get("content", "")
                comments = web_data.get("comments", [])
            else:
                extraction_error = web_data.get("error") if web_data else "Web extraction failed"

        # 2. BÓC TÁCH TÀI LIỆU THAM KHẢO BAN ĐẦU
        full_text_for_refs = f"{primary_content}\n" + "\n".join(comments)
        referenced_docs = extract_references(full_text_for_refs, current_url=clean_url)

        # 3. SUY LUẬN TÌM REPO NẾU ĐÂY KHÔNG PHẢI LÀ GITHUB TRỰC TIẾP
        if stype != "GITHUB":
            # 3A. Kiểm tra xem trong referenced_docs đã có link GitHub nào chưa
            repo_refs = [r for r in referenced_docs if r.get("doc_type") == "REPO"]
            if repo_refs:
                identified_repo_url = repo_refs[0]["url"]
                logger.info(f"Phát hiện repo từ liên kết trích dẫn: {identified_repo_url}")
            else:
                # 3B. Suy luận từ tên dự án nhắc trong bài
                inferred_name = self.infer_repo_name_from_text(primary_content)
                if inferred_name:
                    logger.info(f"Suy luận được tên repo tiềm năng: '{inferred_name}'. Đang tra cứu GitHub...")
                    found_url = self.github_ext.search_repo_by_name(inferred_name)
                    if found_url:
                        identified_repo_url = found_url
                        logger.info(f"Đã tìm thấy repo GitHub chính xác: {identified_repo_url}")
                        referenced_docs.append({
                            "title": f"Mã nguồn GitHub: {inferred_name}",
                            "url": identified_repo_url,
                            "doc_type": "REPO",
                            "context": f"Tự động phát hiện từ bài viết: {inferred_name}"
                        })

            # 3C. Nếu đã tìm thấy repo, tiến hành khai phá chiều sâu (Deep Harvest)
            if identified_repo_url:
                gh_deep = self.github_ext.extract(identified_repo_url)
                if gh_deep and "error" not in gh_deep:
                    repo_readme = gh_deep.get("raw_readme", "")
                    # Gộp visual assets từ repo
                    for asset in gh_deep.get("visual_assets", []):
                        if not any(v["url"] == asset["url"] for v in visual_assets):
                            visual_assets.append(asset)
                    repo_metadata = {
                        "stars": gh_deep.get("stars", 0),
                        "language": gh_deep.get("language", ""),
                        "topics": gh_deep.get("topics", []),
                        "description": gh_deep.get("description", "")
                    }
                    if not title or title == "Tài liệu kỹ thuật":
                        title = f"{gh_deep.get('title')} - Phân Tích Kỹ Thuật"

        # Đảm bảo có ít nhất tiêu đề hợp lệ
        if not title:
            title = "Tài liệu phân tích kỹ thuật"

        dossier_error = None
        if not primary_content and not repo_readme and not video_transcript:
            dossier_error = extraction_error or "Không thể trích xuất nội dung từ nguồn"

        return UnifiedContextDossier(
            canonical_url=clean_url,
            source_type=stype,
            title=title,
            primary_content=primary_content,
            comments=comments,
            identified_repo_url=identified_repo_url,
            repo_metadata=repo_metadata,
            repo_readme=repo_readme,
            visual_assets=visual_assets,
            referenced_docs=referenced_docs,
            video_transcript=video_transcript,
            error=dossier_error
        )

    def infer_repo_name_from_text(self, text: str) -> Optional[str]:
        """
        Dùng heuristics & regex để tìm tên thư viện / repo được nhắc trong bài viết
        ví dụ: "thư viện vllm", "repo crawl4ai", "dự án Nanobot", "framework LangGraph", "vllm-project/vllm"
        """
        if not text:
            return None

        # 1. Ưu tiên tìm slug owner/repo viết trực tiếp trong văn bản (ví dụ: unclecode/crawl4ai, vllm-project/vllm)
        slug_match = re.search(r'\b([a-zA-Z0-9_.-]{2,30}/[a-zA-Z0-9_.-]{2,35})\b', text)
        if slug_match:
            candidate = slug_match.group(1).strip()
            if not re.match(r'^\d+/\d+$', candidate) and not any(ext in candidate.lower() for ext in ["image/", "text/", "application/"]):
                return candidate

        # 2. Regex tìm các mẫu: (thư viện|repo|dự án|framework|package|công cụ|tool) [Tên]
        pattern = re.compile(
            r'(?:thư viện|repo|dự án|framework|package|công cụ|tool)\s+([a-zA-Z0-9_\-\./]{2,40})',
            re.IGNORECASE
        )
        match = pattern.search(text)
        if match:
            candidate = match.group(1).strip().rstrip(".,;:")
            # Bỏ qua các từ thông dụng tiếng Việt / tiếng Anh
            stop_words = {"nay", "kia", "do", "va", "cua", "trong", "cho", "la", "new", "this", "that", "the"}
            if candidate.lower() not in stop_words:
                return candidate

        return None
