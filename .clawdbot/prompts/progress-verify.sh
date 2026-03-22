#!/bin/bash
# $1 = PROMPT_FILE, $2 = WORKDIR, $3 = LOG_FILE
cd "$2"
CLAWCLAU_PROMPT_FILE="$1"
export CLAWCLAU_PROMPT_FILE
# --output-format stream-json: each API token/event is flushed to stdout
# immediately, making tee write to the log file in real time.
# --include-partial-messages: emit each text token as a separate event.
# --verbose: required when --output-format=stream-json is used with --print.
claude -p --dangerously-skip-permissions \
    --verbose --output-format stream-json --include-partial-messages \
    "$(cat "$CLAWCLAU_PROMPT_FILE")" 2>&1 | tee "$3"
