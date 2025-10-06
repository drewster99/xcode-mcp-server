#!/usr/bin/env python3
"""debug_list_notification_history tool - List all notifications that have been posted"""

import subprocess
import tempfile
import os
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

    # Also show in TextEdit (scrollable)
    try:
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix='xcode-mcp-notifications-') as f:
            f.write(result)
            temp_path = f.name

        # Open in TextEdit
        subprocess.run(['open', '-a', 'TextEdit', temp_path], capture_output=True)
    except Exception as e:
        pass  # Ignore display errors

    return result
