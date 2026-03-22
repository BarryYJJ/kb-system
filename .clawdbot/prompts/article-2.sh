#!/bin/bash
cd "$2"
exec claude -p --dangerously-skip-permissions "$(cat "$1")" > "$3" 2>&1
