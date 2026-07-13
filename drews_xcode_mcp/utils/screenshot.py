#!/usr/bin/env python3
"""Screenshot and window management utilities"""

import os
import subprocess
import tempfile
import time
import uuid

from drews_xcode_mcp.exceptions import XCodeMCPError
from drews_xcode_mcp.utils.paths import SCREENSHOT_DIR

# Screenshots are written to a per-user cache directory (see utils.paths) so
# they are not world-readable like /tmp would be. Files older than the
# retention window are pruned on each call to keep the directory bounded
# without an external cron.
SCREENSHOT_RETENTION_SECONDS = 24 * 60 * 60


def _prune_old_screenshots(directory: str, retention_seconds: int) -> None:
    """Delete .png files in `directory` older than `retention_seconds`."""
    cutoff = time.time() - retention_seconds
    try:
        entries = os.listdir(directory)
    except OSError:
        return
    for name in entries:
        if not name.endswith('.png'):
            continue
        path = os.path.join(directory, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)
        except OSError:
            continue


def get_screenshot_path(prefix: str) -> str:
    """
    Return a unique path inside the screenshot cache directory.

    Ensures the directory exists and prunes screenshots older than
    SCREENSHOT_RETENTION_SECONDS so the cache does not grow without bound.
    """
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    _prune_old_screenshots(SCREENSHOT_DIR, SCREENSHOT_RETENTION_SECONDS)
    return os.path.join(SCREENSHOT_DIR, f"{prefix}_{uuid.uuid4()}.png")


def _get_booted_simulators():
    """
    Internal helper to get list of booted simulators using text parsing.
    Returns a list of dicts with 'name', 'udid', and 'os' keys.
    """
    result = subprocess.run(
        ['xcrun', 'simctl', 'list', 'devices', 'booted'],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        raise XCodeMCPError(f"Failed to list simulators: {result.stderr}")

    lines = result.stdout.strip().split('\n')
    booted_simulators = []
    current_os = None

    for line in lines:
        line = line.strip()
        # Check for OS version headers like "-- iOS 26.0 --"
        if line.startswith('-- ') and line.endswith(' --'):
            current_os = line[3:-3].strip()
        # Check for booted device lines
        elif '(Booted)' in line and current_os:
            # Parse device info from line like: "iPad (A16) (D89C8520-3426-49B2-9CF5-09DCA506DC66) (Booted)"
            import re
            match = re.match(r'(.+?)\s+\(([A-F0-9-]+)\)\s+\(Booted\)', line)
            if match:
                device_name = match.group(1).strip()
                device_udid = match.group(2).strip()
                booted_simulators.append({
                    'name': device_name,
                    'udid': device_udid,
                    'os': current_os
                })

    return booted_simulators


def _get_all_windows():
    """
    Internal helper to get all windows grouped by app.
    Returns a dict of {app_name: [window_info, ...]}
    """
    # Use Swift to get window information via CoreGraphics
    swift_code = '''
import Cocoa
import CoreGraphics

// Get all on-screen windows
let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windowList = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    print("ERROR: Failed to get window list")
    exit(1)
}

// Group windows by app and filter out system UI elements
var appWindows: [String: [(id: Int, title: String, pid: Int)]] = [:]

for window in windowList {
    let windowID = window[kCGWindowNumber as String] as? Int ?? 0
    let appName = window[kCGWindowOwnerName as String] as? String ?? "Unknown"
    let windowTitle = window[kCGWindowName as String] as? String ?? ""
    let windowLayer = window[kCGWindowLayer as String] as? Int ?? 0
    let ownerPID = window[kCGWindowOwnerPID as String] as? Int ?? 0

    // Skip menu bar items and system UI (layer 0 is normal windows)
    // Also skip windows without titles
    if windowLayer == 0 && !windowTitle.isEmpty {
        if appWindows[appName] == nil {
            appWindows[appName] = []
        }
        appWindows[appName]?.append((id: windowID, title: windowTitle, pid: ownerPID))
    }
}

// Output as structured format for parsing
for (app, windows) in appWindows.sorted(by: { $0.key < $1.key }) {
    print("APP:\\(app)")
    for window in windows {
        print("WINDOW:\\(window.id)\\t\\(window.pid)\\t\\(window.title)")
    }
}
'''

    # TemporaryDirectory guarantees cleanup on normal exit, including
    # exceptions raised inside the block.
    with tempfile.TemporaryDirectory(prefix='xcode-mcp-swift-') as tmpdir:
        temp_file = os.path.join(tmpdir, 'get_windows.swift')
        with open(temp_file, 'w') as f:
            f.write(swift_code)

        result = subprocess.run(
            ['swift', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise XCodeMCPError(f"Failed to get window list: {result.stderr}")

        output = result.stdout

    # Check for error
    if output.startswith("ERROR:"):
        raise XCodeMCPError(output.replace("ERROR: ", ""))

    # Parse the output
    apps_with_windows = {}
    current_app = None

    for line in output.strip().split('\n'):
        if line.startswith('APP:'):
            current_app = line[4:]
            apps_with_windows[current_app] = []
        elif line.startswith('WINDOW:') and current_app:
            parts = line[7:].split('\t', 2)
            if len(parts) >= 3:
                window_id = int(parts[0])
                pid = parts[1]
                title = parts[2]
                apps_with_windows[current_app].append({
                    'id': window_id,
                    'pid': pid,
                    'title': title
                })

    return apps_with_windows
