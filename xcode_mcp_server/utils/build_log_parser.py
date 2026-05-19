#!/usr/bin/env python3
"""Build log parsing utilities for aggregating warnings across multiple builds"""

import os
import sys
import time
import gzip
import re
import plistlib
from typing import List, Dict, Set, Tuple, Optional

# Seconds between the Unix epoch (1970-01-01) and the Cocoa/CFAbsoluteTime
# epoch (2001-01-01). Xcode's LogStoreManifest.plist stores timeStartedRecording
# in CFAbsoluteTime — subtract this offset from time.time() to compare.
CF_EPOCH_OFFSET = 978307200.0

# Source-file extensions we recognize in xcactivitylog warnings/errors and
# compile records. Ordered longest-first so the regex alternation prefers
# .mm over .m, .cpp over .c, etc.
_SOURCE_EXTS = (
    'swift', 'metal',
    'mm', 'cpp', 'cxx', 'cc', 'hpp',
    'm', 'c', 'h',
)
_SOURCE_EXT_ALT = '|'.join(_SOURCE_EXTS)


def parse_manifest_plist(manifest_path: str) -> List[Dict]:
    """
    Parse LogStoreManifest.plist and extract build metadata.

    Args:
        manifest_path: Path to LogStoreManifest.plist

    Returns:
        List of build metadata dictionaries, sorted chronologically by timeStartedRecording.
        Each dict contains: uuid, fileName, timeStartedRecording, title, errors, warnings, status
    """
    try:
        with open(manifest_path, 'rb') as f:
            plist_data = plistlib.load(f)

        builds = []
        logs = plist_data.get('logs', {})

        for uuid, log_entry in logs.items():
            primary = log_entry.get('primaryObservable', {})

            build_info = {
                'uuid': uuid,
                'fileName': log_entry.get('fileName', ''),
                'timeStartedRecording': log_entry.get('timeStartedRecording', 0),
                'title': log_entry.get('title', ''),
                'errors': primary.get('totalNumberOfErrors', 0),
                'warnings': primary.get('totalNumberOfWarnings', 0),
                'status': primary.get('highLevelStatus', 'U')  # S=Success, W=Warning, E=Error, U=Unknown
            }

            builds.append(build_info)

        # Sort chronologically by timeStartedRecording
        builds.sort(key=lambda x: x['timeStartedRecording'])

        return builds

    except Exception as e:
        print(f"Error parsing manifest plist: {e}", file=sys.stderr)
        return []


def parse_xcactivitylog(log_path: str) -> Tuple[List[Dict], Set[str]]:
    """
    Parse an .xcactivitylog file to extract warnings and compiled files.

    The log files are gzip-compressed and contain both binary and text data.
    We use gzip to decompress and then extract text with error handling for binary data.

    Args:
        log_path: Path to the .xcactivitylog file

    Returns:
        Tuple of (warnings_list, compiled_files_set)
        - warnings_list: List of dicts with keys: file, line, column, message
        - compiled_files_set: Set of file paths that were compiled in this build
    """
    warnings = []
    compiled_files = set()

    # Path char class: any printable byte except control bytes, the U+FFFD
    # replacement character (binary bytes after errors='replace' decode), the
    # path-list/colon separators, and a few characters Xcode's log format uses
    # as field separators between the path and following metadata.
    # This still allows spaces, parentheses inside paths, etc., because we
    # anchor the end of the match to a known terminator below.
    path_char = r'[^\r\n\x00-\x1f�]'

    # Warning/error lines:
    #   /abs/path/to/File.ext:LINE:COL: warning|error: message
    # The non-greedy {path}+? combined with the literal `.ext:digits:digits:`
    # naturally terminates the path at the right place even when it contains
    # spaces. Limit the message to non-control characters so we don't slurp
    # binary trailing bytes.
    warning_pattern = re.compile(
        rf'(/{path_char}+?\.(?:{_SOURCE_EXT_ALT})):(\d+):(\d+): warning: ([^\n\r\x00-\x08\x0b-\x1f�]+)'
    )
    error_pattern = re.compile(
        rf'(/{path_char}+?\.(?:{_SOURCE_EXT_ALT})):(\d+):(\d+): error: ([^\n\r\x00-\x08\x0b-\x1f�]+)'
    )

    # SwiftCompile lines:
    #   SwiftCompile normal <arch> /abs/path/to/File.swift (in target '...' from project '...')
    # The path ends at " (in target" or at end-of-line / control byte.
    swift_compile_pattern = re.compile(
        rf'SwiftCompile normal \S+ (/{path_char}+?\.swift)(?= \(in target|\s*[\r\n]|\s*$)'
    )

    # CompileC / CompileCpp / CompileObjC / CompileObjCpp / CompileMetalFile:
    # Format starts with the object-file path then a space then the source path:
    #   CompileC <output>.o <source>.m normal arm64 objective-c ...
    #   CompileMetalFile <source>.metal ...
    # We want the SOURCE path, which is the last filename-with-known-extension.
    cc_compile_pattern = re.compile(
        rf'Compile(?:C|Cpp|ObjC|ObjCpp) \S+\.o (/{path_char}+?\.(?:m|mm|c|cc|cpp|cxx))(?= \(in target|\s+normal\s|\s+[a-z]|\s*[\r\n]|\s*$)'
    )
    metal_compile_pattern = re.compile(
        rf'CompileMetalFile (/{path_char}+?\.metal)(?= \(in target|\s*[\r\n]|\s*$)'
    )

    try:
        with gzip.open(log_path, 'rb') as f:
            # Read the file and decode with error handling for binary data
            content = f.read()
            # Use 'replace' to handle binary data gracefully
            text = content.decode('utf-8', errors='replace')

            # Extract warnings
            for match in warning_pattern.finditer(text):
                file_path = match.group(1)
                line = int(match.group(2))
                column = int(match.group(3))
                message = match.group(4).strip()

                warnings.append({
                    'file': file_path,
                    'line': line,
                    'column': column,
                    'message': message,
                    'type': 'warning'
                })

            # Extract errors (in case we want to support them later)
            for match in error_pattern.finditer(text):
                file_path = match.group(1)
                line = int(match.group(2))
                column = int(match.group(3))
                message = match.group(4).strip()

                warnings.append({
                    'file': file_path,
                    'line': line,
                    'column': column,
                    'message': message,
                    'type': 'error'
                })

            # Extract compiled files (Swift, ObjC/C/C++, Metal)
            for match in swift_compile_pattern.finditer(text):
                compiled_files.add(match.group(1))
            for match in cc_compile_pattern.finditer(text):
                compiled_files.add(match.group(1))
            for match in metal_compile_pattern.finditer(text):
                compiled_files.add(match.group(1))

    except Exception as e:
        print(f"Error parsing xcactivitylog {log_path}: {e}", file=sys.stderr)

    return warnings, compiled_files


def aggregate_warnings_since_clean(manifest_path: str, logs_dir: str) -> Dict:
    """
    Aggregate warnings from all builds since the last clean operation.

    Strategy:
    1. Parse manifest to find all builds
    2. Find the most recent "Clean" operation
    3. Parse all builds after the clean chronologically
    4. Track which files were recompiled in later builds
    5. Exclude warnings from files that were recompiled

    Args:
        manifest_path: Path to LogStoreManifest.plist
        logs_dir: Path to the Logs/Build directory containing .xcactivitylog files

    Returns:
        Dictionary with:
        - summary: Build counts, clean info, warning counts
        - aggregated_warnings: List of warnings (excluding recompiled files)
        - recompiled_files: List of files that were recompiled and excluded
        - builds_analyzed: List of build metadata
    """
    # Parse manifest
    builds = parse_manifest_plist(manifest_path)

    if not builds:
        return {
            'summary': {
                'total_builds': 0,
                'error': 'Failed to parse manifest or no builds found'
            }
        }

    # Find the most recent clean operation
    last_clean_index = -1
    for i in range(len(builds) - 1, -1, -1):
        if 'Clean' in builds[i]['title']:
            last_clean_index = i
            break

    # If no clean found, use all builds
    if last_clean_index == -1:
        builds_to_analyze = builds
        clean_info = 'No clean operation found - analyzing all builds'
    else:
        # Use builds after the clean (not including the clean itself)
        builds_to_analyze = builds[last_clean_index + 1:]
        clean_info = f"Found clean at index {last_clean_index}: {builds[last_clean_index]['title']}"

    print(f"Analyzing {len(builds_to_analyze)} builds since last clean", file=sys.stderr)

    # Parse each build's xcactivitylog file
    all_warnings = []
    file_last_compiled: Dict[str, float] = {}
    builds_analyzed = []

    for build in builds_to_analyze:
        log_file = os.path.join(logs_dir, build['fileName'])

        if not os.path.exists(log_file):
            print(f"Warning: Log file not found: {log_file}", file=sys.stderr)
            continue

        warnings, compiled_files = parse_xcactivitylog(log_file)

        # Track the latest build time each file was compiled in
        build_time = build['timeStartedRecording']
        for f in compiled_files:
            if f not in file_last_compiled or build_time > file_last_compiled[f]:
                file_last_compiled[f] = build_time

        # Store warnings with build context
        for warning in warnings:
            warning['build_uuid'] = build['uuid']
            warning['build_time'] = build_time
            all_warnings.append(warning)

        builds_analyzed.append({
            'uuid': build['uuid'],
            'title': build['title'],
            'time': build_time,
            'warnings_found': len(warnings),
            'files_compiled': len(compiled_files)
        })

    # Now filter warnings: keep only the LATEST warning for each file
    # Strategy: For each file, keep only warnings from the most recent build that touched that file

    # Group warnings by file
    warnings_by_file = {}
    for warning in all_warnings:
        file_path = warning['file']
        if file_path not in warnings_by_file:
            warnings_by_file[file_path] = []
        warnings_by_file[file_path].append(warning)

    # For each file, keep only warnings from the most recent build
    aggregated_warnings = []
    files_with_multiple_builds = []

    for file_path, file_warnings in warnings_by_file.items():
        # Sort by build time (descending) to get most recent first
        file_warnings.sort(key=lambda x: x['build_time'], reverse=True)

        # Get the most recent build time for this file's warnings
        most_recent_warning_time = file_warnings[0]['build_time']

        # If this file was recompiled in a later build without warnings, the
        # old warnings are stale — the file now compiles cleanly.
        last_compiled = file_last_compiled.get(file_path)
        if last_compiled is not None and last_compiled > most_recent_warning_time:
            continue

        # Keep only warnings from the most recent build
        recent_warnings = [w for w in file_warnings if w['build_time'] == most_recent_warning_time]

        # Track if file had warnings in multiple builds
        unique_build_times = set(w['build_time'] for w in file_warnings)
        if len(unique_build_times) > 1:
            files_with_multiple_builds.append({
                'file': file_path,
                'builds': len(unique_build_times),
                'warnings_excluded': len(file_warnings) - len(recent_warnings)
            })

        aggregated_warnings.extend(recent_warnings)

    # Sort final warnings by file, then line number
    aggregated_warnings.sort(key=lambda x: (x['file'], x['line']))

    # Build summary
    summary = {
        'total_builds': len(builds),
        'builds_since_clean': len(builds_to_analyze),
        'builds_analyzed': len(builds_analyzed),
        'clean_info': clean_info,
        'total_warnings': len(aggregated_warnings),
        'warnings_by_type': {
            'warnings': len([w for w in aggregated_warnings if w['type'] == 'warning']),
            'errors': len([w for w in aggregated_warnings if w['type'] == 'error'])
        },
        'unique_files_with_warnings': len(warnings_by_file),
        'files_recompiled_multiple_times': len(files_with_multiple_builds)
    }

    # Format aggregated warnings for output (remove build context)
    formatted_warnings = []
    for warning in aggregated_warnings:
        formatted_warnings.append({
            'file': warning['file'],
            'line': warning['line'],
            'column': warning['column'],
            'message': warning['message'],
            'type': warning['type']
        })

    return {
        'summary': summary,
        'aggregated_warnings': formatted_warnings,
        'files_with_multiple_builds': files_with_multiple_builds,
        'builds_analyzed': builds_analyzed
    }


def snapshot_build_uuids(manifest_path: str) -> Set[str]:
    """
    Return the set of uniqueIdentifier values currently in the manifest.

    Used to detect which manifest entries already existed before kicking off
    a build, so we can spot the new entry our build creates.

    Returns an empty set if the manifest doesn't exist (first-ever build) or
    can't be parsed — callers treat that as "no snapshot, accept any new entry".
    """
    if not os.path.exists(manifest_path):
        return set()
    try:
        with open(manifest_path, 'rb') as f:
            plist_data = plistlib.load(f)
        return set(plist_data.get('logs', {}).keys())
    except Exception as e:
        print(f"Warning: failed to snapshot manifest {manifest_path}: {e}", file=sys.stderr)
        return set()


def wait_for_new_build_uuid(
    manifest_path: str,
    before_uuids: Set[str],
    unix_start_time: float,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.25,
) -> Optional[str]:
    """
    Poll the manifest until a new build entry (not in before_uuids) appears
    that started at or after unix_start_time.

    The timestamp lower bound guards against the rare case where a user
    triggers a build via the Xcode UI between our snapshot and our wait;
    such an entry would not be in before_uuids but would have a
    timeStartedRecording older than our start.

    Entries whose title indicates a non-build action (currently: "Clean ...")
    are ignored, since the manifest records cleans alongside builds.

    Args:
        manifest_path: Path to LogStoreManifest.plist
        before_uuids: Set returned by snapshot_build_uuids() before the build started
        unix_start_time: time.time() captured before AppleScript was invoked
        timeout_seconds: Maximum time to wait for the new entry
        poll_interval: Sleep between polls

    Returns:
        The uniqueIdentifier of our build, or None on timeout.
    """
    # Filesystem mtimes and CFAbsoluteTime conversion both have sub-second
    # granularity — allow a small slack so a manifest entry written in the
    # same wall-clock second as our start isn't rejected as "too old".
    timestamp_slack_seconds = 1.0
    effective_start_cf = unix_start_time - CF_EPOCH_OFFSET - timestamp_slack_seconds

    deadline = time.time() + timeout_seconds

    while True:
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, 'rb') as f:
                    plist_data = plistlib.load(f)

                for log_uuid, entry in plist_data.get('logs', {}).items():
                    if log_uuid in before_uuids:
                        continue

                    title = entry.get('title', '')
                    # Build entries start with "Build " in Xcode's manifest;
                    # Clean entries start with "Clean ". Skip anything that
                    # doesn't look like a build action.
                    if not title.startswith('Build'):
                        continue

                    started = entry.get('timeStartedRecording', 0)
                    if not isinstance(started, (int, float)):
                        continue

                    if started >= effective_start_cf:
                        return log_uuid
        except Exception as e:
            print(f"Warning: error polling manifest {manifest_path}: {e}", file=sys.stderr)

        if time.time() >= deadline:
            return None
        time.sleep(poll_interval)


def find_derived_data_for_project(project_path: str) -> Optional[str]:
    """
    Find the DerivedData directory for a given project.

    Args:
        project_path: Path to .xcodeproj or .xcworkspace

    Returns:
        Path to the project's DerivedData directory, or None if not found
    """
    # Normalize and get project name
    normalized_path = os.path.realpath(project_path)
    project_name = os.path.basename(normalized_path).replace('.xcworkspace', '').replace('.xcodeproj', '')

    # Find DerivedData directory
    derived_data_base = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")

    if not os.path.exists(derived_data_base):
        return None

    # Look for directories matching the project name
    # DerivedData directories typically have format: ProjectName-randomhash
    try:
        for derived_dir in os.listdir(derived_data_base):
            # More precise matching: must start with project name followed by a dash
            if derived_dir.startswith(project_name + "-"):
                derived_data_path = os.path.join(derived_data_base, derived_dir)
                if os.path.isdir(derived_data_path):
                    return derived_data_path
    except Exception as e:
        print(f"Error searching for DerivedData: {e}", file=sys.stderr)

    return None
