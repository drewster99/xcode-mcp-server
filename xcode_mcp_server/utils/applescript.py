#!/usr/bin/env python3
"""AppleScript execution and notification utilities"""

import subprocess
import datetime
from typing import Tuple, List, Dict

# Global notification setting - initialized by CLI
NOTIFICATIONS_ENABLED = True

# Global notification history - stores all notifications posted
NOTIFICATION_HISTORY: List[Dict[str, str]] = []


def set_notifications_enabled(enabled: bool):
    """Set the global notification setting"""
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = enabled


def get_notification_history() -> List[Dict[str, str]]:
    """Get the notification history"""
    return NOTIFICATION_HISTORY.copy()


def clear_notification_history():
    """Clear the notification history"""
    global NOTIFICATION_HISTORY
    NOTIFICATION_HISTORY = []


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


def show_notification(title: str, subtitle: str = None, message: str = None, sound: bool = False):
    """Show a macOS notification if notifications are enabled

    Args:
        title: Notification title
        subtitle: Optional subtitle (shown below title)
        message: Notification message body
        sound: Whether to play a sound (for errors/important events)
    """
    # Record in history (always, even if notifications are disabled)
    global NOTIFICATION_HISTORY
    NOTIFICATION_HISTORY.append({
        'timestamp': datetime.datetime.now().isoformat(),
        'title': title,
        'subtitle': subtitle or '',
        'message': message or '',
        'sound': str(sound)
    })

    if NOTIFICATIONS_ENABLED:
        try:
            # Build AppleScript command - message is required by AppleScript
            msg = message or subtitle or title
            script = f'display notification "{msg}" with title "{title}"'
            if subtitle:
                script += f' subtitle "{subtitle}"'
            if sound:
                script += ' sound name "Frog"'

            subprocess.run(['osascript', '-e', script], capture_output=True)
        except:
            pass  # Ignore notification errors


def show_error_notification(message: str, details: str = None):
    """Show an error notification with sound"""
    show_notification("Drew's Xcode MCP", subtitle=details, message=f"❌ {message}", sound=True)


def show_warning_notification(message: str, details: str = None):
    """Show a warning notification"""
    show_notification("Drew's Xcode MCP", subtitle=details, message=f"⚠️ {message}")


def show_access_denied_notification(message: str, details: str = None):
    """Show an access denied notification with sound"""
    show_notification("Drew's Xcode MCP", subtitle=details, message=f"⛔ {message}", sound=True)


def show_result_notification(message: str, details: str = None):
    """Show a result notification"""
    show_notification("Drew's Xcode MCP", subtitle=details, message=message)
