# 📦 Tri Thức Kỹ Thuật Dự Án: solofounder-ai/solofounder

> **Mô tả ngắn**: AI virtual team for solopreneurs. One request — SoloFounder assembles specialist roles, designs the optimal workflow, and executes with review gates at every stage

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/1778571810053730](https://www.facebook.com/reel/1778571810053730)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/solofounder-ai/solofounder](https://github.com/solofounder-ai/solofounder)
- **Chỉ số cộng đồng**: ⭐ **3** stars | 🍴 **0** forks
- **Ngôn ngữ chủ đạo**: `JavaScript`
- **Giấy phép bản quyền (License)**: `MIT`
- **Chủ đề (Topics)**: `ai`, `ai-agents`, `ai-team`, `claude-code`, `claude-code-plugin`, `developer-tools`, `solofounder`, `solopreneur`, `virtual-team`
- **Cập nhật gần nhất**: 2026-06-03T17:34:16Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `AI & Autonomous Agents`
- **Kiến Trúc Kỹ Thuật**: `Autonomous Multi-Agent`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > SoloFounder giải quyết bài toán của founder một người cần thực hiện nhiều vai trò chuyên biệt (phát triển phần mềm, marketing, pháp lý, thiết kế…) mà không phải thuê đội ngũ thực. Nó tự động lắp ráp đội ngũ ảo AI chuyên môn, tạo quy trình làm việc tối ưu và thực hiện với các cổng xem xét ở mỗi giai đoạn. Dùng khi bạn cần một giải pháp end-to-end linh hoạt, không có pipeline cứng, để nhanh chóng chuyển ý tưởng thành sản phẩm.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Xây dựng MVP phần mềm từ ý tưởng đến bản phát hành
  * Thiết kế và triển khai chiến dịch marketing bao gồm nội dung, quảng cáo và phân tích
  * Kiểm tra hợp đồng pháp lý, tạo tài liệu tuân thủ và đưa ra lời khuyên
  * Thiết kế thương hiệu, logo và hướng dẫn kiểu dáng cho sản phẩm

- **Các Thành Phần / API Cốt Lõi**:
  * TeamOrchestrator
  * SpecialistAgent
  * WorkflowGenerator
  * ReviewGate

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
npm install solofounder
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```javascript
const { SoloFounder } = require('solofounder');

async function demo() {
  // Định nghĩa mục tiêu kinh doanh
  const goal = { description: 'Build a landing page for a SaaS product', techStack: ['React', 'TailwindCSS'] };

  // Tự động lắp ráp đội ngũ chuyên gia
  const team = await SoloFounder.assembleTeam(goal);
  console.log('Assembled team:', team.map(a => a.role));

  // Thực hiện quy trình làm việc được tạo ra
  const result = await SoloFounder.execute(team, goal);
  console.log('Output:', result);
}

demo().catch(console.error);
```

## 📖 6. Nội Dung README.md Chính Thức
<div align="center">

![SoloFounder — One founder commanding a virtual team of specialists](assets/solofounder-banner.jpg)

# SoloFounder

### Your AI Virtual Team

**One founder. Any challenge. A full team assembled in seconds.**

[![Version](https://img.shields.io/badge/version-0.2.0-blue?style=for-the-badge)]()
[![AI Powered](https://img.shields.io/badge/AI-Powered-cc785c?style=for-the-badge)]()
[![Cursor](https://img.shields.io/badge/Cursor-Plugin-22d3ee?style=for-the-badge)]()
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen?style=for-the-badge)]()
[![License](https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge)]()

---

*SoloFounder dynamically composes specialist teams and optimized workflows*
*for any business challenge — software, marketing, legal, operations, design.*
*No templates. No hardcoded pipelines. Every flow is generated fresh.*

[Getting Started](#getting-started) &#8226; [How It Works](#how-it-works) &#8226; [Iron Laws](#the-five-iron-laws) &#8226; [Architecture](#architecture) &#8226; [Capabilities](#capabilities)

</div>

---

## The Problem

You're a solo founder. You need to ship software, design brands, plan marketing, review contracts, architect infrastructure — all by yourself.

AI coding assistants give you a single generalist. That's like hiring one intern for every department.

**SoloFounder gives you a full company.**

For every challenge you face, SoloFounder assembles a team of specialists — not generic "agents," but deeply specialized roles like *"React Native 0.84 + Expo SDK 55 Specialist with EAS Build expertise"* or *"B2B SaaS Content Strategist with PLG funnel experience."*

Each specialist knows what to check, what to flag, and when to stop. They review each other's work. They resolve conflicts through structured arbitration. And after every completed project, the system learns — making your next project faster and higher quality.

---

## How It Works

```
  YOU                          SOLOFOUNDER
  ───                          ────────────

  "Build me a                  ┌─────────────────────────┐
   language learning    ──────>│  1. CLARIFY             │
   app"                        │     Ask smart questions  │
                               │     with options &       │
                               │     recommendations      │
                               └────────────┬────────────┘
                                            │
  Review & answer              ┌────────────v────────────┐
  questions            <──────>│  2. DESIGN THE FLOW     │
                               │     Generate optimal     │
                               │     stage sequence        │
                               └────────────┬────────────┘
                                            │
  Approve team                 ┌────────────v────────────┐
  composition          <──────>│  3. ASSEMBLE THE TEAM   │
                               │     Generate specialist  │
                               │     roles with deep      │
                               │     domain expertise     │
                               └────────────┬────────────┘
                                            │
                               ┌────────────v────────────┐
  Approve each stage   <──────>│  4. EXECUTE & VERIFY    │
  deliverable                  │     Specialists work in  │
                               │     parallel, review     │
                               │     each other, verify   │
                               │     everything           │
                               └────────────┬────────────┘
                                            │
                               ┌────────────v────────────┐
                               │  5. LEARN               │
                               │     Analyze what worked, │
                               │     update knowledge for │
                               │     next project         │
                               └─────────────────────────┘
```

### The Clarification Phase

SoloFounder doesn't jump straight to work. It asks you the right questions first — each with **concrete options** and a **recommended path**:

```
Q1: Who is the primary audience for this app?
  1. Children (6-12) learning their first foreign language
  2. Adults learning conversationally for travel
  3. Professionals needing business-level fluency
  4. Heritage speakers reconnecting with family language
  → Recommended: 2 — largest addressable market with clearest monetization path

Q2: What's the core learning mechanic?
  1. Spaced repetition flashcards (Anki-style)
  2. Conversational AI practice (chat-based)
  3. Gamified lessons with progression (Duolingo-style)
  4. Immersion through real content (news, videos, podcasts)
  → Recommended: 2 — highest engagement ceiling, best use of AI capabilities
```

Only after understanding your vision does it design the flow.

### Progressive Flow Generation

SoloFounder doesn't commit to a tech stack before deciding one. Flows are generated in phases:

```
PHASE 1 — Generated immediately (no stack assumptions)
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Discovery   │───>│  Research &  │───>│   [EXPAND]   │
│  & Brainstorm│    │  Architecture│    │              │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
    Architecture decides: React Native 0.84 + Supabase + Claude API
                                               │
PHASE 2 — Generated AFTER decisions            v
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Design  │─>│  Brand   │─>│  Visual  │─>│  Plan &  │─>│Implement │
│  Research│  │  Book    │  │  Design  │  │  Review  │  │  (TDD)   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

A *"React Native Specialist"* is only created **after** the architecture stage decides on React Native. No premature commitments.

### Structured Artifacts

Every stage defines exactly what it produces — not just a filename, but a **contract**:

```
Stage 2: Research & Architecture

  Artifacts:
    Research Report → .solofounder/stages/architecture/research.md
      Format:        markdown with comparison tables
      Sections:      options evaluated, comparison matrix, runtime performance, maturity
      Complete when: every recommendation cites a live source, 3+ options per decision

    Architecture Decision Record → .solofounder/stages/architecture/adr.md
      Format:        markdown
      Sections:      decisions, rationale, rejected alternatives
      Complete when: every decision has rationale tied to research findings

  Completion Checklist:
    [x] Research covers 3+ alternatives per major decision
    [x] Every recommendation cites live documentation
    [x] Runtime performance comparison included
    [x] No unresolved exceptions
    [x] User approves
```

Downstream stages know exactly what they're receiving. Long sessions stay on track.

---

## The Five Iron Laws

Every agent, every stage, every role operates under these laws. They are not guidelines — they are **enforcement mechanisms**.

| | Law |
|:---:|-----|
| **I** | **NO FALLBACKS. NO SILENT FAILURES. NO TEMP SOLUTIONS.** Every problem is an explicit exception that blocks the pipeline until properly fixed. |
| **II** | **ONE CORRECT PATH.** Never offer alternatives to the correct approach. Never degrade gracefully. If the correct path fails, STOP with full context. |
| **III** | **EVERY EXCEPTION IS ACTIONABLE.** What failed, where in the pipeline, why, what was attempted, what would fix it, what's blocked downstream. |
| **IV** | **IMPLEMENTATION COSTS NOTHING.** Time and budget do not exist. Never trade quality for speed. The only cost is poor quality. |
| **V** | **EVERYTHING IS REVIEWED AND VERIFIED.** Nothing moves forward unchecked. Evidence before claims. No output moves forward without review and verification. |

These laws include **rationalization prevention** — when an agent catches itself thinking *"this is good enough for now"* or *"I'll fix this later"*, the Iron Laws mandate: **STOP. Do it right.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SOLOFOUNDER SYSTEM                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              META-SKILLS (The Brain)                  │    │
│  │                                                       │    │
│  │  Bootstrap → Flow Composer → Role Generator → Learn   │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│                    generates & uses                           │
│                            │                                 │
│  ┌─────────────────────────v───────────────────────────┐    │
│  │            CAPABILITIES (The Toolbox)                 │    │
│  │                                                       │    │
│  │  TDD  |  Debugging  |  Verify  |  Research  |  Mockups│   │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│                    generates at runtime                       │
│                            │                                 │
│  ┌─────────────────────────v───────────────────────────┐    │
│  │          DYNAMIC LAYER (Generated Per-Request)        │    │
│  │                                                       │    │
│  │  Flows  |  Stages  |  Specialist Roles  |  Artifacts  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          CROSS-PROJECT LEARNING (Compounds)           │    │
│  │                                                       │    │
│  │  ~/.solofounder/learning/                             │    │
│  │    insights.md   — loaded every session                │    │
│  │    stacks/       — tech-specific patterns              │    │
│  │    domains/      — domain-specific patterns            │    │
│  │    roles/        — role effectiveness tracking         │    │
│  │    conflicts/    — recurring conflict patterns         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Static Layer (Ships with the plugin)

| Component | What It Does |
|-----------|-------------|
| **Bootstrap** | Loads Iron Laws, cross-project learning, prior state at session start |
| **Flow Composer** | Clarifies requirements, designs optimal stage sequence, orchestrates execution |
| **Role Generator** | Creates deeply specialized roles with 3-layer composition |
| **Conversation Analysis** | Post-completion learning engine — 5 analysis dimensions |
| **TDD Methodology** | RED-GREEN-REFACTOR enforcement. No code without failing test first |
| **Systematic Debugging** | 4-phase root cause investigation before any fix attempt |
| **Verification** | Evidence before claims. Run commands, read output, then assert |
| **Live Research** | Verify tech recommendations against live docs. Design research from Dribbble/Behance |
| **Exception Enforcement** | Iron Laws applied to every output with rationalization prevention |
| **Mockup Server** | Browser-based visual preview with multi-variant voting |

### Dynamic Layer (Generated per-request)

Everything else is generated fresh: flows, stages, specialist roles, artifact definitions, completion checklists. No templates. No standard pipeline.

---

## Capabilities

### Specialist Roles — Not Generic Agents

SoloFounder doesn't use generic "Backend Agent" or "Frontend Agent" roles. Every specialist is deeply specialized for your specific project:

```diff
- Generic (useless):
  "Backend Agent"
  Review: Check for security issues. Verify performance.

+ SoloFounder (actionable):
  "ASP.NET 10 + Entity Framework Core 10 + Azure SQL Backend Specialist"
  Review:
    - EF Core: no raw SQL with string interpolation (parameterized only)
    - EF Core: .Include() chains max 3 levels, use projection beyond
    - Auth: tokens in httpOnly cookies, never localStorage
    - Connection strings: Azure Managed Identity, not passwords
    - MediatR handlers: one handler per file, validation in pipeline
```

Roles are composed from **three layers**:

1. **Foundation** — core expertise, review methodology, output format
2. **Stack Specialization** — technology-specific concerns, patterns, anti-patterns
3. **Cross-Project Learning** — patterns discovered in past projects (grows over time)

### Conflict Resolution

When specialists disagree, SoloFounder doesn't just pick one — it generates an **arbiter** specialized for the conflict domain:

```
Performance Specialist: "Use server-side rendering for initial load"
UX Specialist: "Client-side rendering gives better interactivity"
                    │
                    v
        ┌───────────────────────┐
        │   ARBITER GENERATED   │
        │  (Technical Product   │
        │   Manager)            │
        │                       │
        │  Iteration 1: Propose │
        │  Iteration 2: Refine  │
        │  Iteration 3: Final   │
        │                       │
        │  Still disagree?      │
        │  → Escalate to user   │
        │    with full context   │
        └───────────────────────┘
```

### Deep Research

When research is needed, SoloFounder goes deep — multiple sources, cross-referenced, structured deliverables:

```
Research: Mobile Framework Selection

Landscape Compared
  Framework       Runtime Perf   Bundle Size   Ecosystem   Maturity
  React Native    Near-native    7-12 MB       Massive     Mature (0.84)
  Flutter         Near-native    5-8 MB        Large       Mature (3.41)
  Kotlin Multi.   Native         Minimal       Growing     Stable (2.3)

Risks & Gotchas
  - React Native: New Architecture is now default since 0.82 — verify all libraries support it
  - Flutter: Platform channel overhead for heavy native API usage

Recommendation
  React Native — largest ecosystem, proven at scale, New Architecture
  default since 0.82. Source: reactnative.dev/blog (verified live)
```

### Visual Brainstorming

The mockup server enables visual collaboration directly in your browser:

- **Multi-variant comparison** — see design options side by side
- **Click to vote** — select preferred variants
- **Per-variant feedback** — annotate what works and what doesn't
- **Design references** — curated from Dribbble/Behance, saved and persisted
- **Brand books** — generated for new projects, enforced as contracts

### Cross-Project Learning

SoloFounder gets smarter with every project:

```
Project 1: "EF Core lazy loading caused N+1 in production"
                          │
                          v
Project 2: Role automatically includes:
           "Exception: EF Core lazy loading in API controller → BLOCKS (N+1)"
```

After every completed flow, **Conversation Analysis** examines five dimensions:

1. **Wasted Work** — what was produced and thrown away?
2. **Misalignment** — where did intent and execution diverge?
3. **Exception Archaeology** — could issues have been caught earlier?
4. **Role Effectiveness** — which specialists gave advice that was used?
5. **Flow Effectiveness** — were stages in the right order?

Insights feed back into role definitions, flow generation, and cross-project learning files.

---

## Getting Started

### Install from Marketplace

```bash
/plugin install solofounder
```

That's it. One command. SoloFounder loads automatically on every session.

### Alternative: Install from GitHub

If SoloFounder isn't in the official marketplace yet, add it as a custom marketplace:

```bash
# Add the marketplace (one time)
/plugin marketplace add solofounder-ai/solofounder

# Install the plugin
/plugin install solofounder@solofounder
```

### Cursor

```bash
/add-plugin solofounder
```

### Usage

Just start talking. SoloFounder bootstraps automatically on every session.

```
You: "Build a subscription analytics dashboard for my SaaS"

SoloFounder:
  → Asks clarifying questions (audience, metrics, integrations, quality bar)
  → Designs flow (research → architecture → design → implement)
  → Assembles team (Product Analyst, Data Viz Specialist, React Architect, ...)
  → Executes stages with review gates
  → Learns for next time
```

It works for any domain:

| Domain | Example Request |
|--------|----------------|
| **Software** | "Build a real-time collaboration feature" |
| **Design** | "Redesign our onboarding flow" |
| **Marketing** | "Create a content strategy for our B2B SaaS" |
| **Legal** | "Review this partnership agreement" |
| **Operations** | "Design our incident response process" |
| **Strategy** | "Analyze our pricing model vs competitors" |

---

## Project Structure

```
solofounder/
  skills/                          # Meta-skills (the brain)
    using-solofounder/SKILL.md     #   Session bootstrap
    flow-composer/                  #   Flow design & orchestration
      SKILL.md
      stage-execution.md
    role-generator/SKILL.md        #   Specialist role creation
    conversation-analysis/SKILL.md #   Post-completion learning

  capabilities/                    # Battle-tested disciplines (the toolbox)
    tdd-methodology/SKILL.md       #   RED-GREEN-REFACTOR
    systematic-debugging/          #   4-phase root cause investigation
    verification/SKILL.md          #   Evidence before claims
    exception-enforcement/SKILL.md #   Iron Laws enforcement
    mockup-server/                 #   Visual preview & voting
    live-research/SKILL.md         #   Tech verification & design research

  hooks/                           # Platform integration
  .claude-plugin/                  # Claude Code manifest
  .cursor-plugin/                  # Cursor manifest
```

### Runtime State (Generated per-project)

```
your-project/.solofounder/
  flow.md                          # Current flow definition
  artifacts.md                     # Registry of all produced artifacts
  roles/                           # Specialist role definitions
  stages/                          # Stage deliverables
  design-references/               # Curated design inspiration
  brand/                           # Brand book (new projects)
  insights/                        # Stage metrics & conflict records
  retrospective.md                 # Post-completion analysis
```

---

## What Makes This Different

| Traditional AI Assistant | SoloFounder |
|-------------------------|-------------|
| One generalist agent | Specialized team per challenge |
| Jumps straight to code | Clarifies, researches, designs, then executes |
| Generic advice | Stack-specific review checklists |
| Silent failures | Explicit exceptions that block the pipeline |
| Forgets everything | Cross-project learning compounds |
| "Good enough" | Iron Law IV: Implementation costs nothing |
| Trusts its own output | Everything reviewed and verified |
| Static workflow | Dynamic flow generated per request |
| Hardcoded stages | Progressive — discovery first, implementation after decisions |

---

## Spec

Full product design: [`docs/solofounder/specs/2026-04-01-solofounder-design.md`](docs/solofounder/specs/2026-04-01-solofounder-design.md)

---

<div align="center">

**Built for founders who refuse to compromise on quality.**

*SoloFounder is open source. Contributions welcome.*

</div>