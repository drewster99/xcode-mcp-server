#!/usr/bin/env python3
"""list_project_tests tool - List available tests"""

import os
import re
import subprocess

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.utils.applescript import show_result_notification, show_error_notification


@mcp.tool()
@apply_config
def list_project_tests(project_path: str) -> str:
    """
    List all available tests in the specified Xcode project or workspace.

    Args:
        project_path: Path to Xcode project/workspace directory

    Returns:
        A list of all test identifiers in the format:
        BundleName/ClassName/testMethodName
    """
    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "list_project_tests")

    # Try to find test files in the project
    try:
        # Find test files in the project directory
        project_dir = os.path.dirname(project_path)
        test_files = []

        result = subprocess.run(
            ['find', project_dir, '-name', '*Tests.swift', '-o', '-name', '*Test.swift'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            test_files = result.stdout.strip().split('\n')

            # Parse test files to extract test methods
            tests = []
            for file_path in test_files:
                if file_path and os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            # Extract test class name from filename
                            filename = os.path.basename(file_path)
                            class_name = filename.replace('.swift', '')

                            # Find test methods (simple regex)
                            test_methods = re.findall(r'func\s+(test\w+)\s*\(', content)

                            for method in test_methods:
                                # Guess bundle name from path
                                if 'UITests' in file_path:
                                    bundle = f"{os.path.basename(project_path).replace('.xcodeproj', '').replace('.xcworkspace', '')}UITests"
                                else:
                                    bundle = f"{os.path.basename(project_path).replace('.xcodeproj', '').replace('.xcworkspace', '')}Tests"

                                tests.append(f"{bundle}/{class_name}/{method}")
                    except:
                        continue

            if tests:
                test_count = len(tests)
                show_result_notification(f"Found {test_count} test{'s' if test_count != 1 else ''}", os.path.basename(project_path))
                result = "\n".join(sorted(tests))
                result += "\n\nUse `run_project_tests` to run all tests or pass specific test identifiers to run selected tests."
                return result

        show_result_notification("Found 0 tests", os.path.basename(project_path))
        return f"Could not find test files for project: {os.path.basename(project_path)}\n" + \
               "Make sure your test files follow naming convention (*Test.swift or *Tests.swift)"

    except Exception as e:
        show_error_notification("Error listing tests", str(e))
        return f"Error listing tests: {str(e)}"
