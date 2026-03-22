#!/usr/bin/env bash
# steer.sh — ClawClau v2: Send a mid-task correction to a running agent
#
# Usage: steer.sh <task-id> "<message>"
#
# Behavior by mode:
#   steerable (claude interactive) — injects message directly into the running session
#   codex                          — injects message into the running session
#   print (claude -p)              — not steer-capable; offers kill+retry instead

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

cc_require tmux jq

if [[ $# -lt 2 ]]; then
    echo "Usage: steer.sh <task-id> \"<message>\"" >&2; exit 1
fi

TASK_ID="$1"
MESSAGE="$2"

if ! cc_task_exists "$TASK_ID"; then
    echo "ERROR: task '$TASK_ID' not found in registry" >&2; exit 1
fi

SESSION=$(cc_tmux_session "$TASK_ID")
MODE=$(cc_task_get "$TASK_ID" "mode")
STATUS=$(cc_task_get "$TASK_ID" "status")

# Check task is alive
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "ERROR: task '$TASK_ID' is not running (status: $STATUS)" >&2; exit 1
fi

# ── Print mode: not directly steer-capable ────────────────────────────────
if [[ "$MODE" == "print" ]]; then
    echo "WARNING: Task '$TASK_ID' is running in print mode (claude -p)."
    echo "  Print mode tasks cannot receive interactive steering."
    echo ""
    echo "Options:"
    echo "  1. Kill and retry with amended prompt:"
    echo "     kill.sh $TASK_ID && retry.sh $TASK_ID \"$MESSAGE\""
    echo ""
    echo "  2. Spawn a new steerable task:"
    echo "     spawn.sh --steerable <new-id> \"$MESSAGE\" <workdir>"
    exit 1
fi

# ── Steerable / Codex: inject message ─────────────────────────────────────
# Write message to temp file and use paste-buffer to handle special chars
STEER_FILE=$(mktemp /tmp/clawclau-steer-XXXXXX.txt)
printf '%s' "$MESSAGE" > "$STEER_FILE"

tmux load-buffer -b "steer-$TASK_ID" "$STEER_FILE"
tmux paste-buffer -t "$SESSION" -b "steer-$TASK_ID" -p
tmux send-keys -t "$SESSION" "" Enter

rm -f "$STEER_FILE"

# Log the steering action in registry
cc_task_steer_log "$TASK_ID" "$MESSAGE"

echo "OK: steered '$TASK_ID'"
echo "  Message: $MESSAGE"
