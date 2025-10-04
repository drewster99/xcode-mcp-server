#!/usr/bin/env python3
"""debug_list_notification_history tool - List all notifications that have been posted"""

import subprocess
from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.utils.applescript import get_notification_history


@mcp.tool()
@apply_config
def debug_list_notification_history() -> str:
    """
    List all notifications that have been posted since the server started.
    This is a debugging tool to help understand notification behavior.

    Returns:
        A formatted list of all notifications with timestamps, titles, messages, and subtitles.
    """
    history = get_notification_history()

    if not history:
        result = "No notifications have been posted yet."
    else:
        lines = [f"Notification History ({len(history)} notification{'s' if len(history) != 1 else ''}):", ""]

        for i, notif in enumerate(history, 1):
            lines.append(f"{i}. [{notif['timestamp']}]")
            lines.append(f"   Title: {notif['title']}")
            if notif['subtitle']:
                lines.append(f"   Subtitle: {notif['subtitle']}")
            if notif['message']:
                lines.append(f"   Message: {notif['message']}")
            lines.append(f"   Sound: {notif['sound']}")
            lines.append("")

        result = "\n".join(lines)

    # Also show in an alert
    try:
        # Escape for AppleScript
        alert_msg = result.replace('"', '\\"').replace('\n', '\\n')
        alert_script = f'display alert "Notification History" message "{alert_msg}"'
        # No timeout - let the user dismiss it when ready
        subprocess.run(['osascript', '-e', alert_script], capture_output=True)
    except:
        pass  # Ignore alert errors

    return result
