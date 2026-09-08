import re
from typing import List, Dict, Any, Set
from urllib.parse import urlparse

EXCLUDED_DOMAINS = {
    "shields.io", "badge.fury.io", "badgen.net", "img.shields.io",
    "twitter.com", "x.com", "t.co", "facebook.com", "fb.com", "linkedin.com",
    "discord.gg", "discord.com", "slack.com", "youtube.com", "youtu.be",
    "instagram.com", "reddit.com", "tiktok.com", "patreon.com"
}

GITHUB_NON_REPOS = {
    "features", "topics", "collections", "trending", "pricing", "marketplace",
    "settings", "notifications", "search", "explore", "about", "contact",
    "site", "security", "pulls", "issues", "sponsors", "login", "join"
}

def extract_references(text: str, current_url: str = "") -> List[Dict[str, Any]]:
    """
    Tự động bóc tách các bài báo khoa học (ArXiv), kho mã nguồn (GitHub Repos)
    và các liên kết kiến trúc/học thuật được tác giả trích dẫn trong văn bản.
    """
    if not text:
        return []

    curr_parsed = urlparse(current_url) if current_url else None
    curr_clean_url = current_url.lower().rstrip("/") if current_url else ""

    references: List[Dict[str, Any]] = []
    seen_urls: Set[str] = {curr_clean_url}

    # 1. BÓC TÁCH BÀI BÁO KHOA HỌC ARXIV
    # Regex: arxiv.org/abs/2309.06180 hoặc arXiv:2309.06180
    arxiv_pattern = re.compile(r'(?:https?://arxiv\.org/(?:abs|pdf)/(\d+\.\d+)|(?:arXiv:\s*(\d+\.\d+)))', re.IGNORECASE)
    for m in arxiv_pattern.finditer(text):
        arxiv_id = m.group(1) or m.group(2)
        if not arxiv_id:
            continue
        paper_url = f"https://arxiv.org/abs/{arxiv_id}"
        if paper_url.lower() in seen_urls:
            continue
        seen_urls.add(paper_url.lower())

        # Tìm ngữ cảnh xung quanh
        start = max(0, m.start() - 100)
        end = min(len(text), m.end() + 100)
        snippet = text[start:end].replace("\n", " ").strip()

        references.append({
            "title": f"Nghiên cứu ArXiv: {arxiv_id}",
            "url": paper_url,
            "doc_type": "PAPER",
            "context": f"...{snippet}..." if start > 0 else f"{snippet}...",
            "target_id": arxiv_id
        })

    # 2. BÓC TÁCH KHO MÃ NGUỒN GITHUB
    github_pattern = re.compile(r'https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)', re.IGNORECASE)
    for m in github_pattern.finditer(text):
        owner, repo = m.group(1), m.group(2)
        repo_clean = repo.rstrip(".git").rstrip("/")
        if owner.lower() in GITHUB_NON_REPOS or repo_clean.lower() in GITHUB_NON_REPOS:
            continue
        full_repo_url = f"https://github.com/{owner}/{repo_clean}"
        if full_repo_url.lower() in seen_urls:
            continue
        seen_urls.add(full_repo_url.lower())

        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        snippet = text[start:end].replace("\n", " ").strip()

        references.append({
            "title": f"Mã nguồn GitHub: {owner}/{repo_clean}",
            "url": full_repo_url,
            "doc_type": "REPO",
            "context": f"...{snippet}..." if start > 0 else f"{snippet}...",
            "target_id": f"{owner}/{repo_clean}"
        })

    # 3. BÓC TÁCH CÁC BÀI VIẾT & SÁCH KIẾN TRÚC TỪ MARKDOWN LINKS
    link_pattern = re.compile(r'\[([^\]]{3,80})\]\((https?://[^\)\s]+)\)')
    for m in link_pattern.finditer(text):
        anchor_text = m.group(1).strip()
        link_url = m.group(2).strip()
        link_url_lower = link_url.lower().rstrip("/")

        if link_url_lower in seen_urls:
            continue

        try:
            parsed = urlparse(link_url)
            domain = parsed.netloc.lower()
            # Bỏ qua các domain rác hoặc không hợp lệ
            if any(ex in domain for ex in EXCLUDED_DOMAINS):
                continue
            if "license" in link_url_lower or "badge" in link_url_lower or "shields" in link_url_lower:
                continue
            if anchor_text.startswith("!") or anchor_text.lower() in ["link", "here", "image", "logo", "more"]:
                continue
        except Exception:
            continue

        seen_urls.add(link_url_lower)
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        snippet = text[start:end].replace("\n", " ").strip()

        doc_type = "ARTICLE"
        if "arxiv.org" in domain:
            doc_type = "PAPER"
        elif "github.com" in domain:
            doc_type = "REPO"

        references.append({
            "title": anchor_text,
            "url": link_url,
            "doc_type": doc_type,
            "context": f"...{snippet}..." if start > 0 else f"{snippet}...",
            "target_id": link_url
        })

    # Giới hạn tối đa 10 tài liệu tham chiếu quan trọng nhất
    return references[:10]
