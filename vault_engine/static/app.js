/**
 * Knowledge Vault v3.0 - UI Craftsman Client Application
 * Lucide Icons, Dual-Tab Smart Reader, Live Ingest Modal & FTS5 Instant Search
 */

(function () {
  "use strict";

  // Application State
  let currentItems = [];
  let currentCategory = "";
  let currentArchetype = "";
  let searchQuery = "";
  let onlyStarred = false;
  let minScore = 1;
  let activeItemId = null;
  let activeTab = "all"; // 'all' | 'brief' | 'reader' | 'network' | 'associations'
  let currentLang = "vi"; // 'vi' | 'en'
  let activeItemFullMd = "";
  let searchTimeout = null;
  let currentBrainMode = "APPROVED"; // 'APPROVED' | 'INBOX' | 'TOPICS' | 'HEURISTICS'

  // DOM Elements
  const gridContainer = document.getElementById("grid-container");
  const searchInput = document.getElementById("search-input");
  const categoryPills = document.getElementById("category-pills");
  const archetypeFilters = document.getElementById("archetype-filters");
  const filterStarred = document.getElementById("filter-starred");
  const filterScore = document.getElementById("filter-score");
  const scoreVal = document.getElementById("score-val");

  const statTotal = document.getElementById("stat-total");
  const statUnread = document.getElementById("stat-unread");
  const statStarred = document.getElementById("stat-starred");

  // Brain Mode Nav & Badges
  const brainModeNav = document.getElementById("brain-mode-nav");
  const badgeApproved = document.getElementById("badge-approved-count");
  const badgeInbox = document.getElementById("badge-inbox-count");
  const badgeTopics = document.getElementById("badge-topics-count");
  const badgeHeuristics = document.getElementById("badge-heuristics-count");
  const subFilterBar = document.getElementById("sub-filter-bar");
  const curationHint = document.getElementById("curation-hint");

  // Reader Drawer Elements
  const readerDrawer = document.getElementById("reader-drawer");
  const readerOverlay = document.getElementById("reader-overlay");
  const btnCloseDrawer = document.getElementById("btn-close-drawer");
  const drawerTitle = document.getElementById("drawer-title");
  const drawerCategory = document.getElementById("drawer-category");
  const drawerArchetype = document.getElementById("drawer-archetype");
  const drawerScore = document.getElementById("drawer-score");
  const drawerOrigLink = document.getElementById("drawer-orig-link");
  const drawerCurationActions = document.getElementById("drawer-curation-actions");
  const btnDrawerStar = document.getElementById("btn-drawer-star");
  const drawerTabs = document.getElementById("drawer-tabs");
  const btnLangVi = document.getElementById("btn-lang-vi");
  const btnLangEn = document.getElementById("btn-lang-en");
  const deepResearchContent = document.getElementById("deep-research-content");
  const autoToc = document.getElementById("auto-toc");
  const readingProgress = document.getElementById("reading-progress");

  // Ingest Modal Elements
  const btnOpenIngest = document.getElementById("btn-open-ingest");
  const ingestModal = document.getElementById("ingest-modal");
  const ingestOverlay = document.getElementById("ingest-overlay");
  const btnCloseIngestModal = document.getElementById("btn-close-ingest-modal");
  const btnCancelIngest = document.getElementById("btn-cancel-ingest");
  const ingestForm = document.getElementById("ingest-form");
  const ingestUrlInput = document.getElementById("ingest-url-input");
  const ingestStatusMsg = document.getElementById("ingest-status-msg");
  const btnSubmitIngest = document.getElementById("btn-submit-ingest");

  // Global Graph Modal Elements
  const btnOpenGlobalGraph = document.getElementById("btn-open-global-graph");
  const globalGraphModal = document.getElementById("global-graph-modal");
  const globalGraphOverlay = document.getElementById("global-graph-overlay");
  const btnCloseGlobalGraph = document.getElementById("btn-close-global-graph");
  const btnGlobalGraphFit = document.getElementById("btn-global-graph-fit");

  let activeVisNetwork = null;
  let activeGlobalNetwork = null;
  let isPhysicsActive = true;

  const toastContainer = document.getElementById("toast-container");

  // Initialize Mermaid
  if (window.mermaid) {
    window.mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      themeVariables: {
        darkMode: true,
        background: "#090c13",
        primaryColor: "#1e293b",
        primaryTextColor: "#f8fafc",
        primaryBorderColor: "#38bdf8",
        lineColor: "#64748b",
        secondaryColor: "#161e2e",
        tertiaryColor: "#0f172a"
      }
    });
  }

  // Setup Custom Marked Renderer for Mermaid & Highlight.js
  const renderer = new marked.Renderer();
  renderer.code = function ({ text, lang }) {
    const language = (lang || "").trim().toLowerCase();
    if (language === "mermaid") {
      return `<div class="mermaid-wrapper"><pre class="mermaid">${escapeHtml(text)}</pre></div>`;
    }
    const validLang = hljs.getLanguage(language) ? language : "plaintext";
    const highlighted = hljs.highlight(text, { language: validLang }).value;
    return `<pre><code class="hljs language-${validLang}">${highlighted}</code></pre>`;
  };

  marked.use({ renderer });

  // Init
  document.addEventListener("DOMContentLoaded", () => {
    initEvents();
    loadVaultStats();
    loadVaultItems();
    initKeyboardShortcuts();
    hydrateIcons();
  });

  function hydrateIcons() {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = "toast";
    let iconName = "check-circle-2";
    let iconColor = "text-cyan-400";
    if (type === "error") {
      iconName = "alert-circle";
      iconColor = "text-rose-400";
    } else if (type === "star") {
      iconName = "star";
      iconColor = "text-amber-400";
    }

    toast.innerHTML = `<i data-lucide="${iconName}" class="w-4 h-4 ${iconColor}"></i><span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);
    hydrateIcons();

    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 250);
    }, 2800);
  }

  function initKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      // Focus Search: Ctrl+K or /
      if ((e.ctrlKey && e.key.toLowerCase() === "k") || (e.key === "/" && document.activeElement !== searchInput && document.activeElement !== ingestUrlInput)) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
      // Escape closes drawer or modal
      if (e.key === "Escape") {
        if (globalGraphModal && !globalGraphModal.classList.contains("hidden")) {
          closeGlobalGraphModal();
        } else if (!ingestModal.classList.contains("hidden")) {
          closeIngestModal();
        } else if (readerDrawer.classList.contains("active")) {
          closeDrawer();
        }
      }
    });
  }

  function initEvents() {
    // Search with 250ms debounce
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchQuery = e.target.value.trim();
        loadVaultItems();
      }, 250);
    });

    // Category pills click
    categoryPills.addEventListener("click", (e) => {
      const btn = e.target.closest(".cat-pill");
      if (!btn) return;
      categoryPills.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      currentCategory = btn.dataset.cat || "";
      loadVaultItems();
    });

    // Archetype filter toggles
    archetypeFilters.addEventListener("click", (e) => {
      const btn = e.target.closest(".arch-toggle-btn");
      if (!btn) return;
      archetypeFilters.querySelectorAll(".arch-toggle-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentArchetype = btn.dataset.arch || "";
      renderGrid();
    });

    // Star filter toggle
    filterStarred.addEventListener("change", (e) => {
      onlyStarred = e.target.checked;
      loadVaultItems();
    });

    // Min score slider
    filterScore.addEventListener("input", (e) => {
      minScore = parseInt(e.target.value, 10);
      scoreVal.textContent = minScore;
    });
    filterScore.addEventListener("change", () => {
      loadVaultItems();
    });

    // Drawer Tabs switching
    drawerTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".drawer-tab");
      if (!btn) return;
      drawerTabs.querySelectorAll(".drawer-tab").forEach(t => t.classList.remove("active"));
      btn.classList.add("active");
      activeTab = btn.dataset.tab;
      renderActiveTabContent();
    });

    // Close Drawer events
    btnCloseDrawer.addEventListener("click", closeDrawer);
    readerOverlay.addEventListener("click", closeDrawer);

    // Drawer Star Toggle
    btnDrawerStar.addEventListener("click", async () => {
      if (!activeItemId) return;
      const item = currentItems.find(i => i.id === activeItemId);
      if (!item) return;
      const newStarred = !item.is_starred;
      await updateItemStatus(activeItemId, { is_starred: newStarred });
      item.is_starred = newStarred ? 1 : 0;
      updateDrawerStarUI(item.is_starred);
      renderGrid();
      loadVaultStats();
      showToast(newStarred ? "Đã gắn sao VIP ⭐" : "Đã hủy gắn sao VIP", "star");
    });

    // Brain Mode Nav Switcher
    if (brainModeNav) {
      brainModeNav.addEventListener("click", (e) => {
        const btn = e.target.closest(".brain-nav-btn");
        if (!btn) return;
        brainModeNav.querySelectorAll(".brain-nav-btn").forEach(b => {
          b.classList.remove("active", "text-white", "bg-gradient-to-r", "from-cyan-500/20", "to-indigo-500/20", "border-cyan-500/40");
          b.classList.add("text-slate-400", "border-transparent");
        });
        btn.classList.add("active", "text-white", "bg-gradient-to-r", "from-cyan-500/20", "to-indigo-500/20", "border-cyan-500/40");
        btn.classList.remove("text-slate-400", "border-transparent");

        currentBrainMode = btn.dataset.mode;
        if (currentBrainMode === "APPROVED") {
          if (subFilterBar) subFilterBar.style.display = "";
          if (curationHint) curationHint.innerHTML = '<span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span><span>Kho tri thức tinh hoa đã được tuyển chọn & củng cố nơ-ron</span>';
          loadVaultItems();
        } else if (currentBrainMode === "INBOX") {
          if (subFilterBar) subFilterBar.style.display = "";
          if (curationHint) curationHint.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span><span>Hộp thư chờ Kỹ sư trưởng đọc sơ khảo và duyệt vào Não Bộ</span>';
          loadVaultItems();
        } else if (currentBrainMode === "TOPICS") {
          if (subFilterBar) subFilterBar.style.display = "none";
          if (curationHint) curationHint.innerHTML = '<span class="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></span><span>Hồ Sơ Chuyên Đề Sống: Tự động tổng hợp & tiến hóa qua các bài duyệt</span>';
          loadBrainTopics();
        } else if (currentBrainMode === "HEURISTICS") {
          if (subFilterBar) subFilterBar.style.display = "none";
          if (curationHint) curationHint.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span><span>Procedural Memory: Quy tắc hành động & cạm bẫy phục vụ AI Agent</span>';
          loadBrainHeuristics();
        }
      });
    }

    // Ingest Modal Open / Close
    btnOpenIngest.addEventListener("click", openIngestModal);
    btnCloseIngestModal.addEventListener("click", closeIngestModal);
    btnCancelIngest.addEventListener("click", closeIngestModal);
    ingestOverlay.addEventListener("click", closeIngestModal);

    // Global Knowledge Graph Modal
    if (btnOpenGlobalGraph) {
      btnOpenGlobalGraph.addEventListener("click", openGlobalGraphModal);
    }
    if (btnCloseGlobalGraph) {
      btnCloseGlobalGraph.addEventListener("click", closeGlobalGraphModal);
    }
    if (globalGraphOverlay) {
      globalGraphOverlay.addEventListener("click", closeGlobalGraphModal);
    }
    if (btnGlobalGraphFit) {
      btnGlobalGraphFit.addEventListener("click", () => {
        if (activeGlobalNetwork) activeGlobalNetwork.fit({ animation: { duration: 400 } });
      });
    }

    // WikiLinks Click Delegation (Bi-directional Knowledge Traversal)
    document.addEventListener("click", (e) => {
      const wikiEl = e.target.closest(".wikilink");
      if (!wikiEl) return;
      const term = wikiEl.dataset.wiki;
      if (!term) return;

      const matched = currentItems.find(i => 
        (i.title || "").toLowerCase().includes(term.toLowerCase())
      );
      if (matched && matched.id !== activeItemId) {
        openDrawer(matched.id);
        showToast(`Đã chuyển tới bài: ${matched.title}`, "info");
      } else {
        closeDrawer();
        if (globalGraphModal && !globalGraphModal.classList.contains("hidden")) {
          closeGlobalGraphModal();
        }
        searchInput.value = term;
        searchQuery = term;
        loadVaultItems();
        showToast(`Đang tìm kiếm khái niệm: [[${term}]]`, "info");
      }
    });

    // Ingest Form Submit
    ingestForm.addEventListener("submit", handleIngestSubmit);

    // Reading progress & TOC active state on scroll
    deepResearchContent.addEventListener("scroll", handleDrawerScroll);

    // Language Toggle
    if (btnLangVi && btnLangEn) {
      btnLangVi.addEventListener("click", () => setLanguage("vi"));
      btnLangEn.addEventListener("click", () => setLanguage("en"));
    }

    // 1-Click Ingest for Referenced Docs
    deepResearchContent.addEventListener("click", handleReferencedDocIngest);

    // Floating Selection Toolbar & Inline AI
    const selToolbar = document.getElementById("selection-toolbar");
    const btnInlineAi = document.getElementById("btn-inline-ai");
    const btnInlineQuote = document.getElementById("btn-inline-quote");
    const inlineAiPopover = document.getElementById("inline-ai-popover");
    const inlineAiContent = document.getElementById("inline-ai-content");
    const btnCloseAiPopover = document.getElementById("btn-close-ai-popover");

    let currentSelectedText = "";

    function hideSelectionUi() {
      if (selToolbar) selToolbar.classList.add("hidden");
    }

    if (deepResearchContent && selToolbar) {
      deepResearchContent.addEventListener("mouseup", handleTextSelection);
      deepResearchContent.addEventListener("touchend", handleTextSelection);

      function handleTextSelection() {
        setTimeout(() => {
          const sel = window.getSelection();
          const text = sel ? sel.toString().trim() : "";
          if (text.length >= 3) {
            currentSelectedText = text;
            const range = sel.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            
            // Position toolbar centered directly above selected text
            selToolbar.style.top = `${rect.top - 10}px`;
            selToolbar.style.left = `${rect.left + rect.width / 2}px`;
            selToolbar.classList.remove("hidden");
            hydrateIcons();
          } else {
            hideSelectionUi();
          }
        }, 40);
      }

      // Hide on click outside
      document.addEventListener("mousedown", (e) => {
        if (!e.target.closest("#selection-toolbar") && !e.target.closest("#inline-ai-popover")) {
          hideSelectionUi();
        }
      });

      // Copy Quote Action
      if (btnInlineQuote) {
        btnInlineQuote.addEventListener("click", () => {
          if (!currentSelectedText) return;
          const quoteText = `"${currentSelectedText}"\n\n— Trích dẫn từ: ${drawerTitle.textContent} (${drawerOrigLink.href})`;
          copyTextToClipboard(quoteText).then(() => {
            showToast("Đã copy trích dẫn kèm nguồn vào clipboard!", "info");
            hideSelectionUi();
          });
        });
      }

      // Ask AI Inline Action
      if (btnInlineAi && inlineAiPopover) {
        btnInlineAi.addEventListener("click", async () => {
          if (!currentSelectedText) return;
          const sel = window.getSelection();
          if (sel && sel.rangeCount > 0) {
            const rect = sel.getRangeAt(0).getBoundingClientRect();
            inlineAiPopover.style.top = `${rect.bottom + 10}px`;
            inlineAiPopover.style.left = `${Math.min(window.innerWidth - 170, Math.max(170, rect.left + rect.width / 2))}px`;
          }
          inlineAiContent.innerHTML = '<div class="flex items-center gap-2 text-cyan-400 py-1"><i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Kỹ sư trưởng đang phân tích bản chất...</span></div>';
          inlineAiPopover.classList.remove("hidden");
          hideSelectionUi();
          hydrateIcons();

          try {
            const resp = await fetch("/api/v1/explain-inline", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                selected_text: currentSelectedText,
                article_title: drawerTitle.textContent
              })
            });
            const data = await resp.json();
            inlineAiContent.textContent = data.explanation || "Không thể phân tích đoạn này.";
          } catch (err) {
            inlineAiContent.textContent = "Lỗi kết nối AI: " + err.message;
          }
        });
      }

      if (btnCloseAiPopover) {
        btnCloseAiPopover.addEventListener("click", () => {
          inlineAiPopover.classList.add("hidden");
        });
      }
    }
  }

  // API Callers
  async function loadVaultStats() {
    try {
      const res = await fetch("/api/v1/stats");
      if (!res.ok) return;
      const data = await res.json();
      statTotal.textContent = data.total_vault_items ?? data.total_items ?? 0;
      statUnread.textContent = data.unread_items ?? data.unread_count ?? 0;
      statStarred.textContent = data.starred_items ?? data.starred_count ?? 0;

      if (badgeApproved) badgeApproved.textContent = data.approved_count ?? data.total_items ?? 0;
      if (badgeInbox) badgeInbox.textContent = data.inbox_count ?? 0;
      if (badgeTopics) badgeTopics.textContent = data.synthesis_topics_count ?? 0;
      if (badgeHeuristics) badgeHeuristics.textContent = data.heuristics_count ?? 0;
    } catch (err) {
      console.warn("Lỗi tải stats:", err);
    }
  }

  async function loadVaultItems() {
    const params = new URLSearchParams();
    if (searchQuery) params.append("q", searchQuery);
    if (currentCategory) params.append("category", currentCategory);
    if (onlyStarred) params.append("starred", "true");
    if (minScore > 1) params.append("min_score", minScore.toString());
    params.append("curation_status", currentBrainMode);

    gridContainer.innerHTML = `
      <div class="col-span-full py-20 text-center text-slate-400 text-xs font-mono">
        <div class="inline-block animate-spin w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full mb-3"></div>
        <p>Đang truy vấn ${currentBrainMode === 'INBOX' ? 'Hộp thư chờ duyệt' : 'Bộ Não Tự Học'}...</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/v1/vault?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentItems = data.items || [];
      renderGrid();
    } catch (err) {
      gridContainer.innerHTML = `<div class="col-span-full py-16 text-center text-rose-400 text-xs font-mono">⚠️ Lỗi tải dữ liệu: ${err.message}</div>`;
    }
  }

  async function curateItem(id, action) {
    try {
      showToast(action === "APPROVE" ? "🧠 Đang duyệt và hợp nhất vào Não Bộ..." : "Đang loại bỏ...", "info");
      const res = await fetch(`/api/v1/vault/${id}/curate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (action === "APPROVE") {
        const cons = data.consolidation || {};
        showToast(`🧠 Đã duyệt vào Não Bộ! Nối ${cons.associations_count || 0} nơ-ron và nạp ${cons.heuristics_count || 0} quy tắc Agent.`, "success");
      } else {
        showToast("🗑️ Đã loại bỏ tài liệu.", "info");
      }
      closeDrawer();
      loadVaultStats();
      if (currentBrainMode === "INBOX" || currentBrainMode === "APPROVED") {
        loadVaultItems();
      }
    } catch (err) {
      showToast("❌ Lỗi duyệt: " + err.message, "error");
    }
  }

  async function loadBrainTopics() {
    gridContainer.innerHTML = `
      <div class="col-span-full py-20 text-center text-slate-400 text-xs font-mono">
        <div class="inline-block animate-spin w-5 h-5 border-2 border-purple-400 border-t-transparent rounded-full mb-3"></div>
        <p>Đang tổng hợp các Hồ Sơ Chuyên Đề Sống...</p>
      </div>
    `;
    try {
      const res = await fetch("/api/v1/brain/topics");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const topics = await res.json();
      if (!topics || topics.length === 0) {
        gridContainer.innerHTML = `
          <div class="col-span-full py-20 text-center border border-dashed border-[#1e2638] rounded-2xl p-10 bg-[#0a0e16]">
            <div class="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto mb-3 text-purple-400">
              <i data-lucide="layers" class="w-6 h-6"></i>
            </div>
            <p class="text-slate-300 text-sm font-semibold">Chưa có Hồ Sơ Chuyên Đề Sống nào</p>
            <p class="text-slate-500 text-xs mt-1.5 font-mono">Khi duyệt bài viết vào Não Bộ, hệ thống sẽ tự động khởi tạo và tiến hóa các chuyên đề.</p>
          </div>
        `;
        hydrateIcons();
        return;
      }

      gridContainer.innerHTML = topics.map(t => {
        const itemIds = Array.isArray(t.included_item_ids) ? t.included_item_ids : [];
        return `
          <div class="bento-card border-purple-500/30 hover:border-purple-400/60 transition-all cursor-pointer topic-card" data-slug="${escapeHtml(t.topic_slug)}">
            <div>
              <div class="bento-card-header">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  CHUYÊN ĐỀ SỐNG
                </span>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#162032] text-cyan-400 border border-cyan-500/25">
                  v${t.version}
                </span>
              </div>
              <h3 class="card-title text-purple-200 mt-2">${escapeHtml(t.topic_title)}</h3>
              <p class="card-summary line-clamp-4 mt-2 text-slate-300 text-xs">
                ${escapeHtml((t.master_synthesis_md || "").slice(0, 220))}...
              </p>
            </div>
            <div class="card-footer mt-4 pt-3 border-t border-[#1a2336] flex items-center justify-between text-xs font-mono">
              <span class="text-slate-400 flex items-center gap-1">
                <i data-lucide="file-check" class="w-3.5 h-3.5 text-cyan-400"></i>
                <span>${itemIds.length} bài viết hợp nhất</span>
              </span>
              <span class="text-purple-400 font-semibold flex items-center gap-1">
                <span>Xem bản tổng luận</span>
                <i data-lucide="arrow-right" class="w-3 h-3"></i>
              </span>
            </div>
          </div>
        `;
      }).join("");

      gridContainer.querySelectorAll(".topic-card").forEach(card => {
        card.addEventListener("click", () => openTopicDrawer(card.dataset.slug));
      });

      hydrateIcons();
    } catch (err) {
      gridContainer.innerHTML = `<div class="col-span-full py-16 text-center text-rose-400 text-xs font-mono">⚠️ Lỗi tải chuyên đề: ${err.message}</div>`;
    }
  }

  async function openTopicDrawer(slug) {
    try {
      const res = await fetch(`/api/v1/brain/topics/${slug}`);
      if (!res.ok) throw new Error("Không thể tải chuyên đề");
      const topic = await res.json();
      drawerTitle.textContent = topic.topic_title;
      drawerCategory.textContent = "CHUYÊN ĐỀ SỐNG";
      drawerArchetype.textContent = `v${topic.version}`;
      drawerScore.textContent = `${(topic.included_item_ids || []).length} BÀI`;
      drawerOrigLink.style.display = "none";
      if (drawerCurationActions) {
        drawerCurationActions.innerHTML = `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-mono">LIVING SYNTHESIS</span>`;
      }
      btnDrawerStar.style.display = "none";

      activeItemFullMd = topic.master_synthesis_md;
      renderActiveTabContent();
      readerDrawer.classList.remove("translate-x-full");
      readerOverlay.classList.remove("hidden");
      document.body.style.overflow = "hidden";
    } catch (err) {
      showToast("Lỗi: " + err.message, "error");
    }
  }

  async function loadBrainHeuristics() {
    gridContainer.innerHTML = `
      <div class="col-span-full py-20 text-center text-slate-400 text-xs font-mono">
        <div class="inline-block animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mb-3"></div>
        <p>Đang tải bộ nhớ quy tắc hành động (Procedural Memory)...</p>
      </div>
    `;
    try {
      const res = await fetch("/api/v1/brain/heuristics");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const heuristics = await res.json();
      if (!heuristics || heuristics.length === 0) {
        gridContainer.innerHTML = `
          <div class="col-span-full py-20 text-center border border-dashed border-[#1e2638] rounded-2xl p-10 bg-[#0a0e16]">
            <div class="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-3 text-emerald-400">
              <i data-lucide="zap" class="w-6 h-6"></i>
            </div>
            <p class="text-slate-300 text-sm font-semibold">Chưa có Quy tắc Agent nào được trích xuất</p>
            <p class="text-slate-500 text-xs mt-1.5 font-mono">Khi duyệt bài viết vào Não Bộ, các quy tắc hành động và anti-patterns sẽ tự động được sinh ra ở đây.</p>
          </div>
        `;
        hydrateIcons();
        return;
      }

      gridContainer.innerHTML = heuristics.map(h => {
        const conf = h.confidence_score ?? 1.0;
        return `
          <div class="bento-card border-emerald-500/25 p-5 bg-[#0a0e16]">
            <div class="bento-card-header">
              <span class="card-category-badge">${escapeHtml(h.topic || "General")}</span>
              <span class="px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                ⭐ Độ tin cậy: ${conf.toFixed(2)}
              </span>
            </div>
            <div class="mt-3">
              <div class="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-200 font-sans leading-relaxed">
                <strong>⚡ Quy Tắc Hành Động:</strong><br>
                ${escapeHtml(h.rule_statement)}
              </div>
              ${h.anti_pattern ? `
                <div class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 font-sans leading-relaxed mt-2.5">
                  <strong>⚠️ Cạm Bẫy (Anti-Pattern):</strong><br>
                  ${escapeHtml(h.anti_pattern)}
                </div>
              ` : ''}
            </div>
            <div class="card-footer mt-4 pt-3 border-t border-[#1a2336] flex items-center justify-between text-[11px] font-mono">
              <span class="text-slate-400">
                Thực thi: <strong>${h.execution_count || 0}</strong> | Thành công: <strong>${h.success_count || 0}</strong>
              </span>
              <div class="flex items-center space-x-1.5">
                <button class="btn-feedback-pos px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-[10px]" data-id="${h.id}" title="Ghi nhận áp dụng thành công">
                  👍 Hiệu quả
                </button>
                <button class="btn-feedback-neg px-2 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[10px]" data-id="${h.id}" title="Ghi nhận gặp gotcha/lỗi">
                  👎 Thất bại
                </button>
              </div>
            </div>
          </div>
        `;
      }).join("");

      gridContainer.querySelectorAll(".btn-feedback-pos").forEach(btn => {
        btn.addEventListener("click", () => recordAgentFeedback(parseInt(btn.dataset.id, 10), true));
      });
      gridContainer.querySelectorAll(".btn-feedback-neg").forEach(btn => {
        btn.addEventListener("click", () => recordAgentFeedback(parseInt(btn.dataset.id, 10), false));
      });

      hydrateIcons();
    } catch (err) {
      gridContainer.innerHTML = `<div class="col-span-full py-16 text-center text-rose-400 text-xs font-mono">⚠️ Lỗi tải quy tắc: ${err.message}</div>`;
    }
  }

  async function recordAgentFeedback(heuristicId, success) {
    try {
      const res = await fetch("/api/v1/brain/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ heuristic_id: heuristicId, success, note: success ? "Thực nghiệm đạt chuẩn" : "Gặp gotcha khi thực thi" })
      });
      if (!res.ok) throw new Error("Ghi nhận thất bại");
      showToast(success ? "👍 Đã củng cố nơ-ron thành công (+0.05)" : "👎 Đã điều chỉnh hạ điểm tin cậy (-0.15)", success ? "success" : "info");
      loadBrainHeuristics();
    } catch (e) {
      showToast("Lỗi: " + e.message, "error");
    }
  }

  async function updateItemStatus(id, { reading_status, is_starred }) {
    const params = new URLSearchParams();
    if (reading_status !== undefined) params.append("reading_status", reading_status);
    if (is_starred !== undefined) params.append("is_starred", is_starred.toString());

    try {
      await fetch(`/api/v1/vault/${id}/status?${params.toString()}`, { method: "PUT" });
    } catch (err) {
      console.error("Lỗi cập nhật trạng thái:", err);
    }
  }

  // Ingest Modal Logic
  function openIngestModal() {
    ingestModal.classList.remove("hidden");
    ingestUrlInput.value = "";
    ingestStatusMsg.className = "text-xs hidden p-2.5 rounded-lg font-mono";
    ingestStatusMsg.textContent = "";
    ingestUrlInput.focus();
    hydrateIcons();
  }

  function closeIngestModal() {
    ingestModal.classList.add("hidden");
  }

  async function handleIngestSubmit(e) {
    e.preventDefault();
    const url = ingestUrlInput.value.trim();
    if (!url) return;

    btnSubmitIngest.disabled = true;
    btnSubmitIngest.innerHTML = `<span class="inline-block animate-spin w-3.5 h-3.5 border-2 border-slate-900 border-t-transparent rounded-full mr-1.5"></span><span>Đang xử lý...</span>`;
    ingestStatusMsg.classList.remove("hidden");
    ingestStatusMsg.className = "text-xs p-2.5 rounded-lg font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-500/20";
    ingestStatusMsg.textContent = "⚡ Đang bóc tách & phân tích theo chuẩn Smart Article Reader...";

    try {
      const res = await fetch("/api/v1/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Không thể nạp link");

      ingestStatusMsg.className = "text-xs p-2.5 rounded-lg font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
      ingestStatusMsg.textContent = "✓ " + (data.message || "Đã tiếp nhận vào hàng đợi xử lý");
      showToast("Đã đưa vào hàng đợi phân tích!", "info");

      setTimeout(() => {
        closeIngestModal();
        btnSubmitIngest.disabled = false;
        btnSubmitIngest.innerHTML = `<i data-lucide="sparkles" class="w-3.5 h-3.5 mr-1.5"></i><span>Bắt đầu phân tích</span>`;
        // Reload items after 2s
        setTimeout(() => {
          loadVaultStats();
          loadVaultItems();
        }, 1500);
      }, 1000);

    } catch (err) {
      ingestStatusMsg.className = "text-xs p-2.5 rounded-lg font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20";
      ingestStatusMsg.textContent = "❌ " + err.message;
      btnSubmitIngest.disabled = false;
      btnSubmitIngest.innerHTML = `<i data-lucide="sparkles" class="w-3.5 h-3.5 mr-1.5"></i><span>Thử lại</span>`;
    }
  }

  // Render Functions
  function renderGrid() {
    let filtered = currentItems;
    if (currentArchetype) {
      filtered = filtered.filter(item => {
        const st = (item.source_type || "").toLowerCase();
        const arch = item.archetype || (st.includes("github") ? "CODE_REPO" : (st.includes("arxiv") ? "TECH_DEEPDIVE" : "CONCEPT_THOUGHT"));
        return arch === currentArchetype;
      });
    }

    if (filtered.length === 0) {
      gridContainer.innerHTML = `
        <div class="col-span-full py-20 text-center border border-dashed border-[#1e2638] rounded-2xl p-10 bg-[#0a0e16]">
          <div class="w-12 h-12 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-center mx-auto mb-3 text-slate-400">
            <i data-lucide="inbox" class="w-6 h-6"></i>
          </div>
          <p class="text-slate-300 text-sm font-semibold">Chưa có tài liệu nào trong danh mục này</p>
          <p class="text-slate-500 text-xs mt-1.5 font-mono">Bấm nút "+ Nạp Link" ở góc trên để thêm bài viết mới</p>
        </div>
      `;
      hydrateIcons();
      return;
    }

    gridContainer.innerHTML = filtered.map((item, index) => {
      const score = item.practical_score ?? 0;
      let scoreClass = "score-low";
      if (score >= 8.0) scoreClass = "score-high";
      else if (score >= 6.0) scoreClass = "score-medium";

      const rawTags = Array.isArray(item.tech_stack) ? item.tech_stack : [];
      const tags = rawTags.slice(0, 4).map(t => `<span class="card-tag">${escapeHtml(t)}</span>`).join("");
      const isStarred = item.is_starred ? "active" : "";
      const cardStarredClass = item.is_starred ? "starred" : "";
      const isHero = (index === 0 && !searchQuery && !currentCategory) || score >= 9.5;
      const heroClass = isHero ? "hero-card" : "";

      const st = (item.source_type || "").toLowerCase();
      const arch = item.archetype || (st.includes("github") ? "CODE_REPO" : (st.includes("arxiv") ? "TECH_DEEPDIVE" : "CONCEPT_THOUGHT"));

      let archIcon = "code-2";
      let archText = "MÃ NGUỒN";
      let archStyle = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      if (arch === "CONCEPT_THOUGHT") {
        archIcon = "brain";
        archText = "TƯ DUY";
        archStyle = "bg-blue-500/10 text-blue-400 border-blue-500/20";
      } else if (arch === "TECH_DEEPDIVE") {
        archIcon = "microscope";
        archText = "KỸ THUẬT";
        archStyle = "bg-purple-500/10 text-purple-400 border-purple-500/20";
      }

      let sourceIconName = "globe";
      if (st.includes("github")) sourceIconName = "git-branch";
      else if (st.includes("youtube")) sourceIconName = "video";
      else if (st.includes("arxiv")) sourceIconName = "file-text";

      const isUnread = (item.reading_status || "").toUpperCase() === "UNREAD";

      const isInbox = (item.curation_status || "").toUpperCase() === "INBOX" || currentBrainMode === "INBOX";
      const inboxActionHtml = isInbox ? `
        <div class="mt-3 pt-2.5 border-t border-amber-500/20 flex items-center justify-between gap-2">
          <span class="text-[10px] font-mono text-amber-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            Chờ duyệt
          </span>
          <div class="flex items-center space-x-1.5">
            <button class="btn-card-approve px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-[11px] font-semibold flex items-center gap-1 transition-all" data-id="${item.id}" title="Duyệt vào Não Bộ">
              <i data-lucide="brain" class="w-3 h-3 text-emerald-400"></i>
              <span>Duyệt</span>
            </button>
            <button class="btn-card-reject px-2 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 text-[11px] font-medium transition-all" data-id="${item.id}" title="Loại bỏ bài viết">
              Loại
            </button>
          </div>
        </div>
      ` : "";

      return `
        <div class="bento-card ${cardStarredClass} ${heroClass} ${isInbox ? 'border-amber-500/30' : ''}" data-id="${item.id}">
          <div>
            <div class="bento-card-header">
              <div class="flex items-center space-x-1.5">
                <span class="card-category-badge">${escapeHtml(item.category || "General")}</span>
                <span class="px-1.5 py-0.5 rounded text-[10px] font-mono border flex items-center gap-1 ${archStyle}">
                  <i data-lucide="${archIcon}" class="w-3 h-3"></i>
                  <span>${archText}</span>
                </span>
              </div>
              <div class="flex items-center space-x-1.5">
                <span class="card-score-badge ${scoreClass}">${score.toFixed(1)} ★</span>
                <button class="star-btn ${isStarred}" data-id="${item.id}" title="Đánh dấu VIP" aria-label="Đánh dấu VIP">
                  <i data-lucide="star" class="w-3.5 h-3.5 ${item.is_starred ? 'fill-amber-400 text-amber-400' : 'text-slate-400'}"></i>
                </button>
              </div>
            </div>
            <h3 class="card-title">${escapeHtml(item.title || "Tài liệu không tên")}</h3>
            <p class="card-summary">${escapeHtml(item.short_summary || "Không có tóm tắt.")}</p>
          </div>
          <div>
            <div class="card-tags">${tags}</div>
            ${inboxActionHtml}
            <div class="card-footer ${isInbox ? 'mt-2' : ''}">
              <span class="font-mono flex items-center gap-1 text-[11px] text-slate-400">
                <i data-lucide="${sourceIconName}" class="w-3 h-3 text-slate-500"></i>
                <span>${escapeHtml(st.toUpperCase())}</span>
              </span>
              <div class="flex items-center space-x-2.5">
                <span class="${isUnread ? 'text-amber-400 font-semibold font-mono' : 'text-slate-500 font-mono'} text-[11px]">
                  ${isUnread ? '● Mới' : '✓ Đã đọc'}
                </span>
                <span class="text-cyan-400 hover:text-cyan-300 font-mono text-[11px] font-semibold flex items-center gap-0.5">
                  <span>Đọc</span>
                  <i data-lucide="arrow-right" class="w-3 h-3"></i>
                </span>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join("");

    // Bind card click & star click & curate clicks
    gridContainer.querySelectorAll(".bento-card").forEach(card => {
      card.addEventListener("click", (e) => {
        if (e.target.closest(".star-btn")) {
          e.stopPropagation();
          const starBtn = e.target.closest(".star-btn");
          toggleStarItem(parseInt(starBtn.dataset.id, 10));
          return;
        }
        if (e.target.closest(".btn-card-approve")) {
          e.stopPropagation();
          const btn = e.target.closest(".btn-card-approve");
          curateItem(parseInt(btn.dataset.id, 10), "APPROVE");
          return;
        }
        if (e.target.closest(".btn-card-reject")) {
          e.stopPropagation();
          const btn = e.target.closest(".btn-card-reject");
          curateItem(parseInt(btn.dataset.id, 10), "REJECT");
          return;
        }
        openDrawer(parseInt(card.dataset.id, 10));
      });
    });

    hydrateIcons();
  }

  async function toggleStarItem(id) {
    const item = currentItems.find(i => i.id === id);
    if (!item) return;
    const newStarred = !item.is_starred;
    item.is_starred = newStarred ? 1 : 0;
    await updateItemStatus(id, { is_starred: newStarred });
    renderGrid();
    loadVaultStats();
    showToast(newStarred ? "Đã gắn sao VIP ⭐" : "Đã hủy gắn sao VIP", "star");
  }

  // Parse GitHub Callouts with Progressive Disclosure
  function parseGitHubCallouts(html) {
    const alertIcons = {
      NOTE: '<i data-lucide="info" class="w-4 h-4 text-cyan-400"></i>',
      TIP: '<i data-lucide="lightbulb" class="w-4 h-4 text-emerald-400"></i>',
      IMPORTANT: '<i data-lucide="zap" class="w-4 h-4 text-purple-400"></i>',
      WARNING: '<i data-lucide="alert-triangle" class="w-4 h-4 text-amber-400"></i>',
      CAUTION: '<i data-lucide="octagon-alert" class="w-4 h-4 text-rose-400"></i>'
    };

    return html.replace(/<blockquote>\s*<p>\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]([\s\S]*?)<\/blockquote>/gi, (match, type, content) => {
      const upperType = type.toUpperCase();
      const icon = alertIcons[upperType] || '<i data-lucide="pin" class="w-4 h-4"></i>';
      const cleanContent = content.trim();

      // Progressive Disclosure: Thu gọn các phần ẩn dụ / động cơ thiết kế nếu là khối giải thích chuyên sâu
      const isSmartAnnotation = cleanContent.includes("Giải Thích Chuyên Sâu") || 
                               cleanContent.includes("Bản chất kỹ thuật") || 
                               cleanContent.includes("Ẩn dụ");

      if (isSmartAnnotation) {
        // Tách phần Bản chất kỹ thuật (Hiển thị ngay) và phần Ẩn dụ / Lý do (Thu gọn)
        const parts = cleanContent.split(/(?=<li>\s*<strong>\s*(?:Ẩn dụ|Ví dụ đời thực|Lý do tác giả làm vậy))/i);
        if (parts.length > 1) {
          const primaryText = parts[0];
          const secondaryText = "<ul>" + parts.slice(1).join("") + "</ul>";
          return `
            <div class="callout-progressive">
              <div class="callout-title">${icon} <span>GIẢI THÍCH CHUYÊN SÂU (SMART ANNOTATION)</span></div>
              <div class="callout-primary">${primaryText}</div>
              <details class="callout-accordion">
                <summary>
                  <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
                  <span>Xem Ẩn Dụ Đời Thực & Động Cơ Thiết Kế</span>
                </summary>
                <div class="callout-accordion-body">${secondaryText}</div>
              </details>
            </div>
          `;
        }
      }

      return `
        <div class="callout callout-${upperType.toLowerCase()}">
          <div class="callout-title">${icon} <span>${upperType}</span></div>
          <div>${cleanContent}</div>
        </div>
      `;
    });
  }

  function normalizeMarkdownTables(md) {
    if (!md) return "";
    const lines = md.split("\n");
    const result = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      const isTableRow = trimmed.startsWith("|") && trimmed.endsWith("|");

      result.push(line);

      if (isTableRow) {
        const nextLine = (i + 1 < lines.length) ? lines[i + 1].trim() : "";
        const hasSeparator = nextLine.startsWith("|") && /^[|:\-\s]+$/.test(nextLine);
        const prevLine = (i > 0) ? lines[i - 1].trim() : "";
        const prevIsTableRow = prevLine.startsWith("|") && prevLine.endsWith("|");

        if (!prevIsTableRow && !hasSeparator && nextLine.startsWith("|")) {
          const colCount = Math.max(1, (trimmed.match(/\|/g) || []).length - 1);
          const sep = "| " + Array(colCount).fill(":---").join(" | ") + " |";
          result.push(sep);
        }
      }
    }
    return result.join("\n");
  }

  // Language Toggle & Content Selection
  function updateActiveItemFullMd(item) {
    if (!item) return;
    if (currentLang === "en" && item.original_md) {
      activeItemFullMd = item.original_md;
    } else {
      activeItemFullMd = item.deep_research_md || `## ${item.title}\n\n${item.short_summary}`;
    }
  }

  function setLanguage(lang) {
    currentLang = lang;
    if (btnLangVi && btnLangEn) {
      if (lang === "vi") {
        btnLangVi.classList.add("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangVi.classList.remove("text-slate-400", "border-[#1e2638]");
        btnLangEn.classList.remove("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangEn.classList.add("text-slate-400", "border-[#1e2638]");
      } else {
        btnLangEn.classList.add("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangEn.classList.remove("text-slate-400", "border-[#1e2638]");
        btnLangVi.classList.remove("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangVi.classList.add("text-slate-400", "border-[#1e2638]");
      }
    }

    if (activeItemId) {
      const item = currentItems.find(i => i.id === activeItemId);
      if (item) {
        if (lang === "en" && !item.original_md) {
          showToast("Không tìm thấy văn bản tiếng Anh gốc cho mục này", "info");
        }
        updateActiveItemFullMd(item);
        renderActiveTabContent();
        showToast(lang === "vi" ? "Đã chuyển sang Tiếng Việt 🇻🇳" : "Switched to English 🇺🇸", "info");
      }
    }
  }

  // Slide-over Drawer
  async function openDrawer(id) {
    const item = currentItems.find(i => i.id === id);
    if (!item) return;
    activeItemId = id;
    
    // Set language display
    updateActiveItemFullMd(item);
    if (btnLangVi && btnLangEn) {
      if (currentLang === "vi") {
        btnLangVi.classList.add("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangEn.classList.remove("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
      } else {
        btnLangEn.classList.add("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
        btnLangVi.classList.remove("bg-cyan-500/20", "text-cyan-300", "border-cyan-500/40");
      }
    }

    drawerTitle.textContent = item.title;
    drawerCategory.textContent = item.category || "General";
    drawerScore.textContent = `${(item.practical_score ?? 0).toFixed(1)} ★`;
    drawerOrigLink.href = item.source_url || item.canonical_url || "#";
    drawerOrigLink.style.display = "";
    btnDrawerStar.style.display = "";

    if (drawerCurationActions) {
      const isInbox = (item.curation_status || "").toUpperCase() === "INBOX";
      if (isInbox) {
        drawerCurationActions.innerHTML = `
          <button id="btn-drawer-approve" class="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1 transition-all" title="Duyệt vào Não Bộ">
            <i data-lucide="brain" class="w-3.5 h-3.5 text-emerald-400"></i>
            <span>Duyệt Vào Não</span>
          </button>
          <button id="btn-drawer-reject" class="px-2.5 py-1 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30 text-xs font-medium transition-all" title="Loại bỏ bài này">
            Loại Bỏ
          </button>
        `;
        const bApp = document.getElementById("btn-drawer-approve");
        const bRej = document.getElementById("btn-drawer-reject");
        if (bApp) bApp.onclick = () => curateItem(id, "APPROVE");
        if (bRej) bRej.onclick = () => curateItem(id, "REJECT");
      } else {
        drawerCurationActions.innerHTML = `
          <span class="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono flex items-center gap-1">
            <i data-lucide="shield-check" class="w-3 h-3 text-cyan-400"></i>
            <span>ĐÃ DUYỆT VÀO NÃO</span>
          </span>
        `;
      }
    }

    const st = (item.source_type || "").toLowerCase();
    const arch = item.archetype || (st.includes("github") ? "CODE_REPO" : (st.includes("arxiv") ? "TECH_DEEPDIVE" : "CONCEPT_THOUGHT"));
    drawerArchetype.textContent = arch === "CODE_REPO" ? "Mã Nguồn" : (arch === "CONCEPT_THOUGHT" ? "Tư Duy" : "Kỹ Thuật");

    updateDrawerStarUI(item.is_starred);

    // Default to 'all' tab
    activeTab = "all";
    drawerTabs.querySelectorAll(".drawer-tab").forEach(t => {
      if (t.dataset.tab === "all") t.classList.add("active");
      else t.classList.remove("active");
    });

    renderActiveTabContent();

    // Open drawer UI
    readerDrawer.classList.remove("hidden");
    void readerDrawer.offsetWidth;
    readerDrawer.classList.add("active");
    readingProgress.style.width = "0%";
    deepResearchContent.scrollTop = 0;

    // Mark as read if unread
    if ((item.reading_status || "").toUpperCase() === "UNREAD") {
      item.reading_status = "READ";
      await updateItemStatus(id, { reading_status: "READ" });
      loadVaultStats();
      const card = gridContainer.querySelector(`.bento-card[data-id="${id}"]`);
      if (card) {
        const readBadge = card.querySelector(".card-footer span:last-child span:first-child");
        if (readBadge) {
          readBadge.className = "text-slate-500 font-mono text-[11px]";
          readBadge.textContent = "✓ Đã đọc";
        }
      }
    }
  }

  function renderActiveTabContent() {
    if (activeTab === "associations" && activeItemId) {
      renderAssociationsTab(activeItemId);
      return;
    }

    let mdToRender = activeItemFullMd;
    const item = currentItems.find(i => i.id === activeItemId);
    const part2Pos = activeItemFullMd.indexOf("## PHẦN II");
    const part3Pos = activeItemFullMd.indexOf("## PHẦN III");

    if (activeTab === "brief") {
      // Show only Part I: up until '## PHẦN II'
      if (part2Pos !== -1) {
        mdToRender = activeItemFullMd.substring(0, part2Pos).trim();
      }
    } else if (activeTab === "reader") {
      // Show only Part II: from '## PHẦN II' up to '## PHẦN III'
      if (part2Pos !== -1) {
        const titleMatch = activeItemFullMd.match(/^#\s+([^\n]+)/);
        const heading = titleMatch ? `# ${titleMatch[1]}\n\n` : "";
        if (part3Pos !== -1 && part3Pos > part2Pos) {
          mdToRender = heading + activeItemFullMd.substring(part2Pos, part3Pos).trim();
        } else {
          mdToRender = heading + activeItemFullMd.substring(part2Pos).trim();
        }
      }
    } else if (activeTab === "network") {
      // Show Part III: from '## PHẦN III' onward
      if (part3Pos !== -1) {
        mdToRender = activeItemFullMd.substring(part3Pos).trim();
      } else {
        mdToRender = `## PHẦN III: MẠNG LƯỚI TRI THỨC LIÊN KẾT (REFERENCED KNOWLEDGE)\n\n> [!NOTE]\n> **Thông tin mạng lưới:** Bài viết này không chứa liên kết trích dẫn chéo (ArXiv Paper hoặc GitHub Repository) nào bên trong nội dung gốc.`;
      }
    }

    const normalizedMd = normalizeMarkdownTables(mdToRender);
    const parsedHtml = marked.parse(normalizedMd);
    const enrichedHtml = parseGitHubCallouts(parsedHtml);
    const withWikiLinks = parseWikiLinks(enrichedHtml);
    deepResearchContent.innerHTML = withWikiLinks;

    // Phase 2: Render Interactive Knowledge Graph if in 'network' tab
    if (activeTab === "network" && activeItemId) {
      const graphCardHtml = `
        <div class="network-graph-card mb-8">
          <div class="flex items-center justify-between px-4 py-3 border-b border-[#1f293d] bg-[#0c1017]">
            <div class="flex items-center gap-2">
              <i data-lucide="network" class="w-4 h-4 text-cyan-400"></i>
              <span class="text-xs font-bold text-slate-200 uppercase tracking-wider">ĐỒ THỊ TRI THỨC TƯƠNG TÁC (FORCE-DIRECTED GRAPH)</span>
            </div>
            <div class="flex items-center gap-2">
              <button id="btn-graph-fit" class="graph-ctrl-btn" title="Căn chỉnh toàn cảnh"><i data-lucide="maximize-2" class="w-3.5 h-3.5"></i></button>
              <button id="btn-graph-physics" class="graph-ctrl-btn active" title="Bật/Tắt vật lý động"><i data-lucide="activity" class="w-3.5 h-3.5"></i></button>
            </div>
          </div>
          <div id="vis-graph-canvas">
            <div id="graph-loading" class="absolute inset-0 flex items-center justify-center text-xs font-mono text-slate-400">
              <i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-2 text-cyan-400"></i> Đang tính toán đồ thị tri thức...
            </div>
            <div id="graph-node-popover" class="graph-node-popover hidden"></div>
          </div>
          <div class="flex flex-wrap items-center gap-3 px-4 py-2 border-t border-[#1a2335] bg-[#0c1017] text-[11px] font-mono text-slate-400">
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#38bdf8]"></span> Bài này</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#475569]"></span> Bài khác</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded bg-[#10b981]"></span> Tech Stack</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-[#a855f7]"></span> Danh mục</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#06b6d4]"></span> WikiLink</span>
            <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rotate-45 bg-[#f59e0b]"></span> Trích dẫn</span>
          </div>
        </div>
      `;
      deepResearchContent.insertAdjacentHTML("afterbegin", graphCardHtml);
      setTimeout(() => renderNetworkGraph(activeItemId), 40);
    }

    // Render interactive Reference Cards Grid if referenced_docs exist and in 'all' or 'network' tab
    if (item && (activeTab === "all" || activeTab === "network")) {
      let refDocs = [];
      try {
        if (Array.isArray(item.referenced_docs)) {
          refDocs = item.referenced_docs;
        } else if (typeof item.referenced_docs === "string" && item.referenced_docs.trim()) {
          refDocs = JSON.parse(item.referenced_docs);
        }
      } catch (err) {
        console.warn("Lỗi parse referenced_docs:", err);
      }

      if (refDocs && refDocs.length > 0) {
        renderInteractiveRefCards(refDocs);
      }
    }

    // Render Mermaid diagrams
    if (window.mermaid) {
      try {
        const mermaidElements = deepResearchContent.querySelectorAll(".mermaid");
        if (mermaidElements.length > 0) {
          window.mermaid.run({ nodes: mermaidElements });
        }
      } catch (mErr) {
        console.warn("Lỗi render Mermaid:", mErr);
      }
    }

    attachCodeCopyButtons();
    generateAutoTOC();
    hydrateIcons();
  }

  function renderInteractiveRefCards(refDocs) {
    const section = document.createElement("div");
    section.className = "mt-8 pt-6 border-t border-[#1e2638]";
    section.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
          <i data-lucide="network" class="w-4 h-4"></i>
          <span>Tài Liệu & Mã Nguồn Trích Dẫn (${refDocs.length})</span>
        </h3>
        <span class="text-xs text-slate-500 font-mono">Bấm [+ Nạp Vào Kho] để bóc tách tự động</span>
      </div>
      <div class="ref-grid">
        ${refDocs.map(doc => {
          let badgeClass = "ref-badge-article";
          let badgeText = "ARTICLE";
          let iconName = "file-text";
          if (doc.type === "arxiv" || doc.type === "paper") {
            badgeClass = "ref-badge-paper";
            badgeText = "ARXIV PAPER";
            iconName = "graduation-cap";
          } else if (doc.type === "repo" || (doc.url || "").includes("github.com")) {
            badgeClass = "ref-badge-repo";
            badgeText = "GITHUB REPO";
            iconName = "git-branch";
          }

          return `
            <div class="ref-card">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-mono border ${badgeClass} flex items-center gap-1">
                    <i data-lucide="${iconName}" class="w-3 h-3"></i>
                    <span>${badgeText}</span>
                  </span>
                  <a href="${escapeHtml(doc.url)}" target="_blank" rel="noopener noreferrer" class="text-slate-400 hover:text-cyan-400 text-xs">
                    <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                  </a>
                </div>
                <h4 class="text-xs font-semibold text-slate-200 line-clamp-2 mb-1.5 hover:text-cyan-300">
                  <a href="${escapeHtml(doc.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(doc.title || doc.url)}</a>
                </h4>
                ${doc.context ? `<p class="text-[11px] text-slate-400 line-clamp-2 mb-2 italic">“${escapeHtml(doc.context)}”</p>` : ""}
              </div>
              <div class="pt-2 border-t border-[#1a2234] flex items-center justify-between">
                <span class="text-[10px] text-slate-500 font-mono truncate max-w-[150px]">${escapeHtml(doc.url)}</span>
                <button class="btn-ingest-ref" data-url="${escapeHtml(doc.url)}">
                  <i data-lucide="plus" class="w-3 h-3"></i>
                  <span>+ Nạp Vào Kho</span>
                </button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
    deepResearchContent.appendChild(section);
  }

  function handleReferencedDocIngest(e) {
    const btn = e.target.closest(".btn-ingest-ref");
    if (!btn) return;
    const url = btn.dataset.url;
    if (!url) return;

    openIngestModal();
    ingestUrlInput.value = url;
    ingestStatusMsg.className = "text-xs p-2.5 rounded-lg font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20";
    ingestStatusMsg.textContent = `Đã chọn tài liệu trích dẫn: ${url}. Bấm "Bắt đầu nạp" để bóc tách tri thức.`;
    ingestStatusMsg.classList.remove("hidden");
  }

  function closeDrawer() {
    readerDrawer.classList.remove("active");
    setTimeout(() => {
      readerDrawer.classList.add("hidden");
      activeItemId = null;
      readingProgress.style.width = "0%";
    }, 250);
  }

  function updateDrawerStarUI(isStarred) {
    if (isStarred) {
      btnDrawerStar.classList.add("text-amber-400");
      btnDrawerStar.classList.remove("text-slate-400");
    } else {
      btnDrawerStar.classList.remove("text-amber-400");
      btnDrawerStar.classList.add("text-slate-400");
    }
  }

  function openGlobalGraphModal() {
    if (!globalGraphModal) return;
    globalGraphModal.classList.remove("hidden");
    hydrateIcons();
    setTimeout(() => renderGlobalNetworkGraph(), 60);
  }

  function closeGlobalGraphModal() {
    if (!globalGraphModal) return;
    globalGraphModal.classList.add("hidden");
    const popover = document.getElementById("global-node-popover");
    if (popover) popover.classList.add("hidden");
  }

  function parseWikiLinks(html) {
    if (!html) return "";
    return html.replace(/\[\[(.*?)\]\]/g, (match, term) => {
      const clean = escapeHtml(term.trim());
      return `<span class="wikilink" data-wiki="${clean}" title="Khám phá [[${clean}]] trong kho tri thức"><i data-lucide="compass" class="w-3 h-3 text-cyan-400"></i><span>[[${clean}]]</span></span>`;
    });
  }

  async function renderNetworkGraph(itemId) {
    const canvasContainer = document.getElementById("vis-graph-canvas");
    if (!canvasContainer) return;

    try {
      const resp = await fetch(`/api/v1/vault/${itemId}/graph`);
      if (!resp.ok) throw new Error("API returned " + resp.status);
      const graphData = await resp.json();

      const loadingEl = document.getElementById("graph-loading");
      if (loadingEl) loadingEl.remove();

      if (!window.vis || !window.vis.Network) {
        canvasContainer.innerHTML = `<div class="flex items-center justify-center h-full text-xs font-mono text-slate-500">Đang tải thư viện đồ thị Vis.js...</div>`;
        return;
      }

      const data = {
        nodes: new vis.DataSet(graphData.nodes || []),
        edges: new vis.DataSet(graphData.edges || [])
      };

      const options = {
        nodes: {
          borderWidth: 1.5,
          borderWidthSelected: 2.5,
          shadow: { enabled: true, color: "rgba(0,0,0,0.5)", size: 6, x: 1, y: 1 }
        },
        edges: {
          width: 1.2,
          smooth: { type: "continuous", roundness: 0.15 },
          font: { color: "#64748b", size: 10, align: "middle", strokeWidth: 0 },
          color: { color: "#2d3748", highlight: "#38bdf8", hover: "#06b6d4" },
          arrows: { to: { enabled: true, scaleFactor: 0.5 } }
        },
        physics: {
          enabled: isPhysicsActive,
          barnesHut: {
            gravitationalConstant: -2800,
            centralGravity: 0.3,
            springLength: 90,
            springConstant: 0.04,
            damping: 0.09
          },
          stabilization: { iterations: 100 }
        },
        interaction: {
          hover: true,
          tooltipDelay: 150,
          zoomView: true,
          dragView: true
        }
      };

      activeVisNetwork = new vis.Network(canvasContainer, data, options);

      // Node click handler
      activeVisNetwork.on("click", (params) => {
        const popover = document.getElementById("graph-node-popover");
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const node = (graphData.nodes || []).find(n => n.id === nodeId);
          if (!node || !popover) return;

          let actionBtn = "";
          if (node.group === "vault_item" && node.item_id) {
            actionBtn = `<button class="mt-2 w-full px-2 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-[11px] font-mono border border-cyan-500/40 btn-open-node-item" data-id="${node.item_id}">📖 Mở bài viết này</button>`;
          } else if (node.url) {
            actionBtn = `<a href="${escapeHtml(node.url)}" target="_blank" rel="noopener noreferrer" class="mt-2 block text-center px-2 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-[11px] font-mono border border-amber-500/40">🔗 Mở liên kết ngoài</a>`;
          } else if (node.group === "concept") {
            const conceptTerm = node.label.replace(/^\[\[/, "").replace(/\]\]$/, "");
            actionBtn = `<button class="mt-2 w-full px-2 py-1 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 text-[11px] font-mono border border-blue-500/40 btn-search-node-concept" data-concept="${escapeHtml(conceptTerm)}">🔍 Tra cứu khái niệm</button>`;
          }

          popover.innerHTML = `
            <div class="flex items-center justify-between mb-1 pb-1 border-b border-[#222e44]">
              <span class="text-[10px] font-mono uppercase text-slate-400">${escapeHtml(node.group || "node")}</span>
              <button class="text-slate-400 hover:text-white text-xs px-1" onclick="document.getElementById('graph-node-popover').classList.add('hidden')">✕</button>
            </div>
            <div class="text-xs font-bold text-slate-100">${escapeHtml(node.label)}</div>
            ${node.summary ? `<div class="text-[11px] text-slate-400 mt-1 line-clamp-2">${escapeHtml(node.summary)}</div>` : ""}
            ${actionBtn}
          `;
          popover.classList.remove("hidden");
          hydrateIcons();

          const openItemBtn = popover.querySelector(".btn-open-node-item");
          if (openItemBtn) {
            openItemBtn.onclick = () => openDrawer(parseInt(openItemBtn.dataset.id, 10));
          }
          const searchConceptBtn = popover.querySelector(".btn-search-node-concept");
          if (searchConceptBtn) {
            searchConceptBtn.onclick = () => {
              const term = searchConceptBtn.dataset.concept;
              closeDrawer();
              searchInput.value = term;
              searchQuery = term;
              loadVaultItems();
            };
          }
        } else if (popover) {
          popover.classList.add("hidden");
        }
      });

      const btnFit = document.getElementById("btn-graph-fit");
      if (btnFit) {
        btnFit.onclick = () => activeVisNetwork && activeVisNetwork.fit({ animation: { duration: 400 } });
      }
      const btnPhysics = document.getElementById("btn-graph-physics");
      if (btnPhysics) {
        btnPhysics.onclick = () => {
          isPhysicsActive = !isPhysicsActive;
          btnPhysics.classList.toggle("active", isPhysicsActive);
          activeVisNetwork && activeVisNetwork.setOptions({ physics: { enabled: isPhysicsActive } });
        };
      }

    } catch (err) {
      console.warn("Lỗi render đồ thị:", err);
      if (canvasContainer) {
        canvasContainer.innerHTML = `<div class="flex items-center justify-center h-full text-xs font-mono text-slate-500">Chưa thể tải đồ thị: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  async function renderGlobalNetworkGraph() {
    const canvasContainer = document.getElementById("vis-global-canvas");
    if (!canvasContainer) return;

    try {
      const resp = await fetch("/api/v1/vault-graph");
      if (!resp.ok) throw new Error("API returned " + resp.status);
      const graphData = await resp.json();

      const loadingEl = document.getElementById("global-graph-loading");
      if (loadingEl) loadingEl.remove();

      if (!window.vis || !window.vis.Network) {
        canvasContainer.innerHTML = `<div class="flex items-center justify-center h-full text-xs font-mono text-slate-500">Đang tải thư viện đồ thị Vis.js...</div>`;
        return;
      }

      const data = {
        nodes: new vis.DataSet(graphData.nodes || []),
        edges: new vis.DataSet(graphData.edges || [])
      };

      const options = {
        nodes: {
          borderWidth: 1.5,
          borderWidthSelected: 2.5,
          shadow: { enabled: true, color: "rgba(0,0,0,0.5)", size: 6, x: 1, y: 1 }
        },
        edges: {
          width: 1.2,
          smooth: { type: "continuous", roundness: 0.15 },
          font: { color: "#64748b", size: 10, align: "middle", strokeWidth: 0 },
          color: { color: "#2d3748", highlight: "#38bdf8", hover: "#06b6d4" }
        },
        physics: {
          enabled: true,
          barnesHut: {
            gravitationalConstant: -3500,
            centralGravity: 0.25,
            springLength: 100,
            springConstant: 0.04,
            damping: 0.09
          },
          stabilization: { iterations: 120 }
        },
        interaction: {
          hover: true,
          tooltipDelay: 150,
          zoomView: true,
          dragView: true
        }
      };

      activeGlobalNetwork = new vis.Network(canvasContainer, data, options);

      // Node click handler
      activeGlobalNetwork.on("click", (params) => {
        const popover = document.getElementById("global-node-popover");
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const node = (graphData.nodes || []).find(n => n.id === nodeId);
          if (!node || !popover) return;

          let actionBtn = "";
          if (node.group === "vault_item" && node.item_id) {
            actionBtn = `<button class="mt-2 w-full px-2 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-[11px] font-mono border border-cyan-500/40 btn-open-global-item" data-id="${node.item_id}">📖 Mở bài đọc</button>`;
          }

          popover.innerHTML = `
            <div class="flex items-center justify-between mb-1 pb-1 border-b border-[#222e44]">
              <span class="text-[10px] font-mono uppercase text-slate-400">${escapeHtml(node.group || "node")}</span>
              <button class="text-slate-400 hover:text-white text-xs px-1" onclick="document.getElementById('global-node-popover').classList.add('hidden')">✕</button>
            </div>
            <div class="text-xs font-bold text-slate-100">${escapeHtml(node.label)}</div>
            ${node.summary ? `<div class="text-[11px] text-slate-400 mt-1 line-clamp-2">${escapeHtml(node.summary)}</div>` : ""}
            ${actionBtn}
          `;
          popover.classList.remove("hidden");
          hydrateIcons();

          const openItemBtn = popover.querySelector(".btn-open-global-item");
          if (openItemBtn) {
            openItemBtn.onclick = () => {
              const id = parseInt(openItemBtn.dataset.id, 10);
              closeGlobalGraphModal();
              openDrawer(id);
            };
          }
        } else if (popover) {
          popover.classList.add("hidden");
        }
      });

    } catch (err) {
      console.warn("Lỗi render đồ thị toàn cảnh:", err);
      if (canvasContainer) {
        canvasContainer.innerHTML = `<div class="flex items-center justify-center h-full text-xs font-mono text-slate-500">Chưa thể tải đồ thị: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    } else {
      return new Promise((resolve, reject) => {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
          const success = document.execCommand("copy");
          document.body.removeChild(textArea);
          if (success) resolve();
          else reject(new Error("execCommand failed"));
        } catch (err) {
          document.body.removeChild(textArea);
          reject(err);
        }
      });
    }
  }

  function attachCodeCopyButtons() {
    deepResearchContent.querySelectorAll("pre:not(.mermaid)").forEach(pre => {
      if (pre.querySelector(".copy-code-btn")) return;
      const btn = document.createElement("button");
      btn.className = "copy-code-btn";
      btn.textContent = "COPY";
      btn.addEventListener("click", () => {
        const codeEl = pre.querySelector("code");
        const code = codeEl ? codeEl.innerText : pre.innerText;
        copyTextToClipboard(code).then(() => {
          btn.textContent = "COPIED!";
          btn.style.color = "#38bdf8";
          showToast("Đã sao chép mã nguồn vào clipboard!", "info");
          setTimeout(() => {
            btn.textContent = "COPY";
            btn.style.color = "";
          }, 1500);
        }).catch(err => {
          console.error("Clipboard copy failed:", err);
          showToast("Không thể sao chép, vui lòng chọn thủ công", "info");
        });
      });
      pre.appendChild(btn);
    });
  }

  function generateAutoTOC() {
    autoToc.innerHTML = "";
    const headings = deepResearchContent.querySelectorAll("h2, h3");
    if (headings.length === 0) {
      autoToc.innerHTML = `<span class="text-slate-500 text-xs font-mono">Không có mục lục con.</span>`;
      return;
    }

    headings.forEach((h, index) => {
      const id = `toc-heading-${index}`;
      h.id = id;
      const link = document.createElement("a");
      link.href = `#${id}`;
      link.className = `toc-link ${h.tagName.toLowerCase() === "h2" ? "toc-h2" : "toc-h3"}`;
      link.textContent = h.textContent.replace(/^#+\s*/, "");
      link.addEventListener("click", (e) => {
        e.preventDefault();
        h.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      autoToc.appendChild(link);
    });
  }

  function handleDrawerScroll() {
    const el = deepResearchContent;
    const maxScroll = el.scrollHeight - el.clientHeight;
    if (maxScroll > 0) {
      const pct = (el.scrollTop / maxScroll) * 100;
      readingProgress.style.width = `${Math.min(100, Math.max(0, pct))}%`;
    }

    // ScrollSpy
    const headings = el.querySelectorAll("h2, h3");
    let activeId = "";
    headings.forEach(h => {
      const rect = h.getBoundingClientRect();
      const parentRect = el.getBoundingClientRect();
      if (rect.top - parentRect.top <= 140) {
        activeId = h.id;
      }
    });

    if (activeId) {
      autoToc.querySelectorAll(".toc-link").forEach(a => {
        if (a.getAttribute("href") === `#${activeId}`) {
          a.classList.add("active");
        } else {
          a.classList.remove("active");
        }
      });
    }
  }

  async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
    } finally {
      textArea.remove();
    }
  }

  async function renderAssociationsTab(itemId) {
    deepResearchContent.innerHTML = `
      <div class="p-8 text-center text-slate-400 font-mono text-xs flex flex-col items-center justify-center gap-3">
        <i data-lucide="loader-2" class="w-6 h-6 text-cyan-400 animate-spin"></i>
        <span>Đang nạp mạng lưới liên kết nơ-ron não bộ...</span>
      </div>
    `;
    hydrateIcons();

    try {
      const res = await fetch(`/api/v1/vault/${itemId}/associations`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const assocs = data.associations || [];

      if (assocs.length === 0) {
        deepResearchContent.innerHTML = `
          <div class="py-12 px-6 max-w-xl mx-auto text-center">
            <div class="w-12 h-12 mx-auto mb-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <i data-lucide="git-merge" class="w-6 h-6"></i>
            </div>
            <h3 class="text-base font-bold text-slate-200 mb-2">Chưa có liên kết nơ-ron nào</h3>
            <p class="text-xs text-slate-400 leading-relaxed mb-6 font-mono">
              Tài liệu này hiện chưa được đối chiếu đa chiều với các kiến thức khác trong Não Bộ, hoặc chưa phát hiện sự tương đồng/mâu thuẫn đáng kể.
            </p>
            <button id="btn-re-consolidate" class="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/30 text-xs font-semibold inline-flex items-center gap-2 transition-all">
              <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Kích hoạt Củng cố Tri thức Ngay
            </button>
          </div>
        `;
        hydrateIcons();
        const btnRe = document.getElementById("btn-re-consolidate");
        if (btnRe) {
          btnRe.onclick = async () => {
            btnRe.disabled = true;
            btnRe.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Đang phân tích nơ-ron...`;
            hydrateIcons();
            try {
              await curateItem(itemId, "APPROVE");
              showToast("Đã kích hoạt củng cố tri thức ngầm!", "success");
              setTimeout(() => renderAssociationsTab(itemId), 2000);
            } catch (err) {
              showToast("Lỗi củng cố: " + err.message, "error");
              btnRe.disabled = false;
            }
          };
        }
        return;
      }

      // Map relation types to colors & badges
      const relConfig = {
        REINFORCES: { label: "CỦNG CỐ (+1)", color: "emerald", icon: "shield-check", desc: "Tương đồng quan điểm hoặc bổ trợ luận điểm" },
        CONTRADICTS: { label: "MÂU THUẪN (CẢNH BÁO)", color: "rose", icon: "alert-triangle", desc: "Trực diện bất đồng cách tiếp cận hoặc kết luận" },
        EXTENDS: { label: "MỞ RỘNG", color: "indigo", icon: "git-branch", desc: "Kế thừa và đào sâu thêm khía cạnh mới" },
        ALTERNATIVE: { label: "THAY THẾ", color: "amber", icon: "shuffle", desc: "Phương pháp hoặc công cụ giải quyết bài toán tương đương" }
      };

      let html = `
        <div class="max-w-4xl mx-auto space-y-6 pb-12">
          <div class="flex items-center justify-between border-b border-[#1f293d] pb-4">
            <div>
              <h2 class="text-sm font-bold text-slate-100 flex items-center gap-2">
                <i data-lucide="git-merge" class="w-4 h-4 text-cyan-400"></i>
                <span>MẠNG LƯỚI NƠ-RON LIÊN KẾT ĐA CHIỀU</span>
              </h2>
              <p class="text-xs text-slate-400 mt-1">Phát hiện ${assocs.length} kết nối chéo với các tài liệu khác trong Cognitive Brain Vault.</p>
            </div>
            <span class="px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-mono text-xs">
              ${assocs.length} Connections
            </span>
          </div>

          <div class="space-y-4">
      `;

      assocs.forEach((a, idx) => {
        const type = (a.relation_type || "REINFORCES").toUpperCase();
        const conf = relConfig[type] || relConfig.REINFORCES;
        const targetTitle = a.target_title || `Tài liệu #${a.target_item_id}`;

        html += `
          <div class="rounded-xl bg-[#0d131f] border border-[#1f293d] p-4 transition-all hover:border-${conf.color}-500/40">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-2.5">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider bg-${conf.color}-500/15 text-${conf.color}-300 border border-${conf.color}-500/30 flex items-center gap-1">
                  <i data-lucide="${conf.icon}" class="w-3 h-3"></i>
                  ${conf.label}
                </span>
                <span class="text-[11px] text-slate-400 font-mono">${conf.desc}</span>
              </div>
              <button onclick="window.__openVaultDoc(${a.target_item_id})" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono flex items-center gap-1 transition-all">
                <span>Mở tài liệu đối chiếu</span>
                <i data-lucide="arrow-up-right" class="w-3 h-3"></i>
              </button>
            </div>

            <div class="mb-2">
              <a href="javascript:void(0)" onclick="window.__openVaultDoc(${a.target_item_id})" class="text-sm font-semibold text-slate-200 hover:text-cyan-300 transition-colors">
                ${escapeHtml(targetTitle)}
              </a>
            </div>

            <div class="p-3 rounded-lg bg-[#080d16] border border-[#172236] text-xs text-slate-300 leading-relaxed font-sans">
              <strong class="text-slate-400 font-mono text-[11px] block mb-1">Lý giải đối chiếu:</strong>
              ${escapeHtml(a.reasoning || "Không có lý giải cụ thể.")}
            </div>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;

      deepResearchContent.innerHTML = html;
      hydrateIcons();
    } catch (err) {
      deepResearchContent.innerHTML = `
        <div class="p-6 text-center text-rose-400 font-mono text-xs">
          Lỗi tải mạng lưới nơ-ron: ${escapeHtml(err.message)}
        </div>
      `;
    }
  }

  // Expose global opener for associations and cross-doc navigation
  window.__openVaultDoc = function(id) {
    if (!id) return;
    openDrawer(parseInt(id, 10));
  };

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

})();

