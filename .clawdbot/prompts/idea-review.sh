#!/bin/bash
cd "$2"
claude -p --dangerously-skip-permissions "$(cat "$1")" 2>&1 | tee "$3"
