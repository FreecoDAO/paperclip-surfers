#!/usr/bin/env python3
"""
Freeco AI — CEO Task Queue Writer
==================================
This script is the Paperclip-Surfers process adapter for the CEO agent.
Instead of calling an external API, it writes the task directive to the
shared project file (ceo_task_queue.md) which the scheduled Manus CEO
task will pick up and process on its next run.

Usage:
    Called by Paperclip process adapter:
        python3 manus_ceo_queue.py "Approve Q3 marketing budget of CHF 50,000"

    Or via environment variable:
        PAPERCLIP_TASK_PROMPT="Review hiring plan" python3 manus_ceo_queue.py

The script:
1. Reads the current ceo_task_queue.md from the project files
2. Appends the new directive to the Pending Tasks section
3. Writes the updated file back
4. Returns a JSON response to Paperclip confirming the task was queued

The Manus scheduled task (running 3x/day on weekdays at 09:00, 13:00, 17:00)
will then process the queue and make CEO decisions.
"""

import json
import os
import sys
import re
from datetime import datetime, timezone


# ─── Configuration ───────────────────────────────────────────────────────────

# Path to the CEO task queue (project shared file)
# This is synced across all Manus tasks in the FreEco.AI project
QUEUE_FILE = os.environ.get(
    "CEO_QUEUE_FILE",
    "/home/ubuntu/projects/freeco-ai-50725060/ceo_task_queue.md"
)

# Fallback paths (in case the project file location differs)
QUEUE_FILE_ALTERNATIVES = [
    "/home/ubuntu/.manus/config/project-file/ceo_task_queue.md",
    "/home/ubuntu/paperclip-surfers/ceo_task_queue.md",
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def find_queue_file() -> str:
    """Find the CEO task queue file."""
    if os.path.exists(QUEUE_FILE):
        return QUEUE_FILE
    for alt in QUEUE_FILE_ALTERNATIVES:
        if os.path.exists(alt):
            return alt
    # If none exist, create at the primary location
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    return QUEUE_FILE


def read_queue(path: str) -> str:
    """Read the current queue file content."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """# CEO Task Queue

## Pending Tasks

*No pending tasks.*

## Completed Tasks

*None yet.*
"""


def write_queue(path: str, content: str) -> None:
    """Write the updated queue file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def add_task_to_queue(
    queue_content: str,
    directive: str,
    from_agent: str = "Paperclip-Surfers",
    priority: str = "High",
) -> str:
    """Insert a new task into the Pending Tasks section of the queue."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    task_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    new_task = f"""
### Task-{task_id}: Pending Directive
**From:** {from_agent}
**Priority:** {priority}
**Submitted:** {timestamp}
**Directive:** {directive}
"""

    # Replace the "No pending tasks" placeholder if present
    if "*No pending tasks.*" in queue_content:
        queue_content = queue_content.replace("*No pending tasks.*", new_task.strip())
    else:
        # Insert before the "## Completed Tasks" section
        completed_marker = "## Completed Tasks"
        if completed_marker in queue_content:
            queue_content = queue_content.replace(
                completed_marker,
                new_task + "\n" + completed_marker,
            )
        else:
            # Fallback: append to end of Pending Tasks section
            queue_content += "\n" + new_task

    return queue_content


def format_response(
    success: bool,
    task_id: str,
    message: str,
    queue_path: str = "",
) -> str:
    """Format the JSON response for Paperclip."""
    response = {
        "source": "manus-ceo",
        "method": "scheduled-task-queue",
        "success": success,
        "task_id": task_id,
        "message": message,
        "queue_file": queue_path,
        "schedule": "Weekdays at 09:00, 13:00, 17:00 (Europe/Madrid)",
        "note": "The CEO (Manus) will process this directive on the next scheduled run.",
    }
    return json.dumps(response, indent=2)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # Get the task directive
    directive = None

    # Priority 1: Command-line argument
    if len(sys.argv) > 1:
        directive = " ".join(sys.argv[1:])

    # Priority 2: Environment variable
    if not directive:
        directive = os.environ.get("PAPERCLIP_TASK_PROMPT", "").strip()

    # Priority 3: stdin (for piped input)
    if not directive and not sys.stdin.isatty():
        directive = sys.stdin.read().strip()

    if not directive:
        error_response = {
            "source": "manus-ceo",
            "error": True,
            "error_code": "no_directive",
            "error_message": "No CEO directive provided. Pass as argument, PAPERCLIP_TASK_PROMPT env var, or stdin.",
        }
        print(json.dumps(error_response, indent=2), file=sys.stderr)
        sys.exit(1)

    # Get metadata from Paperclip environment
    from_agent = os.environ.get("PAPERCLIP_AGENT_NAME", "Paperclip-Surfers")
    priority = os.environ.get("PAPERCLIP_PRIORITY", "High")

    # Find and read the queue
    queue_path = find_queue_file()
    queue_content = read_queue(queue_path)

    # Add the task
    task_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    updated_queue = add_task_to_queue(queue_content, directive, from_agent, priority)

    # Write back
    write_queue(queue_path, updated_queue)

    # Return success response to Paperclip
    response = format_response(
        success=True,
        task_id=f"CEO-{task_id}",
        message=f"Directive queued for CEO processing. The Manus CEO agent will review and decide on the next scheduled run.",
        queue_path=queue_path,
    )
    print(response)
    sys.exit(0)


if __name__ == "__main__":
    main()
