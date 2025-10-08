#!/usr/bin/env python3
"""AppleScript execution and notification utilities"""

import subprocess
import sys
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

    # Check global setting first
    if not NOTIFICATIONS_ENABLED:
        return

    # Check if we're in a tool context and if that tool has notifications disabled
    try:
        from xcode_mcp_server.config_manager import get_active_tool_context, ConfigManager

        context = get_active_tool_context()
        if context:
            # We're in a tool execution context
            tool_name = context.get('tool_name')
            project_path = context.get('project_path')

            if tool_name:
                config = ConfigManager()
                # Check if this specific tool should show notifications
                if not config.should_show_notification(tool_name, project_path):
                    return
    except ImportError:
        # If we can't import, just use global setting
        pass

    # Show the notification
    try:
        # Build AppleScript command - message is required by AppleScript
        msg = message or subtitle or title
        escaped_msg = escape_applescript_string(msg)
        escaped_title = escape_applescript_string(title)

        script = f'display notification "{escaped_msg}" with title "{escaped_title}"'
        if subtitle:
            escaped_subtitle = escape_applescript_string(subtitle)
            script += f' subtitle "{escaped_subtitle}"'
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


def show_persistent_alert(title: str, message: str, button_text: str = "OK") -> subprocess.Popen:
    """
    Show a persistent macOS alert dialog that stays on screen until dismissed.

    Returns a Popen object representing the background process. The process will
    exit when the user clicks the button, allowing you to detect dismissal.

    Args:
        title: Alert dialog title
        message: Alert dialog message body
        button_text: Text for the button (default "OK")

    Returns:
        subprocess.Popen object for the alert process (None if notifications disabled)
    """
    if NOTIFICATIONS_ENABLED:
        try:
            # Escape strings for AppleScript
            escaped_title = escape_applescript_string(title)
            escaped_message = escape_applescript_string(message)
            escaped_button = escape_applescript_string(button_text)

            # Build AppleScript for alert dialog
            script = f'display dialog "{escaped_message}" with title "{escaped_title}" buttons {{"{escaped_button}"}} default button "{escaped_button}" with icon caution'

            # Run in background (non-blocking) and return the process
            return subprocess.Popen(
                ['osascript', '-e', script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Warning: Failed to show alert: {e}", file=sys.stderr)
            return None
    return None
