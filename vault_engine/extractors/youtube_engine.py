import re
import urllib.parse
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("youtube_engine")

class YouTubeExtractor:
    def extract(self, url: str) -> Optional[Dict[str, Any]]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return None

        transcript_text = self._fetch_transcript(video_id)
        title = f"YouTube Video: {video_id}"

        content = f"# {title}\n\n* **URL:** https://www.youtube.com/watch?v={video_id}\n\n## Phụ Đề & Mốc Thời Gian\n\n{transcript_text}"
        return {
            "title": title,
            "video_id": video_id,
            "content": content[:25000],
            "transcript": transcript_text
        }

    def _extract_video_id(self, url: str) -> Optional[str]:
        parsed = urllib.parse.urlparse(url)
        if "youtube.com" in parsed.netloc:
            if "/shorts/" in parsed.path:
                return parsed.path.split("/shorts/")[1].split("/")[0].split("?")[0]
            if "/embed/" in parsed.path:
                return parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]
            qs = urllib.parse.parse_qs(parsed.query)
            return qs.get("v", [None])[0]
        elif "youtu.be" in parsed.netloc:
            return parsed.path.strip("/").split("?")[0]
        return None

    def _format_time(self, seconds: float) -> str:
        s = int(seconds)
        hours = s // 3600
        mins = (s % 3600) // 60
        secs = s % 60
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def _fetch_transcript(self, video_id: str) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                t = transcript_list.find_transcript(['vi'])
            except Exception:
                try:
                    t = transcript_list.find_transcript(['en'])
                except Exception:
                    t = transcript_list.find_generated_transcript(['vi', 'en'])

            subtitles = t.fetch()
            full_text = []
            chunk_time = 0
            current_chunk = []

            for item in subtitles:
                current_chunk.append(item['text'])
                if item['start'] - chunk_time > 60:
                    mins = int(chunk_time // 60)
                    secs = int(chunk_time % 60)
                    full_text.append(f"[{mins:02d}:{secs:02d}] " + " ".join(current_chunk))
                    current_chunk = []
                    chunk_time = item['start']

            if current_chunk:
                mins = int(chunk_time // 60)
                secs = int(chunk_time % 60)
                full_text.append(f"[{mins:02d}:{secs:02d}] " + " ".join(current_chunk))

            return "\n\n".join(full_text)
        except Exception as e:
            logger.warning(f"Không thể lấy transcript YouTube cho {video_id}: {e}")
            return f"Video YouTube (ID: {video_id}). Không tìm thấy phụ đề tự động."
