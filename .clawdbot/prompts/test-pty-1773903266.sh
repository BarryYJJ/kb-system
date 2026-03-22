#!/bin/bash
# $1 = PROMPT_FILE, $2 = WORKDIR, $3 = LOG_FILE
cd "$2"
CLAWCLAU_PROMPT_FILE="$1"
export CLAWCLAU_PROMPT_FILE
# -q suppresses the "Script started/done" header lines
script -q "$3" bash -c 'claude -p --dangerously-skip-permissions "$(cat "$CLAWCLAU_PROMPT_FILE")" 2>&1'
