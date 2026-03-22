#!/usr/bin/env bash
# spawn.sh — ClawClau v2: Spawn a Claude Code or Codex agent task
#
# Usage: spawn.sh [OPTIONS] <task-id> "<prompt>" [workdir]
#
# Options:
#   --agent <claude|codex>    agent type (default: claude)
#   --steerable               interactive mode — enables mid-task steering
#   --worktree                isolate in a dedicated git worktree
#   --branch <name>           worktree branch name (default: clawclau/<id>)
#   --timeout <sec>           timeout in seconds (default: 600)
#   --interval <sec>          progress report interval, 0=off (default: 0)
#   --max-retries <n>         max auto-retry count (default: 3)
#   --done-check <script>     path to Definition of Done check script
#   --model <name>            model to pass to the agent

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

# ── Defaults ───────────────────────────────────────────────────────────────
AGENT="claude"
STEERABLE=false
USE_WORKTREE=false
BRANCH=""
TIMEOUT=600
INTERVAL=0
MAX_RETRIES=3
DONE_CHECK=""
MODEL=""
PARENT_TASK_ID=""
RETRY_COUNT=0

# ── Parse flags ────────────────────────────────────────────────────────────
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent)        AGENT="$2";         shift 2 ;;
        --steerable)    STEERABLE=true;     shift   ;;
        --worktree)     USE_WORKTREE=true;  shift   ;;
        --branch)       BRANCH="$2";        shift 2 ;;
        --timeout)      TIMEOUT="$2";       shift 2 ;;
        --interval)     INTERVAL="$2";      shift 2 ;;
        --max-retries)  MAX_RETRIES="$2";   shift 2 ;;
        --done-check)   DONE_CHECK="$2";    shift 2 ;;
        --model)        MODEL="$2";         shift 2 ;;
        # Internal: used by retry.sh
        --parent)       PARENT_TASK_ID="$2"; shift 2 ;;
        --retry-count)  RETRY_COUNT="$2";   shift 2 ;;
        --)             shift; break ;;
        -*) echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
        *)  POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

# ── Positional args ────────────────────────────────────────────────────────
if [[ $# -lt 2 ]]; then
    echo "Usage: spawn.sh [OPTIONS] <task-id> \"<prompt>\" [workdir]" >&2
    exit 1
fi

TASK_ID="$1"
PROMPT="$2"
WORKDIR="${3:-$(pwd)}"

# ── Validate ───────────────────────────────────────────────────────────────
cc_validate_task_id "$TASK_ID"

if ! [[ "$AGENT" =~ ^(claude|codex)$ ]]; then
    echo "ERROR: --agent must be 'claude' or 'codex'" >&2; exit 1
fi
if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [[ "$TIMEOUT" -lt 1 ]]; then
    echo "ERROR: --timeout must be a positive integer" >&2; exit 1
fi
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --interval must be a non-negative integer" >&2; exit 1
fi
if [[ -n "$DONE_CHECK" ]] && [[ ! -x "$DONE_CHECK" ]]; then
    echo "ERROR: --done-check '$DONE_CHECK' not found or not executable" >&2; exit 1
fi

REQUIRED=(tmux jq)
[[ "$AGENT" == "claude" ]] && REQUIRED+=(claude)
[[ "$AGENT" == "codex" ]]  && REQUIRED+=(codex)
cc_require "${REQUIRED[@]}"

# ── Init ───────────────────────────────────────────────────────────────────
cc_init

LOG_EXT="json"
[[ "$AGENT" == "codex" ]] && LOG_EXT="txt"
$STEERABLE && LOG_EXT="txt"

LOG_FILE="$CC_LOG_DIR/${TASK_ID}.${LOG_EXT}"
PROMPT_FILE="$CC_PROMPT_DIR/${TASK_ID}.txt"
WRAPPER_FILE="$CC_PROMPT_DIR/${TASK_ID}-wrapper.sh"
TMUX_SESSION=$(cc_tmux_session "$TASK_ID")

# Check for task ID collision
if cc_task_exists "$TASK_ID"; then
    echo "ERROR: task '$TASK_ID' already exists in registry. Use a different ID." >&2
    exit 1
fi
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "ERROR: tmux session '$TMUX_SESSION' already exists" >&2
    exit 1
fi

# ── Git worktree (optional) ────────────────────────────────────────────────
AGENT_WORKDIR="$WORKDIR"
WORKTREE_PATH=""
BRANCH_NAME=""

if $USE_WORKTREE; then
    REPO_ROOT=$(git -C "$WORKDIR" rev-parse --show-toplevel 2>/dev/null) || {
        echo "ERROR: --worktree requires workdir to be inside a git repository" >&2; exit 1
    }
    BRANCH_NAME="${BRANCH:-clawclau/${TASK_ID}}"
    WORKTREE_PATH="$CC_WORKTREE_DIR/${TASK_ID}"

    # Create new branch from current HEAD
    git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" 2>/dev/null || {
        echo "ERROR: Failed to create worktree at '$WORKTREE_PATH' (branch may already exist)" >&2
        exit 1
    }
    AGENT_WORKDIR="$WORKTREE_PATH"
    echo "Worktree: $WORKTREE_PATH (branch: $BRANCH_NAME)"
fi

# ── Write prompt file ──────────────────────────────────────────────────────
printf '%s' "$PROMPT" > "$PROMPT_FILE"

# ── Build wrapper script ───────────────────────────────────────────────────
# The wrapper is called: bash -l wrapper.sh
# Using a wrapper avoids quote-escaping hell when passing the prompt through tmux.

if [[ "$AGENT" == "claude" ]] && ! $STEERABLE; then
    # Claude print mode: stream-json, real-time logging, no steering
    cat > "$WRAPPER_FILE" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Args: $1=PROMPT_FILE $2=WORKDIR $3=LOG_FILE [$4=MODEL]
cd "$2"
MODEL_FLAG=()
[[ -n "${4:-}" ]] && MODEL_FLAG=(--model "$4")
exec claude -p --dangerously-skip-permissions \
    --verbose --output-format stream-json --include-partial-messages \
    "${MODEL_FLAG[@]}" \
    "$(cat "$1")" 2>&1 | tee "$3"
WRAPPER_EOF

elif [[ "$AGENT" == "claude" ]] && $STEERABLE; then
    # Claude steerable mode: interactive, logged via tmux pipe-pane
    cat > "$WRAPPER_FILE" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Args: $1=WORKDIR [$2=MODEL]
cd "$1"
MODEL_FLAG=()
[[ -n "${2:-}" ]] && MODEL_FLAG=(--model "$2")
exec claude --dangerously-skip-permissions "${MODEL_FLAG[@]}"
WRAPPER_EOF

elif [[ "$AGENT" == "codex" ]]; then
    # Codex: full-auto mode, plain text log
    cat > "$WRAPPER_FILE" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Args: $1=PROMPT_FILE $2=WORKDIR $3=LOG_FILE [$4=MODEL]
cd "$2"
MODEL_FLAG=()
[[ -n "${4:-}" ]] && MODEL_FLAG=(-m "$4")
exec codex --approval-mode full-auto "${MODEL_FLAG[@]}" "$(cat "$1")" 2>&1 | tee "$3"
WRAPPER_EOF
fi
chmod +x "$WRAPPER_FILE"

# ── Launch tmux session ────────────────────────────────────────────────────
if [[ "$AGENT" == "claude" ]] && $STEERABLE; then
    # Interactive: launch claude, then inject prompt via tmux paste-buffer
    tmux new-session -d -s "$TMUX_SESSION" -c "$AGENT_WORKDIR" \
        "bash -l $WRAPPER_FILE $AGENT_WORKDIR ${MODEL:-}"
    sleep 0.5
    # Capture output via pipe-pane (works in interactive PTY mode)
    tmux pipe-pane -t "$TMUX_SESSION" "cat >> $LOG_FILE"
    sleep 0.3
    # Inject prompt using load-buffer + paste-buffer (handles special chars)
    tmux load-buffer -b "prompt-$TASK_ID" "$PROMPT_FILE"
    tmux paste-buffer -t "$TMUX_SESSION" -b "prompt-$TASK_ID" -p
    tmux send-keys -t "$TMUX_SESSION" "" Enter
else
    # Print / Codex mode: wrapper handles the log piping
    tmux new-session -d -s "$TMUX_SESSION" -c "$AGENT_WORKDIR" \
        "bash -l $WRAPPER_FILE $PROMPT_FILE $AGENT_WORKDIR $LOG_FILE ${MODEL:-}"
fi

# Verify session actually started
sleep 1
if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "ERROR: tmux session '$TMUX_SESSION' failed to start" >&2
    if [[ -s "$LOG_FILE" ]]; then
        echo "Last log output:" >&2
        tail -5 "$LOG_FILE" >&2
    fi
    # Cleanup worktree if we created one
    if [[ -n "$WORKTREE_PATH" ]]; then
        git -C "$WORKDIR" worktree remove "$WORKTREE_PATH" --force 2>/dev/null || true
    fi
    exit 1
fi

# ── Register task ──────────────────────────────────────────────────────────
NOW_MS=$(cc_now_ms)
TASK_JSON=$(jq -n \
    --arg id          "$TASK_ID" \
    --arg agent       "$AGENT" \
    --arg mode        "$(if $STEERABLE; then echo steerable; else echo print; fi)" \
    --arg session     "$TMUX_SESSION" \
    --arg prompt      "$PROMPT" \
    --arg workdir     "$WORKDIR" \
    --arg agentDir    "$AGENT_WORKDIR" \
    --arg log         "$LOG_FILE" \
    --arg model       "$MODEL" \
    --argjson startTs "$NOW_MS" \
    --argjson timeout "$TIMEOUT" \
    --argjson interval "$INTERVAL" \
    --argjson maxR    "$MAX_RETRIES" \
    --argjson retryC  "$RETRY_COUNT" \
    --arg parent      "$PARENT_TASK_ID" \
    --arg worktree    "$WORKTREE_PATH" \
    --arg branch      "$BRANCH_NAME" \
    --arg doneCheck   "$DONE_CHECK" \
    '{
        id:           $id,
        agent:        $agent,
        mode:         $mode,
        tmuxSession:  $session,
        prompt:       $prompt,
        workdir:      $workdir,
        agentWorkdir: $agentDir,
        log:          $log,
        model:        $model,
        startedAt:    $startTs,
        timeout:      $timeout,
        interval:     $interval,
        status:       "running",
        completedAt:  null,
        maxRetries:   $maxR,
        retryCount:   $retryC,
        parentTaskId: (if $parent != "" then $parent else null end),
        worktree:     (if $worktree != "" then $worktree else null end),
        branch:       (if $branch != "" then $branch else null end),
        doneCheck:    (if $doneCheck != "" then $doneCheck else null end),
        steerLog:     []
    }')

cc_task_register "$TASK_JSON"

# ── Background: completion detector ───────────────────────────────────────
(
    export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.openclaw/bin:$PATH"
    _TASK_ID="$TASK_ID"
    _SESSION="$TMUX_SESSION"
    _LOG="$LOG_FILE"
    _REGISTRY="$CC_REGISTRY"
    _DONE_CHECK="$DONE_CHECK"
    _AGENT_DIR="$AGENT_WORKDIR"
    _REPO_DIR="$WORKDIR"
    _WORKTREE="$WORKTREE_PATH"

    while tmux has-session -t "$_SESSION" 2>/dev/null; do
        sleep 5
    done
    sleep 2   # allow log flush

    NOW=$(date +%s000)
    STATUS="failed"

    if [[ -s "$_LOG" ]]; then
        STATUS="done"
        # Run DoD check if provided
        if [[ -n "$_DONE_CHECK" ]] && [[ -x "$_DONE_CHECK" ]]; then
            if ! "$_DONE_CHECK" "$_TASK_ID" "$_LOG" "$_AGENT_DIR" 2>/dev/null; then
                STATUS="failed"
            fi
        fi
    fi

    jq --arg id "$_TASK_ID" --argjson ts "$NOW" --arg st "$STATUS" \
        '(.[] | select(.id == $id)) |= . + {status: $st, completedAt: $ts}' \
        "$_REGISTRY" > "$_REGISTRY.tmp" && mv "$_REGISTRY.tmp" "$_REGISTRY"

    # Notify
    command -v openclaw >/dev/null 2>&1 && \
        openclaw system event --text "ClawClau: 任务 $_TASK_ID [$STATUS]" --mode now 2>/dev/null || true
) &
disown

# ── Background: progress reporter ─────────────────────────────────────────
if [[ "$INTERVAL" -gt 0 ]]; then
(
    set +e
    export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.openclaw/bin:$PATH"
    _TASK_ID="$TASK_ID"
    _SESSION="$TMUX_SESSION"
    _LOG="$LOG_FILE"
    _INTERVAL="$INTERVAL"
    _START_MS=$(date +%s000)
    _LAST_BYTES=0

    while tmux has-session -t "$_SESSION" 2>/dev/null; do
        sleep "$_INTERVAL"
        [[ -f "$_LOG" ]] || continue

        CURRENT_BYTES=$(wc -c < "$_LOG" 2>/dev/null | tr -d ' ' || echo 0)
        [[ "$CURRENT_BYTES" -le "$_LAST_BYTES" ]] && continue
        _LAST_BYTES=$CURRENT_BYTES

        NOW_MS=$(date +%s000)
        ELAPSED=$(( (NOW_MS - _START_MS) / 1000 ))
        if [[ $ELAPSED -lt 60 ]]; then TIME_STR="${ELAPSED}秒"; else TIME_STR="$((ELAPSED/60))分钟"; fi

        SNIPPET=$(cc_extract_text "$_LOG" 200)
        TEXT="[进度] 任务 $_TASK_ID: 已运行 $TIME_STR"$'\n'"最新输出: ${SNIPPET}"

        command -v openclaw >/dev/null 2>&1 && \
            openclaw system event --text "$TEXT" --mode now 2>/dev/null || true
    done
) &
disown
fi

# ── Done ───────────────────────────────────────────────────────────────────
MODE_STR="print"
$STEERABLE && MODE_STR="steerable"

echo "Spawned: $TASK_ID"
echo "  Agent:    $AGENT ($MODE_STR)"
echo "  Session:  $TMUX_SESSION"
echo "  Workdir:  $AGENT_WORKDIR"
[[ -n "$WORKTREE_PATH" ]] && echo "  Worktree: $WORKTREE_PATH  branch: $BRANCH_NAME"
echo "  Log:      $LOG_FILE"
echo "  Timeout:  ${TIMEOUT}s  MaxRetries: $MAX_RETRIES"
[[ -n "$DONE_CHECK" ]] && echo "  DoneCheck: $DONE_CHECK"
[[ "$INTERVAL" -gt 0 ]] && echo "  Progress: every ${INTERVAL}s"
