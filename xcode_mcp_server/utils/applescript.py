#!/usr/bin/env python3
"""AppleScript execution and notification utilities"""

import subprocess
from typing import Tuple

# Global notification setting - initialized by CLI
NOTIFICATIONS_ENABLED = True


def set_notifications_enabled(enabled: bool):
    """Set the global notification setting"""
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = enabled


def escape_applescript_string(s: str) -> str:
    """
    Escape a string for safe use in AppleScript.

    Args:
        s: String to escape

    Returns:
        Escaped string safe for AppleScript
    """
    # Escape backslashes first, then quotes
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def run_applescript(script: str) -> Tuple[bool, str]:
    """Run an AppleScript and return success status and output"""
    try:
        result = subprocess.run(['osascript', '-e', script],
                               capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()


def show_notification(title: str, message: str, subtitle: str = None, sound: bool = False):
    """Show a macOS notification if notifications are enabled

    Args:
        title: Notification title
        message: Notification message body
        subtitle: Optional subtitle (shown below title)
        sound: Whether to play a sound (for errors/important events)
    """
    if NOTIFICATIONS_ENABLED:
        try:
            # Build AppleScript command
            script = f'display notification "{message}" with title "{title}"'
            if subtitle:
                script += f' subtitle "{subtitle}"'
            if sound:
                script += ' sound name "Frog"'

            subprocess.run(['osascript', '-e', script], capture_output=True)
        except:
            pass  # Ignore notification errors


def show_error_notification(message: str, details: str = None):
    """Show an error notification with sound"""
    show_notification("Xcode MCP", message, subtitle=details, sound=True)


def show_result_notification(message: str, details: str = None):
    """Show a result notification"""
    show_notification("Xcode MCP", message, subtitle=details)
