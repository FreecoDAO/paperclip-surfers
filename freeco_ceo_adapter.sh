#!/usr/bin/env bash
# ============================================================================
# Freeco AI — CEO Adapter Wrapper
# ============================================================================
# Called by Paperclip-Surfers process adapter to delegate CEO tasks to
# Manus (manus.im) via the manus_ceo_bridge.py Python script.
#
# Paperclip passes the task prompt as $1 and injects PAPERCLIP_AGENT_ID,
# PAPERCLIP_COMPANY_ID, and PAPERCLIP_API_URL via environment variables.
#
# The MANUS_API_KEY must be set in the adapter_config.env or .env file.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SCRIPT="${SCRIPT_DIR}/manus_ceo_bridge.py"

# Load environment from .env if MANUS_API_KEY is not already set
if [ -z "${MANUS_API_KEY:-}" ]; then
    ENV_FILE="${SCRIPT_DIR}/.env"
    if [ -f "$ENV_FILE" ]; then
        # shellcheck disable=SC1090
        set -a
        source "$ENV_FILE"
        set +a
    fi
fi

# Validate that the API key is available
if [ -z "${MANUS_API_KEY:-}" ]; then
    echo '{"source":"manus-ceo","error":true,"error_code":"missing_api_key","error_message":"MANUS_API_KEY environment variable is not set. Configure it in the Paperclip adapter config or .env file."}' >&2
    exit 1
fi

# Task prompt from Paperclip
TASK="${1:-}"

if [ -z "$TASK" ]; then
    echo '{"source":"manus-ceo","error":true,"error_code":"no_task","error_message":"No task prompt provided."}' >&2
    exit 1
fi

# Execute the Python bridge
exec python3 "$BRIDGE_SCRIPT" "$TASK"
