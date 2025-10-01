#!/usr/bin/env python3
"""Debug script to understand build_project output."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_runner import XcodeMCPTestRunner

def debug_build():
    runner = XcodeMCPTestRunner()
    runner.setup()

    try:
        # Copy SimpleApp
        simple_app_path = runner.copy_project("SimpleApp")
        xcodeproj_path = simple_app_path / "SimpleApp.xcodeproj"

        print(f"Testing build of: {xcodeproj_path}")

        # Build
        result = runner.run_mcp_tool("build_project", project_path=str(xcodeproj_path))

        print(f"\nBuild result:")
        print(f"  Success: {result.get('success')}")
        print(f"  Result: {result.get('result')}")
        print(f"  Error: {result.get('error')}")

        # Check what the result contains
        if result.get('success') and result.get('result'):
            output = result['result']
            print(f"\nChecking for 'succeeded': {'succeeded' in output.lower()}")
            print(f"Actual output: '{output}'")

    finally:
        runner.teardown()

if __name__ == "__main__":
    debug_build()