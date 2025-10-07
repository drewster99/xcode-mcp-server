#!/usr/bin/env python3
"""take_simulator_screenshot tool - Screenshot iOS simulator"""

import os
import sys
import re
import time
import uuid
import subprocess
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import show_result_notification, show_error_notification
from xcode_mcp_server.utils.screenshot import _get_booted_simulators


@mcp.tool()
@apply_config
def take_simulator_screenshot(udid: Optional[str] = None) -> str:
    """
    Take a screenshot of a booted iOS simulator.

    Args:
        udid: Optional UDID (device identifier) of the simulator to screenshot.
              If not provided or empty, the first booted simulator found is used.
              A list of running simulators can be found with `list_booted_simulators`.

    Returns:
        The file path to the saved screenshot.

    Raises:
        XCodeMCPError: If no booted simulators found or screenshot fails.
    """
    try:
        target_udid = None
        target_name = "Unknown"

        if udid and udid.strip():
            # User specified a UDID - use it directly without checking booted list
            # xcrun simctl will fail appropriately if it's not booted
            target_udid = udid.strip()

            # Try to get the name for better logging (optional)
            try:
                booted_simulators = _get_booted_simulators()
                for sim in booted_simulators:
                    if sim['udid'] == target_udid:
                        target_name = sim['name']
                        break
            except:
                # If we can't get the name, continue anyway
                pass
        else:
            # No UDID specified - find first booted simulator
            booted_simulators = _get_booted_simulators()

            if not booted_simulators:
                error_msg = "No booted simulators"
                show_error_notification(error_msg)
                raise XCodeMCPError("No booted simulators found")

            # Use first booted simulator
            target_udid = booted_simulators[0]['udid']
            target_name = booted_simulators[0]['name']

        # Create screenshot directory
        screenshot_dir = "/tmp/xcode-mcp-server/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        # Generate filename with UUID
        unique_id = uuid.uuid4()
        filename = f"simulator_{unique_id}.png"
        screenshot_path = os.path.join(screenshot_dir, filename)

        print(f"Taking screenshot of '{target_name}' (UDID: {target_udid})", file=sys.stderr)

        # Take the screenshot
        result = subprocess.run(
            ['xcrun', 'simctl', 'io', target_udid, 'screenshot', screenshot_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            # Provide more helpful error messages
            if 'Invalid device' in error_msg:
                show_error_notification("Invalid simulator UDID", target_udid)
                raise XCodeMCPError(f"Simulator with UDID '{target_udid}' does not exist")
            elif 'not booted' in error_msg.lower():
                show_error_notification("Simulator not booted", target_udid)
                raise XCodeMCPError(f"Simulator with UDID '{target_udid}' is not booted")
            else:
                show_error_notification("Failed to take screenshot", error_msg)
                raise XCodeMCPError(f"Failed to take screenshot: {error_msg}")

        # Verify the file was created
        if not os.path.exists(screenshot_path):
            error_msg = "Screenshot failed"
            show_error_notification(error_msg, "File not created")
            raise XCodeMCPError("Screenshot file was not created")

        print(f"Screenshot saved to: {screenshot_path}", file=sys.stderr)
        show_result_notification(f"Screenshotting {target_name}")
        return screenshot_path

    except subprocess.TimeoutExpired:
        error_msg = "Screenshot timeout"
        show_error_notification(error_msg)
        raise XCodeMCPError("Timeout while taking screenshot")
    except Exception as e:
        if isinstance(e, XCodeMCPError):
            if "not found" not in str(e).lower() and "No booted" not in str(e):
                show_error_notification("Screenshot failed", str(e))
            raise
        error_msg = "Screenshot failed"
        show_error_notification(error_msg, str(e))
        raise XCodeMCPError(f"Error taking screenshot: {e}")
