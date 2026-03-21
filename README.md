# kb-system

一套基于 ChromaDB + Sentence Transformers 的**本地语义知识库系统**，设计用于配合 AI Agent（如 OpenClaw）自动将飞书群消息内容（文章、PDF、图片、视频、小红书等）入库并支持语义检索。

---

## 功能概述

- **多源内容入库**：支持 PDF、图片（OCR）、B站/小红书视频（音频转写）、网页链接、纯文本
- **本地语义检索**：ChromaDB 向量存储 + 多语言 Sentence Transformers，完全本地运行，无需外部 API
- **Markdown 备份**：每条入库内容同时保存一份 Markdown 文件，人类可读
- **双 OCR 引擎**：RapidOCR + macOS Vision OCR 并行识别，自动选优

---

## 架构

```
用户发消息（飞书/任意渠道）
      ↓
主 Agent 识别内容类型
      ↓ 委派给 Claude Code
KB_PLAYBOOK.md 定义的 Pipeline
      ↓ 按需调用
  [OCR] [Whisper] [yt-dlp] [Jina Reader]
      ↓
kb.py curate → ChromaDB + Markdown 备份
```

---

## 核心文件

| 文件 | 说明 |
|------|------|
| `scripts/kb.py` | 知识库核心 CLI：存储（curate）、检索（query）、最近记录（recent） |
| `scripts/ocr_dual.sh` | 双引擎 OCR 脚本（RapidOCR + macOS Vision） |
| `docs/KB_PLAYBOOK.md` | 完整处理流程手册（Agent 参考文档） |
| `docs/FRAMEWORK.md` | 主 Agent × Claude Code 协作框架 |
| `config/openclaw.json.example` | 配置文件模板 |

---

## 快速开始

> **Python 版本要求**：>= 3.9

### 一键安装（推荐）

```bash
# 方式一：直接通过 curl 安装
curl -fsSL https://raw.githubusercontent.com/BarryYJJ/kb-system/main/install.sh | bash
```

```bash
# 方式二：clone 后本地安装
git clone https://github.com/BarryYJJ/kb-system /tmp/kb-system && cd /tmp/kb-system && bash install.sh
```

安装脚本会自动完成：检查依赖 → clone 仓库到 `~/.openclaw/workspace/kb-system/` → 安装 Python 依赖 → 创建必要目录 → 复制配置文件 → 运行验证测试 → 输出安装摘要。

**已安装过？** 再次运行 `install.sh` 会自动执行 `git pull` 更新，仅更新有变化的部分。

> **首次运行提示**：第一次执行时会自动下载多语言模型（`paraphrase-multilingual-MiniLM-L12-v2`，约 90 MB），请确保网络畅通。
>
> **正常警告（可忽略）**：
> - `Warning: You are sending unauthenticated requests to the HF Hub` — 未设 HF_TOKEN，不影响使用，可忽略
> - `BertModel LOAD REPORT — UNEXPECTED` — sentence-transformers 版本升级后的无害输出，可忽略

---

### 手动安装（备选）

> 推荐将仓库克隆到 `~/.openclaw/workspace/` 下，因为 KB_PLAYBOOK 中的命令路径基于此目录。

```bash
git clone https://github.com/BarryYJJ/kb-system ~/.openclaw/workspace/kb-system
cd ~/.openclaw/workspace/kb-system
pip3 install -r requirements.txt
cp config/openclaw.json.example config/openclaw.json
```

**OCR 支持（可选，macOS）**：

```bash
python -m venv ~/Desktop/rapidocr_venv
source ~/Desktop/rapidocr_venv/bin/activate
pip3 install rapidocr-onnxruntime
```

> `macos-vision-ocr` 为可选的 Swift CLI OCR 工具，需要 Xcode 编译。如果不安装，系统会自动降级为仅使用 RapidOCR。编译方法待补充。

**视频转写支持（可选）**：

```bash
pip3 install openai-whisper
brew install yt-dlp
```

### 2. 创建必要目录

```bash
mkdir -p ~/.openclaw/media/inbound
```

PDF、图片等附件需放入此目录，Agent 会从这里读取文件。

### 3. 存入内容

```bash
python3 scripts/kb.py curate \
  --kb ai_research \
  --title "Jensen Huang 演讲要点" \
  --source "webpage | https://example.com" \
  --content "演讲全文..." \
  --type webpage
```

支持的 `--kb` 值：`ai_research`（投研）、`personal`（个人）或任意自定义名称。

支持的 `--type` 值：`pdf`、`image_ocr`、`video`、`xiaohongshu`、`webpage`、`text`

### 4. 语义检索

```bash
python3 scripts/kb.py query --kb ai_research --question "数据中心投资机会"
```

> `relevance` 字段为 `1 - cosine_distance` 值，正常范围 0.05-0.4。>0.3 表示高匹配，<0.1 表示低匹配但仍有语义关联。<0 表示几乎无语义关联，可忽略。

### 5. 查看最近入库

```bash
python3 scripts/kb.py recent --kb ai_research --n 10
```

### 6. OCR 图片

```bash
# 配置路径（或直接修改脚本顶部变量）
export RAPIDOCR_VENV="$HOME/Desktop/rapidocr_venv"
export RAPIDOCR_DIR="path/to/RapidOCR/python"
export VISION_OCR_BIN="path/to/macos-vision-ocr"

bash scripts/ocr_dual.sh /path/to/image.png
```

---

## 依赖项（外部开源项目）

| 工具 | 用途 | 链接 |
|------|------|------|
| ChromaDB | 本地向量数据库 | https://github.com/chroma-core/chroma |
| Sentence Transformers | 文本向量化（`paraphrase-multilingual-MiniLM-L12-v2`） | https://github.com/UKPLab/sentence-transformers |
| RapidOCR | OCR 识别引擎 | https://github.com/RapidAI/RapidOCR |
| macOS Vision OCR | Apple Vision Framework OCR（macOS 专属） | 需自行编译 Swift CLI |
| yt-dlp | 视频/音频下载 | https://github.com/yt-dlp/yt-dlp |
| Whisper | 语音转文字 | https://github.com/openai/whisper |
| PyMuPDF | PDF 文字提取 | https://github.com/pymupdf/PyMuPDF |
| Jina Reader | 网页正文提取 | https://r.jina.ai |

---

## 数据存储位置

默认存储在 `~/.openclaw/workspace/knowledge_bases/{kb_name}/`：

```
knowledge_bases/
├── ai_research/
│   ├── chroma_db/      ← 向量数据库（自动创建）
│   └── documents/      ← Markdown 备份（自动创建）
└── personal/
    ├── chroma_db/
    └── documents/
```

修改 `kb.py` 第 21 行的 `BASE_DIR` 可自定义存储路径。

---

## 配合 AI Agent 使用

本系统设计为 AI Agent 的后端存储层。详见：

- `docs/KB_PLAYBOOK.md`：Agent 应如何处理不同来源的内容
- `docs/FRAMEWORK.md`：主 Agent 与 Claude Code 的分工协作模式

---

## License

MIT
