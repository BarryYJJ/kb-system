#!/usr/bin/env bash
# OpenClaw KB System — One-click Installer
# Usage:  bash install.sh
# Custom: HOME=/path/to/dir bash install.sh  (for isolated testing)

set -euo pipefail

# ─── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ─── Paths ─────────────────────────────────────────────────────────────────────
INSTALL_ROOT="$HOME/.openclaw"
SCRIPTS_DIR="$INSTALL_ROOT/workspace/scripts"
KB_BASE="$INSTALL_ROOT/workspace/knowledge_bases"
MEDIA_INBOUND="$INSTALL_ROOT/media/inbound"
CONFIG_DIR="$INSTALL_ROOT/workspace/config"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     OpenClaw KB System Installer v1.0        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "Install root : $INSTALL_ROOT"
echo ""

# ─── Step 1: Python check ──────────────────────────────────────────────────────
echo -e "${BLUE}[1/6]${NC} Checking Python 3..."
if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}✗ python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo -e "  ${GREEN}✓${NC} $PY_VER"

# ─── Step 2: Install Python dependencies ──────────────────────────────────────
echo -e "${BLUE}[2/6]${NC} Checking Python dependencies..."

_check_or_install() {
    local pkg="$1"
    local import_name="${2:-$1}"
    if KMP_DUPLICATE_LIB_OK=TRUE python3 -c "import ${import_name}" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $pkg already available"
    else
        echo -e "  Installing $pkg ..."
        if pip3 install "$pkg" --quiet 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $pkg installed"
        elif pip3 install "$pkg" --user --quiet 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $pkg installed (--user)"
        else
            echo -e "  ${RED}✗ Failed to install $pkg${NC}"
            exit 1
        fi
    fi
}

_check_or_install "chromadb" "chromadb"
_check_or_install "sentence-transformers" "sentence_transformers"

# ─── Step 3: Create directories ────────────────────────────────────────────────
echo -e "${BLUE}[3/6]${NC} Creating directories..."
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$KB_BASE/ai_research/documents"
mkdir -p "$KB_BASE/personal/documents"
mkdir -p "$MEDIA_INBOUND"
mkdir -p "$CONFIG_DIR"
echo -e "  ${GREEN}✓${NC} $SCRIPTS_DIR"
echo -e "  ${GREEN}✓${NC} $KB_BASE/ai_research/"
echo -e "  ${GREEN}✓${NC} $KB_BASE/personal/"
echo -e "  ${GREEN}✓${NC} $MEDIA_INBOUND"
echo -e "  ${GREEN}✓${NC} $CONFIG_DIR"

# ─── Step 4: Install kb.py ─────────────────────────────────────────────────────
echo -e "${BLUE}[4/6]${NC} Installing kb.py..."
KB_SRC="$SELF_DIR/scripts/kb.py"
if [ ! -f "$KB_SRC" ]; then
    echo -e "  ${RED}✗ Cannot find $KB_SRC${NC}"
    exit 1
fi

# Only overwrite if newer or not present
if [ ! -f "$SCRIPTS_DIR/kb.py" ] || [ "$KB_SRC" -nt "$SCRIPTS_DIR/kb.py" ]; then
    cp "$KB_SRC" "$SCRIPTS_DIR/kb.py"
    chmod +x "$SCRIPTS_DIR/kb.py"
    echo -e "  ${GREEN}✓${NC} kb.py installed → $SCRIPTS_DIR/kb.py"
else
    echo -e "  ${GREEN}✓${NC} kb.py already up to date"
fi

# ─── Step 5: Create config ─────────────────────────────────────────────────────
echo -e "${BLUE}[5/6]${NC} Creating config..."
CONFIG_FILE="$CONFIG_DIR/openclaw.json"
if [ ! -f "$CONFIG_FILE" ]; then
    python3 - <<PYEOF
import json, os
config = {
    "kb": {
        "base_dir": "$KB_BASE",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "chunk_size": 6000,
        "knowledge_bases": ["ai_research", "personal"]
    },
    "media": {
        "inbound": "$MEDIA_INBOUND"
    },
    "installed_at": __import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    "version": "1.0.0"
}
with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print("  Config written.")
PYEOF
    echo -e "  ${GREEN}✓${NC} $CONFIG_FILE"
else
    echo -e "  ${GREEN}✓${NC} Config already exists (skipped)"
fi

# ─── Step 6: Verification tests ────────────────────────────────────────────────
echo -e "${BLUE}[6/6]${NC} Running verification tests..."

KB_PY="$SCRIPTS_DIR/kb.py"
TMPFILE="$(mktemp /tmp/kb_install_test_XXXXXX.json)"
trap 'rm -f "$TMPFILE"' EXIT

# Test curate
echo -n "  curate ... "
if KMP_DUPLICATE_LIB_OK=TRUE python3 "$KB_PY" curate \
    --kb "personal" \
    --title "Install Verification" \
    --source "install.sh | auto-test" \
    --content "OpenClaw KB system installation verification test. 知识库安装验证。This entry is created automatically." \
    --type "text" > "$TMPFILE" 2>/dev/null; then
    DOC_ID=$(python3 -c "import json; d=json.load(open('$TMPFILE')); print(d.get('doc_id','?'))")
    echo -e "${GREEN}PASSED${NC} — doc_id: $DOC_ID"
else
    echo -e "${RED}FAILED${NC}"
    exit 1
fi

# Test query
echo -n "  query  ... "
if KMP_DUPLICATE_LIB_OK=TRUE python3 "$KB_PY" query \
    --kb "personal" \
    --question "installation verification 知识库" \
    --n 1 > "$TMPFILE" 2>/dev/null; then
    HITS=$(python3 -c "import json; d=json.load(open('$TMPFILE')); print(len(d.get('results',[])))")
    if [ "$HITS" -gt 0 ]; then
        RELEVANCE=$(python3 -c "import json; d=json.load(open('$TMPFILE')); print(d['results'][0].get('relevance','?'))")
        echo -e "${GREEN}PASSED${NC} — $HITS hit(s), relevance: $RELEVANCE"
    else
        echo -e "${RED}FAILED${NC} — 0 results returned"
        exit 1
    fi
else
    echo -e "${RED}FAILED${NC}"
    exit 1
fi

# Test recent
echo -n "  recent ... "
if KMP_DUPLICATE_LIB_OK=TRUE python3 "$KB_PY" recent \
    --kb "personal" \
    --n 5 > "$TMPFILE" 2>/dev/null; then
    COUNT=$(python3 -c "import json; d=json.load(open('$TMPFILE')); print(len(d.get('documents',[])))")
    echo -e "${GREEN}PASSED${NC} — $COUNT recent doc(s)"
else
    echo -e "${RED}FAILED${NC}"
    exit 1
fi

# ─── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Installation Complete!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  kb.py        : $SCRIPTS_DIR/kb.py"
echo "  Knowledge DB : $KB_BASE/"
echo "  Media inbox  : $MEDIA_INBOUND"
echo "  Config       : $CONFIG_FILE"
echo ""
echo "Quick start:"
echo "  python3 $SCRIPTS_DIR/kb.py curate \\"
echo "    --kb personal --title 'My Note' --source 'manual' --content 'text'"
echo "  python3 $SCRIPTS_DIR/kb.py query --kb personal --question 'search terms'"
echo "  python3 $SCRIPTS_DIR/kb.py recent --kb personal"
echo ""
