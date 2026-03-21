#!/usr/bin/env bash
set -euo pipefail

# ─── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; }
info() { echo -e "${BLUE}ℹ️  $*${NC}"; }

echo ""
echo -e "${RED}🗑️  kb-system 卸载程序${NC}"
echo "=================="
echo ""

INSTALL_DIR="$HOME/.openclaw/workspace/kb-system"
INBOUND_DIR="$HOME/.openclaw/media/inbound"
KB_DATA_DIR="$HOME/.openclaw/workspace/knowledge_bases"

# ─── 确认卸载 ─────────────────────────────────────────────────────────────────
warn "即将卸载 kb-system，此操作不可逆。"
echo ""
echo "  将删除："
echo "    • $INSTALL_DIR（代码目录）"

# 检查 inbound 是否为空
if [[ -d "$INBOUND_DIR" ]]; then
    INBOUND_COUNT=$(find "$INBOUND_DIR" -maxdepth 1 -mindepth 1 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$INBOUND_COUNT" -eq 0 ]]; then
        echo "    • $INBOUND_DIR（空目录，将一并删除）"
        DELETE_INBOUND=1
    else
        echo "    • $INBOUND_DIR（非空，将保留）"
        DELETE_INBOUND=0
    fi
else
    DELETE_INBOUND=0
fi

echo ""
echo "  将保留："
echo "    • $KB_DATA_DIR（知识库数据，默认保留）"
echo ""

read -r -p "确认卸载？[y/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo ""
    info "已取消卸载。"
    exit 0
fi

echo ""

# ─── 询问是否删除知识库数据 ──────────────────────────────────────────────────
DELETE_KB_DATA=0
if [[ -d "$KB_DATA_DIR" ]]; then
    echo ""
    warn "是否同时删除知识库数据？（向量数据库和 Markdown 备份）"
    echo "  路径：$KB_DATA_DIR"
    warn "此操作不可逆，所有入库内容将永久丢失！"
    echo ""
    read -r -p "删除知识库数据？[y/N] " CONFIRM_KB
    if [[ "$CONFIRM_KB" =~ ^[Yy]$ ]]; then
        DELETE_KB_DATA=1
    fi
fi

echo ""

# ─── 卸载 pip 依赖 ────────────────────────────────────────────────────────────
REQ_FILE="$INSTALL_DIR/requirements.txt"
if [[ -f "$REQ_FILE" ]]; then
    info "卸载 pip 依赖..."
    # 提取包名（去掉版本约束）
    PACKAGES=$(grep -v '^\s*#' "$REQ_FILE" | grep -v '^\s*$' | sed 's/[>=<].*//' | tr '\n' ' ')
    if [[ -n "$PACKAGES" ]]; then
        # shellcheck disable=SC2086
        pip3 uninstall -y $PACKAGES 2>&1 | sed 's/^/  /' || warn "部分包卸载失败（可能从未安装），继续..."
        ok "pip 依赖已卸载"
    fi
else
    warn "未找到 requirements.txt，跳过 pip 卸载"
fi

echo ""

# ─── 删除代码目录 ─────────────────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    ok "已删除：$INSTALL_DIR"
else
    warn "目录不存在，跳过：$INSTALL_DIR"
fi

# ─── 删除 inbound 目录（如果为空）────────────────────────────────────────────
if [[ "$DELETE_INBOUND" -eq 1 && -d "$INBOUND_DIR" ]]; then
    rmdir "$INBOUND_DIR" 2>/dev/null && ok "已删除空目录：$INBOUND_DIR" || warn "删除 $INBOUND_DIR 失败"
fi

# ─── 删除知识库数据（可选）──────────────────────────────────────────────────
if [[ "$DELETE_KB_DATA" -eq 1 && -d "$KB_DATA_DIR" ]]; then
    rm -rf "$KB_DATA_DIR"
    ok "已删除知识库数据：$KB_DATA_DIR"
else
    ok "知识库数据已保留：$KB_DATA_DIR"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "kb-system 卸载完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
