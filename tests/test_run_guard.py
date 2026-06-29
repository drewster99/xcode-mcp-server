#!/usr/bin/env python3
"""Tests for the per-project run/test exclusivity guard.

The guard rejects a second concurrent run/test of the SAME project (result
isolation assumes a single in-flight action per project), while letting
different projects proceed and always releasing the key — including on
exception. It must also preserve the wrapped function's signature so the
@apply_config / FastMCP layers above it still bind parameters.
"""

import inspect
import os
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from xcode_mcp_server.utils.run_guard import exclusive_per_project
import xcode_mcp_server.utils.run_guard as run_guard
from xcode_mcp_server.exceptions import XCodeMCPError


class RunGuardTests(unittest.TestCase):
    def setUp(self):
        # Ensure a clean global state between tests.
        with run_guard._active_lock:
            run_guard._active_projects.clear()

    def test_signature_is_preserved(self):
        @exclusive_per_project
        def tool(project_path, scheme=None, timeout=None):
            return "ok"
        self.assertEqual(
            list(inspect.signature(tool).parameters),
            ["project_path", "scheme", "timeout"],
        )

    def test_rejects_concurrent_same_project(self):
        entered = threading.Event()
        release = threading.Event()

        @exclusive_per_project
        def tool(project_path):
            entered.set()
            release.wait(timeout=5)
            return "ran"

        path = os.path.realpath(".")
        t = threading.Thread(target=lambda: tool(path))
        t.start()
        self.assertTrue(entered.wait(timeout=5))
        try:
            with self.assertRaises(XCodeMCPError):
                tool(path)
        finally:
            release.set()
            t.join(timeout=5)

    def test_allows_different_projects_concurrently(self):
        entered = threading.Event()
        release = threading.Event()

        @exclusive_per_project
        def tool(project_path):
            entered.set()
            release.wait(timeout=5)
            return "ran"

        a = os.path.realpath(os.sep)            # "/"
        b = os.path.realpath(os.path.expanduser("~"))
        self.assertNotEqual(a, b)
        t = threading.Thread(target=lambda: tool(a))
        t.start()
        self.assertTrue(entered.wait(timeout=5))
        # Different project must NOT be rejected — it acquires its own key.
        with run_guard._active_lock:
            already = b in run_guard._active_projects
        self.assertFalse(already)
        # Prove acquisition for b doesn't raise (run it briefly, then release).
        release.set()
        t.join(timeout=5)
        self.assertEqual(tool(b), "ran")

    def test_key_released_after_normal_return(self):
        @exclusive_per_project
        def tool(project_path):
            return "ran"
        path = os.path.realpath(".")
        tool(path)
        tool(path)  # would raise if the key leaked
        with run_guard._active_lock:
            self.assertNotIn(path, run_guard._active_projects)

    def test_key_released_after_exception(self):
        @exclusive_per_project
        def tool(project_path):
            raise ValueError("boom")
        path = os.path.realpath(".")
        with self.assertRaises(ValueError):
            tool(path)
        with run_guard._active_lock:
            self.assertNotIn(path, run_guard._active_projects)

    def test_empty_path_is_not_guarded(self):
        # An empty project_path is left to the body's own validation; the guard
        # must not key on it (and must not raise here).
        @exclusive_per_project
        def tool(project_path):
            return "ran"
        self.assertEqual(tool(""), "ran")
        with run_guard._active_lock:
            self.assertEqual(len(run_guard._active_projects), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
