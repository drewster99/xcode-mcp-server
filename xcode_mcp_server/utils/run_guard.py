#!/usr/bin/env python3
"""Per-project exclusivity guard for runtime/test tools.

Runtime and test result isolation assumes a single in-flight action per
project: the tool snapshots the existing .xcresult bundles, launches, then waits
for a bundle that wasn't there before. Two concurrent run/test actions on the
SAME project would each produce a new bundle, and neither caller could tell
which bundle is its own (the AppleScript scheme-action-result exposes no link to
its .xcresult, and the bundle metadata only carries a coarse start time). Rather
than race, reject the second caller.

FastMCP dispatches synchronous tools on a threadpool, so two tool invocations
can run at once — this guard protects against real concurrency, not just a
theoretical case.
"""

import functools
import inspect
import os
import threading

from xcode_mcp_server.exceptions import XCodeMCPError

# Realpaths of projects with a run/test action currently in flight, guarded by a
# lock. A single key per project makes any two of the run/test tools mutually
# exclusive for the same project (which is the intent — no parallel same-project
# runs), while different projects still run concurrently.
_active_lock = threading.Lock()
_active_projects: set = set()


def exclusive_per_project(func):
    """Reject a concurrent run/test of the same project (fail fast).

    Keyed by ``os.path.realpath(project_path)``. Apply BELOW ``@apply_config`` so
    config overrides are resolved first and the original signature still reaches
    FastMCP:

        @mcp.tool(...)
        @apply_config
        @exclusive_per_project
        def run_...(project_path, ...): ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound = inspect.signature(func).bind(*args, **kwargs)
        bound.apply_defaults()
        raw = bound.arguments.get('project_path')
        # An empty/missing path is left to the body's own validation to reject;
        # we just don't guard it.
        key = os.path.realpath(raw) if raw else None
        if key is None:
            return func(*args, **kwargs)

        with _active_lock:
            if key in _active_projects:
                raise XCodeMCPError(
                    f"A run or test is already in progress for this project "
                    f"({key}). Wait for it to finish before starting another — "
                    f"concurrent runs of the same project are not supported."
                )
            _active_projects.add(key)
        try:
            return func(*args, **kwargs)
        finally:
            with _active_lock:
                _active_projects.discard(key)

    return wrapper
