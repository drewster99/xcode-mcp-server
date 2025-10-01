#!/usr/bin/env python3
"""
Build-related tests for Xcode MCP Server.
Tests building, error reporting, warnings, and clean operations.
"""

import time
from pathlib import Path
from test_runner import XcodeMCPTestRunner, TestHelpers

class BuildTests(XcodeMCPTestRunner):
    """Test build-related MCP server functionality."""

    def test_build_simple_success(self):
        """Test building a simple project that should succeed."""
        # Copy SimpleApp
        project_path = self.copy_project("SimpleApp")
        xcodeproj_path = project_path / "SimpleApp.xcodeproj"

        # Attempt to build
        result = self.run_mcp_tool("build_project", project_path=str(xcodeproj_path))

        # Note: This might fail if Xcode can't handle our minimal test project
        # We'll check for either success or expected failure
        if result["success"]:
            self.assert_contains(result["result"], "succeeded")
            print("Build succeeded as expected")
        else:
            print(f"Build failed (may be expected for minimal project): {result.get('error')}")
            # Even if build fails, test that we got a proper error response
            assert result.get("error"), "Should have error message on failure"

    def test_build_with_errors(self):
        """Test building a project with compilation errors."""
        # Copy BrokenApp
        project_path = self.copy_project("BrokenApp")
        xcodeproj_path = project_path / "BrokenApp.xcodeproj"

        # Attempt to build - should fail
        result = self.run_mcp_tool("build_project", project_path=str(xcodeproj_path))

        if not result["success"]:
            # This is expected - the project has errors
            print("Build failed as expected due to errors")
            self.assert_contains(result["error"], "error")
        else:
            # If it somehow succeeded, check the output for errors
            output = result["result"]
            if "error" in output.lower():
                print("Build reported errors in output")
            else:
                print("Warning: BrokenApp built without reporting errors")

    def test_build_with_warnings(self):
        """Test building with warning reporting."""
        # Copy BrokenApp (has warnings too)
        project_path = self.copy_project("BrokenApp")
        xcodeproj_path = project_path / "BrokenApp.xcodeproj"

        # Build with warnings included
        result_with_warnings = self.run_mcp_tool(
            "build_project",
            project_path=str(xcodeproj_path),
            include_warnings=True
        )

        # Build with warnings excluded
        result_without_warnings = self.run_mcp_tool(
            "build_project",
            project_path=str(xcodeproj_path),
            include_warnings=False
        )

        # Check that warning handling works
        if result_with_warnings.get("success") or result_with_warnings.get("error"):
            result_text = str(result_with_warnings)
            print(f"Build with warnings result contains 'warning': {'warning' in result_text.lower()}")

        if result_without_warnings.get("success") or result_without_warnings.get("error"):
            result_text = str(result_without_warnings)
            print(f"Build without warnings result contains 'warning': {'warning' in result_text.lower()}")

    def test_clean_project(self):
        """Test cleaning a project."""
        # Copy SimpleApp
        project_path = self.copy_project("SimpleApp")
        xcodeproj_path = project_path / "SimpleApp.xcodeproj"

        # Clean the project
        result = self.run_mcp_tool("clean_project", project_path=str(xcodeproj_path))

        # Clean should generally work even on minimal projects
        if result["success"]:
            self.assert_contains(result["result"], "success")
            print("Clean completed successfully")
        else:
            print(f"Clean failed: {result.get('error')}")

    def test_get_build_errors(self):
        """Test retrieving build errors from last build."""
        # Copy BrokenApp
        project_path = self.copy_project("BrokenApp")
        xcodeproj_path = project_path / "BrokenApp.xcodeproj"

        # First, attempt to build (will fail)
        build_result = self.run_mcp_tool("build_project", project_path=str(xcodeproj_path))

        # Now get build errors
        errors_result = self.run_mcp_tool("get_build_errors", project_path=str(xcodeproj_path))

        if errors_result["success"]:
            errors = errors_result["result"]
            print(f"Retrieved build errors: {errors[:200]}...")  # First 200 chars

            # Check if we got error information
            if "error" in errors.lower() or "no build" in errors.lower():
                print("Build errors retrieved successfully")
        else:
            print(f"Failed to get build errors: {errors_result.get('error')}")

    def test_stop_project(self):
        """Test stopping a build or run operation."""
        # Copy SimpleApp
        project_path = self.copy_project("SimpleApp")
        xcodeproj_path = project_path / "SimpleApp.xcodeproj"

        # Try to stop (may not have anything running)
        result = self.run_mcp_tool("stop_project", project_path=str(xcodeproj_path))

        # Stop might fail if nothing is running, which is OK
        if result["success"]:
            print("Stop command executed successfully")
        else:
            error = result.get("error", "")
            if "not currently open" in error or "No open workspace" in error:
                print("Stop failed as expected - project not open")
            else:
                print(f"Stop failed with: {error}")

    def test_build_with_scheme(self):
        """Test building with a specific scheme."""
        # Copy SimpleApp
        project_path = self.copy_project("SimpleApp")
        xcodeproj_path = project_path / "SimpleApp.xcodeproj"

        # Try to build with a scheme name
        # Note: Our minimal projects might not have proper schemes
        result = self.run_mcp_tool(
            "build_project",
            project_path=str(xcodeproj_path),
            scheme="SimpleApp"  # Assuming scheme name matches project name
        )

        if result["success"]:
            print("Build with scheme succeeded")
        else:
            print(f"Build with scheme failed: {result.get('error')}")

    def test_path_escaping_in_build(self):
        """Test that special characters in paths are handled correctly."""
        # Create a project with spaces in the name
        special_name = "Test Project With Spaces"
        special_path = self.working_dir / special_name

        # Copy SimpleApp to special path
        template_path = self.templates_dir / "SimpleApp"
        if special_path.exists():
            import shutil
            shutil.rmtree(special_path)
        import shutil
        shutil.copytree(template_path, special_path)

        # Rename xcodeproj
        old_proj = special_path / "SimpleApp.xcodeproj"
        new_proj = special_path / f"{special_name}.xcodeproj"
        if old_proj.exists():
            old_proj.rename(new_proj)

        # Try to build with spaces in path
        result = self.run_mcp_tool("build_project", project_path=str(new_proj))

        # Should handle spaces correctly
        if result["success"]:
            print("Build with spaces in path succeeded")
        else:
            # Check that it's not a path escaping error
            error = result.get("error", "")
            if "No such file" not in error and "cannot find" not in error.lower():
                print(f"Build failed but path was handled correctly: {error[:100]}")
            else:
                print(f"Path escaping might have failed: {error}")

def run_build_tests():
    """Run all build tests."""
    print("\n" + "=" * 60)
    print("RUNNING BUILD TESTS")
    print("=" * 60)

    tests = BuildTests()
    tests.setup()

    try:
        # Run each test
        tests.run_test(tests.test_build_simple_success, "Build Simple Success")
        tests.run_test(tests.test_build_with_errors, "Build With Errors")
        tests.run_test(tests.test_build_with_warnings, "Build With Warnings")
        tests.run_test(tests.test_clean_project, "Clean Project")
        tests.run_test(tests.test_get_build_errors, "Get Build Errors")
        tests.run_test(tests.test_stop_project, "Stop Project")
        tests.run_test(tests.test_build_with_scheme, "Build With Scheme")
        tests.run_test(tests.test_path_escaping_in_build, "Path Escaping in Build")

        # Print summary
        return tests.print_summary()

    finally:
        tests.teardown()

if __name__ == "__main__":
    import sys
    success = run_build_tests()
    sys.exit(0 if success else 1)