#!/usr/bin/env python3
"""Shared xcodebuild query helpers for scheme and run-destination discovery.

These wrap read-only `xcodebuild -list` / `-showdestinations` invocations that
have no Xcode side effects, so multiple tools (list_run_destinations,
list_project_tests, and the selective test runner) can resolve a scheme and a
buildable destination the same way.
"""

import glob
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional


def project_flag_for(project_path: str) -> str:
    """Return the xcodebuild flag (`-workspace` or `-project`) for a path."""
    return '-workspace' if project_path.endswith('.xcworkspace') else '-project'


def get_active_scheme(project_path: str) -> Optional[str]:
    """
    Return the active scheme from xcschememanagement.plist without opening Xcode.

    "Active" here means the scheme with the lowest orderHint (the top of Xcode's
    scheme menu). This is a side-effect-free heuristic; the only way to read the
    truly-selected scheme is AppleScript, which would open the project in Xcode.
    Returns None if the plist is missing or unreadable.
    """
    pattern = os.path.join(project_path, "xcuserdata", "*", "xcschemes", "xcschememanagement.plist")
    matches = glob.glob(pattern)
    if not matches:
        return None

    plist_path = max(matches, key=os.path.getmtime)
    try:
        result = subprocess.run(
            ['plutil', '-convert', 'json', '-o', '-', plist_path],
            capture_output=True, text=True, timeout=5,
        )
    except subprocess.TimeoutExpired:
        print(f"warn: plutil timed out reading {plist_path}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("warn: `plutil` binary not found on PATH", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"warn: plutil exited {result.returncode} for {plist_path}: "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"warn: plutil produced invalid JSON for {plist_path}: {e}", file=sys.stderr)
        return None

    scheme_state = data.get("SchemeUserState", {})
    best_scheme = None
    best_order = float('inf')
    for key, value in scheme_state.items():
        scheme_name = key.split('.xcscheme')[0]
        order = value.get('orderHint', 999)
        if order < best_order:
            best_order = order
            best_scheme = scheme_name
    return best_scheme


def get_first_scheme(project_path: str) -> Optional[str]:
    """Return the first scheme name via `xcodebuild -list` (no Xcode side effects)."""
    try:
        result = subprocess.run(
            ['xcodebuild', '-list', project_flag_for(project_path), project_path],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        print(f"warn: xcodebuild -list timed out for {project_path}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("warn: `xcodebuild` binary not found on PATH", file=sys.stderr)
        return None

    in_schemes = False
    for line in result.stdout.split('\n'):
        stripped = line.strip()
        if stripped == 'Schemes:':
            in_schemes = True
            continue
        if in_schemes:
            if stripped == '' or stripped.endswith(':'):
                break
            return stripped
    return None


def parse_destination_line(line: str) -> Optional[Dict]:
    """
    Parse a single `xcodebuild -showdestinations` destination line.
    Format: { platform:iOS Simulator, arch:arm64, id:ABC123, OS:26.4, name:iPhone 17 Pro }

    Ineligible destinations carry a trailing `error:` describing why the
    scheme can't use them; that key is preserved so callers can filter on it.
    Returns None for lines without both a name and an id (e.g. generic
    "Any Mac" placeholders).
    """
    line = line.strip()
    if not line.startswith('{') or not line.endswith('}'):
        return None

    inner = line[1:-1].strip()
    if not inner:
        return None

    # Parse key:value pairs — keys are simple words, values run until next ", key:" or end
    result = {}
    pattern = r'(\w+):(.+?)(?=, \w+:|$)'
    for match in re.finditer(pattern, inner):
        key = match.group(1).strip()
        value = match.group(2).strip()
        result[key] = value

    if not result.get('name') or not result.get('id'):
        return None

    return result


def list_destinations(project_path: str, scheme: str, timeout: int = 30) -> List[Dict]:
    """
    Return parsed destinations for a scheme via `xcodebuild -showdestinations`.

    Generic placeholder destinations (those whose id contains 'placeholder')
    are dropped. Ineligible destinations are kept, each with an 'error' field.
    Raises subprocess.TimeoutExpired if xcodebuild does not respond in time.
    """
    result = subprocess.run(
        ['xcodebuild', '-showdestinations', project_flag_for(project_path),
         project_path, '-scheme', scheme],
        capture_output=True, text=True, timeout=timeout,
    )
    output = result.stdout + result.stderr

    destinations = []
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            parsed = parse_destination_line(line)
            if parsed and 'placeholder' not in parsed.get('id', ''):
                destinations.append(parsed)
    return destinations


def _destination_test_rank(dest: Dict) -> int:
    """
    Rank a compatible destination by how well it supports building and loading a
    test bundle (lower is better):

      0  Simulator — no code signing, the test bundle loads reliably, and it
         enumerates the same tests as the matching device.
      1  Native macOS — for genuine Mac apps (no "Designed for iPad" variant).
      2  Everything else — physical devices (need signing/attachment) and the
         "My Mac (Designed for iPad)" Catalyst-style destination, where an iOS
         test bundle can fail to load.
    """
    platform = dest.get('platform', '')
    variant = dest.get('variant', '')
    if 'Simulator' in platform:
        return 0
    if platform == 'macOS' and 'Designed for' not in variant:
        return 1
    return 2


def resolve_buildable_destination(project_path: str, scheme: str) -> Optional[str]:
    """
    Return a `-destination` argument value (e.g. "id=00006040-...") for the
    destination best suited to building and enumerating the scheme's tests.

    Considers only destinations xcodebuild reports as compatible (no 'error'),
    then prefers a simulator, then a native Mac, then anything else (see
    _destination_test_rank). This avoids the "My Mac (Designed for iPad)"
    destination, on which an iOS test bundle can fail to load. The enumerated
    test set is identical across same-platform destinations, so any compatible
    one of the preferred kind suffices.

    Returns None if no compatible destination can be determined (e.g. xcodebuild
    timed out, or the scheme has no eligible destinations).
    """
    try:
        destinations = list_destinations(project_path, scheme)
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return None

    compatible = [dest for dest in destinations if 'error' not in dest]
    if not compatible:
        return None

    # min() is stable, so this keeps xcodebuild's order within a rank.
    best = min(compatible, key=_destination_test_rank)
    return f"id={best['id']}"
