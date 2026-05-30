#!/usr/bin/env bash
# ============================================================================
# Freeco AI — CEO Adapter Wrapper (Scheduled Task Queue)
# ============================================================================
# Called by Paperclip-Surfers process adapter to queue CEO directives.
# Directives are written to the shared project file (ceo_task_queue.md)
# and processed by the Manus scheduled task (3x/day on weekdays).
#
# This approach uses Manus's native scheduling system — no API key required.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUEUE_SCRIPT="${SCRIPT_DIR}/manus_ceo_queue.py"

# Task prompt from Paperclip
TASK="${1:-}"

if [ -z "$TASK" ]; then
    echo '{"source":"manus-ceo","error":true,"error_code":"no_task","error_message":"No task prompt provided."}' >&2
    exit 1
fi

# Execute the Python queue writer
exec python3 "$QUEUE_SCRIPT" "$TASK"
