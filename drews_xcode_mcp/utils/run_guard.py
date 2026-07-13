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

from drews_xcode_mcp.exceptions import XCodeMCPError

# Realpaths of projects with a run/test action currently in flight, guarded by a
# lock. A single key per project makes any two of the run/test tools mutually
# exclusive for the same project (which is the intent — no parallel same-project
# runs), while different projects still run concurrently.
_active_lock = threading.Lock()
_active_projects: set = set()


def _project_key(project_path: str) -> str:
    """Canonical exclusivity key for a project path.

    Resolves symlinks/trailing slashes via realpath, and additionally collapses
    a bare `.xcodeproj`'s implicit workspace
    (`<proj>.xcodeproj/project.xcworkspace`) onto the `.xcodeproj` itself, so a
    caller naming the project and a caller naming its implicit workspace share
    one key and can't run concurrently. (realpath alone would key them
    separately, defeating the guard.)
    """
    real = os.path.realpath(project_path)
    parent = os.path.dirname(real)
    if os.path.basename(real) == "project.xcworkspace" and parent.endswith(".xcodeproj"):
        return parent
    return real


def exclusive_per_project(func):
    """Reject a concurrent run/test of the same project (fail fast).

    Keyed by ``_project_key(project_path)`` (realpath, with a bare .xcodeproj's
    implicit project.xcworkspace collapsed onto the .xcodeproj). Apply BELOW
    ``@apply_config`` so config overrides are resolved first and the original
    signature still reaches FastMCP:

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
        key = _project_key(raw) if raw else None
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
