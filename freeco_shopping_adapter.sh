#!/bin/bash
# Freeco AI Shopping Agent - Paperclip Process Adapter
# This script is called by Paperclip-Surfers as a process adapter.
# It receives the task description as the first argument and runs the
# Freeco Shopping Agent, returning structured results.

set -euo pipefail

TASK="${1:-}"
if [ -z "$TASK" ]; then
  echo '{"error": "No task provided"}' >&2
  exit 1
fi

# Load environment variables
source /home/ubuntu/product-research-agent/.env 2>/dev/null || true

# Run the Freeco Luxury Agent with the task
cd /home/ubuntu/product-research-agent
python3 freeco_luxury_agent.py "$TASK"
