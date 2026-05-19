#!/usr/bin/env python3
"""AppleScript execution and notification utilities"""

import subprocess
import sys
import datetime
import threading
from collections import deque
from typing import Tuple, List, Dict, Optional

from xcode_mcp_server.exceptions import XCodeMCPError

# Global notification setting - initialized by CLI
NOTIFICATIONS_ENABLED = True

# Bounded notification history. Long-lived MCP servers post many notifications;
# capping the history prevents unbounded memory growth.
NOTIFICATION_HISTORY_MAX = 100
NOTIFICATION_HISTORY: "deque[Dict[str, str]]" = deque(maxlen=NOTIFICATION_HISTORY_MAX)
# Guards both `.append()` in show_notification and `list(...)` in
# get_notification_history. FastMCP dispatches sync tools onto a threadpool;
# without this, an interleaved iterate-during-append can raise
# `RuntimeError: deque mutated during iteration` from the C iterator.
_NOTIFICATION_HISTORY_LOCK = threading.Lock()

# Number of 0.5-second poll iterations before giving up on waiting for an Xcode
# workspace document to load.
WORKSPACE_LOAD_REPEATS = 60

# Maximum time (seconds) to wait for a build or run action to complete in
# AppleScript polling loops.
BUILD_TIMEOUT_SECONDS = 600

# Default subprocess timeout for `osascript` invocations that are expected to
# return quickly (lookups, cleanup commands, individual status checks). Callers
# that wrap a long-running inner AppleScript loop (build/run/test) must pass an
# explicit longer timeout — see callers in tools/build_project.py and
# tools/run_project_*.py.
DEFAULT_APPLESCRIPT_TIMEOUT = 60

# Subprocess timeout for fire-and-forget notification dispatch. Short on
# purpose: if Notification Center is wedged we don't want to block any tool.
NOTIFICATION_TIMEOUT = 5


def set_notifications_enabled(enabled: bool):
    """Set the global notification setting"""
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = enabled


def get_notification_history() -> List[Dict[str, str]]:
    """Get a snapshot of the notification history"""
    with _NOTIFICATION_HISTORY_LOCK:
        return list(NOTIFICATION_HISTORY)


def clear_notification_history():
    """Clear the notification history"""
    with _NOTIFICATION_HISTORY_LOCK:
        NOTIFICATION_HISTORY.clear()


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


def build_open_and_wait_applescript(escaped_path: str, escaped_scheme: Optional[str] = None) -> str:
    """
    Return the AppleScript prologue that opens an Xcode project, waits for the
    workspace document to load, and (if a scheme is provided) sets it active.

    The returned snippet starts with `set projectPath to ...`, opens a
    `tell application "Xcode"` block, and defines `workspaceDoc`. It does NOT
    close the `tell` block — callers append their action statements and a final
    `end tell`.

    Args:
        escaped_path: Project path, already passed through escape_applescript_string.
        escaped_scheme: Optional scheme name, already escaped. When provided,
            the snippet also sets the active scheme on the workspace document.
    """
    scheme_decl = f'set schemeName to "{escaped_scheme}"\n' if escaped_scheme else ""
    scheme_setup = (
        "    set active scheme of workspaceDoc to (first scheme of workspaceDoc whose name is schemeName)\n"
        if escaped_scheme else ""
    )
    return (
        f'set projectPath to "{escaped_path}"\n'
        f'{scheme_decl}'
        f'tell application "Xcode"\n'
        f'    open projectPath\n'
        f'    set workspaceDoc to first workspace document whose path is projectPath\n'
        f'\n'
        f'    repeat {WORKSPACE_LOAD_REPEATS} times\n'
        f'        if loaded of workspaceDoc is true then exit repeat\n'
        f'        delay 0.5\n'
        f'    end repeat\n'
        f'    if loaded of workspaceDoc is false then\n'
        f'        error "Xcode workspace did not load in time."\n'
        f'    end if\n'
        f'\n'
        f'{scheme_setup}'
    )


def build_wait_for_completion_applescript(
    result_var: str = "actionResult",
    timeout_seconds: int = BUILD_TIMEOUT_SECONDS,
) -> str:
    """
    Return the AppleScript snippet that polls `<result_var>.completed` until
    true or the timeout fires.

    Args:
        result_var: AppleScript variable holding a scheme-action-result.
        timeout_seconds: Seconds before the loop errors out.
    """
    minutes = timeout_seconds // 60
    return (
        f'    set buildWaitTime to 0\n'
        f'    repeat\n'
        f'        if completed of {result_var} is true then exit repeat\n'
        f'        if buildWaitTime >= {timeout_seconds} then\n'
        f'            error "Build timed out after {minutes} minutes"\n'
        f'        end if\n'
        f'        delay 0.5\n'
        f'        set buildWaitTime to buildWaitTime + 0.5\n'
        f'    end repeat\n'
    )


def run_applescript(script: str, timeout: int = DEFAULT_APPLESCRIPT_TIMEOUT) -> Tuple[bool, str]:
    """Run an AppleScript and return success status and output.

    Args:
        script: AppleScript source to evaluate.
        timeout: Wall-clock seconds before the osascript subprocess is killed.
            The default suits quick dispatch (lookups, status checks). Callers
            that wrap a long-running inner AppleScript loop (build/run/test
            poll loops up to BUILD_TIMEOUT_SECONDS) MUST pass an explicit
            longer value (typically `BUILD_TIMEOUT_SECONDS` plus a buffer for
            workspace load + IPC).

    Returns:
        (success, output) tuple. On AppleScript failure, output is the
        captured stderr. On timeout the subprocess is killed and an
        XCodeMCPError is raised so the caller can't accidentally treat a hang
        as a normal failure.

    Raises:
        XCodeMCPError: If the osascript subprocess exceeds `timeout` seconds.
    """
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
    except subprocess.TimeoutExpired:
        raise XCodeMCPError(
            f"AppleScript timed out after {timeout}s — Xcode may be unresponsive "
            f"(modal sheet, indexing, or frozen). Try again after dismissing any "
            f"dialogs in Xcode."
        )


def show_notification(title: str, subtitle: str = None, message: str = None, sound: bool = False):
    """Show a macOS notification if notifications are enabled

    Args:
        title: Notification title
        subtitle: Optional subtitle (shown below title)
        message: Notification message body
        sound: Whether to play a sound (for errors/important events)
    """
    # Record in history (always, even if notifications are disabled)
    with _NOTIFICATION_HISTORY_LOCK:
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

    try:
        subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            timeout=NOTIFICATION_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(
            f"Warning: notification dispatch timed out after {NOTIFICATION_TIMEOUT}s "
            f"(Notification Center may be wedged): title={title!r}",
            file=sys.stderr,
        )
    except FileNotFoundError:
        print("Warning: osascript not found on PATH; cannot show notification", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Warning: notification dispatch failed: {e}", file=sys.stderr)


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
        message: Alert dialog message body (newlines are supported)
        button_text: Text for the button (default "OK")

    Returns:
        subprocess.Popen object for the alert process (None if notifications disabled)
    """
    if NOTIFICATIONS_ENABLED:
        try:
            escaped_title = escape_applescript_string(title)
            escaped_button = escape_applescript_string(button_text)

            # Newlines must become AppleScript's `return` concatenation; a raw
            # newline inside a quoted AppleScript string is a syntax error.
            # Split first, escape each chunk, then join — escaping the whole
            # message and then trying to replace newlines is unsafe because the
            # escape step has already changed which characters are which.
            message_expr = " & return & ".join(
                f'"{escape_applescript_string(chunk)}"' for chunk in message.split("\n")
            )

            script = (
                f'display dialog {message_expr} with title "{escaped_title}" '
                f'buttons {{"{escaped_button}"}} default button "{escaped_button}" '
                f'with icon caution'
            )

            # Run in background (non-blocking) and return the process
            return subprocess.Popen(
                ['osascript', '-e', script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except OSError as e:
            print(f"Warning: Failed to spawn alert process: {e}", file=sys.stderr)
            return None
    return None
