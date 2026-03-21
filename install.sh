#!/usr/bin/env bash
set -euo pipefail

# ─── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${BLUE}ℹ️  $*${NC}"; }

# ─── 欢迎 ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}🧠 kb-system 安装程序${NC}"
echo "=================="
echo ""

# ─── 操作系统检测 ─────────────────────────────────────────────────────────────
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    info "检测到操作系统：macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    info "检测到操作系统：Linux"
else
    warn "未识别的操作系统：$OSTYPE，将按 Linux 处理"
    OS="linux"
fi

# ─── 依赖检查 ────────────────────────────────────────────────────────────────
MISSING_DEPS=0

# Python 3 >= 3.9
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 9 ]]; then
        ok "Python $PY_VER"
    else
        err "Python 版本过低：$PY_VER（需要 >= 3.9）"
        if [[ "$OS" == "macos" ]]; then
            echo "    安装命令：brew install python@3.11"
        else
            echo "    安装命令：sudo apt install python3.11  # Ubuntu/Debian"
            echo "              sudo dnf install python3.11  # Fedora/RHEL"
        fi
        MISSING_DEPS=1
    fi
else
    err "未找到 python3"
    if [[ "$OS" == "macos" ]]; then
        echo "    安装命令：brew install python@3.11"
    else
        echo "    安装命令：sudo apt install python3  # Ubuntu/Debian"
    fi
    MISSING_DEPS=1
fi

# pip3
if command -v pip3 &>/dev/null; then
    ok "pip3 $(pip3 --version | awk '{print $2}')"
else
    err "未找到 pip3"
    echo "    安装命令：python3 -m ensurepip --upgrade"
    MISSING_DEPS=1
fi

# python3 与 pip3 版本一致性检查
if command -v python3 &>/dev/null && command -v pip3 &>/dev/null; then
    PIP_PY_VER=$(pip3 --version | grep -oE 'python [0-9]+\.[0-9]+' | awk '{print $2}')
    if [[ -n "$PIP_PY_VER" && "$PIP_PY_VER" != "$PY_VER" ]]; then
        warn "pip3 关联的 Python 版本（$PIP_PY_VER）与 python3（$PY_VER）不一致"
        warn "将使用 'python3 -m pip install' 以确保安装到正确的 Python 环境"
    fi
fi

# git
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    err "未找到 git"
    if [[ "$OS" == "macos" ]]; then
        echo "    安装命令：brew install git  或  xcode-select --install"
    else
        echo "    安装命令：sudo apt install git  # Ubuntu/Debian"
    fi
    MISSING_DEPS=1
fi

if [[ "$MISSING_DEPS" -ne 0 ]]; then
    echo ""
    err "请先安装上述缺失依赖，再重新运行此脚本。"
    exit 1
fi

echo ""

# ─── 安装目标路径 ─────────────────────────────────────────────────────────────
INSTALL_DIR="$HOME/.openclaw/workspace/kb-system"
REPO_URL="https://github.com/BarryYJJ/kb-system"

info "安装目标：$INSTALL_DIR"

# ─── Clone 或 Pull ────────────────────────────────────────────────────────────
IS_UPDATE=0
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "检测到已有安装，执行 git pull 更新..."
    OLD_HASH=$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || echo "")
    git -C "$INSTALL_DIR" pull --ff-only 2>&1 | sed 's/^/  /'
    NEW_HASH=$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || echo "")
    if [[ "$OLD_HASH" != "$NEW_HASH" ]]; then
        ok "已更新到最新版本（$NEW_HASH）"
        IS_UPDATE=1
    else
        ok "已是最新版本（$NEW_HASH）"
    fi
elif [[ -d "$INSTALL_DIR" ]]; then
    warn "目录已存在但不是 git 仓库，跳过 clone"
else
    info "克隆仓库..."
    git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | sed 's/^/  /'
    ok "克隆完成"
fi

cd "$INSTALL_DIR"
CURRENT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo ""

# ─── 安装 Python 依赖 ─────────────────────────────────────────────────────────
info "安装 Python 依赖（requirements.txt）..."
python3 -m pip install -r requirements.txt 2>&1 | sed 's/^/  /'
ok "Python 依赖安装完成"

echo ""

# ─── 创建必要目录 ─────────────────────────────────────────────────────────────
mkdir -p "$HOME/.openclaw/media/inbound"
ok "目录已就绪：~/.openclaw/media/inbound"

# ─── 配置文件 ─────────────────────────────────────────────────────────────────
CONFIG_FILE="$INSTALL_DIR/config/openclaw.json"
CONFIG_EXAMPLE="$INSTALL_DIR/config/openclaw.json.example"
CONFIG_CREATED=0

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        ok "配置文件已创建：config/openclaw.json（从模板复制）"
        CONFIG_CREATED=1
    else
        warn "未找到配置模板文件 config/openclaw.json.example"
    fi
else
    ok "配置文件已存在：config/openclaw.json（跳过）"
fi

echo ""

# ─── 安装验证 ─────────────────────────────────────────────────────────────────
info "运行安装验证测试..."
VERIFY_OK=0
VERIFY_KB="kb_install_test"

# 验证 curate
if python3 scripts/kb.py curate \
    --kb "$VERIFY_KB" \
    --title "安装验证测试" \
    --source "text | install_test" \
    --content "kb-system 安装验证 install verification test" \
    --type text \
    2>&1 | sed 's/^/  /'; then

    # 验证 query
    if python3 scripts/kb.py query \
        --kb "$VERIFY_KB" \
        --question "安装验证" \
        2>&1 | sed 's/^/  /'; then
        ok "安装验证通过"
        VERIFY_OK=1
    else
        warn "安装完成但 query 验证失败，请检查输出"
    fi
else
    warn "安装完成但 curate 验证失败，请检查输出"
fi

# 清理测试数据
VERIFY_DB="$HOME/.openclaw/workspace/knowledge_bases/$VERIFY_KB"
if [[ -d "$VERIFY_DB" ]]; then
    rm -rf "$VERIFY_DB"
fi

echo ""

# ─── 可选功能检测 ─────────────────────────────────────────────────────────────
OCR_STATUS="❌ 未安装"
WHISPER_STATUS="❌ 未安装"
YTDLP_STATUS="❌ 未安装"

if python3 -c "import rapidocr_onnxruntime" 2>/dev/null; then
    OCR_STATUS="✅ rapidocr-onnxruntime 已安装"
fi

if python3 -c "import whisper" 2>/dev/null; then
    WHISPER_STATUS="✅ openai-whisper 已安装"
fi

if command -v yt-dlp &>/dev/null; then
    YTDLP_STATUS="✅ yt-dlp $(yt-dlp --version 2>/dev/null)"
fi

# ─── 安装摘要 ─────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 kb-system 安装完成${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 安装位置   ：$INSTALL_DIR"
echo "🐍 Python 版本：$PY_VER"
echo "📦 版本 (git) ：$CURRENT_HASH"
echo ""
echo "─── 可选功能状态 ───────────────────────────"
echo "  OCR          ：$OCR_STATUS"
echo "  视频转写     ：$WHISPER_STATUS"
echo "  视频下载     ：$YTDLP_STATUS"
echo ""
echo "─── 接下来要做 ─────────────────────────────"

if [[ "$CONFIG_CREATED" -eq 1 ]]; then
    echo -e "  ${YELLOW}1. 编辑配置文件，填入飞书群 ID 等真实配置：${NC}"
    echo "     $CONFIG_FILE"
    echo ""
fi

echo "  2. 存入第一条内容："
echo "     python3 $INSTALL_DIR/scripts/kb.py curate \\"
echo "       --kb personal --title \"标题\" --source \"text | 来源\" \\"
echo "       --content \"内容\" --type text"
echo ""
echo "  3. 语义检索："
echo "     python3 $INSTALL_DIR/scripts/kb.py query --kb personal --question \"问题\""
echo ""

if [[ "$OCR_STATUS" == "❌ 未安装" ]]; then
    echo "─── 安装可选功能（OCR 支持）───────────────"
    echo "  python3 -m venv ~/Desktop/rapidocr_venv"
    echo "  source ~/Desktop/rapidocr_venv/bin/activate"
    echo "  pip3 install rapidocr-onnxruntime"
    echo ""
fi

if [[ "$WHISPER_STATUS" == "❌ 未安装" || "$YTDLP_STATUS" == "❌ 未安装" ]]; then
    echo "─── 安装可选功能（视频转写）───────────────"
    [[ "$WHISPER_STATUS" == "❌ 未安装" ]] && echo "  pip3 install openai-whisper"
    if [[ "$YTDLP_STATUS" == "❌ 未安装" ]]; then
        if [[ "$OS" == "macos" ]]; then
            echo "  brew install yt-dlp"
        else
            echo "  pip3 install yt-dlp"
        fi
    fi
    echo ""
fi

echo "─── 接入 AI Agent ──────────────────────────"
echo -e "  ${YELLOW}要接入 OpenClaw Agent，请将以下文档加载到 Agent 系统提示：${NC}"
echo "  • $INSTALL_DIR/docs/KB_PLAYBOOK.md"
echo "  • $INSTALL_DIR/docs/FRAMEWORK.md"
echo ""

if [[ "$VERIFY_OK" -ne 1 ]]; then
    warn "安装验证未完全通过。首次运行时会下载 ~90MB 的模型文件，请确保网络畅通后重试。"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
