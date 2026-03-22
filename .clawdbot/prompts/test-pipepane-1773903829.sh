#!/bin/bash
# $1 = PROMPT_FILE, $2 = WORKDIR
cd "$2"
CLAWCLAU_PROMPT_FILE="$1"
export CLAWCLAU_PROMPT_FILE
# Run claude directly — the tmux PTY gives it a terminal so it line-buffers.
# pipe-pane (started after session creation) captures output to the log file.
claude -p --dangerously-skip-permissions "$(cat "$CLAWCLAU_PROMPT_FILE")" 2>&1
