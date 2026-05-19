#!/usr/bin/env python3
"""
Regression tests for the LogStoreManifest UUID-diff wait used to fix stale
build warnings.

Before this fix, build_project read the manifest immediately after AppleScript
returned, before Xcode had necessarily written the current build's xcactivitylog
entry. Aggregation then operated on stale data and surfaced warnings the user
had already fixed.

These tests exercise the deterministic alternative: snapshot the manifest's
build UUIDs before kicking off the build, then poll until a new build UUID
appears whose timeStartedRecording is at or after our start time.
"""

import os
import sys
import time
import plistlib
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from xcode_mcp_server.utils.build_log_parser import (
    CF_EPOCH_OFFSET,
    snapshot_build_uuids,
    wait_for_new_build_uuid,
)


def _make_entry(title: str, time_started_cf: float, file_uuid: str = None) -> dict:
    """Build a single LogStoreManifest-style log entry."""
    if file_uuid is None:
        file_uuid = str(uuid.uuid4()).upper()
    return {
        'className': 'IDEActivityLogSection',
        'documentTypeString': '<nil>',
        'domainType': 'Xcode.IDEActivityLogDomainType.BuildLog',
        'fileName': f'{file_uuid}.xcactivitylog',
        'hasPrimaryLog': True,
        'primaryObservable': {
            'highLevelStatus': 'S',
            'totalNumberOfAnalyzerIssues': 0,
            'totalNumberOfErrors': 0,
            'totalNumberOfTestFailures': 0,
            'totalNumberOfWarnings': 0,
        },
        'schemeIdentifier-containerName': 'Test project',
        'schemeIdentifier-schemeName': 'TestScheme',
        'schemeIdentifier-sharedScheme': 1,
        'signature': title,
        'timeStartedRecording': time_started_cf,
        'timeStoppedRecording': time_started_cf + 1.0,
        'title': title,
        'uniqueIdentifier': file_uuid,
    }


def _write_manifest(path: str, entries: list) -> None:
    plist = {
        'logFormatVersion': 11,
        'logs': {e['uniqueIdentifier']: e for e in entries},
    }
    with open(path, 'wb') as f:
        plistlib.dump(plist, f)


def _now_cf() -> float:
    """Current time as CFAbsoluteTime (seconds since 2001-01-01 UTC)."""
    return time.time() - CF_EPOCH_OFFSET


class SnapshotTests(unittest.TestCase):
    def test_snapshot_returns_all_uuids_regardless_of_title(self):
        """The snapshot is just the existing UUIDs — title filtering happens later."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            build_uuid = str(uuid.uuid4()).upper()
            clean_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, build_uuid),
                _make_entry('Clean TestScheme', _now_cf() - 30, clean_uuid),
            ])

            snap = snapshot_build_uuids(manifest)

            self.assertIn(build_uuid, snap)
            self.assertIn(clean_uuid, snap)

    def test_snapshot_missing_manifest_returns_empty_set(self):
        """First-ever build has no manifest yet — must not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            snap = snapshot_build_uuids(manifest)
            self.assertEqual(snap, set())


class WaitForNewBuildUUIDTests(unittest.TestCase):
    def test_returns_immediately_when_new_build_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            existing_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
            ])
            before = snapshot_build_uuids(manifest)

            start_unix = time.time()
            new_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
                _make_entry('Build TestScheme', _now_cf() + 0.1, new_uuid),
            ])

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=2.0)
            self.assertEqual(found, new_uuid)

    def test_returns_new_uuid_added_mid_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            existing_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
            ])
            before = snapshot_build_uuids(manifest)
            start_unix = time.time()
            new_uuid = str(uuid.uuid4()).upper()

            def append_after_delay():
                time.sleep(0.6)
                _write_manifest(manifest, [
                    _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
                    _make_entry('Build TestScheme', _now_cf(), new_uuid),
                ])

            t = threading.Thread(target=append_after_delay, daemon=True)
            t.start()

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=5.0)
            t.join(timeout=2.0)
            self.assertEqual(found, new_uuid)

    def test_timeout_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            existing_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
            ])
            before = snapshot_build_uuids(manifest)
            start_unix = time.time()

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=1.0)
            self.assertIsNone(found)

    def test_clean_entries_are_ignored(self):
        """A Clean operation creates a manifest entry too; it must not be mistaken for our build."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            existing_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
            ])
            before = snapshot_build_uuids(manifest)
            start_unix = time.time()
            clean_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
                _make_entry('Clean TestScheme', _now_cf(), clean_uuid),
            ])

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=1.0)
            self.assertIsNone(found, "Clean entry must not be returned as 'our' build")

    def test_pre_existing_build_with_old_timestamp_is_rejected(self):
        """
        If a user-triggered build finished before our snapshot (but somehow wasn't
        in the snapshot — e.g. they hit Cmd-B between our snapshot and our wait),
        its older timestamp must exclude it from being treated as ours.
        """
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            old_present_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, old_present_uuid),
            ])
            before = snapshot_build_uuids(manifest)

            start_unix = time.time()
            # A build entry that started well before our start time, but isn't
            # in `before` — this represents an entry we missed.
            stray_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, old_present_uuid),
                _make_entry('Build TestScheme', _now_cf() - 30, stray_uuid),
            ])

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=1.0)
            self.assertIsNone(found)

    def test_accepts_only_build_with_timestamp_at_or_after_start(self):
        """Stale stray entry (older) ignored; our entry (newer) accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = os.path.join(tmp, 'LogStoreManifest.plist')
            existing_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
            ])
            before = snapshot_build_uuids(manifest)
            start_unix = time.time()

            stray_uuid = str(uuid.uuid4()).upper()
            our_uuid = str(uuid.uuid4()).upper()
            _write_manifest(manifest, [
                _make_entry('Build TestScheme', _now_cf() - 60, existing_uuid),
                _make_entry('Build TestScheme', _now_cf() - 30, stray_uuid),
                _make_entry('Build TestScheme', _now_cf() + 0.1, our_uuid),
            ])

            found = wait_for_new_build_uuid(manifest, before, start_unix, timeout_seconds=2.0)
            self.assertEqual(found, our_uuid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
