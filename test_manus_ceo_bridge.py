#!/usr/bin/env python3
"""
Test suite for the Manus CEO Bridge Script.
Tests core logic, error handling, and security without requiring a live API key.
"""

import json
import os
import subprocess
import sys
import unittest

# Add the script directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manus_ceo_bridge import (
    ManusClient,
    ManusAPIError,
    build_ceo_prompt,
    format_result,
    FREECO_CEO_SYSTEM_CONTEXT,
)


class TestBuildCEOPrompt(unittest.TestCase):
    """Test the prompt construction logic."""

    def test_prompt_contains_system_context(self):
        prompt = build_ceo_prompt("Test task", "agent-1", "company-1")
        self.assertIn(FREECO_CEO_SYSTEM_CONTEXT, prompt)

    def test_prompt_contains_task_input(self):
        prompt = build_ceo_prompt("Approve Q3 budget", "agent-1", "company-1")
        self.assertIn("Approve Q3 budget", prompt)

    def test_prompt_contains_paperclip_metadata(self):
        prompt = build_ceo_prompt("Test", "agent-xyz", "company-abc")
        self.assertIn("agent-xyz", prompt)
        self.assertIn("company-abc", prompt)

    def test_prompt_structure(self):
        prompt = build_ceo_prompt("Test", "a1", "c1")
        self.assertIn("--- Paperclip Task Context ---", prompt)
        self.assertIn("--- End Context ---", prompt)
        self.assertIn("CEO-level response", prompt)


class TestFormatResult(unittest.TestCase):
    """Test the result formatting logic."""

    def test_basic_result(self):
        result = format_result("CEO decision here", [], "task-123", "https://manus.im/app/task-123")
        parsed = json.loads(result)
        self.assertEqual(parsed["source"], "manus-ceo")
        self.assertEqual(parsed["task_id"], "task-123")
        self.assertEqual(parsed["content"], "CEO decision here")
        self.assertEqual(parsed["attachments"], [])

    def test_result_with_attachments(self):
        attachments = [
            {"file_name": "report.pdf", "url": "https://example.com/report.pdf", "size_bytes": 1024}
        ]
        result = format_result("See attached", attachments, "task-456")
        parsed = json.loads(result)
        self.assertEqual(len(parsed["attachments"]), 1)
        self.assertEqual(parsed["attachments"][0]["file_name"], "report.pdf")

    def test_empty_content_fallback(self):
        result = format_result(None, [], "task-789")
        parsed = json.loads(result)
        self.assertEqual(parsed["content"], "(No response content)")

    def test_result_is_valid_json(self):
        result = format_result("Test with special chars: <>&\"'", [], "t1")
        parsed = json.loads(result)
        self.assertIn("<>&", parsed["content"])


class TestManusClient(unittest.TestCase):
    """Test the ManusClient class (without live API calls)."""

    def test_client_initialization(self):
        client = ManusClient("test-key")
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.base_url, "https://api.manus.ai")

    def test_custom_base_url(self):
        client = ManusClient("test-key", base_url="https://custom.api.com/")
        self.assertEqual(client.base_url, "https://custom.api.com")

    def test_headers_contain_api_key(self):
        client = ManusClient("my-secret-key")
        headers = client._headers()
        self.assertEqual(headers["x-manus-api-key"], "my-secret-key")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_api_error_class(self):
        err = ManusAPIError("auth_error", "Invalid API key", "req-123")
        self.assertEqual(err.code, "auth_error")
        self.assertEqual(err.message, "Invalid API key")
        self.assertIn("auth_error", str(err))


class TestBashWrapper(unittest.TestCase):
    """Test the Bash wrapper script."""

    def test_missing_api_key_error(self):
        """Without MANUS_API_KEY, the wrapper should fail with a clear error."""
        env = os.environ.copy()
        env.pop("MANUS_API_KEY", None)
        result = subprocess.run(
            ["/home/ubuntu/paperclip-surfers/freeco_ceo_adapter.sh", "test task"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MANUS_API_KEY", result.stderr)

    def test_missing_task_error(self):
        """Without a task argument, the wrapper should fail."""
        env = os.environ.copy()
        env["MANUS_API_KEY"] = "test-key-for-validation"
        result = subprocess.run(
            ["/home/ubuntu/paperclip-surfers/freeco_ceo_adapter.sh"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no_task", result.stderr)


class TestPythonBridgeErrorHandling(unittest.TestCase):
    """Test the Python bridge's error handling without a live API."""

    def test_missing_api_key_exits(self):
        """Without MANUS_API_KEY, the bridge should exit with code 1."""
        env = os.environ.copy()
        env.pop("MANUS_API_KEY", None)
        result = subprocess.run(
            [sys.executable, "/home/ubuntu/paperclip-surfers/manus_ceo_bridge.py", "test"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("MANUS_API_KEY", result.stderr)

    def test_missing_task_exits(self):
        """Without a task prompt, the bridge should exit with code 1."""
        env = os.environ.copy()
        env["MANUS_API_KEY"] = "test-key"
        env.pop("PAPERCLIP_TASK_PROMPT", None)
        result = subprocess.run(
            [sys.executable, "/home/ubuntu/paperclip-surfers/manus_ceo_bridge.py"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("No task input", result.stderr)

    def test_invalid_api_key_returns_error_json(self):
        """With an invalid API key, the bridge should return error JSON on stdout."""
        env = os.environ.copy()
        env["MANUS_API_KEY"] = "invalid-key-for-testing"
        result = subprocess.run(
            [sys.executable, "/home/ubuntu/paperclip-surfers/manus_ceo_bridge.py",
             "Test CEO directive"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        # Should exit with error code
        self.assertEqual(result.returncode, 1)
        # Should output valid JSON with error info
        try:
            parsed = json.loads(result.stdout)
            self.assertTrue(parsed.get("error", False))
            self.assertEqual(parsed["source"], "manus-ceo")
        except json.JSONDecodeError:
            # If no JSON on stdout, the error is in stderr which is also acceptable
            self.assertIn("Failed to create", result.stderr)


class TestSecurityChecks(unittest.TestCase):
    """Verify security properties of the bridge."""

    def test_no_hardcoded_secrets(self):
        """Ensure no API keys are hardcoded in the script."""
        with open("/home/ubuntu/paperclip-surfers/manus_ceo_bridge.py", "r") as f:
            content = f.read()
        # Should not contain any actual API keys
        self.assertNotIn("sk-", content)
        self.assertNotIn("sk__", content)
        self.assertNotIn("tvly-", content)
        # Should read from env
        self.assertIn("MANUS_API_KEY", content)
        self.assertIn("os.environ", content)

    def test_no_secrets_in_stdout(self):
        """Ensure error output doesn't leak the API key."""
        env = os.environ.copy()
        env["MANUS_API_KEY"] = "super-secret-test-key-12345"
        result = subprocess.run(
            [sys.executable, "/home/ubuntu/paperclip-surfers/manus_ceo_bridge.py",
             "Test task"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        # The API key should not appear in stdout
        self.assertNotIn("super-secret-test-key-12345", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
