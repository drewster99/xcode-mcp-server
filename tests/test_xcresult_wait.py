#!/usr/bin/env python3
"""Tests for wait_for_xcresult_after_timestamp's new-bundle selection.

The wait helper must accept a bundle that is genuinely new — either a path
absent from the pre-action snapshot, OR a pre-existing path whose mtime has
advanced since the snapshot (Xcode rewriting a bundle in place) — and must NOT
re-accept an unchanged prior-run bundle. The snapshot records {path: mtime} so
the in-place-rewrite case is distinguishable from a stale result.
"""

import os
import sys
import time
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import drews_xcode_mcp.utils.xcresult as xcresult
from drews_xcode_mcp.utils.xcresult import (
    snapshot_xcresult_mtimes,
    wait_for_xcresult_after_timestamp,
)


def _make_xcresult(logs_dir: str, name: str, mtime: float) -> str:
    path = os.path.join(logs_dir, name)
    os.makedirs(path, exist_ok=True)
    os.utime(path, (mtime, mtime))
    return path


class WaitForXcresultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        # Emulate a single matching DerivedData root with a Logs/Launch folder.
        self.derived_root = os.path.join(root, "MyApp-abc123")
        self.logs_dir = os.path.join(self.derived_root, "Logs", "Launch")
        os.makedirs(self.logs_dir)

        # Pin directory matching to our fake root so the helper never touches
        # the real ~/Library/Developer/Xcode/DerivedData.
        self._orig_matching = xcresult._matching_derived_data_dirs
        xcresult._matching_derived_data_dirs = lambda project_path: [(0.0, self.derived_root)]

    def tearDown(self):
        xcresult._matching_derived_data_dirs = self._orig_matching
        self._tmp.cleanup()

    def test_accepts_brand_new_bundle_not_in_snapshot(self):
        now = time.time()
        _make_xcresult(self.logs_dir, "old.xcresult", now - 100)
        prior = snapshot_xcresult_mtimes("MyApp.xcodeproj", logs_subdir="Launch")

        new_path = _make_xcresult(self.logs_dir, "new.xcresult", now)
        result = wait_for_xcresult_after_timestamp(
            "MyApp.xcodeproj", now, timeout_seconds=2,
            logs_subdir="Launch", prior_mtimes=prior,
        )
        self.assertEqual(result, new_path)

    def test_accepts_pre_existing_bundle_rewritten_in_place(self):
        now = time.time()
        reused = _make_xcresult(self.logs_dir, "run.xcresult", now - 100)
        prior = snapshot_xcresult_mtimes("MyApp.xcodeproj", logs_subdir="Launch")
        self.assertIn(reused, prior)

        # Xcode rewrites the same bundle path in place: mtime advances.
        os.utime(reused, (now, now))
        result = wait_for_xcresult_after_timestamp(
            "MyApp.xcodeproj", now, timeout_seconds=2,
            logs_subdir="Launch", prior_mtimes=prior,
        )
        self.assertEqual(result, reused)

    def test_rejects_unchanged_prior_bundle(self):
        now = time.time()
        _make_xcresult(self.logs_dir, "stale.xcresult", now - 100)
        prior = snapshot_xcresult_mtimes("MyApp.xcodeproj", logs_subdir="Launch")

        # Nothing new and nothing rewritten: must time out to None, never
        # re-accept the stale prior-run bundle.
        result = wait_for_xcresult_after_timestamp(
            "MyApp.xcodeproj", now, timeout_seconds=1,
            logs_subdir="Launch", prior_mtimes=prior,
        )
        self.assertIsNone(result)

    def test_newest_new_bundle_is_preferred(self):
        now = time.time()
        prior = snapshot_xcresult_mtimes("MyApp.xcodeproj", logs_subdir="Launch")
        _make_xcresult(self.logs_dir, "a.xcresult", now)
        newest = _make_xcresult(self.logs_dir, "b.xcresult", now + 5)
        result = wait_for_xcresult_after_timestamp(
            "MyApp.xcodeproj", now, timeout_seconds=2,
            logs_subdir="Launch", prior_mtimes=prior,
        )
        self.assertEqual(result, newest)


if __name__ == "__main__":
    unittest.main(verbosity=2)
