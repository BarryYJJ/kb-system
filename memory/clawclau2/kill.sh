#!/usr/bin/env bash
# kill.sh — ClawClau v2: Terminate a running task
#
# Usage: kill.sh <task-id> [--cleanup-worktree]
#
# Options:
#   --cleanup-worktree    Remove the git worktree after killing

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

cc_require tmux jq

CLEANUP_WORKTREE=false
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cleanup-worktree) CLEANUP_WORKTREE=true; shift ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

if [[ $# -lt 1 ]]; then
    echo "Usage: kill.sh <task-id> [--cleanup-worktree]" >&2; exit 1
fi

TASK_ID="$1"

if ! cc_task_exists "$TASK_ID"; then
    echo "ERROR: task '$TASK_ID' not found in registry" >&2; exit 1
fi

SESSION=$(cc_tmux_session "$TASK_ID")
WORKTREE=$(cc_task_get "$TASK_ID" "worktree")
WORKDIR=$(cc_task_get "$TASK_ID" "workdir")

# Kill tmux session
if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    echo "Killed: tmux session '$SESSION'"
else
    echo "Session '$SESSION' already gone (task may have completed)"
fi

# Update registry
cc_task_update "$TASK_ID" "{\"status\":\"killed\",\"killedAt\":$(cc_now_ms)}"
echo "Registry: task '$TASK_ID' marked as killed"

# Cleanup worktree (optional)
if $CLEANUP_WORKTREE && [[ -n "$WORKTREE" ]] && [[ "$WORKTREE" != "null" ]]; then
    if [[ -d "$WORKTREE" ]]; then
        # Find repo root from original workdir
        REPO_ROOT=$(git -C "$WORKDIR" rev-parse --show-toplevel 2>/dev/null || echo "")
        if [[ -n "$REPO_ROOT" ]]; then
            git -C "$REPO_ROOT" worktree remove "$WORKTREE" --force 2>/dev/null && \
                echo "Worktree removed: $WORKTREE" || \
                echo "WARNING: Failed to remove worktree '$WORKTREE' (may need manual cleanup)"
        else
            echo "WARNING: Cannot find repo root for worktree cleanup"
        fi
    else
        echo "Worktree '$WORKTREE' already removed"
    fi
fi
