#!/usr/bin/env python3
"""
Freeco AI — Manus CEO Bridge Script
====================================
Bridges Paperclip-Surfers process adapter to the Manus (manus.im) API v2.

When Paperclip assigns a task to the CEO agent, it invokes this script via the
generic `process` adapter. The script:

  1. Reads task context from Paperclip environment variables.
  2. Creates a new task on the Manus API (POST /v2/task.create).
  3. Polls task.listMessages until the agent reaches a terminal state.
  4. Extracts the final assistant message(s) and prints them to stdout.
  5. Paperclip captures stdout as the adapter result.

Environment Variables (set by Paperclip buildPaperclipEnv + adapter_config.env):
  MANUS_API_KEY          — Required. Manus API key (x-manus-api-key).
  MANUS_PROJECT_ID       — Optional. Manus project ID for durable instructions.
  MANUS_AGENT_PROFILE    — Optional. "manus-1.6", "manus-1.6-lite", "manus-1.6-max".
  MANUS_POLL_INTERVAL    — Optional. Seconds between polls (default: 5).
  MANUS_TIMEOUT          — Optional. Max seconds to wait for completion (default: 600).
  PAPERCLIP_AGENT_ID     — Set by Paperclip. The agent ID within the company.
  PAPERCLIP_COMPANY_ID   — Set by Paperclip. The company ID.
  PAPERCLIP_API_URL      — Set by Paperclip. Internal Paperclip API URL.

Usage:
  Called by Paperclip process adapter. The first positional argument ($1) is the
  task prompt. If not provided, reads from PAPERCLIP_TASK_PROMPT env var.

Security:
  - API key is read from environment only (never hardcoded).
  - All HTTP responses are validated before parsing.
  - Timeout prevents indefinite polling.
  - No secrets are logged to stdout/stderr.

Author: Freeco AI Platform
License: MIT
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MANUS_API_BASE = "https://api.manus.ai"
DEFAULT_POLL_INTERVAL = 5       # seconds
DEFAULT_TIMEOUT = 600           # 10 minutes
DEFAULT_AGENT_PROFILE = "manus-1.6"

# Freeco AI CEO system context — injected into every task
FREECO_CEO_SYSTEM_CONTEXT = (
    "You are the CEO of Freeco AI, a Swiss high-end sustainable concierge platform. "
    "Your company provides AI-powered services for healthy shopping (organic/vegan), "
    "restaurant recommendations, travel planning, and wellness. "
    "You operate with Swiss precision, prioritizing quality, sustainability, and privacy. "
    "Your decisions should reflect luxury positioning — never economy. "
    "You lead a team of 12 AI agents across Operations, Business Development, Marketing, "
    "Sales, HR, and Software & Infrastructure departments. "
    "Your secretary is Hermes (OpenFang agent). "
    "Always respond with strategic clarity and actionable directives."
)


def log(msg: str) -> None:
    """Log to stderr (Paperclip captures stdout as result, stderr as logs)."""
    print(f"[manus-ceo-bridge] {msg}", file=sys.stderr, flush=True)


def get_env(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Read an environment variable with optional requirement enforcement."""
    value = os.environ.get(key, default)
    if required and not value:
        log(f"FATAL: Required environment variable {key} is not set.")
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Manus API Client
# ---------------------------------------------------------------------------

class ManusAPIError(Exception):
    """Raised when the Manus API returns an error response."""
    def __init__(self, code: str, message: str, request_id: str = ""):
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"Manus API error [{code}]: {message} (request_id={request_id})")


class ManusClient:
    """Minimal, dependency-free client for the Manus API v2."""

    def __init__(self, api_key: str, base_url: str = MANUS_API_BASE):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "x-manus-api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "FreecoCEOBridge/1.0",
        }

    def _request(self, method: str, path: str, body: Optional[dict] = None,
                 params: Optional[dict] = None) -> dict:
        """Make an HTTP request to the Manus API and return parsed JSON."""
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                err = json.loads(raw)
                error_obj = err.get("error", {})
                raise ManusAPIError(
                    code=error_obj.get("code", str(e.code)),
                    message=error_obj.get("message", raw[:500]),
                    request_id=err.get("request_id", ""),
                )
            except (json.JSONDecodeError, KeyError):
                raise ManusAPIError(code=str(e.code), message=raw[:500])
        except urllib.error.URLError as e:
            raise ManusAPIError(code="network_error", message=str(e.reason))

        if not result.get("ok", False):
            error_obj = result.get("error", {})
            raise ManusAPIError(
                code=error_obj.get("code", "unknown"),
                message=error_obj.get("message", "Unknown error"),
                request_id=result.get("request_id", ""),
            )

        return result

    def create_task(self, prompt: str, project_id: Optional[str] = None,
                    agent_profile: str = DEFAULT_AGENT_PROFILE,
                    title: Optional[str] = None) -> dict:
        """Create a new task on the Manus API."""
        body = {
            "message": {
                "content": prompt,
            },
            "agent_profile": agent_profile,
            "interactive_mode": False,
            "hide_in_task_list": False,
        }
        if project_id:
            body["project_id"] = project_id
        if title:
            body["title"] = title

        return self._request("POST", "/v2/task.create", body=body)

    def list_messages(self, task_id: str, order: str = "desc",
                      limit: int = 20) -> dict:
        """Poll task messages to check status and retrieve results."""
        params = {
            "task_id": task_id,
            "order": order,
            "limit": str(limit),
        }
        return self._request("GET", "/v2/task.listMessages", params=params)

    def get_latest_status(self, task_id: str) -> tuple:
        """
        Get the latest agent status and the most recent assistant message.
        Returns: (agent_status, assistant_content, full_messages)
        """
        result = self.list_messages(task_id, order="desc", limit=50)
        messages = result.get("messages", [])

        agent_status = None
        assistant_content = None
        assistant_attachments = []

        for msg in messages:
            msg_type = msg.get("type")

            if msg_type == "status_update" and agent_status is None:
                agent_status = msg.get("status_update", {}).get("agent_status")

            if msg_type == "assistant_message" and assistant_content is None:
                am = msg.get("assistant_message", {})
                assistant_content = am.get("content", "")
                assistant_attachments = am.get("attachments", [])

        return agent_status, assistant_content, assistant_attachments, messages


# ---------------------------------------------------------------------------
# Main Bridge Logic
# ---------------------------------------------------------------------------

def build_ceo_prompt(task_input: str, paperclip_agent_id: str,
                     paperclip_company_id: str) -> str:
    """
    Construct the full CEO prompt with Freeco AI context and Paperclip metadata.
    """
    return (
        f"{FREECO_CEO_SYSTEM_CONTEXT}\n\n"
        f"--- Paperclip Task Context ---\n"
        f"Company ID: {paperclip_company_id}\n"
        f"Requesting Agent ID: {paperclip_agent_id}\n"
        f"Task:\n{task_input}\n"
        f"--- End Context ---\n\n"
        f"Please provide your CEO-level response to this task."
    )


def format_result(content: str, attachments: list, task_id: str,
                  task_url: str = "") -> str:
    """
    Format the Manus response for Paperclip consumption.
    Returns a JSON string that Paperclip process adapter can parse.
    """
    result = {
        "source": "manus-ceo",
        "task_id": task_id,
        "task_url": task_url,
        "content": content or "(No response content)",
        "attachments": [
            {
                "file_name": att.get("file_name", ""),
                "url": att.get("url", ""),
                "size_bytes": att.get("size_bytes", 0),
            }
            for att in attachments
        ],
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def main():
    """Entry point for the Manus CEO bridge."""
    # --- Read configuration ---
    api_key = get_env("MANUS_API_KEY", required=True)
    project_id = get_env("MANUS_PROJECT_ID")
    agent_profile = get_env("MANUS_AGENT_PROFILE", DEFAULT_AGENT_PROFILE)
    poll_interval = int(get_env("MANUS_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
    timeout = int(get_env("MANUS_TIMEOUT", str(DEFAULT_TIMEOUT)))

    # Paperclip context
    paperclip_agent_id = get_env("PAPERCLIP_AGENT_ID", "unknown")
    paperclip_company_id = get_env("PAPERCLIP_COMPANY_ID", "unknown")

    # Task input: first argument or env var
    if len(sys.argv) > 1:
        task_input = sys.argv[1]
    else:
        task_input = get_env("PAPERCLIP_TASK_PROMPT", "")

    if not task_input.strip():
        log("FATAL: No task input provided (neither argument nor PAPERCLIP_TASK_PROMPT).")
        sys.exit(1)

    log(f"Starting CEO bridge for agent={paperclip_agent_id}, company={paperclip_company_id}")
    log(f"Agent profile: {agent_profile}, timeout: {timeout}s, poll: {poll_interval}s")

    # --- Create Manus task ---
    client = ManusClient(api_key)
    prompt = build_ceo_prompt(task_input, paperclip_agent_id, paperclip_company_id)

    try:
        create_result = client.create_task(
            prompt=prompt,
            project_id=project_id,
            agent_profile=agent_profile,
            title=f"[Freeco CEO] {task_input[:80]}",
        )
    except ManusAPIError as e:
        log(f"FATAL: Failed to create Manus task: {e}")
        # Output error as JSON for Paperclip
        error_result = {
            "source": "manus-ceo",
            "error": True,
            "error_code": e.code,
            "error_message": e.message,
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

    task_id = create_result.get("task_id", "")
    task_url = create_result.get("task_url", "")
    log(f"Manus task created: {task_id}")
    log(f"Task URL: {task_url}")

    # --- Poll for completion ---
    start_time = time.time()
    final_content = None
    final_attachments = []

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            log(f"TIMEOUT: Task {task_id} did not complete within {timeout}s.")
            timeout_result = {
                "source": "manus-ceo",
                "task_id": task_id,
                "task_url": task_url,
                "error": True,
                "error_code": "timeout",
                "error_message": f"Task did not complete within {timeout} seconds. "
                                 f"Check task at: {task_url}",
            }
            print(json.dumps(timeout_result, indent=2))
            sys.exit(1)

        time.sleep(poll_interval)

        try:
            status, content, attachments, messages = client.get_latest_status(task_id)
        except ManusAPIError as e:
            log(f"WARNING: Poll error (will retry): {e}")
            continue

        log(f"Poll [{int(elapsed)}s]: agent_status={status}")

        if status == "stopped":
            final_content = content
            final_attachments = attachments
            log("Task completed successfully.")
            break

        elif status == "error":
            # Extract error details
            error_content = ""
            for msg in messages:
                if msg.get("type") == "error_message":
                    error_content = msg.get("error_message", {}).get("content", "Unknown error")
                    break

            log(f"Task failed: {error_content}")
            error_result = {
                "source": "manus-ceo",
                "task_id": task_id,
                "task_url": task_url,
                "error": True,
                "error_code": "task_error",
                "error_message": error_content,
            }
            print(json.dumps(error_result, indent=2))
            sys.exit(1)

        elif status == "waiting":
            # For non-interactive mode, log and continue polling
            # The agent should proceed without user input
            log("Agent is waiting (non-interactive mode — will continue polling).")
            continue

        # status == "running" or None → keep polling

    # --- Output result ---
    output = format_result(final_content, final_attachments, task_id, task_url)
    print(output)
    log("Bridge completed successfully.")


if __name__ == "__main__":
    main()
