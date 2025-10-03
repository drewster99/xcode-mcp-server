#!/usr/bin/env python3
"""Screenshot and window management utilities"""

import os
import sys
import subprocess
import tempfile

from xcode_mcp_server.exceptions import XCodeMCPError


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

    # Write Swift code to temporary file and execute
    with tempfile.NamedTemporaryFile(mode='w', suffix='.swift', delete=False) as f:
        f.write(swift_code)
        temp_file = f.name

    try:
        # Run Swift code
        result = subprocess.run(
            ['swift', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise XCodeMCPError(f"Failed to get window list: {result.stderr}")

        output = result.stdout

    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file)
        except:
            pass

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
