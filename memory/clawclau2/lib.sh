#!/usr/bin/env bash
# lib.sh — ClawClau v2 shared utilities
# Source this file: source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# ── Paths ──────────────────────────────────────────────────────────────────
CC_HOME="${CC_HOME:-$HOME/.openclaw/.clawclau2}"
CC_REGISTRY="$CC_HOME/active-tasks.json"
CC_LOG_DIR="$CC_HOME/logs"
CC_PROMPT_DIR="$CC_HOME/prompts"
CC_WORKTREE_DIR="$CC_HOME/worktrees"

# ── Init ───────────────────────────────────────────────────────────────────
cc_init() {
    mkdir -p "$CC_LOG_DIR" "$CC_PROMPT_DIR" "$CC_WORKTREE_DIR"
    [[ -f "$CC_REGISTRY" ]] || echo '[]' > "$CC_REGISTRY"
}

# ── Dependency check ───────────────────────────────────────────────────────
cc_require() {
    for cmd in "$@"; do
        command -v "$cmd" >/dev/null 2>&1 || {
            echo "ERROR: '$cmd' is required but not installed." >&2
            exit 1
        }
    done
}

# ── Registry helpers ───────────────────────────────────────────────────────

# Get a field value from a task in the registry
# Usage: cc_task_get <task-id> <field>
cc_task_get() {
    local id="$1" field="$2"
    jq -r --arg id "$id" --arg f "$field" \
        '.[] | select(.id == $id) | .[$f] // ""' \
        "$CC_REGISTRY" 2>/dev/null
}

# Check if task exists in registry
# Usage: cc_task_exists <task-id>
cc_task_exists() {
    local id="$1"
    local count
    count=$(jq --arg id "$id" '[.[] | select(.id == $id)] | length' "$CC_REGISTRY" 2>/dev/null || echo 0)
    [[ "$count" -gt 0 ]]
}

# Add a new task to the registry
# Usage: cc_task_register <json-object>
cc_task_register() {
    local task_json="$1"
    jq --argjson t "$task_json" '. += [$t]' \
        "$CC_REGISTRY" > "$CC_REGISTRY.tmp" \
        && mv "$CC_REGISTRY.tmp" "$CC_REGISTRY"
}

# Update one or more fields on an existing task
# Usage: cc_task_update <task-id> <json-patch>
# Example: cc_task_update "my-task" '{"status":"done","completedAt":1234}'
cc_task_update() {
    local id="$1" patch="$2"
    jq --arg id "$id" --argjson p "$patch" \
        '(.[] | select(.id == $id)) |= . + $p' \
        "$CC_REGISTRY" > "$CC_REGISTRY.tmp" \
        && mv "$CC_REGISTRY.tmp" "$CC_REGISTRY"
}

# Append to the steerLog array on a task
cc_task_steer_log() {
    local id="$1" message="$2"
    local ts
    ts=$(date +%s000)
    jq --arg id "$id" --arg msg "$message" --argjson ts "$ts" \
        '(.[] | select(.id == $id)) |= . + {steerLog: ((.steerLog // []) + [{at: $ts, message: $msg}])}' \
        "$CC_REGISTRY" > "$CC_REGISTRY.tmp" \
        && mv "$CC_REGISTRY.tmp" "$CC_REGISTRY"
}

# ── tmux helpers ───────────────────────────────────────────────────────────

cc_tmux_session() {
    echo "cc-${1}"
}

cc_tmux_alive() {
    local session
    session=$(cc_tmux_session "$1")
    tmux has-session -t "$session" 2>/dev/null
}

# ── Log text extraction ────────────────────────────────────────────────────

# Extract human-readable text from a log file
# Handles both stream-json (claude) and plain text (codex)
# Usage: cc_extract_text <log-file> [max-chars]
cc_extract_text() {
    local log_file="$1"
    local max_chars="${2:-500}"

    [[ -f "$log_file" ]] || { echo ""; return; }
    [[ -s "$log_file" ]] || { echo ""; return; }

    # Detect format: stream-json starts with '{'
    local first_char
    first_char=$(head -c1 "$log_file" 2>/dev/null)

    if [[ "$first_char" == "{" ]]; then
        # Claude stream-json format
        # Priority: result > last assistant message > text_delta fragments
        # Use -Rs + fromjson per-line to tolerate truncated/non-JSON lines
        local text
        text=$(jq -Rs '
          [split("\n")[] | select(length > 0) | (try fromjson catch null) | select(. != null)] |
          ([ .[] | select(.type == "result") | (.result // "") ] | last // "") as $result |
          ([ .[] | select(.type == "assistant") |
             ((.message.content // []) | map(select(.type == "text") | .text) | join(""))
          ] | last // "") as $assistant |
          ([ .[] |
             select(.type == "stream_event") |
             select(.event.type == "content_block_delta") |
             select(.event.delta.type == "text_delta") |
             .event.delta.text
          ] | join("")) as $delta |
          if $result != "" then $result
          elif $assistant != "" then $assistant
          elif $delta != "" then $delta
          else ""
          end
        ' "$log_file" 2>/dev/null)
        # Return last N chars (bash 3.2 compat: ${v: -N} returns empty when N>len)
        if [[ "${#text}" -le "$max_chars" ]]; then
            echo "$text"
        else
            echo "${text: -$max_chars}"
        fi
    else
        # Plain text (codex or steerable claude with ANSI stripped)
        # Strip ANSI escape codes, return last N chars
        local text
        text=$(tail -200 "$log_file" 2>/dev/null \
            | perl -pe 's/\x1b\[[0-9;]*[mGKHF]//g' \
            | tr -d '\r' \
            | grep -v '^$' \
            | tail -c "$max_chars")
        echo "$text"
    fi
}

# ── Notification ───────────────────────────────────────────────────────────
cc_notify() {
    local text="$1"
    export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.openclaw/bin:$PATH"
    command -v openclaw >/dev/null 2>&1 \
        && openclaw system event --text "$text" --mode now 2>/dev/null || true
}

# ── Timestamp helpers ──────────────────────────────────────────────────────
cc_now_ms() { date +%s000; }
cc_elapsed_human() {
    local start_ms="$1"
    local now_ms
    now_ms=$(cc_now_ms)
    local elapsed=$(( (now_ms - start_ms) / 1000 ))
    if [[ $elapsed -lt 60 ]]; then
        echo "${elapsed}秒"
    else
        echo "$((elapsed / 60))分钟"
    fi
}

# ── Validation ─────────────────────────────────────────────────────────────
cc_validate_task_id() {
    local id="$1"
    if ! [[ "$id" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "ERROR: task-id must be alphanumeric (a-z, A-Z, 0-9, -, _). Got: '$id'" >&2
        exit 1
    fi
}
