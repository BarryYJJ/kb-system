# OpenClaw — Product Requirements Document

> **Version**: 2026.3.12 | **Last Updated**: 2026-03-19 | **Status**: Production

---

## 1. Architecture Overview

OpenClaw is a personal AI agent platform that routes messages across communication channels (Feishu, WhatsApp), orchestrates LLM calls across multiple providers, manages persistent knowledge bases, runs scheduled automation jobs, and exposes a plugin/skill ecosystem for extensible capabilities.

### Directory Layout

```
~/.openclaw/
├── openclaw.json            # Master configuration
├── exec-approvals.json      # Command execution approval socket
├── agents/                  # Agent instances & session history
│   └── main/
│       ├── agent/           # Per-agent model & auth configs
│       └── sessions/        # 200+ conversation session dirs
├── browser/                 # Chromium instance for web automation (1.7 GB)
├── cron/                    # Cron job definitions (jobs.json, 32+ jobs)
├── delivery-queue/          # Async message delivery with retry
├── extensions/              # Installed plugins (acpx, feishu, whatsapp)
├── hooks/                   # System lifecycle hooks
├── identity/                # Device keypairs (EdDSA)
├── logs/                    # Gateway & error logs (~14 MB)
├── media/                   # Inbound uploads & browser cache (165 MB)
├── memory/                  # SQLite session memory (main.sqlite)
├── skills/                  # Installed skills with source & venv (784 MB)
├── venv/                    # Shared Python 3.14+ virtual environment
├── workspace/               # Main working directory (1.1 GB)
├── workspace-claude/        # Claude Code integration workspace
└── workspace-whatsapp/      # WhatsApp-specific workspace
```

### Key Architectural Patterns

| Pattern | Detail |
|---|---|
| LLM Routing | Multi-provider with per-request model selection |
| Session Memory | SQLite WAL-mode (main.sqlite, schema v4) |
| Vector Search | ChromaDB + paraphrase-multilingual-MiniLM-L12-v2 |
| Communication | Feishu (primary, 13 groups) + WhatsApp (1 user) |
| Scheduling | Cron + heartbeat-wake, Asia/Shanghai timezone |
| Async Delivery | Queue with exponential retry, up to 5 attempts |
| Identity | EdDSA device keypair, created 2026-02-06 |
| Gateway | HTTP, port 18789, loopback mode, token auth |

---

## 2. Platform Configuration

### Gateway

| Parameter | Value |
|---|---|
| Port | 18789 |
| Mode | Loopback (local) |
| Auth | 24-byte hex token |
| Log level | Info / Error / Debug |

### LLM Providers

| Provider | Model | Context | Notes |
|---|---|---|---|
| Claude (custom proxy) | claude-opus-4.6 | — | Primary reasoning model; via onemillon.nextmind.space |
| MiniMax | MiniMax-M2.5 | 200K | Cost-tracked per 1K tokens |
| Zhipu GLM | GLM-5-Turbo | 128K | Config default; $0.001/$0.001 per 1K |
| Moonshot / Kimi | kimi-coding | 256K | Code-heavy tasks |

Provider auth profiles are stored in `/agents/main/agent/auth-profiles.json` (Moonshot, MiniMax, Kimi keys) and in the master `openclaw.json` auth section.

### Agent Settings

- **Single main agent** (`agents/main/`)
- Each agent carries its own `models.json` and `auth-profiles.json`
- Session isolation per conversation directory

### Enabled Plugins

| Plugin | Package | Purpose |
|---|---|---|
| acpx | internal | ACP protocol for Claude Code integration |
| feishu | @openclaw/feishu v2026.2.25 | Feishu messaging bridge |
| whatsapp | internal | WhatsApp messaging bridge |

### Enabled Hooks

| Hook | Trigger | Function |
|---|---|---|
| boot-md | Startup | Load bootstrap markdown context |
| bootstrap | Agent init | System-level context injection |
| command-logging | Every command | Append to `/logs/commands.log` |
| memory | Session end | Persist session notes to SQLite |
| self-improvement | Session end | Reflective learning loop |

### External Tool Integrations

| Tool | Integration Point |
|---|---|
| Brave Search | API key configured; available as tool |
| Notion | API key in skills config |
| 1Password | Credential lookup in skills config |

---

## 3. Communication Channels

### Feishu (飞书)

- **App ID**: `cli_a903dd0f9c62dbde`
- **Streaming**: Enabled
- **Group Allowlist**: 13 groups (investment research + discussion)
- **Policy**: Allowlist-based; ignores non-allowlisted senders
- **Deduplication**: Feishu-specific dedup cache at `/feishu/`

### WhatsApp

- **Allowed Sender**: +85246237097 (1 user)
- **Max Media Size**: 50 MB
- **Self-chat Mode**: Enabled
- **DM Policy**: Allowlist
- **Workspace**: `/workspace-whatsapp/`

---

## 4. Skill System

Each skill lives under `/skills/{skill-name}/` with the following layout:

```
{skill-name}/
├── SKILL.md       # Trigger keywords, usage docs
├── README.md      # Full developer documentation
├── app.py         # Flask backend
├── static/app.js  # Frontend (Vanilla JS)
├── templates/     # Jinja2 HTML templates
├── venv/          # Isolated Python environment
└── .git/          # Version control
```

### Installed Skills

| Skill | Purpose | Notable Detail |
|---|---|---|
| deepseek-ocr | OCR for images, PDFs, videos | Apple Silicon (Metal GPU); 14 MB core; Flask 1770 LOC + JS 3033 LOC; 5-level precision |
| calendar | Apple Calendar CRUD | Query / add / complete / postpone events; emoji completion tags |
| xiaohongshu | Xiaohongshu content extraction | Auto-pagination, multi-image post support |
| techcrunch-ai-news | RSS aggregation | TechCrunch AI feed; seen-dedup via .json |
| x-ai-news | X (Twitter) AI news scraper | Browser-based; 4-hour interval |
| naval-tracker | Naval Ravikant quote monitoring | Disabled cron job; X scraper backend |
| find-skills | Skill discovery | Query installed skill catalog |
| ifind-trading-log | Trading log analysis | iFind data source integration |

### Skill Activation

`SKILL.md` declares:
- Name & description
- Trigger keywords (matched by agent)
- Chinese time definitions (早上 5–11:59, 中午 11–13:59, etc.)
- Implementation and dependency notes

Skills are hot-loaded; no gateway restart required.

---

## 5. Knowledge Base System

**Location**: `/workspace/knowledge_bases/`

### Knowledge Bases

| KB Name | Topic | Backend |
|---|---|---|
| ai_research | Investment research, AI/market intel | ChromaDB + SQLite |
| personal | Personal development, barbell strategy, neuroscience | ChromaDB + SQLite |

### Embedding Model

`paraphrase-multilingual-MiniLM-L12-v2` — multilingual sentence embeddings; supports Chinese + English.

### Chunking Strategy

- Max chunk size: 6,000 characters
- Auto text-splitting on ingest
- Context tree organization via `.brv/` directories

### KB CLI (`/workspace/scripts/kb.py` — 180 LOC)

| Command | Function |
|---|---|
| `curate` | Add document with auto-embedding |
| `query` | Semantic search with top-k retrieval |
| `recent` | List recently added documents |

### KB Processing Pipeline (`KB_PLAYBOOK.md`)

Four ingestion pipelines based on content type:

| Pipeline | Content Type | Processing Steps |
|---|---|---|
| A | PDF | Extract text → chunk → embed → store |
| B | Image | deepseek-ocr → text → chunk → embed → store |
| C | Web link | Browser fetch / yt-dlp (Bilibili) / browser automation (Xiaohongshu) → text → embed |
| D | Raw text | Direct chunk → embed → store |

Special handling:
- **Bilibili**: `yt-dlp` video download + Whisper transcription
- **Xiaohongshu**: Chromium browser automation + page parsing
- **General web**: HTTP fetch with fallback to browser

---

## 6. Cron Job System

**Config**: `/cron/jobs.json` (40 KB, 32+ active jobs)

### Job Schema

```json
{
  "schedule": "cron" | "every",
  "expr": "0 6 * * 1",
  "tz": "Asia/Shanghai",
  "wakeMode": "next-heartbeat" | "now",
  "payload": "systemEvent" | "agentTurn",
  "delivery": { "channel": "feishu", "to": "<group_id>" },
  "state": {
    "nextRunAtMs": ...,
    "lastRunAtMs": ...,
    "consecutiveErrors": 0,
    "lastStatus": "ok"
  }
}
```

### Job Categories

| Category | Examples | Frequency |
|---|---|---|
| Market Intelligence | Stock watchlist reports | Weekdays 9:20–10:00 AM |
| Content Aggregation | TechCrunch AI RSS, X AI feed | Every 3–4 hours |
| Weekly Admin | Folder creation | Monday 6 AM |
| Social Monitoring | Naval Ravikant Twitter | Disabled |
| Newsletter Aggregation | Various sources | Daily |
| Trading Logs | iFind log sync | Scheduled |

All jobs deliver to specific Feishu groups or isolated agent sessions.

---

## 7. Automation Scripts

**Location**: `/workspace/scripts/`

| Script | Size | Function |
|---|---|---|
| `kb.py` | 180 LOC | Knowledge base CLI (curate / query / recent) |
| `ai_news_rss.py` | 13 KB | RSS feed aggregation with dedup |
| `ai_xfeed.py` | 13 KB | X (Twitter) feed monitoring |
| `ai_xfeed_browser.py` | 3 KB | X scraper via Chromium |
| `ai_x_browser.py` | 16 KB | X browser automation core |
| `ai_x_parse.py` | 8 KB | X content parsing & formatting |
| `ocr_dual.sh` | 2 KB | DeepSeek-OCR fallback wrapper |

---

## 8. Memory & Session Persistence

### Session Memory (`/memory/main.sqlite`)

- SQLite3, schema version 4, 69 KB
- Stores: conversation context, session notes, key facts
- Updated by the `memory` hook at session end

### Workspace Memory (`/workspace/memory/`)

- Dated markdown files: 2026-02-07 through 2026-03-17
- Contents: session startup notes, cron execution logs, error/timeout notes
- Human-readable; versioned alongside workspace

### Session Storage (`/agents/main/sessions/`)

- 200+ session directories
- Full conversation history per session
- Isolated per agent instance

---

## 9. Delivery Queue

**Location**: `/delivery-queue/`

- Async message delivery with retry logic
- Up to 5 retry attempts per message
- Tracks: `retryCount`, `lastError`, `nextRetryAt`
- Mirror tracking for session reconciliation
- Failed messages remain in queue for inspection

---

## 10. Multi-Workspace Architecture

| Workspace | Path | Purpose |
|---|---|---|
| Main | `/workspace/` | Default; knowledge bases, scripts, memory (1.1 GB) |
| Claude Code | `/workspace-claude/` | Claude Code integration (116 KB) |
| WhatsApp | `/workspace-whatsapp/` | WhatsApp-specific context (112 KB) |

Each workspace contains:
- `.openclaw/` — local config override
- `IDENTITY.md` — agent identity definition
- `SOUL.md` — values and behavior directives
- `USER.md` — user profile
- `AGENTS.md` — agent collaboration instructions
- `BOOTSTRAP.md` — session startup playbook

---

## 11. Security & Identity

### Device Identity (`/identity/device.json`)

| Field | Detail |
|---|---|
| deviceId | SHA256 hash |
| Keypair | EdDSA (public + private) |
| Created | 2026-02-06 |

### Access Controls

| Mechanism | Function |
|---|---|
| Gateway token | 24-byte hex; required on all requests |
| Exec approvals | `/exec-approvals.json` socket; command-level ACL |
| Channel policies | Allowlist / open / pairing modes per channel |
| Credential isolation | API keys split across agent-level auth-profiles |

---

## 12. Infrastructure & Logging

### Python Environment

- Python 3.14+ shared venv at `/venv/` (230 MB)
- Per-skill isolated venvs in `/skills/{name}/venv/`
- Shared packages: ChromaDB, sentence-transformers, Flask, yt-dlp, Whisper

### Browser Automation

- Dedicated Chromium instance at `/browser/openclaw/` (1.7 GB)
- Used by: Xiaohongshu scraper, X scraper, general web automation
- Cache at `/media/browser/` (82 dirs)

### Log Files

| File | Size | Content |
|---|---|---|
| `logs/gateway.log` | 10.1 MB | All gateway operations |
| `logs/gateway.err.log` | 3.2 MB | Error stream |
| `logs/config-audit.jsonl` | — | Configuration change history |
| `logs/commands.log` | — | CLI command audit trail |

---

## 13. Version Management

| Item | Value |
|---|---|
| Current version | 2026.3.12 |
| Last update check | 2026-03-19 |
| Latest available | 2026.3.12 |
| Config backups | `openclaw.json.bak` through `.bak.4` |

---

## 14. System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        OpenClaw Core                         │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │   Feishu    │    │  WhatsApp   │    │  Direct / API   │  │
│  │ (13 groups) │    │  (1 user)   │    │    Gateway      │  │
│  └──────┬──────┘    └──────┬──────┘    └────────┬────────┘  │
│         └─────────────────┼───────────────────── ┘          │
│                           ▼                                  │
│                  ┌────────────────┐                          │
│                  │  Main Agent    │                          │
│                  │  (port 18789)  │                          │
│                  └───────┬────────┘                          │
│           ┌──────────────┼──────────────────┐                │
│           ▼              ▼                  ▼                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │  LLM Router  │ │  Skill Loader│ │   Cron Scheduler     │ │
│  │  Claude      │ │  8+ skills   │ │   32+ jobs           │ │
│  │  MiniMax     │ │  Hot-reload  │ │   Asia/Shanghai TZ   │ │
│  │  GLM-5       │ └──────────────┘ └──────────────────────┘ │
│  │  Kimi        │                                            │
│  └──────────────┘                                            │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐                  │
│  │  Knowledge Base │  │  Session Memory  │                  │
│  │  ChromaDB x2    │  │  SQLite (69 KB)  │                  │
│  │  MiniLM embeds  │  │  Schema v4       │                  │
│  └─────────────────┘  └──────────────────┘                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Chromium Browser  (1.7 GB — scraping & automation)  │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 15. Key File Reference

| File | Purpose |
|---|---|
| `~/.openclaw/openclaw.json` | Master platform configuration |
| `~/.openclaw/cron/jobs.json` | All scheduled job definitions |
| `~/.openclaw/memory/main.sqlite` | Session memory database |
| `~/.openclaw/workspace/KB_PLAYBOOK.md` | Knowledge base ingestion runbook |
| `~/.openclaw/workspace/BOOTSTRAP.md` | Agent startup playbook |
| `~/.openclaw/workspace/scripts/kb.py` | Knowledge base CLI |
| `~/.openclaw/identity/device.json` | Device identity & keypair |
| `~/.openclaw/agents/main/agent/auth-profiles.json` | LLM API credentials |
| `~/.openclaw/skills/{name}/SKILL.md` | Per-skill trigger & usage docs |
