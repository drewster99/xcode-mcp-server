#!/usr/bin/env python3
"""
Regression tests for xcactivitylog parsing.

Two coverage gaps caused persistent stale warnings in build_project output:

1. The path regex required [a-zA-Z0-9_/.-] only, silently dropping any project
   path containing a space (very common: "/Users/x/My Project/..."). Files
   missing from compiled_files can never be cleared from the stale-warning set,
   so old warnings linger across incremental builds until the user does a clean.

2. Only SwiftCompile lines and .swift warnings/errors were matched. Mixed-language
   projects (ObjC/C/C++/Metal) were invisible to the parser, so their warnings
   never appeared in aggregation and recompiles never cleared anything.
"""

import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import xcode_mcp_server.utils.build_log_parser as build_log_parser
from xcode_mcp_server.utils.build_log_parser import (
    parse_xcactivitylog,
    select_derived_data_dirs_for_project,
)


def _write_gzipped_log(path: str, text: str) -> None:
    """xcactivitylog files are gzipped — write a fake one."""
    with gzip.open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


class SelectDerivedDataDirsTests(unittest.TestCase):
    """The name-prefix candidate list must collapse to confirmed dirs, and when
    none are confirmed fall back ONLY to dirs of unknown ownership — never to
    ones info.plist proved belong to a different same-named project."""

    def setUp(self):
        self._orig = build_log_parser.derived_data_matches_project

    def tearDown(self):
        build_log_parser.derived_data_matches_project = self._orig

    def _patch(self, verdicts):
        build_log_parser.derived_data_matches_project = (
            lambda path, project_realpath: verdicts[path]
        )

    def test_confirmed_only_when_any_confirmed(self):
        self._patch({'/c1': True, '/c2': True, '/mm': False, '/uk': None})
        dirs = [(0.0, '/c1'), (0.0, '/c2'), (0.0, '/mm'), (0.0, '/uk')]
        self.assertEqual(
            select_derived_data_dirs_for_project(dirs, '/p'),
            [(0.0, '/c1'), (0.0, '/c2')],
        )

    def test_falls_back_to_unknown_excluding_mismatch(self):
        self._patch({'/mm': False, '/uk': None})
        dirs = [(0.0, '/mm'), (0.0, '/uk')]
        self.assertEqual(
            select_derived_data_dirs_for_project(dirs, '/p'),
            [(0.0, '/uk')],
        )

    def test_all_mismatch_returns_empty(self):
        self._patch({'/mm1': False, '/mm2': False})
        dirs = [(0.0, '/mm1'), (0.0, '/mm2')]
        self.assertEqual(select_derived_data_dirs_for_project(dirs, '/p'), [])

    def test_find_derived_data_returns_none_when_all_mismatch(self):
        """find_derived_data_for_project must return None (not IndexError) when
        the selector filters every candidate out as a proven mismatch."""
        from unittest import mock
        with tempfile.TemporaryDirectory() as base:
            os.makedirs(os.path.join(base, "MyApp-abc123"))
            # Every name-prefix dir is a proven mismatch -> selector returns [].
            build_log_parser.derived_data_matches_project = (
                lambda path, project_realpath: False
            )
            with mock.patch.object(
                build_log_parser.os.path, "expanduser", return_value=base
            ):
                result = build_log_parser.find_derived_data_for_project(
                    "/somewhere/MyApp.xcodeproj"
                )
        self.assertIsNone(result)


class PathsWithSpacesTests(unittest.TestCase):
    def test_swift_file_with_space_in_path_is_tracked_as_compiled(self):
        """A path with a space must be recognized in SwiftCompile lines."""
        log_text = (
            "Some preamble\r"
            "SwiftCompile normal arm64 /Users/test/My Project/Sources/Foo.swift "
            "(in target 'App' from project 'App')\r"
            "more output\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            warnings, compiled = parse_xcactivitylog(tmp_path)
            self.assertIn('/Users/test/My Project/Sources/Foo.swift', compiled,
                          f"compiled files were: {compiled}")
        finally:
            os.unlink(tmp_path)

    def test_warning_on_path_with_space_is_extracted(self):
        log_text = (
            "/Users/test/My Project/Sources/Foo.swift:42:5: warning: "
            "variable 'x' was never used\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            warnings, _ = parse_xcactivitylog(tmp_path)
            files = [w['file'] for w in warnings]
            self.assertIn('/Users/test/My Project/Sources/Foo.swift', files,
                          f"warnings were: {warnings}")
        finally:
            os.unlink(tmp_path)


class MixedLanguageTests(unittest.TestCase):
    def test_objc_compilec_line_tracks_source_file(self):
        """CompileC <obj> <source> — we want the source path tracked."""
        log_text = (
            "CompileC /tmp/Build/Foo.o /Users/test/MyProj/Foo.m "
            "normal arm64 objective-c\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            _, compiled = parse_xcactivitylog(tmp_path)
            self.assertIn('/Users/test/MyProj/Foo.m', compiled,
                          f"compiled files were: {compiled}")
        finally:
            os.unlink(tmp_path)

    def test_objc_compilec_with_space_in_object_path_tracks_source(self):
        """The object-file path (under DerivedData) may contain a space; the
        source file must still be tracked rather than dropped."""
        log_text = (
            "CompileC /Users/test/My Project/Build/Foo.o "
            "/Users/test/My Project/Foo.m normal arm64 objective-c\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            _, compiled = parse_xcactivitylog(tmp_path)
            self.assertIn('/Users/test/My Project/Foo.m', compiled,
                          f"compiled files were: {compiled}")
        finally:
            os.unlink(tmp_path)

    def test_objc_warning_is_extracted(self):
        log_text = (
            "/Users/test/MyProj/Foo.m:10:3: warning: "
            "'someAPI' is deprecated\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            warnings, _ = parse_xcactivitylog(tmp_path)
            self.assertTrue(
                any(w['file'] == '/Users/test/MyProj/Foo.m' for w in warnings),
                f"warnings were: {warnings}"
            )
        finally:
            os.unlink(tmp_path)


class ExistingBehaviorPreservedTests(unittest.TestCase):
    def test_plain_swift_path_still_works(self):
        log_text = (
            "SwiftCompile normal arm64 /Users/test/Proj/Sources/Foo.swift "
            "(in target 'App' from project 'App')\r"
            "/Users/test/Proj/Sources/Foo.swift:99:1: warning: shadows\r"
        )
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            warnings, compiled = parse_xcactivitylog(tmp_path)
            self.assertIn('/Users/test/Proj/Sources/Foo.swift', compiled)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]['line'], 99)
            self.assertEqual(warnings[0]['column'], 1)
            self.assertEqual(warnings[0]['type'], 'warning')
        finally:
            os.unlink(tmp_path)

    def test_error_extracted_with_type_error(self):
        log_text = "/Users/test/Proj/Sources/Foo.swift:5:1: error: bad thing\r"
        with tempfile.NamedTemporaryFile(suffix='.xcactivitylog', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _write_gzipped_log(tmp_path, log_text)
            warnings, _ = parse_xcactivitylog(tmp_path)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]['type'], 'error')
        finally:
            os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
