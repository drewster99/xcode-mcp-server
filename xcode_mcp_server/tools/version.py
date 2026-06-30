#!/usr/bin/env python3
"""version tool - Get server version"""

import hashlib
import os

from xcode_mcp_server import __version__
from xcode_mcp_server.server import mcp, TOOL_READONLY
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.utils.applescript import show_result_notification


def _compute_dev_source_fingerprint():
    """Short hash of all .py source in the package, or None.

    Returns None unless the server is running from a git working tree (i.e. the
    local dev server, run_local_for_claude.sh), so deployed/published builds keep
    a clean version string. Computed once at import, so it reflects the source
    THIS process actually loaded — not whatever is on disk now. That is the whole
    point: when testing edited code, a fresh server process produces a new
    fingerprint, and the version tool can confirm the running code matches the
    edits. An already-running (frozen) process keeps its old fingerprint, which
    correctly signals "restart to pick up your changes".
    """
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # xcode_mcp_server/
    repo_root = os.path.dirname(pkg_dir)
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return None

    try:
        digest = hashlib.sha256()
        for root, dirs, files in os.walk(pkg_dir):
            # Deterministic traversal; ignore caches so the hash tracks source only.
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                if name.endswith(".py"):
                    with open(os.path.join(root, name), "rb") as handle:
                        digest.update(handle.read())
        return digest.hexdigest()[:8]
    except OSError:
        return None


_DEV_SOURCE_FINGERPRINT = _compute_dev_source_fingerprint()


@mcp.tool(annotations=TOOL_READONLY)
@apply_config
def version() -> str:
    """
    Get the current version of the Xcode MCP Server.

    Returns:
        The version string of the server. When running from a source checkout
        (the local dev server), a "dev source <hash>" suffix identifies the exact
        source the process loaded, so you can confirm the running server matches
        the code you just edited.
    """
    version_string = f"Xcode MCP Server version {__version__}"
    if _DEV_SOURCE_FINGERPRINT:
        version_string = f"{version_string} (dev source {_DEV_SOURCE_FINGERPRINT})"

    show_result_notification(f"Version {__version__}")
    return version_string
