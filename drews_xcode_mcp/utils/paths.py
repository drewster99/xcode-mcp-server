#!/usr/bin/env python3
"""Shared cache and runtime path constants.

All transient files written by the server land under a per-user cache
directory rather than world-readable /tmp. Centralized here so screenshots,
runtime logs, build logs, and debug dumps share one convention.
"""

import os

# Retains the pre-rename directory name so caches and logs written by the old
# xcode-mcp-server package remain in one place after the move to drews-xcode-mcp.
CACHE_ROOT = os.path.expanduser("~/Library/Caches/xcode-mcp-server")
SCREENSHOT_DIR = os.path.join(CACHE_ROOT, "screenshots")
LOG_DIR = os.path.join(CACHE_ROOT, "logs")
DEBUG_DIR = os.path.join(CACHE_ROOT, "debug")
