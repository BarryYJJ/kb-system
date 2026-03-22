#!/usr/bin/env bash
# result.sh — ClawClau v2: Extract the full readable result from a task log
#
# Usage: result.sh <task-id> [--raw]
#
# Options:
#   --raw    Output the raw log file content without parsing

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

cc_require jq

RAW=false
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --raw) RAW=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

if [[ $# -lt 1 ]]; then
    echo "Usage: result.sh <task-id> [--raw]" >&2; exit 1
fi

TASK_ID="$1"

if ! cc_task_exists "$TASK_ID"; then
    echo "ERROR: task '$TASK_ID' not found in registry" >&2; exit 1
fi

LOG_FILE=$(cc_task_get "$TASK_ID" "log")
STATUS=$(cc_task_get "$TASK_ID" "status")
SESSION=$(cc_tmux_session "$TASK_ID")

# ── Task still running ─────────────────────────────────────────────────────
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[Task '$TASK_ID' is still running]"
    echo ""
    if [[ -f "$LOG_FILE" ]] && [[ -s "$LOG_FILE" ]]; then
        echo "── Partial output ──────────────────────"
        if $RAW; then
            cat "$LOG_FILE"
        else
            cc_extract_text "$LOG_FILE" 2000
        fi
    else
        echo "── Live tmux output ────────────────────"
        tmux capture-pane -t "$SESSION" -p -S - 2>/dev/null || echo "(capture failed)"
    fi
    exit 0
fi

# ── Task completed ─────────────────────────────────────────────────────────
if [[ ! -f "$LOG_FILE" ]]; then
    echo "ERROR: log file not found: $LOG_FILE" >&2
    echo "Task status: $STATUS" >&2
    exit 1
fi

if [[ ! -s "$LOG_FILE" ]]; then
    echo "Task '$TASK_ID' completed with status '$STATUS' but log is empty."
    exit 0
fi

if $RAW; then
    cat "$LOG_FILE"
else
    echo "── Result: $TASK_ID [$STATUS] ──────────────"
    cc_extract_text "$LOG_FILE" 10000
fi
