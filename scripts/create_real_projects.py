#!/usr/bin/env python3
"""
Create real, valid Xcode projects for testing the Xcode MCP Server.
Uses xcodebuild to create proper project structures.
"""

import os
import subprocess
import shutil
import sys
from pathlib import Path

def run_command(cmd, cwd=None, capture=False):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if capture:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str))
        return result.returncode == 0, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
        return result.returncode == 0

def create_simple_ios_app():
    """Create a simple iOS app using Swift Package Manager and convert to Xcode project."""
    print("\n=== Creating SimpleApp (Command Line Tool) ===")

    template_dir = Path("test_projects/templates/SimpleApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)
    template_dir.mkdir(parents=True)

    # Create a Swift command line executable (simpler than iOS app)
    os.chdir(template_dir)

    # Initialize Swift package
    success = run_command(["swift", "package", "init", "--type", "executable", "--name", "SimpleApp"])
    if not success:
        print("Failed to create Swift package")
        return False

    # Modify the main.swift file
    sources_dir = Path("Sources/SimpleApp")
    main_swift = sources_dir / "main.swift"
    main_swift.write_text("""import Foundation

print("Hello from SimpleApp!")
print("Current time: \\(Date())")

for i in 1...5 {
    print("Count: \\(i)")
    Thread.sleep(forTimeInterval: 0.1)
}

print("SimpleApp completed successfully")
""")

    # Generate Xcode project
    success = run_command(["swift", "package", "generate-xcodeproj"])
    if success:
        print("✅ SimpleApp.xcodeproj created successfully")
    else:
        print("❌ Failed to generate Xcode project")

    return success

def create_broken_app():
    """Create an app with compilation errors."""
    print("\n=== Creating BrokenApp (With Errors) ===")

    template_dir = Path("test_projects/templates/BrokenApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)
    template_dir.mkdir(parents=True)

    os.chdir(template_dir)

    # Initialize Swift package
    success = run_command(["swift", "package", "init", "--type", "executable", "--name", "BrokenApp"])
    if not success:
        print("Failed to create Swift package")
        return False

    # Create main.swift with errors
    sources_dir = Path("Sources/BrokenApp")
    main_swift = sources_dir / "main.swift"
    main_swift.write_text("""import Foundation

// This will cause an error - undefined variable
print(undefinedVariable)

// This will cause a warning - unused variable
let unusedVariable = "This is never used"

// This will cause an error - missing closing brace
func brokenFunction() {
    print("This function is broken")
    // Missing closing brace

// This will cause an error - type mismatch
let number: Int = "This is not a number"

print("This line won't be reached")
""")

    # Create another file with warnings
    warnings_swift = sources_dir / "Warnings.swift"
    warnings_swift.write_text("""import Foundation

// Warning: Variable never mutated
var neverMutated = 10

// Warning: Result of call is unused
func returnsValue() -> Int {
    return 42
}

// This will generate a warning
_ = returnsValue()

// Warning: Unreachable code
func unreachableExample() {
    return
    print("This is unreachable")  // Warning
}
""")

    # Generate Xcode project (will succeed even with code errors)
    success = run_command(["swift", "package", "generate-xcodeproj"])
    if success:
        print("✅ BrokenApp.xcodeproj created successfully")
    else:
        print("❌ Failed to generate Xcode project")

    return success

def create_console_app():
    """Create a console app with output."""
    print("\n=== Creating ConsoleApp ===")

    template_dir = Path("test_projects/templates/ConsoleApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)
    template_dir.mkdir(parents=True)

    os.chdir(template_dir)

    # Initialize Swift package
    success = run_command(["swift", "package", "init", "--type", "executable", "--name", "ConsoleApp"])
    if not success:
        print("Failed to create Swift package")
        return False

    # Create main.swift with console output
    sources_dir = Path("Sources/ConsoleApp")
    main_swift = sources_dir / "main.swift"
    main_swift.write_text("""import Foundation

print("=== ConsoleApp Started ===")
print("Process ID: \\(ProcessInfo.processInfo.processIdentifier)")

// Different log levels
print("[INFO] Application initialized")
print("[DEBUG] Debug mode is enabled")
print("[WARNING] This is a warning message")
print("[ERROR] This is an error message (not a real error)")

// Generate some predictable output
for i in 1...10 {
    print("Processing item \\(i) of 10")
    if i % 2 == 0 {
        print("  -> Even number detected: \\(i)")
    }
}

// Test regex filtering with specific patterns
print("TEST_MARKER: Special test output 1")
print("Regular output without marker")
print("TEST_MARKER: Special test output 2")

// Generate numbered output for testing max_lines
for i in 1...30 {
    print("Line \\(String(format: "%03d", i)): This is line number \\(i)")
}

print("=== ConsoleApp Completed ===")
""")

    # Generate Xcode project
    success = run_command(["swift", "package", "generate-xcodeproj"])
    if success:
        print("✅ ConsoleApp.xcodeproj created successfully")
    else:
        print("❌ Failed to generate Xcode project")

    return success

def create_multi_scheme_app():
    """Create an app with multiple build configurations."""
    print("\n=== Creating MultiScheme App ===")

    template_dir = Path("test_projects/templates/MultiScheme")
    if template_dir.exists():
        shutil.rmtree(template_dir)
    template_dir.mkdir(parents=True)

    os.chdir(template_dir)

    # Create Package.swift with multiple targets
    package_swift = Path("Package.swift")
    package_swift.write_text("""// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MultiScheme",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "MultiSchemeDebug", targets: ["MultiSchemeDebug"]),
        .executable(name: "MultiSchemeRelease", targets: ["MultiSchemeRelease"]),
    ],
    targets: [
        .executableTarget(
            name: "MultiSchemeDebug",
            path: "Sources/Debug"
        ),
        .executableTarget(
            name: "MultiSchemeRelease",
            path: "Sources/Release"
        ),
    ]
)
""")

    # Create debug target
    debug_dir = Path("Sources/Debug")
    debug_dir.mkdir(parents=True)
    (debug_dir / "main.swift").write_text("""import Foundation
print("Running MultiScheme in DEBUG mode")
print("Debug assertions enabled")
print("Optimization level: None")
""")

    # Create release target
    release_dir = Path("Sources/Release")
    release_dir.mkdir(parents=True)
    (release_dir / "main.swift").write_text("""import Foundation
print("Running MultiScheme in RELEASE mode")
print("Debug assertions disabled")
print("Optimization level: Speed")
""")

    # Generate Xcode project
    success = run_command(["swift", "package", "generate-xcodeproj"])
    if success:
        print("✅ MultiScheme.xcodeproj created successfully")
    else:
        print("❌ Failed to generate Xcode project")

    return success

def main():
    """Main function to create all test projects."""
    print("Creating real Xcode projects for testing...")

    # Save current directory
    original_dir = os.getcwd()

    # Change to repo root
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)
    print(f"Working directory: {os.getcwd()}")

    # Create all projects
    success = True

    try:
        success = success and create_simple_ios_app()
        os.chdir(repo_root)  # Reset directory

        success = success and create_broken_app()
        os.chdir(repo_root)  # Reset directory

        success = success and create_console_app()
        os.chdir(repo_root)  # Reset directory

        success = success and create_multi_scheme_app()
        os.chdir(repo_root)  # Reset directory

    finally:
        os.chdir(original_dir)

    if success:
        print("\n✅ All test projects created successfully!")
        print("\nTest projects are located in: test_projects/templates/")
    else:
        print("\n❌ Some projects failed to create")
        print("Make sure you have Xcode and Swift command line tools installed")
        sys.exit(1)

if __name__ == "__main__":
    main()