#!/usr/bin/env bash
# retry.sh — ClawClau v2: Retry a failed task with an improved prompt
#
# Usage: retry.sh <task-id> ["<improved prompt>"]
#
# If no improved prompt is given, the original prompt is reused with a failure
# context block prepended.
#
# Retry task IDs follow the pattern: <original-id>-retry-<n>

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

cc_require tmux jq

if [[ $# -lt 1 ]]; then
    echo "Usage: retry.sh <task-id> [\"<improved prompt>\"]" >&2; exit 1
fi

TASK_ID="$1"
NEW_PROMPT="${2:-}"

if ! cc_task_exists "$TASK_ID"; then
    echo "ERROR: task '$TASK_ID' not found in registry" >&2; exit 1
fi

# Check task is not running
SESSION=$(cc_tmux_session "$TASK_ID")
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "ERROR: task '$TASK_ID' is still running. Kill it first with kill.sh." >&2; exit 1
fi

# Read task metadata
STATUS=$(cc_task_get "$TASK_ID" "status")
RETRY_COUNT=$(cc_task_get "$TASK_ID" "retryCount")
MAX_RETRIES=$(cc_task_get "$TASK_ID" "maxRetries")
ORIGINAL_PROMPT=$(cc_task_get "$TASK_ID" "prompt")
LOG_FILE=$(cc_task_get "$TASK_ID" "log")
WORKDIR=$(cc_task_get "$TASK_ID" "workdir")
AGENT=$(cc_task_get "$TASK_ID" "agent")
MODE=$(cc_task_get "$TASK_ID" "mode")
WORKTREE=$(cc_task_get "$TASK_ID" "worktree")
BRANCH=$(cc_task_get "$TASK_ID" "branch")
DONE_CHECK=$(cc_task_get "$TASK_ID" "doneCheck")
MODEL=$(cc_task_get "$TASK_ID" "model")

# Enforce retry limit
RETRY_COUNT="${RETRY_COUNT:-0}"
MAX_RETRIES="${MAX_RETRIES:-3}"
if [[ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]]; then
    echo "ERROR: task '$TASK_ID' has reached max retries ($MAX_RETRIES/$MAX_RETRIES)" >&2
    echo "  To override, create a new task manually with spawn.sh" >&2
    exit 1
fi

# Build the new task ID
NEW_RETRY_COUNT=$((RETRY_COUNT + 1))
NEW_TASK_ID="${TASK_ID}-retry-${NEW_RETRY_COUNT}"

# Build the improved prompt
if [[ -z "$NEW_PROMPT" ]]; then
    # No custom prompt given — prepend failure context to original
    FAILURE_SNIPPET=""
    if [[ -f "$LOG_FILE" ]] && [[ -s "$LOG_FILE" ]]; then
        FAILURE_SNIPPET=$(cc_extract_text "$LOG_FILE" 300)
    fi

    STEER_HISTORY=$(jq -r --arg id "$TASK_ID" \
        '.[] | select(.id == $id) | .steerLog[] | "- [\(.at)] \(.message)"' \
        "$CC_REGISTRY" 2>/dev/null || true)

    CONTEXT_BLOCK="[Retry $NEW_RETRY_COUNT/$MAX_RETRIES — Previous attempt '$TASK_ID' failed]"
    [[ -n "$FAILURE_SNIPPET" ]] && CONTEXT_BLOCK+=$'\n'"Last output: $FAILURE_SNIPPET"
    [[ -n "$STEER_HISTORY" ]] && CONTEXT_BLOCK+=$'\n'"Steer history:"$'\n'"$STEER_HISTORY"
    CONTEXT_BLOCK+=$'\n'"Please retry carefully addressing the above issues."$'\n'

    NEW_PROMPT="${CONTEXT_BLOCK}"$'\n'"${ORIGINAL_PROMPT}"
else
    # Custom prompt given — just prepend minimal context
    NEW_PROMPT="[Retry $NEW_RETRY_COUNT/$MAX_RETRIES of task '$TASK_ID']"$'\n'"${NEW_PROMPT}"
fi

# Update parent task status to retrying
cc_task_update "$TASK_ID" "{\"status\":\"retrying\"}"

echo "Retrying: $TASK_ID → $NEW_TASK_ID (retry $NEW_RETRY_COUNT/$MAX_RETRIES)"
echo ""

# Build spawn.sh arguments
SPAWN_ARGS=(
    --agent "$AGENT"
    --timeout "$(cc_task_get "$TASK_ID" "timeout")"
    --max-retries "$MAX_RETRIES"
    --retry-count "$NEW_RETRY_COUNT"
    --parent "$TASK_ID"
)

[[ "$MODE" == "steerable" ]] && SPAWN_ARGS+=(--steerable)
[[ -n "$WORKTREE" ]] && [[ "$WORKTREE" != "null" ]] && SPAWN_ARGS+=(--worktree)
[[ -n "$BRANCH" ]] && [[ "$BRANCH" != "null" ]] && SPAWN_ARGS+=(--branch "$BRANCH")
[[ -n "$DONE_CHECK" ]] && [[ "$DONE_CHECK" != "null" ]] && SPAWN_ARGS+=(--done-check "$DONE_CHECK")
[[ -n "$MODEL" ]] && [[ "$MODEL" != "null" ]] && SPAWN_ARGS+=(--model "$MODEL")

INTERVAL=$(cc_task_get "$TASK_ID" "interval")
INTERVAL="${INTERVAL:-0}"
[[ "$INTERVAL" != "null" ]] && [[ "$INTERVAL" -gt 0 ]] && \
    SPAWN_ARGS+=(--interval "$INTERVAL")

exec "$SCRIPT_DIR/spawn.sh" "${SPAWN_ARGS[@]}" "$NEW_TASK_ID" "$NEW_PROMPT" "$WORKDIR"
