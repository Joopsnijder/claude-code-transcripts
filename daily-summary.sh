#!/bin/bash
# Daily Claude Code Transcript Summary
# Usage: daily-summary.sh [--date YYYYMMDD] [--dry-run]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .venv/bin/activate
python daily_summary.py "$@"
