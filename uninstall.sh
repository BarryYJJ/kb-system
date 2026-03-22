#!/usr/bin/env bash
# OpenClaw KB System — Uninstaller
# Usage: bash uninstall.sh
# Custom: HOME=/path/to/dir bash uninstall.sh  (for testing)
#
# What this removes:
#   - $SCRIPTS_DIR/kb.py        (the CLI script)
#   - $KB_BASE/*/chroma_db/     (vector index data only)
#   - $CONFIG_DIR/openclaw.json (config file)
#
# What this PRESERVES:
#   - $KB_BASE/*/documents/     (markdown backups of all your content)
#   - $MEDIA_INBOUND            (your uploaded files)

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

INSTALL_ROOT="$HOME/.openclaw"
SCRIPTS_DIR="$INSTALL_ROOT/workspace/scripts"
KB_BASE="$INSTALL_ROOT/workspace/knowledge_bases"
MEDIA_INBOUND="$INSTALL_ROOT/media/inbound"
CONFIG_DIR="$INSTALL_ROOT/workspace/config"

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     OpenClaw KB System Uninstaller v1.0      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Warning: The following will be removed:${NC}"
echo "  - $SCRIPTS_DIR/kb.py"
echo "  - $KB_BASE/ai_research/chroma_db/"
echo "  - $KB_BASE/personal/chroma_db/"
echo "  - $CONFIG_DIR/openclaw.json"
echo ""
echo -e "${GREEN}Preserved (not touched):${NC}"
echo "  - $KB_BASE/*/documents/  (markdown backups)"
echo "  - $MEDIA_INBOUND         (your files)"
echo ""

# Confirm unless running in CI/test mode
if [ "${KB_UNINSTALL_FORCE:-}" != "1" ]; then
    read -r -p "Proceed? [y/N] " CONFIRM
    case "$CONFIRM" in
        [yY][eE][sS]|[yY]) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
    echo ""
fi

REMOVED=0

# Remove kb.py
if [ -f "$SCRIPTS_DIR/kb.py" ]; then
    rm -f "$SCRIPTS_DIR/kb.py"
    echo -e "  ${GREEN}✓${NC} Removed $SCRIPTS_DIR/kb.py"
    REMOVED=$((REMOVED + 1))
else
    echo -e "  ${YELLOW}-${NC} $SCRIPTS_DIR/kb.py not found (skipped)"
fi

# Remove chroma_db directories (vector index only, preserve documents/)
for kb in ai_research personal; do
    CHROMA_DIR="$KB_BASE/$kb/chroma_db"
    if [ -d "$CHROMA_DIR" ]; then
        rm -rf "$CHROMA_DIR"
        echo -e "  ${GREEN}✓${NC} Removed $CHROMA_DIR"
        REMOVED=$((REMOVED + 1))
    else
        echo -e "  ${YELLOW}-${NC} $CHROMA_DIR not found (skipped)"
    fi
done

# Remove config
if [ -f "$CONFIG_DIR/openclaw.json" ]; then
    rm -f "$CONFIG_DIR/openclaw.json"
    echo -e "  ${GREEN}✓${NC} Removed $CONFIG_DIR/openclaw.json"
    REMOVED=$((REMOVED + 1))
else
    echo -e "  ${YELLOW}-${NC} $CONFIG_DIR/openclaw.json not found (skipped)"
fi

echo ""
if [ "$REMOVED" -gt 0 ]; then
    echo -e "${GREEN}Uninstall complete.${NC} Removed $REMOVED item(s)."
else
    echo -e "${YELLOW}Nothing to remove — system was not installed.${NC}"
fi
echo ""
echo "To reinstall: bash install.sh"
echo ""
