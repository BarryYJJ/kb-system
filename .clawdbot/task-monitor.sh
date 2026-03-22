#!/bin/bash
# task-monitor.sh — Check all active ClawClau tasks and report status
# Output: JSON summary for 小八 to relay to Feishu

set -euo pipefail

CLAWCLAU_HOME="${CLAWCLAU_HOME:-$HOME/.openclaw/workspace/.clawdbot}"
REGISTRY="$CLAWCLAU_HOME/active-tasks.json"

if [ ! -f "$REGISTRY" ]; then
    echo '{"status":"no_tasks"}'
    exit 0
fi

RUNNING=$(jq -r '[.[] | select(.status == "running")]' "$REGISTRY")

if [ "$RUNNING" = "[]" ] || [ -z "$RUNNING" ]; then
    echo '{"status":"no_running_tasks"}'
    exit 0
fi

# Check each running task
REPORTS=[]
while IFS= read -r task; do
    TASK_ID=$(echo "$task" | jq -r '.id')
    TMUX_SESSION=$(echo "$task" | jq -r '.tmuxSession')
    LOG_FILE=$(echo "$task" | jq -r '.log')
    STARTED=$(echo "$task" | jq -r '.startedAt')
    TIMEOUT=$(echo "$task" | jq -r '.timeout // 600')

    NOW_TS=$(date +%s)
    START_SEC=$((STARTED / 1000))
    ELAPSED=$((NOW_TS - START_SEC))
    TIMEOUT_SEC=$TIMEOUT

    if [ "$ELAPSED" -lt 60 ]; then
        ELAPSED_STR="${ELAPSED}秒"
    elif [ "$ELAPSED" -lt 3600 ]; then
        ELAPSED_STR="$((ELAPSED / 60))分钟$((ELAPSED % 60))秒"
    else
        ELAPSED_STR="$((ELAPSED / 3600))小时$((ELAPSED % 3600 / 60))分钟"
    fi

    # Check tmux session
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        # Session alive - check log growth
        if [ -f "$LOG_FILE" ]; then
            LOG_SIZE=$(wc -c < "$LOG_FILE" | tr -d ' ')
            LOG_LINES=$(wc -l < "$LOG_FILE" | tr -d ' ')
        else
            LOG_SIZE=0
            LOG_LINES=0
        fi

        # Extract latest readable text from stream-json log
        if [ "$LOG_SIZE" -gt 0 ]; then
            LATEST_TEXT=$(tail -200 "$LOG_FILE" 2>/dev/null | \
                jq -rs '[.[] | select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text] | join("")' 2>/dev/null | \
                tail -c 200)
            [ -z "$LATEST_TEXT" ] && LATEST_TEXT="(正在思考...)"
        else
            LATEST_TEXT="(日志为空，可能刚启动)"
        fi

        # Check if timed out
        if [ "$ELAPSED" -ge "$TIMEOUT_SEC" ]; then
            TASK_STATE="timeout"
            TASK_STATE_CN="超时"
        else
            TASK_STATE="running"
            TASK_STATE_CN="运行中"
        fi

        jq -n --arg id "$TASK_ID" \
              --arg state "$TASK_STATE" \
              --arg state_cn "$TASK_STATE_CN" \
              --arg elapsed "$ELAPSED_STR" \
              --arg log_bytes "$LOG_SIZE" \
              --arg log_lines "$LOG_LINES" \
              --arg latest "$LATEST_TEXT" \
              '{id: $id, state: $state, state_cn: $state_cn, elapsed: $elapsed, log_bytes: $log_bytes, log_lines: $log_lines, latest: $latest}'

    else
        # Session dead - check log for results
        if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
            HAS_RESULT=$(grep -c '"type":"result"' "$LOG_FILE" 2>/dev/null || echo 0)
            if [ "$HAS_RESULT" -gt 0 ]; then
                TASK_STATE="done"
                TASK_STATE_CN="已完成"
                RESULT_TEXT=$(grep '"type":"result"' "$LOG_FILE" | tail -1 | jq -r '.result // "无结果"' 2>/dev/null | head -c 300)
            else
                TASK_STATE="dead"
                TASK_STATE_CN="异常退出"
                RESULT_TEXT="tmux 会话已退出，但日志中没有 result 事件"
            fi
        else
            TASK_STATE="dead"
            TASK_STATE_CN="异常退出"
            RESULT_TEXT="tmux 会话已退出，日志为空"
        fi

        jq -n --arg id "$TASK_ID" \
              --arg state "$TASK_STATE" \
              --arg state_cn "$TASK_STATE_CN" \
              --arg elapsed "$ELAPSED_STR" \
              --arg result "$RESULT_TEXT" \
              '{id: $id, state: $state, state_cn: $state_cn, elapsed: $elapsed, result: $result}'
    fi
done < <(echo "$RUNNING" | jq -c '.[]')
