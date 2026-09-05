import os
import sys
import io
import json
import logging
import threading
import time
import socketserver
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Unicode safe
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fb_harvester.extractor import FacebookExtractor
from fb_harvester.github_resolver import GitHubResolver
from fb_harvester.packager import RepoPackager
from fb_harvester.catalog import CatalogManager
from fb_harvester.notebook_sync import NotebookSyncEngine
from fb_harvester.page_crawler import PageCrawler
from fb_harvester.cli import process_single_item
from fb_harvester.ideator import IdeaEngine
from fb_harvester.ideation_chat import IdeationChatAgent
from fb_harvester.config_manager import ConfigManager
from fb_harvester.notifier import Notifier
from fb_harvester.scheduler import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web_ui")

PORT = int(os.getenv("PORT", 7860))
HOST = os.getenv("HOST", "0.0.0.0")
BASE_DIR = Path(__file__).resolve().parent.parent

# Global logs memory
LOGS_QUEUE = []

def add_log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    LOGS_QUEUE.append(entry)
    if len(LOGS_QUEUE) > 100:
        LOGS_QUEUE.pop(0)
    logger.info(msg)

# Khởi tạo các module toàn cục
chat_agent = IdeationChatAgent(BASE_DIR)
config_mgr = ConfigManager(BASE_DIR)
notifier = Notifier(BASE_DIR)
scheduler = BackgroundScheduler(BASE_DIR, add_log_func=add_log)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Máy chủ HTTP đa luồng xử lý đồng thời nhiều request mà không bị nghẽn."""
    daemon_threads = True

_AUTH_STATUS_CACHE = {"auth": None, "last_check": 0}

def get_cached_auth_status() -> bool:
    now = time.time()
    if _AUTH_STATUS_CACHE["auth"] is not None and now - _AUTH_STATUS_CACHE["last_check"] < 30:
        return _AUTH_STATUS_CACHE["auth"]
    sync_engine = NotebookSyncEngine()
    is_auth = sync_engine.is_authenticated()
    _AUTH_STATUS_CACHE["auth"] = is_auth
    _AUTH_STATUS_CACHE["last_check"] = now
    return is_auth

HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#020617">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>FB Repo Harvester - Trung Tâm Thu Thập Repo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .prose-dark { color: #e2e8f0; }
        .prose-dark h1, .prose-dark h2, .prose-dark h3, .prose-dark h4 { color: #f8fafc; font-weight: 700; margin-top: 1rem; margin-bottom: 0.5rem; }
        .prose-dark h3 { font-size: 1.1rem; color: #a5b4fc; }
        .prose-dark h4 { font-size: 0.95rem; color: #fcd34d; }
        .prose-dark p { margin-bottom: 0.75rem; line-height: 1.6; }
        .prose-dark ul { list-style-type: disc; margin-left: 1.25rem; margin-bottom: 0.75rem; }
        .prose-dark ol { list-style-type: decimal; margin-left: 1.25rem; margin-bottom: 0.75rem; }
        .prose-dark li { margin-bottom: 0.25rem; }
        .prose-dark code { background: #0f172a; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.85em; color: #38bdf8; border: 1px solid #1e293b; }
        .prose-dark pre { background: #020617; padding: 0.75rem; border-radius: 0.5rem; overflow-x: auto; margin-bottom: 0.75rem; border: 1px solid #1e293b; }
        .prose-dark pre code { background: transparent; padding: 0; border: none; color: #34d399; font-size: 0.85em; }
        .prose-dark blockquote { border-left: 4px solid #6366f1; padding-left: 0.75rem; color: #94a3b8; margin: 0.75rem 0; }
        .prose-dark table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; font-size: 0.85rem; }
        .prose-dark th, .prose-dark td { border: 1px solid #334155; padding: 0.4rem 0.6rem; text-align: left; }
        .prose-dark th { background: #1e293b; color: #f8fafc; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen antialiased selection:bg-indigo-500 selection:text-white">
    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-950/90 sticky top-0 z-40 backdrop-blur">
        <div class="max-w-6xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3.5 flex items-center justify-between gap-2">
            <div class="flex items-center space-x-2.5 sm:space-x-3 min-w-0">
                <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/30 shrink-0">
                    <i class="fa-brands fa-facebook text-white text-lg sm:text-xl"></i>
                </div>
                <div class="min-w-0">
                    <h1 class="font-bold text-sm sm:text-lg text-white truncate">FB Repo Harvester</h1>
                    <p class="text-[10px] sm:text-xs text-slate-400 hidden sm:block truncate">Tự động cào video & Co-Ideation Partner</p>
                </div>
            </div>
            <div class="flex items-center space-x-1.5 sm:space-x-2.5 shrink-0">
                <span id="auth-badge" class="px-2 sm:px-3 py-1 rounded-full text-[10px] sm:text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-slate-500"></span> <span class="hidden sm:inline">NotebookLM:</span> Đang ktra...
                </span>
                <button id="btn-login-nlm" onclick="loginNotebookLM()" class="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-[10px] sm:text-xs font-semibold px-2.5 sm:px-3.5 py-1.5 rounded-lg shadow-md shadow-blue-500/20 flex items-center gap-1.5 transition active:scale-95">
                    <i class="fa-solid fa-arrow-right-to-bracket"></i> <span class="hidden sm:inline">Đăng Nhập</span> NLM
                </button>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-8 space-y-5 sm:space-y-8">
        
        <!-- Input Tabs Section -->
        <div class="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3.5 sm:p-6 shadow-xl backdrop-blur">
            <!-- Responsive Horizontal Scrollable Tabs -->
            <div class="flex border-b border-slate-700 mb-4 sm:mb-6 space-x-2 sm:space-x-4 overflow-x-auto no-scrollbar scroll-smooth whitespace-nowrap pb-1">
                <button onclick="switchTab('page-tab')" id="btn-page-tab" class="tab-btn pb-2 sm:pb-3 font-semibold text-blue-400 border-b-2 border-blue-500 flex items-center gap-1.5 text-xs sm:text-sm shrink-0 transition">
                    <i class="fa-solid fa-flag"></i> Cào Fanpage
                </button>
                <button onclick="switchTab('single-tab')" id="btn-single-tab" class="tab-btn pb-2 sm:pb-3 font-medium text-slate-400 hover:text-slate-200 flex items-center gap-1.5 text-xs sm:text-sm shrink-0 transition">
                    <i class="fa-solid fa-video"></i> Video Lẻ
                </button>
                <button onclick="switchTab('channels-tab')" id="btn-channels-tab" class="tab-btn pb-2 sm:pb-3 font-medium text-slate-400 hover:text-slate-200 flex items-center gap-1.5 text-xs sm:text-sm shrink-0 transition">
                    <i class="fa-solid fa-list-check"></i> Quản Lý Kênh
                </button>
                <button onclick="switchTab('ideas-tab')" id="btn-ideas-tab" class="tab-btn pb-2 sm:pb-3 font-medium text-amber-400 hover:text-amber-300 flex items-center gap-1.5 text-xs sm:text-sm shrink-0 transition">
                    <i class="fa-solid fa-wand-magic-sparkles text-amber-400"></i> Idea Lab (AI)
                </button>
                <button onclick="switchTab('ops-tab')" id="btn-ops-tab" class="tab-btn pb-2 sm:pb-3 font-medium text-emerald-400 hover:text-emerald-300 flex items-center gap-1.5 text-xs sm:text-sm shrink-0 transition">
                    <i class="fa-solid fa-tower-broadcast text-emerald-400"></i> Vận Hành (24/7)
                </button>
            </div>

            <!-- Tab 1: Cào Fanpage -->
            <div id="page-tab" class="tab-content space-y-3.5 sm:space-y-4">
                <p class="text-xs sm:text-sm text-slate-300">Nhập link Fanpage hoặc Profile Facebook đăng video về repository:</p>
                <div class="space-y-3">
                    <div class="relative">
                        <i class="fa-solid fa-link absolute left-3.5 top-3.5 text-slate-400 text-xs sm:text-sm"></i>
                        <input type="text" id="page-url" placeholder="https://www.facebook.com/lachcachai hoặc https://www.facebook.com/Aixamxi" 
                            class="w-full pl-9 sm:pl-11 pr-3.5 py-2.5 sm:py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
                        <div class="flex items-center space-x-2 text-xs text-slate-400">
                            <span>Số lượng video gần nhất:</span>
                            <select id="page-limit" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white">
                                <option value="3" selected>3 video</option>
                                <option value="5">5 video</option>
                                <option value="10">10 video</option>
                            </select>
                        </div>
                        <button onclick="startCrawlPage()" id="btn-crawl-page" class="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 transition text-xs sm:text-sm active:scale-95">
                            <i class="fa-solid fa-bolt"></i> Bắt Đầu Cào Video & Repo
                        </button>
                    </div>
                </div>
            </div>

            <!-- Tab 2: Cào Video Lẻ / Text -->
            <div id="single-tab" class="tab-content hidden space-y-3.5 sm:space-y-4">
                <p class="text-xs sm:text-sm text-slate-300">Dán link video Facebook (Reels, Watch) hoặc đoạn text bài viết:</p>
                <div class="space-y-3">
                    <input type="text" id="single-url" placeholder="https://www.facebook.com/watch/?v=123... hoặc link bài viết" 
                        class="w-full px-3.5 py-2.5 sm:py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <textarea id="single-text" rows="3" placeholder="Hoặc dán đoạn caption / mô tả công cụ vào đây nếu video không có link..." 
                        class="w-full px-3.5 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"></textarea>
                    <div class="flex justify-end">
                        <button onclick="startHarvestSingle()" id="btn-harvest-single" class="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition text-xs sm:text-sm active:scale-95">
                            <i class="fa-solid fa-download"></i> Thu Hoạch Ngay
                        </button>
                    </div>
                </div>
            </div>

            <!-- Tab 3: Quản Lý Kênh -->
            <div id="channels-tab" class="tab-content hidden space-y-3.5 sm:space-y-4">
                <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
                    <p class="text-xs sm:text-sm text-slate-300">Danh sách các kênh Facebook đang theo dõi tự động:</p>
                    <div class="flex items-center justify-between sm:justify-end gap-2">
                        <div class="flex items-center gap-1.5 text-xs text-slate-400">
                            <span>Video/kênh:</span>
                            <select id="crawl-all-limit" class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white">
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3" selected>3</option>
                                <option value="5">5</option>
                            </select>
                        </div>
                        <button onclick="crawlAllChannels()" id="btn-crawl-all" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs sm:text-sm font-medium px-3.5 py-1.5 sm:py-2 rounded-xl shadow-lg shadow-emerald-600/30 flex items-center gap-1.5 transition active:scale-95">
                            <i class="fa-solid fa-arrows-rotate"></i> Quét Tất Cả
                        </button>
                    </div>
                </div>
                <div class="flex flex-col sm:flex-row gap-2">
                    <input type="text" id="new-ch-url" placeholder="URL Page mới (https://facebook.com/...)" class="flex-1 px-3.5 py-2 bg-slate-900/80 border border-slate-700 rounded-xl text-xs sm:text-sm text-white">
                    <input type="text" id="new-ch-name" placeholder="Tên Kênh" class="w-full sm:w-44 px-3.5 py-2 bg-slate-900/80 border border-slate-700 rounded-xl text-xs sm:text-sm text-white">
                    <button onclick="addNewChannel()" class="w-full sm:w-auto bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-xl text-xs sm:text-sm font-medium flex items-center justify-center gap-1 active:scale-95">
                        <i class="fa-solid fa-plus"></i> Thêm Kênh
                    </button>
                </div>
                <div id="channels-list" class="space-y-2 pt-2"></div>
            </div>

            <!-- Tab 4: Lên Ý Tưởng (Idea Lab & Co-Ideation Chatbox) -->
            <div id="ideas-tab" class="tab-content hidden space-y-4 sm:space-y-6">
                <!-- Header Banner -->
                <div class="bg-gradient-to-r from-amber-500/10 via-indigo-500/10 to-blue-500/10 border border-amber-500/20 rounded-2xl p-3.5 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 text-base shrink-0">
                            <i class="fa-solid fa-brain"></i>
                        </div>
                        <div class="min-w-0">
                            <div class="flex flex-wrap items-center gap-1.5">
                                <h3 class="font-bold text-white text-sm sm:text-base">Co-Ideation Partner</h3>
                                <span class="text-[9px] sm:text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40 font-semibold flex items-center gap-1 shadow-sm">
                                    <i class="fa-brands fa-google text-blue-400"></i> NotebookLM (65 Sources)
                                </span>
                            </div>
                            <p class="text-[11px] sm:text-xs text-slate-300 mt-0.5 line-clamp-1 sm:line-clamp-none">
                                Khai thác trực tiếp 65 nguồn tri thức kỹ thuật từ Google NotebookLM.
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center flex-wrap gap-1.5 w-full sm:w-auto justify-end">
                        <button onclick="triggerStudio('audio')" id="btn-studio-audio" class="flex-1 sm:flex-initial bg-indigo-600/80 hover:bg-indigo-500 text-white px-2.5 sm:px-3 py-1.5 rounded-xl border border-indigo-500/40 text-[11px] sm:text-xs font-medium flex items-center justify-center gap-1 transition shadow active:scale-95" title="Tạo podcast âm thanh">
                            <i class="fa-solid fa-podcast"></i> Podcast Audio
                        </button>
                        <button onclick="triggerStudio('report')" id="btn-studio-doc" class="flex-1 sm:flex-initial bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 sm:px-3 py-1.5 rounded-xl border border-slate-700 text-[11px] sm:text-xs font-medium flex items-center justify-center gap-1 transition shadow active:scale-95" title="Tạo tài liệu tóm lược">
                            <i class="fa-solid fa-file-lines"></i> Briefing Doc
                        </button>
                        <button onclick="resetChat()" id="btn-reset-chat" class="p-2 sm:px-3 sm:py-1.5 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl border border-slate-700 text-[11px] sm:text-xs font-medium flex items-center justify-center transition shadow active:scale-95" title="Làm mới hội thoại">
                            <i class="fa-solid fa-rotate-left"></i>
                        </button>
                    </div>
                </div>

                <!-- Chatbox Container -->
                <div class="bg-slate-900/90 border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col h-[500px] sm:h-[650px] overflow-hidden">
                    <!-- Messages Log Area -->
                    <div id="chat-messages" class="flex-1 p-3 sm:p-5 overflow-y-auto space-y-3 sm:space-y-4">
                        <!-- Default greeting message from Assistant -->
                        <div class="flex items-start gap-2.5 sm:gap-3">
                            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white text-xs shrink-0 shadow">
                                <i class="fa-solid fa-wand-magic-sparkles text-[11px]"></i>
                            </div>
                            <div class="max-w-[92%] sm:max-w-[85%] bg-slate-800/90 border border-slate-700/80 rounded-2xl rounded-tl-none p-3 sm:p-4 text-xs text-slate-200 shadow-md">
                                <div class="font-semibold text-amber-300 mb-1 flex items-center gap-1.5">
                                    <span>Co-Ideation Partner</span>
                                    <span class="text-[10px] text-slate-400 font-normal">vừa xong</span>
                                </div>
                                <p class="leading-relaxed text-[11px] sm:text-xs">
                                    Chào bạn! Tôi là Cộng Sự Đồng Sáng Tạo Ý Tưởng. Tôi tra cứu trực tiếp toàn bộ <strong>34+ repositories mã nguồn mở</strong> trong kho và 65 tài liệu kỹ thuật <strong>Google NotebookLM</strong>, sẵn sàng phân tích tính khả thi, vẽ <strong>sơ đồ Mermaid</strong> và sinh <strong>PoC Glue Code</strong> thực chiến.
                                </p>
                                <p class="mt-2 text-slate-300 leading-relaxed text-[11px] sm:text-xs">
                                    Bạn muốn xây dựng hệ thống gì, hay muốn kết hợp công nghệ nào? Hãy nhắn cho tôi hoặc chọn gợi ý bên dưới nhé!
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- Prompt Suggestion Chips (Horizontal Swipe on Mobile) -->
                    <div class="px-3 sm:px-5 py-2 bg-slate-950/70 border-t border-slate-800/80 flex items-center gap-2 overflow-x-auto no-scrollbar whitespace-nowrap text-xs">
                        <span class="text-[10px] sm:text-[11px] text-slate-400 shrink-0 font-medium"><i class="fa-regular fa-lightbulb text-amber-400"></i> Gợi ý:</span>
                        <button onclick="sendPromptSuggestion(this)" class="shrink-0 px-2.5 py-1 bg-slate-900 hover:bg-indigo-950/60 border border-slate-700 hover:border-indigo-500/50 rounded-full text-slate-300 text-[11px] sm:text-xs transition active:scale-95">
                            🤖 Trợ lý phân tích video FB & tóm tắt tự động
                        </button>
                        <button onclick="sendPromptSuggestion(this)" class="shrink-0 px-2.5 py-1 bg-slate-900 hover:bg-indigo-950/60 border border-slate-700 hover:border-indigo-500/50 rounded-full text-slate-300 text-[11px] sm:text-xs transition active:scale-95">
                            🎙️ Cào nội dung MXH + Voice AI làm Podcast
                        </button>
                        <button onclick="sendPromptSuggestion(this)" class="shrink-0 px-2.5 py-1 bg-slate-900 hover:bg-indigo-950/60 border border-slate-700 hover:border-indigo-500/50 rounded-full text-slate-300 text-[11px] sm:text-xs transition active:scale-95">
                            💡 Khám phá ý tưởng đột phá từ các repo
                        </button>
                        <button onclick="sendPromptSuggestion(this)" class="shrink-0 px-2.5 py-1 bg-slate-900 hover:bg-indigo-950/60 border border-slate-700 hover:border-indigo-500/50 rounded-full text-slate-300 text-[11px] sm:text-xs transition active:scale-95">
                            🎲 Ghép 2 repo bất ngờ bằng First-Principles
                        </button>
                    </div>

                    <!-- Tool execution indicator bar -->
                    <div id="chat-tool-indicator" class="hidden px-3 sm:px-5 py-1.5 bg-indigo-950/60 border-t border-indigo-900/60 text-[10px] sm:text-[11px] text-indigo-300 flex items-center gap-2">
                        <i class="fa-solid fa-gear fa-spin text-indigo-400"></i>
                        <span id="chat-tool-text">Đang phân tích và tra cứu...</span>
                    </div>

                    <!-- Input Box -->
                    <div class="p-2.5 sm:p-4 bg-slate-950/90 border-t border-slate-800 flex items-end gap-2">
                        <textarea id="chat-input" rows="1" placeholder="Hỏi AI: 'Tôi muốn làm...', 'Hãy vẽ sơ đồ', 'Viết mã kết nối'..." 
                            class="flex-1 px-3 py-2 sm:px-4 sm:py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none max-h-24"></textarea>
                        <button onclick="sendChatMessage()" id="btn-chat-send" class="h-9 sm:h-10 px-3.5 sm:px-5 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 shadow-lg shadow-indigo-600/30 transition shrink-0 active:scale-95">
                            <span class="hidden sm:inline">Gửi</span>
                            <i class="fa-solid fa-paper-plane text-xs"></i>
                        </button>
                    </div>
                </div>

                <!-- Danh sách các ý tưởng đã lưu -->
                <div class="space-y-3 pt-4 border-t border-slate-800">
                    <div class="flex items-center justify-between">
                        <h4 class="font-bold text-sm text-slate-200 flex items-center gap-2">
                            <i class="fa-solid fa-folder-open text-amber-400"></i> Kho Lưu Trữ Ý Tưởng Đã Tạo (<span id="ideas-count">0</span>)
                        </h4>
                        <button onclick="loadIdeasCatalog()" class="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                            <i class="fa-solid fa-rotate"></i> Làm mới
                        </button>
                    </div>
                    <div id="ideas-catalog-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <!-- Render ideas cards -->
                    </div>
                </div>
            </div>

            <!-- Tab 5: Vận Hành & Giám Sát (24/7) -->
            <div id="ops-tab" class="tab-content hidden space-y-6">
                <!-- Status Cards -->
                <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
                    <div class="bg-slate-900/80 border border-slate-700/80 rounded-xl p-3 sm:p-4">
                        <div class="text-xs text-slate-400 mb-1 flex items-center justify-between">
                            <span>TRẠNG THÁI SERVER</span>
                            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
                        </div>
                        <div class="text-base font-bold text-white flex items-center gap-2">
                            <i class="fa-solid fa-circle-check text-emerald-400"></i> Đang Hoạt Động
                        </div>
                        <p class="text-[11px] text-slate-400 mt-2">
                            Health check: <a href="/api/health" target="_blank" class="text-indigo-400 hover:underline font-mono">/api/health</a> (Dùng cho UptimeRobot)
                        </p>
                    </div>

                    <div class="bg-slate-900/80 border border-slate-700/80 rounded-xl p-3 sm:p-4">
                        <div class="text-xs text-slate-400 mb-1">BACKGROUND SCHEDULER</div>
                        <div id="ops-sched-status" class="text-sm sm:text-base font-bold text-emerald-400 flex items-center gap-2">
                            <i class="fa-solid fa-clock-rotate-left"></i> Đang Chạy Ngầm
                        </div>
                        <p id="ops-last-crawl" class="text-[11px] text-slate-400 mt-2">Lần cào gần nhất: Chưa ghi nhận</p>
                    </div>

                    <div class="bg-slate-900/80 border border-slate-700/80 rounded-xl p-3 sm:p-4 sm:col-span-2 md:col-span-1">
                        <div class="text-xs text-slate-400 mb-1">BÁO CÁO HÀNG NGÀY</div>
                        <div id="ops-report-time-display" class="text-sm sm:text-base font-bold text-amber-400 flex items-center gap-2">
                            <i class="fa-solid fa-newspaper"></i> 07:00 Sáng
                        </div>
                        <p id="ops-last-report" class="text-[11px] text-slate-400 mt-2">Báo cáo gần nhất: Chưa gửi</p>
                    </div>
                </div>

                <!-- Cấu hình Telegram & Lịch trình -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
                    <!-- Cột trái: Kênh Cảnh Báo Telegram & Webhook -->
                    <div class="bg-slate-900/60 border border-slate-700/80 rounded-xl p-3.5 sm:p-5 space-y-3 sm:space-y-4">
                        <h4 class="font-bold text-sm text-white flex items-center gap-2">
                            <i class="fa-brands fa-telegram text-sky-400 text-base"></i> Cảnh Báo Khẩn Cấp & Báo Cáo (Telegram)
                        </h4>
                        <p class="text-xs text-slate-300 leading-relaxed">
                            Nhận thông báo khẩn cấp ngay khi có lỗi (Facebook checkpoint, hết cookie NotebookLM...) và nhận Báo cáo tổng kết 24h mỗi sáng.
                        </p>

                        <div class="space-y-3">
                            <div>
                                <label class="block text-xs text-slate-400 mb-1 font-medium">Telegram Bot Token:</label>
                                <input type="password" id="cfg-telegram-token" placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                                    class="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-500 font-mono">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-400 mb-1 font-medium">Telegram Chat ID (ID của bạn hoặc Group):</label>
                                <input type="text" id="cfg-telegram-chat-id" placeholder="-100123456789 hoặc 987654321"
                                    class="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-500 font-mono">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-400 mb-1 font-medium">Discord Webhook URL (Tùy chọn):</label>
                                <input type="text" id="cfg-discord-webhook" placeholder="https://discord.com/api/webhooks/..."
                                    class="w-full px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono">
                            </div>
                        </div>

                        <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 pt-2">
                            <button onclick="testTelegramConnection()" id="btn-test-tg" class="bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold px-4 py-2.5 sm:py-2 rounded-lg transition flex items-center justify-center gap-1.5 shadow active:scale-95">
                                <i class="fa-solid fa-paper-plane"></i> Gửi Thử Tin Nhắn
                            </button>
                            <span id="test-tg-result" class="text-xs text-slate-400"></span>
                        </div>

                        <div class="bg-slate-950/70 border border-slate-800 rounded-lg p-3 text-[11px] text-slate-400 space-y-1">
                            <div class="font-semibold text-slate-300 flex items-center gap-1">
                                <i class="fa-solid fa-circle-info text-sky-400"></i> Hướng dẫn lấy Token & Chat ID nhanh:
                            </div>
                            <div>1. Mở Telegram tìm <code>@BotFather</code> &rarr; gửi <code>/newbot</code> để nhận <strong>Token</strong>.</div>
                            <div>2. Mở Telegram tìm <code>@userinfobot</code> &rarr; bấm <code>/start</code> để nhận <strong>Chat ID</strong>.</div>
                        </div>
                    </div>

                    <!-- Cột phải: Lịch Trình Tự Động -->
                    <div class="bg-slate-900/60 border border-slate-700/80 rounded-xl p-3.5 sm:p-5 space-y-3 sm:space-y-4 flex flex-col justify-between">
                        <div class="space-y-4">
                            <h4 class="font-bold text-sm text-white flex items-center gap-2">
                                <i class="fa-solid fa-sliders text-emerald-400 text-base"></i> Thiết Lập Tự Động Hóa (Automation)
                            </h4>

                            <div class="space-y-3">
                                <div class="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                                    <div>
                                        <div class="text-xs font-semibold text-white">Tự Động Cào Định Kỳ (Continuous Crawl)</div>
                                        <div class="text-[11px] text-slate-400">Tự động duyệt video từ các kênh đã đăng ký</div>
                                    </div>
                                    <input type="checkbox" id="cfg-auto-crawl" class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-700 rounded focus:ring-emerald-500">
                                </div>

                                <div class="grid grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-xs text-slate-400 mb-1">Chu kỳ cào lặp lại:</label>
                                        <select id="cfg-crawl-interval" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                                            <option value="3">Mỗi 3 giờ</option>
                                            <option value="6" selected>Mỗi 6 giờ</option>
                                            <option value="12">Mỗi 12 giờ</option>
                                            <option value="24">Mỗi 24 giờ</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-xs text-slate-400 mb-1">Giới hạn video/kênh:</label>
                                        <select id="cfg-crawl-limit" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                                            <option value="2">2 video</option>
                                            <option value="3" selected>3 video</option>
                                            <option value="5">5 video</option>
                                        </select>
                                    </div>
                                </div>

                                <div class="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                                    <div>
                                        <div class="text-xs font-semibold text-white">Báo Cáo Định Kỳ Hàng Ngày (Daily Digest)</div>
                                        <div class="text-[11px] text-slate-400">Tổng hợp kết quả 24h & bắn tin Telegram</div>
                                    </div>
                                    <input type="checkbox" id="cfg-daily-report" class="w-4 h-4 text-amber-600 bg-slate-900 border-slate-700 rounded focus:ring-amber-500">
                                </div>

                                <div>
                                    <label class="block text-xs text-slate-400 mb-1">Giờ phát hành Báo cáo (Giờ server):</label>
                                    <input type="time" id="cfg-daily-time" value="07:00" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                                </div>
                            </div>
                        </div>

                        <div class="pt-3 sm:pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 sm:gap-0">
                            <button onclick="triggerDailyReportNow()" id="btn-trigger-digest" class="bg-amber-600/90 hover:bg-amber-500 text-white text-xs font-semibold px-3.5 py-2.5 sm:py-2 rounded-lg transition flex items-center justify-center gap-1.5 shadow active:scale-95">
                                <i class="fa-solid fa-paper-plane"></i> Gửi Báo Cáo Ngay
                            </button>
                            <button onclick="saveSettings()" id="btn-save-settings" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-5 py-2.5 sm:py-2 rounded-lg transition flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-600/20 active:scale-95">
                                <i class="fa-solid fa-floppy-disk"></i> Lưu Cấu Hình Vận Hành
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Activity / Live Log Section -->
        <div id="log-card" class="bg-slate-950 border border-slate-800 rounded-2xl p-3.5 sm:p-5 shadow-xl">
            <div class="flex items-center justify-between mb-2 sm:mb-3">
                <div class="flex items-center gap-2">
                    <span id="log-dot" class="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full bg-emerald-500"></span>
                    <h3 class="font-semibold text-xs sm:text-sm text-white">Live Logs</h3>
                </div>
                <span id="log-status" class="text-[11px] sm:text-xs text-slate-400">Sẵn sàng</span>
            </div>
            <div id="log-content" class="bg-slate-900/90 rounded-xl p-3 sm:p-4 font-mono text-[11px] sm:text-xs text-slate-300 h-36 sm:h-48 overflow-y-auto space-y-1">
                <div>[INFO] Hệ thống sẵn sàng cào video...</div>
            </div>
        </div>

        <!-- Catalog Section -->
        <div class="space-y-3 sm:space-y-4">
            <div class="flex items-center justify-between">
                <h2 class="text-base sm:text-xl font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-boxes-stacked text-blue-500"></i> Kho Repo (<span id="repo-count">0</span>)
                </h2>
                <button onclick="loadCatalog()" class="text-xs sm:text-sm text-slate-400 hover:text-white flex items-center gap-1 active:scale-95">
                    <i class="fa-solid fa-rotate"></i> Làm mới
                </button>
            </div>

            <div id="catalog-container" class="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4"></div>
        </div>
    </main>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(el => {
                el.classList.remove('text-blue-400', 'border-b-2', 'border-blue-500', 'font-semibold');
                el.classList.add('text-slate-400', 'font-medium');
            });
            document.getElementById(tabId).classList.remove('hidden');
            const activeBtn = document.getElementById('btn-' + tabId);
            activeBtn.classList.add('text-blue-400', 'border-b-2', 'border-blue-500', 'font-semibold');
            activeBtn.classList.remove('text-slate-400', 'font-medium');
            if (tabId === 'ideas-tab') {
                loadChatHistory();
                setTimeout(scrollChatToBottom, 100);
            }
            if (tabId === 'ops-tab') {
                loadSettings();
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                const logs = await res.json();
                const box = document.getElementById('log-content');
                box.innerHTML = '';
                logs.forEach(msg => {
                    const row = document.createElement('div');
                    row.textContent = msg;
                    box.appendChild(row);
                });
                box.scrollTop = box.scrollHeight;
            } catch (e) {}
        }

        async function loadCatalog() {
            try {
                const res = await fetch('/api/catalog');
                const data = await res.json();
                document.getElementById('repo-count').textContent = data.length;
                const container = document.getElementById('catalog-container');
                container.innerHTML = '';

                data.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'bg-slate-800/50 border border-slate-700/60 rounded-xl p-3.5 sm:p-5 hover:border-blue-500/50 transition flex flex-col justify-between';
                    const syncBadge = item.synced_to_notebooklm ? 
                        '<span class="text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">NLM ✓</span>' :
                        '<span class="text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded bg-slate-700 text-slate-300">Local</span>';

                    const catBadge = item.category ? 
                        `<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 font-medium">${item.category}</span>` : '';

                    const tagsHtml = (item.tags || []).map(t => `<span class="text-[10px] bg-slate-900 border border-slate-700 text-slate-400 px-1.5 py-0.5 rounded">${t}</span>`).join(' ');

                    const aiSummary = item.summary ? 
                        `<div class="bg-slate-900/60 rounded-lg p-2 sm:p-2.5 my-2 border border-slate-700/40">
                            <div class="text-[10px] font-semibold text-amber-300 mb-1 flex items-center gap-1">
                                <i class="fa-solid fa-robot"></i> AI:
                            </div>
                            <p class="text-[11px] sm:text-xs text-slate-300 leading-relaxed line-clamp-3">${item.summary}</p>
                         </div>` : `<p class="text-[11px] sm:text-xs text-slate-400 my-2 line-clamp-2">${item.description || 'Không có mô tả'}</p>`;

                    card.innerHTML = `
                        <div>
                            <div class="flex items-start justify-between gap-2 mb-1.5">
                                <a href="${item.repo_url}" target="_blank" class="font-bold text-blue-400 hover:underline flex items-center gap-1.5 text-sm sm:text-base truncate">
                                    <i class="fa-brands fa-github shrink-0"></i> ${item.full_name}
                                </a>
                                ${syncBadge}
                            </div>
                            <div class="flex flex-wrap items-center gap-1.5 mb-1">
                                ${catBadge}
                                ${tagsHtml}
                            </div>
                            ${aiSummary}
                        </div>
                        <div class="flex items-center justify-between text-xs text-slate-400 border-t border-slate-700/50 pt-3 mt-2">
                            <div class="flex items-center gap-3">
                                <span><i class="fa-solid fa-star text-amber-400"></i> ${Number(item.stars).toLocaleString()}</span>
                                <span><i class="fa-solid fa-code text-blue-400"></i> ${item.language || 'N/A'}</span>
                            </div>
                            <span class="text-slate-500">${item.created_at ? item.created_at.slice(0, 10) : ''}</span>
                        </div>
                    `;
                    container.appendChild(card);
                });
                populateRepoCheckboxes(data);
            } catch (e) {
                console.error(e);
            }
        }

        async function loadChannels() {
            try {
                const res = await fetch('/api/channels');
                const data = await res.json();
                const container = document.getElementById('channels-list');
                container.innerHTML = '';
                data.forEach(ch => {
                    const row = document.createElement('div');
                    row.className = 'flex flex-col sm:flex-row sm:items-center justify-between bg-slate-900/60 border border-slate-700/60 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl text-sm gap-2';
                    row.innerHTML = `
                        <div class="flex items-center gap-3 min-w-0">
                            <i class="fa-brands fa-facebook text-blue-400 text-lg shrink-0"></i>
                            <div class="min-w-0">
                                <div class="font-medium text-white text-sm truncate">${ch.name}</div>
                                <a href="${ch.url}" target="_blank" class="text-[11px] sm:text-xs text-slate-400 hover:text-blue-400 truncate block">${ch.url}</a>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 self-end sm:self-auto shrink-0">
                            <button onclick="crawlSpecificPage('${ch.url}')" class="text-xs bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 px-3 py-1.5 rounded-lg transition active:scale-95">
                                <i class="fa-solid fa-play"></i> Quét
                            </button>
                            <button onclick="deleteChannel('${ch.url}', '${ch.name}')" class="text-xs bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 px-3 py-1.5 rounded-lg transition active:scale-95">
                                <i class="fa-solid fa-trash"></i> Xóa
                            </button>
                        </div>
                    `;
                    container.appendChild(row);
                });
            } catch (e) {}
        }

        async function deleteChannel(url, name) {
            if (!confirm(`Bạn có chắc muốn xóa kênh "${name}" khỏi danh sách theo dõi?`)) return;
            try {
                await fetch('/api/delete-channel', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url })
                });
                loadChannels();
            } catch (e) {
                alert('Lỗi khi xóa kênh: ' + e.message);
            }
        }

        async function startCrawlPage() {
            const url = document.getElementById('page-url').value.trim();
            const limit = document.getElementById('page-limit').value;
            if (!url) {
                alert('Vui lòng nhập link Fanpage hoặc Profile Facebook!');
                return;
            }
            
            document.getElementById('log-dot').className = 'w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse';
            document.getElementById('log-status').textContent = 'Đang chạy cào ngầm...';

            try {
                await fetch('/api/crawl-page', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url, limit: parseInt(limit) })
                });
            } catch (e) {
                console.error(e);
            }
        }

        function crawlSpecificPage(url) {
            document.getElementById('page-url').value = url;
            switchTab('page-tab');
            startCrawlPage();
        }

        async function startHarvestSingle() {
            const url = document.getElementById('single-url').value.trim();
            const text = document.getElementById('single-text').value.trim();
            if (!url && !text) {
                alert('Vui lòng nhập link video hoặc đoạn text mô tả!');
                return;
            }

            document.getElementById('log-dot').className = 'w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse';
            document.getElementById('log-status').textContent = 'Đang phân tích...';

            try {
                await fetch('/api/harvest-single', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url, text })
                });
            } catch (e) {}
        }

        async function addNewChannel() {
            const url = document.getElementById('new-ch-url').value.trim();
            const name = document.getElementById('new-ch-name').value.trim();
            if (!url) return;
            await fetch('/api/add-channel', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ url, name })
            });
            document.getElementById('new-ch-url').value = '';
            document.getElementById('new-ch-name').value = '';
            loadChannels();
        }

        async function loginNotebookLM() {
            const btn = document.getElementById('btn-login-nlm');
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang mở Chrome...';
            btn.disabled = true;
            try {
                const res = await fetch('/api/login-nlm', { method: 'POST' });
                const data = await res.json();
                alert(data.message || 'Trình duyệt Chrome đang được mở để đăng nhập Google NotebookLM.');
            } catch (e) {
                alert('Lỗi: ' + e.message);
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    checkStatus();
                }, 3000);
            }
        }

        async function crawlAllChannels() {
            const limit = document.getElementById('crawl-all-limit').value;
            document.getElementById('log-dot').className = 'w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse';
            document.getElementById('log-status').textContent = 'Đang quét tất cả kênh (' + limit + ' video/kênh)...';
            try {
                await fetch('/api/crawl-all', { 
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ limit: parseInt(limit) })
                });
            } catch (e) {}
        }

        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const badge = document.getElementById('auth-badge');
                const btn = document.getElementById('btn-login-nlm');
                if (data.notebooklm_authenticated) {
                    badge.className = 'px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5';
                    badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400"></span> NotebookLM: Đã kết nối';
                    if (btn) {
                        btn.className = 'bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium px-3 py-1 rounded-lg border border-slate-700 flex items-center gap-1.5 transition';
                        btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Đổi Tài Khoản';
                    }
                } else {
                    badge.className = 'px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1.5';
                    badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-slate-500"></span> NotebookLM: Chưa login';
                    if (btn) {
                        btn.className = 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold px-3.5 py-1.5 rounded-lg shadow-md shadow-blue-500/20 flex items-center gap-1.5 transition';
                        btn.innerHTML = '<i class="fa-solid fa-arrow-right-to-bracket"></i> Đăng Nhập NotebookLM';
                    }
                }
            } catch (e) {}
        }

        // Tự động kéo logs và cập nhật catalog mỗi 2 giây
        setInterval(() => {
            fetchLogs();
            loadCatalog();
        }, 2000);

        function populateRepoCheckboxes(repos) {
            const list = document.getElementById('repo-checkbox-list');
            if (!list || list.children.length > 0) return;
            list.innerHTML = '';
            repos.forEach(r => {
                const item = document.createElement('label');
                item.className = 'flex items-center gap-2 text-slate-300 hover:text-white cursor-pointer py-0.5';
                item.innerHTML = `<input type="checkbox" name="selected_repo" value="${r.full_name}" class="rounded bg-slate-800 border-slate-700 text-emerald-500 focus:ring-0"> <span class="truncate">${r.full_name}</span>`;
                list.appendChild(item);
            });
        }

        // ==================== CHATBOX CO-IDEATION ====================
        let isChatWaiting = false;

        async function loadChatHistory() {
            try {
                const res = await fetch('/api/chat/history');
                const history = await res.json();
                const container = document.getElementById('chat-messages');
                container.innerHTML = '';

                if (!history || history.length === 0) {
                    renderWelcomeMessage();
                    return;
                }

                history.forEach(item => {
                    renderMessageBubble(item.role, item.content, item.tool_calls);
                });
                scrollChatToBottom();
            } catch (e) {
                console.error('Error loading chat history:', e);
            }
        }

        function renderWelcomeMessage() {
            const container = document.getElementById('chat-messages');
            container.innerHTML = `
                <div class="flex items-start gap-3">
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white text-xs shrink-0 shadow">
                        <i class="fa-solid fa-wand-magic-sparkles"></i>
                    </div>
                    <div class="max-w-[85%] bg-slate-800/90 border border-slate-700/80 rounded-2xl rounded-tl-none p-4 text-xs text-slate-200 shadow-md">
                        <div class="font-semibold text-amber-300 mb-1 flex items-center gap-1.5">
                            <span>Co-Ideation Partner</span>
                            <span class="text-[10px] text-slate-400 font-normal">vừa xong</span>
                        </div>
                        <p class="leading-relaxed">
                            Chào bạn! Tôi là Cộng Sự Đồng Sáng Tạo Ý Tưởng của bạn. Tôi có khả năng tra cứu toàn bộ <strong>29+ repositories mã nguồn mở</strong> trong kho, truy vấn sâu tài liệu <strong>Google NotebookLM</strong>, phân tích tính khả thi kỹ thuật, vẽ <strong>sơ đồ kiến trúc Mermaid</strong> và viết <strong>PoC Glue Code</strong> thực chiến.
                        </p>
                        <p class="mt-2 text-slate-300 leading-relaxed">
                            Bạn đang ấp ủ bài toán nào, hay muốn kết hợp những công nghệ gì? Hãy chia sẻ với tôi hoặc chọn các gợi ý bên dưới để cùng bắt đầu nhé!
                        </p>
                    </div>
                </div>
            `;
        }

        function scrollChatToBottom() {
            const container = document.getElementById('chat-messages');
            container.scrollTop = container.scrollHeight;
        }

        function renderMessageBubble(role, content, tool_calls = []) {
            const container = document.getElementById('chat-messages');
            const div = document.createElement('div');

            if (role === 'user') {
                div.className = 'flex items-start justify-end gap-3';
                div.innerHTML = `
                    <div class="max-w-[80%] bg-indigo-600 text-white rounded-2xl rounded-tr-none p-3.5 text-xs shadow-md leading-relaxed whitespace-pre-wrap">
                        ${content.replace(/</g, "&lt;").replace(/>/g, "&gt;")}
                    </div>
                    <div class="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center text-slate-200 text-xs shrink-0 shadow">
                        <i class="fa-solid fa-user"></i>
                    </div>
                `;
            } else {
                div.className = 'flex items-start gap-3';
                let toolBadges = '';
                if (tool_calls && tool_calls.length > 0) {
                    toolBadges = '<div class="flex flex-wrap gap-1.5 mb-2.5 pb-2 border-b border-slate-700/60">';
                    tool_calls.forEach(tc => {
                        let icon = 'fa-gear';
                        let label = tc.tool;
                        if (tc.tool === 'lookup_catalog') { icon = 'fa-magnifying-glass'; label = 'Tra cứu 29 Repos'; }
                        else if (tc.tool === 'query_notebook_deep') { icon = 'fa-book-bookmark'; label = 'Truy vấn NotebookLM'; }
                        else if (tc.tool === 'check_synergy_feasibility') { icon = 'fa-link'; label = 'Khảo sát tương hỗ'; }
                        else if (tc.tool === 'generate_architecture_diagram') { icon = 'fa-sitemap'; label = 'Sơ đồ kiến trúc'; }
                        else if (tc.tool === 'generate_glue_code') { icon = 'fa-code'; label = 'Sinh PoC Glue Code'; }
                        else if (tc.tool === 'save_ideation_spec') { icon = 'fa-floppy-disk'; label = 'Lưu ý tưởng vào kho'; }

                        toolBadges += `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-950/70 border border-indigo-700/50 text-[10px] text-indigo-300 font-mono"><i class="fa-solid ${icon}"></i> ${label}</span>`;
                    });
                    toolBadges += '</div>';
                }

                const parsedHtml = (typeof marked !== 'undefined' && marked.parse) ? marked.parse(content) : content;
                div.innerHTML = `
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white text-xs shrink-0 shadow">
                        <i class="fa-solid fa-wand-magic-sparkles"></i>
                    </div>
                    <div class="max-w-[85%] bg-slate-800/90 border border-slate-700/80 rounded-2xl rounded-tl-none p-4 text-xs text-slate-200 shadow-md">
                        <div class="font-semibold text-amber-300 mb-1.5 flex items-center gap-1.5">
                            <span>Co-Ideation Partner</span>
                            <span class="text-[10px] text-slate-400 font-normal">vừa xong</span>
                        </div>
                        ${toolBadges}
                        <div class="prose-dark leading-relaxed">${parsedHtml}</div>
                    </div>
                `;
            }

            container.appendChild(div);
            scrollChatToBottom();
        }

        async function sendChatMessage(customText) {
            if (isChatWaiting) return;
            const input = document.getElementById('chat-input');
            const message = (customText || input.value).trim();
            if (!message) return;

            input.value = '';
            renderMessageBubble('user', message);

            const indicator = document.getElementById('chat-tool-indicator');
            const indicatorText = document.getElementById('chat-tool-text');
            const sendBtn = document.getElementById('btn-chat-send');

            indicator.classList.remove('hidden');
            indicatorText.textContent = '🧠 Google NotebookLM đang tra cứu & phân tích 65 tài liệu kỹ thuật...';
            sendBtn.disabled = true;
            sendBtn.classList.add('opacity-50');
            isChatWaiting = true;

            try {
                const res = await fetch('/api/chat/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message })
                });
                const data = await res.json();
                if (data.reply) {
                    renderMessageBubble('assistant', data.reply, data.tool_calls || []);
                    loadIdeasCatalog(); // Cập nhật catalog phòng trường hợp đã lưu ý tưởng
                } else if (data.error) {
                    renderMessageBubble('assistant', '⚠️ Lỗi: ' + data.error);
                }
            } catch (e) {
                renderMessageBubble('assistant', '⚠️ Lỗi kết nối máy chủ: ' + e.message);
            } finally {
                indicator.classList.add('hidden');
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50');
                isChatWaiting = false;
                scrollChatToBottom();
            }
        }

        function sendPromptSuggestion(btn) {
            const rawText = btn.innerText.trim();
            const cleanText = rawText.replace(/^[^\w\s\u00C0-\u1EF9]+/, '').trim();
            sendChatMessage(cleanText);
        }

        async function resetChat() {
            if (!confirm('Bạn có chắc muốn làm mới phiên hội thoại?')) return;
            try {
                await fetch('/api/chat/reset', { method: 'POST' });
                renderWelcomeMessage();
            } catch (e) {
                console.error(e);
            }
        }

        async function triggerStudio(type) {
            const label = type === 'audio' ? 'Podcast Audio Overview' : 'Briefing Doc';
            if (!confirm(`Bạn có muốn yêu cầu Google NotebookLM Studio tạo ${label} cho kho tri thức không?`)) return;
            renderMessageBubble('assistant', `⏳ Đang kích hoạt NotebookLM Studio để tạo **${label}**... Tiến trình đang được gửi lên máy chủ Google.`);
            scrollChatToBottom();
            try {
                const res = await fetch('/api/chat/studio', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ type: type, title: `${label} - Tech Repositories` })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    renderMessageBubble('assistant', `✅ Đã gửi yêu cầu thành công! Google NotebookLM Studio đang tạo **${label}**. Bạn có thể truy cập trực tiếp vào giao diện NotebookLM để nghe Podcast hoặc xem tài liệu.`);
                } else {
                    renderMessageBubble('assistant', `ℹ️ Phản hồi từ NotebookLM Studio: ${data.message || JSON.stringify(data)}`);
                }
            } catch (e) {
                renderMessageBubble('assistant', `⚠️ Lỗi gửi yêu cầu Studio: ${e.message}`);
            }
            scrollChatToBottom();
        }

        setTimeout(() => {
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendChatMessage();
                    }
                });
            }
        }, 500);

        async function loadIdeasCatalog() {
            try {
                const res = await fetch('/api/ideas');
                const ideas = await res.json();
                document.getElementById('ideas-count').textContent = ideas.length;
                const grid = document.getElementById('ideas-catalog-grid');
                grid.innerHTML = '';

                ideas.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'bg-slate-900/70 border border-slate-800 hover:border-indigo-500/50 rounded-xl p-4 transition flex flex-col justify-between';
                    const reposBadges = (item.source_repos || []).map(r => `<span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">${r.split('/').pop()}</span>`).join(' + ');

                    card.innerHTML = `
                        <div>
                            <div class="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                                <span>${item.created_at || ''}</span>
                                <span class="uppercase text-amber-400 font-semibold tracking-wider text-[9px]">${item.mode || 'synergy'}</span>
                            </div>
                            <h5 class="font-bold text-sm text-white hover:text-indigo-400 transition cursor-pointer" onclick="viewIdeaDetail('${item.file_path}')">${item.title}</h5>
                            <p class="text-xs text-slate-400 my-1.5 line-clamp-2">${item.tagline || ''}</p>
                            <div class="flex flex-wrap gap-1 mt-2 text-xs">${reposBadges}</div>
                        </div>
                        <div class="mt-3 pt-2 border-t border-slate-800/80 flex justify-end">
                            <button onclick="viewIdeaDetail('${item.file_path}')" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1">
                                Xem chi tiết <i class="fa-solid fa-arrow-right"></i>
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                });
            } catch (e) {}
        }

        async function viewIdeaDetail(filePath) {
            try {
                const res = await fetch('/api/idea-file?path=' + encodeURIComponent(filePath));
                const data = await res.json();
                if (data.content) {
                    alert(data.content);
                }
            } catch (e) {}
        }

        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const cfg = await res.json();
                document.getElementById('cfg-telegram-token').value = cfg.telegram_bot_token || '';
                document.getElementById('cfg-telegram-chat-id').value = cfg.telegram_chat_id || '';
                document.getElementById('cfg-discord-webhook').value = cfg.discord_webhook_url || '';
                document.getElementById('cfg-auto-crawl').checked = cfg.auto_crawl_enabled !== false;
                document.getElementById('cfg-crawl-interval').value = cfg.crawl_interval_hours || 6;
                document.getElementById('cfg-crawl-limit').value = cfg.crawl_limit_per_channel || 3;
                document.getElementById('cfg-daily-report').checked = cfg.daily_report_enabled !== false;
                document.getElementById('cfg-daily-time').value = cfg.daily_report_time || '07:00';
                
                document.getElementById('ops-report-time-display').innerHTML = `<i class="fa-solid fa-newspaper"></i> ${cfg.daily_report_time || '07:00'} Sáng`;
                if (cfg.last_crawl_time) {
                    const dt = new Date(cfg.last_crawl_time);
                    document.getElementById('ops-last-crawl').textContent = 'Lần cào gần nhất: ' + dt.toLocaleString('vi-VN');
                }
                if (cfg.last_report_date) {
                    document.getElementById('ops-last-report').textContent = 'Báo cáo gần nhất: ' + cfg.last_report_date;
                }
            } catch (e) {
                console.error('Lỗi load settings:', e);
            }
        }

        async function saveSettings() {
            const btn = document.getElementById('btn-save-settings');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
            btn.disabled = true;

            const payload = {
                telegram_bot_token: document.getElementById('cfg-telegram-token').value.trim(),
                telegram_chat_id: document.getElementById('cfg-telegram-chat-id').value.trim(),
                discord_webhook_url: document.getElementById('cfg-discord-webhook').value.trim(),
                auto_crawl_enabled: document.getElementById('cfg-auto-crawl').checked,
                crawl_interval_hours: parseInt(document.getElementById('cfg-crawl-interval').value),
                crawl_limit_per_channel: parseInt(document.getElementById('cfg-crawl-limit').value),
                daily_report_enabled: document.getElementById('cfg-daily-report').checked,
                daily_report_time: document.getElementById('cfg-daily-time').value
            };

            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                alert('✅ Đã lưu cấu hình vận hành thành công!');
                loadSettings();
            } catch (e) {
                alert('❌ Lỗi khi lưu cấu hình: ' + e.message);
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        async function testTelegramConnection() {
            const btn = document.getElementById('btn-test-tg');
            const resSpan = document.getElementById('test-tg-result');
            btn.disabled = true;
            resSpan.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-sky-400"></i> Đang gửi...';

            try {
                // Tự động lưu cấu hình trước khi gửi kiểm tra
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        telegram_bot_token: document.getElementById('cfg-telegram-token').value.trim(),
                        telegram_chat_id: document.getElementById('cfg-telegram-chat-id').value.trim()
                    })
                });

                const res = await fetch('/api/test-telegram', { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    resSpan.innerHTML = '<span class="text-emerald-400 font-medium">✅ Gửi thành công! Hãy kiểm tra Telegram của bạn.</span>';
                } else {
                    resSpan.innerHTML = `<span class="text-rose-400">❌ Thất bại: ${data.error || 'Kiểm tra token/chat_id'}</span>`;
                }
            } catch (e) {
                resSpan.innerHTML = `<span class="text-rose-400">❌ Lỗi: ${e.message}</span>`;
            } finally {
                btn.disabled = false;
            }
        }

        async function triggerDailyReportNow() {
            const btn = document.getElementById('btn-trigger-digest');
            btn.disabled = true;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang gửi...';

            try {
                const res = await fetch('/api/trigger-daily-report', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    alert('✅ Đã tổng hợp và gửi Báo Cáo Hàng Ngày tới Telegram thành công!');
                    loadSettings();
                } else {
                    alert('⚠️ Lỗi gửi báo cáo: ' + (data.error || JSON.stringify(data)));
                }
            } catch (e) {
                alert('❌ Lỗi kết nối: ' + e.message);
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        loadCatalog();
        loadChannels();
        checkStatus();
        fetchLogs();
        loadIdeasCatalog();
        loadChatHistory();
        loadSettings();
    </script>
</body>
</html>
"""

def background_crawl_page(url: str, limit: int):
    add_log(f"Bắt đầu mở trình duyệt cào video từ Page: {url} (Giới hạn {limit} video)...")
    crawler = PageCrawler(BASE_DIR)
    videos = crawler.fetch_videos_from_page(url, limit=limit)
    if not videos:
        add_log(f"Không tìm thấy video nào từ {url} (hoặc trang yêu cầu đăng nhập).")
        return

    add_log(f"Tìm thấy {len(videos)} video từ page. Bắt đầu phân tích từng video...")
    for idx, v in enumerate(videos, 1):
        add_log(f"[{idx}/{len(videos)}] Xử lý: {v['url']} ({v.get('title', '')[:40]})")
        try:
            process_single_item(url=v["url"], text=v.get("title", ""), skip_clone=True)
            add_log(f"Hoàn tất xử lý video {idx}/{len(videos)}.")
        except Exception as e:
            add_log(f"Lỗi khi xử lý video: {e}")
    add_log(f"Đã hoàn thành toàn bộ đợt quét cho {url}!")

def background_harvest_single(url: str, text: str):
    add_log(f"Đang bóc tách và phân tích: {url or text[:40]} ...")
    try:
        ok = process_single_item(url=url, text=text, skip_clone=True)
        if ok:
            add_log("Thu hoạch thành công và đã nạp vào kho!")
        else:
            add_log("Không tìm thấy repo phù hợp.")
    except Exception as e:
        add_log(f"Lỗi: {e}")

class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif path == "/api/catalog":
            catalog = CatalogManager(BASE_DIR)
            self._send_json(catalog.load_data())
        elif path == "/api/channels":
            crawler = PageCrawler(BASE_DIR)
            self._send_json(crawler.load_channels())
        elif path == "/api/logs":
            self._send_json(LOGS_QUEUE)
        elif path == "/api/status":
            self._send_json({"notebooklm_authenticated": get_cached_auth_status()})
        elif path == "/api/ideas":
            engine = IdeaEngine(BASE_DIR)
            self._send_json(engine.load_ideas())
        elif path == "/api/chat/history":
            self._send_json(chat_agent.get_history())
        elif path == "/api/chat/studio-status":
            self._send_json(chat_agent.get_studio_status())
        elif path == "/api/idea-file":
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            file_rel = query_params.get("path", [""])[0]
            if file_rel and ".." not in file_rel:
                file_path = BASE_DIR / file_rel
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        self._send_json({"content": f.read()})
                        return
            self._send_json({"error": "Không tìm thấy file"}, status=404)
        elif path == "/api/health":
            catalog = CatalogManager(BASE_DIR)
            self._send_json({
                "status": "healthy",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "notebooklm_authenticated": get_cached_auth_status(),
                "total_repos": len(catalog.load_data()),
                "scheduler": scheduler.get_status()
            })
        elif path == "/api/settings":
            self._send_json(config_mgr.load())
        elif path == "/api/scheduler/status":
            self._send_json(scheduler.get_status())
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if path == "/api/crawl-page":
            url = body.get("url", "")
            limit = int(body.get("limit", 5))
            if not url:
                self._send_json({"error": "Thiếu URL"}, status=400)
                return
            
            # Khởi chạy trong background thread -> trả về ngay 200 OK cho browser!
            t = threading.Thread(target=background_crawl_page, args=(url, limit))
            t.daemon = True
            t.start()
            self._send_json({"status": "started", "message": f"Đang cào ngầm: {url}"})

        elif path == "/api/harvest-single":
            url = body.get("url", "")
            text = body.get("text", "")
            t = threading.Thread(target=background_harvest_single, args=(url, text))
            t.daemon = True
            t.start()
            self._send_json({"status": "started", "message": "Đang xử lý trong nền..."})

        elif path == "/api/add-channel":
            crawler = PageCrawler(BASE_DIR)
            url = body.get("url", "")
            name = body.get("name", "")
            crawler.add_channel(url, name=name)
            self._send_json({"message": "Đã thêm kênh"})

        elif path == "/api/delete-channel":
            crawler = PageCrawler(BASE_DIR)
            url = body.get("url", "")
            ok = crawler.delete_channel(url)
            self._send_json({"message": "Đã xóa kênh" if ok else "Không tìm thấy kênh"})

        elif path == "/api/login-nlm":
            sync_engine = NotebookSyncEngine()
            def nlm_login_worker():
                add_log("Đang mở trình duyệt để đăng nhập Google NotebookLM...")
                try:
                    import subprocess
                    subprocess.run([sync_engine.nlm_exe, "login"], check=False)
                    add_log("Đã hoàn tất tiến trình đăng nhập NotebookLM!")
                except Exception as e:
                    add_log(f"Lỗi khi chạy nlm login: {e}")
            t = threading.Thread(target=nlm_login_worker)
            t.daemon = True
            t.start()
            self._send_json({
                "status": "started",
                "message": "Đang mở cửa sổ trình duyệt Chrome để đăng nhập Google NotebookLM.\nBạn hãy hoàn tất đăng nhập trên Chrome nhé!"
            })

        elif path == "/api/crawl-all":
            crawler = PageCrawler(BASE_DIR)
            channels = crawler.load_channels()
            limit = int(body.get("limit", 3))
            def crawl_all_worker():
                add_log(f"Bắt đầu quét {len(channels)} kênh theo dõi (Mỗi kênh {limit} video)...")
                for ch in channels:
                    background_crawl_page(ch["url"], limit=limit)
                add_log(f"Đã hoàn thành quét toàn bộ {len(channels)} kênh!")
            t = threading.Thread(target=crawl_all_worker)
            t.daemon = True
            t.start()
            self._send_json({"status": "started", "message": f"Bắt đầu quét tất cả kênh ({limit} video/kênh)..."})

        elif path == "/api/generate-idea":
            mode = body.get("mode", "surprise")
            goal = body.get("goal", "")
            selected_repos = body.get("selected_repos", [])
            add_log(f"Bắt đầu lên ý tưởng kết hợp (Mode: {mode})...")
            try:
                engine = IdeaEngine(BASE_DIR)
                idea = engine.generate_idea(mode=mode, goal=goal, selected_repos=selected_repos)
                if "error" in idea:
                    self._send_json(idea, status=400)
                else:
                    add_log(f"Đã sinh ý tưởng: '{idea.get('title')}'")
                    self._send_json({"status": "success", "idea": idea})
            except Exception as e:
                add_log(f"Lỗi khi lên ý tưởng: {e}")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/chat/send":
            msg = body.get("message", "").strip()
            if not msg:
                self._send_json({"error": "Thiếu nội dung tin nhắn"}, status=400)
                return
            add_log(f"Chatbox Ideation: Nhận câu hỏi từ user: '{msg[:40]}...'")
            try:
                res = chat_agent.chat(msg)
                self._send_json(res)
            except Exception as e:
                add_log(f"Lỗi khi xử lý chat: {e}")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/chat/reset":
            history = chat_agent.reset_chat()
            add_log("Chatbox Ideation: Đã làm mới phiên hội thoại.")
            self._send_json({"status": "reset", "history": history})

        elif path == "/api/chat/studio":
            artifact_type = body.get("type", "report")
            report_format = body.get("format", "Briefing Doc")
            title = body.get("title", "Bản Tóm Lược Ý Tưởng")
            add_log(f"NotebookLM Studio: Đang kích hoạt tạo {artifact_type} ({title})...")
            try:
                res = chat_agent.create_studio_artifact(artifact_type=artifact_type, report_format=report_format, title=title)
                self._send_json(res)
            except Exception as e:
                add_log(f"Lỗi khi tạo studio artifact: {e}")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/settings":
            updated = config_mgr.save(body)
            add_log("Cấu hình vận hành hệ thống đã được cập nhật.")
            self._send_json({"status": "saved", "settings": updated})

        elif path == "/api/test-telegram":
            add_log("Đang gửi tin nhắn kiểm tra kết nối Telegram...")
            res = notifier.test_connection()
            if res.get("ok"):
                add_log("✅ Đã gửi thành công tin nhắn kiểm tra Telegram!")
            else:
                add_log(f"❌ Kiểm tra kết nối Telegram thất bại: {res.get('error')}")
            self._send_json(res)

        elif path == "/api/trigger-daily-report":
            add_log("Đang kích hoạt tổng hợp và phát hành Báo Cáo Định Kỳ theo yêu cầu...")
            res = scheduler.generate_and_send_daily_digest()
            self._send_json(res)

        else:
            self.send_error(404, "Not Found")

def start_server():
    # Khởi động background scheduler
    scheduler.start()
    server = ThreadedHTTPServer((HOST, PORT), RequestHandler)
    url = f"http://{HOST}:{PORT}"
    add_log(f"Máy chủ Threaded Web UI đang chạy tại: {url} (Port: {PORT})")
    server.serve_forever()

if __name__ == "__main__":
    start_server()
