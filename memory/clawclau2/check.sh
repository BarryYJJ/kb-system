#!/usr/bin/env bash
# check.sh — ClawClau v2: Check task status (deterministic, no polling)
#
# Usage:
#   check.sh              # list all tasks
#   check.sh <task-id>    # show single task details

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

cc_require tmux jq

if [[ ! -f "$CC_REGISTRY" ]]; then
    echo "No registry found. Run spawn.sh first."
    exit 0
fi

# ── Single task ────────────────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    TASK_ID="$1"

    if ! cc_task_exists "$TASK_ID"; then
        echo "ERROR: task '$TASK_ID' not found in registry" >&2; exit 1
    fi

    # Read all fields
    TASK_JSON=$(jq -r --arg id "$TASK_ID" '.[] | select(.id == $id)' "$CC_REGISTRY")

    # Live status: tmux is the ground truth for "running"
    SESSION=$(cc_tmux_session "$TASK_ID")
    LIVE_STATUS=$(echo "$TASK_JSON" | jq -r '.status')

    if tmux has-session -t "$SESSION" 2>/dev/null; then
        LIVE_STATUS="running"
    fi

    # Format fields
    AGENT=$(echo "$TASK_JSON"    | jq -r '.agent // "?"')
    MODE=$(echo "$TASK_JSON"     | jq -r '.mode // "?"')
    PROMPT=$(echo "$TASK_JSON"   | jq -r '.prompt // ""')
    WORKDIR=$(echo "$TASK_JSON"  | jq -r '.agentWorkdir // .workdir // ""')
    STARTED=$(echo "$TASK_JSON"  | jq -r '.startedAt // 0')
    TIMEOUT=$(echo "$TASK_JSON"  | jq -r '.timeout // 600')
    LOG=$(echo "$TASK_JSON"      | jq -r '.log // ""')
    BRANCH=$(echo "$TASK_JSON"   | jq -r '.branch // ""')
    RETRIES=$(echo "$TASK_JSON"  | jq -r '.retryCount // 0')
    MAX_R=$(echo "$TASK_JSON"    | jq -r '.maxRetries // 3')
    PARENT=$(echo "$TASK_JSON"   | jq -r '.parentTaskId // ""')

    # Human-readable start time
    START_HUMAN=$(date -r "$((STARTED / 1000))" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$STARTED")

    echo "══════════════════════════════════════"
    echo "Task:     $TASK_ID"
    echo "Status:   $LIVE_STATUS"
    echo "Agent:    $AGENT ($MODE)"
    echo "Session:  $SESSION"
    [[ -n "$BRANCH" ]] && echo "Branch:   $BRANCH"
    echo "Started:  $START_HUMAN"
    echo "Timeout:  ${TIMEOUT}s"
    echo "Retries:  $RETRIES / $MAX_R"
    [[ -n "$PARENT" ]] && echo "Parent:   $PARENT"
    echo "Workdir:  $WORKDIR"
    echo "Log:      $LOG"
    echo "Prompt:   $PROMPT"
    echo ""

    # Show current output
    if [[ "$LIVE_STATUS" == "running" ]]; then
        echo "── Live output (tmux) ──────────────────"
        tmux capture-pane -t "$SESSION" -p 2>/dev/null | tail -15 || echo "(empty)"
    elif [[ -n "$LOG" ]] && [[ -f "$LOG" ]]; then
        echo "── Result (log) ────────────────────────"
        # Use lib extractor for clean text
        TEXT=$(cc_extract_text "$LOG" 1000)
        if [[ -n "$TEXT" ]]; then
            echo "$TEXT"
        else
            echo "(log exists but no extractable text)"
        fi
    fi

    # Show steer log if any entries
    STEER_COUNT=$(echo "$TASK_JSON" | jq '.steerLog | length' 2>/dev/null || echo 0)
    if [[ "$STEER_COUNT" -gt 0 ]]; then
        echo ""
        echo "── Steer history ($STEER_COUNT entries) ────────"
        echo "$TASK_JSON" | jq -r '.steerLog[] | "  [\(.at)] \(.message)"' 2>/dev/null
    fi
    echo "══════════════════════════════════════"

# ── All tasks ──────────────────────────────────────────────────────────────
else
    TOTAL=$(jq 'length' "$CC_REGISTRY" 2>/dev/null || echo 0)

    if [[ "$TOTAL" -eq 0 ]]; then
        echo "No tasks registered."
        exit 0
    fi

    echo "══ ClawClau v2 Tasks ($TOTAL) ══════════════════"
    printf "%-20s %-8s %-10s %-10s %s\n" "ID" "AGENT" "STATUS" "RETRIES" "STARTED"
    echo "──────────────────────────────────────────────────────"

    jq -r '.[] | [.id, .agent, .status, ((.retryCount // 0 | tostring) + "/" + (.maxRetries // 3 | tostring)), (.startedAt | . / 1000 | floor | tostring)] | @tsv' \
        "$CC_REGISTRY" 2>/dev/null \
    | while IFS=$'\t' read -r id agent status retries started_ts; do
        # Override status if tmux session alive
        SESSION=$(cc_tmux_session "$id")
        if tmux has-session -t "$SESSION" 2>/dev/null; then
            status="running"
        fi

        START_HUMAN=$(date -r "$started_ts" "+%m-%d %H:%M" 2>/dev/null || echo "$started_ts")
        printf "%-20s %-8s %-10s %-10s %s\n" "$id" "$agent" "$status" "$retries" "$START_HUMAN"
    done

    echo ""
    RUNNING=$(jq '[.[] | select(.status == "running")] | length' "$CC_REGISTRY" 2>/dev/null || echo 0)
    DONE=$(jq '[.[] | select(.status == "done")] | length' "$CC_REGISTRY" 2>/dev/null || echo 0)
    FAILED=$(jq '[.[] | select(.status == "failed" or .status == "timeout")] | length' "$CC_REGISTRY" 2>/dev/null || echo 0)
    echo "Summary: $RUNNING running, $DONE done, $FAILED failed/timeout"
fi
