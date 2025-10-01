#!/usr/bin/env python3
"""
Create test Xcode projects for testing the Xcode MCP Server.
This script generates various test projects with different characteristics.
"""

import os
import subprocess
import shutil
import sys
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def create_simple_app():
    """Create a simple iOS app that builds cleanly."""
    print("\n=== Creating SimpleApp ===")

    template_dir = Path("test_projects/templates/SimpleApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)

    # Create iOS app using xcodebuild
    cmd = [
        "xcodebuild", "-create-project",
        "-name", "SimpleApp",
        "-type", "Application",
        "-language", "Swift"
    ]

    # Use xcodeproj command line tool if available, otherwise create manually
    os.makedirs(template_dir, exist_ok=True)

    # Create project structure manually
    project_dir = template_dir / "SimpleApp"
    os.makedirs(project_dir, exist_ok=True)

    # Create a simple Swift file
    main_swift = project_dir / "main.swift"
    main_swift.write_text("""import Foundation

print("Hello from SimpleApp!")
print("Current time: \\(Date())")

for i in 1...5 {
    print("Count: \\(i)")
    Thread.sleep(forTimeInterval: 0.5)
}

print("SimpleApp completed successfully")
""")

    # Create Info.plist
    info_plist = project_dir / "Info.plist"
    info_plist.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SimpleApp</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.SimpleApp</string>
    <key>CFBundleName</key>
    <string>SimpleApp</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
""")

    print("SimpleApp structure created")
    return True

def create_broken_app():
    """Create an iOS app with deliberate compilation errors."""
    print("\n=== Creating BrokenApp ===")

    template_dir = Path("test_projects/templates/BrokenApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)

    os.makedirs(template_dir, exist_ok=True)
    project_dir = template_dir / "BrokenApp"
    os.makedirs(project_dir, exist_ok=True)

    # Create a Swift file with errors
    main_swift = project_dir / "main.swift"
    main_swift.write_text("""import Foundation

// This will cause an error - undefined variable
print(undefinedVariable)

// This will cause a warning - unused variable
let unusedVariable = "This is never used"

// This will cause an error - missing closing brace
func brokenFunction() {
    print("This function is broken"
    // Missing closing brace

// This will cause an error - type mismatch
let number: Int = "This is not a number"

print("This line won't be reached")
""")

    # Create another file with warnings
    warnings_swift = project_dir / "Warnings.swift"
    warnings_swift.write_text("""import Foundation

// Warning: Variable never mutated
var neverMutated = 10

// Warning: Result of call is unused
func returnsValue() -> Int {
    return 42
}

returnsValue()  // Result unused

// Warning: Unreachable code
func unreachableExample() {
    return
    print("This is unreachable")  // Warning
}
""")

    print("BrokenApp structure created")
    return True

def create_console_app():
    """Create a macOS console app with extensive output."""
    print("\n=== Creating ConsoleApp ===")

    template_dir = Path("test_projects/templates/ConsoleApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)

    os.makedirs(template_dir, exist_ok=True)
    project_dir = template_dir / "ConsoleApp"
    os.makedirs(project_dir, exist_ok=True)

    # Create main.swift with extensive console output
    main_swift = project_dir / "main.swift"
    main_swift.write_text("""import Foundation

print("=== ConsoleApp Started ===")
print("Process ID: \\(ProcessInfo.processInfo.processIdentifier)")
print("Arguments: \\(ProcessInfo.processInfo.arguments)")

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
    Thread.sleep(forTimeInterval: 0.1)
}

// Test regex filtering with specific patterns
print("TEST_MARKER: Special test output 1")
print("Regular output without marker")
print("TEST_MARKER: Special test output 2")

// Generate numbered output for testing max_lines
for i in 1...50 {
    print("Line \\(String(format: "%03d", i)): This is line number \\(i)")
}

print("=== ConsoleApp Completed ===")
exit(0)
""")

    print("ConsoleApp structure created")
    return True

def create_multiplatform_app():
    """Create a multi-platform app with multiple schemes."""
    print("\n=== Creating MultiPlatformApp ===")

    template_dir = Path("test_projects/templates/MultiPlatformApp")
    if template_dir.exists():
        shutil.rmtree(template_dir)

    os.makedirs(template_dir, exist_ok=True)

    # Create shared code
    shared_dir = template_dir / "Shared"
    os.makedirs(shared_dir, exist_ok=True)

    shared_swift = shared_dir / "SharedCode.swift"
    shared_swift.write_text("""import Foundation

public struct SharedModel {
    public let message: String
    public let timestamp: Date

    public init(message: String) {
        self.message = message
        self.timestamp = Date()
    }

    public func display() -> String {
        return "[\\(timestamp)] \\(message)"
    }
}

public class SharedService {
    public static func performTask() {
        print("Performing shared task...")
        Thread.sleep(forTimeInterval: 1.0)
        print("Shared task completed")
    }
}
""")

    # Create iOS-specific code
    ios_dir = template_dir / "iOS"
    os.makedirs(ios_dir, exist_ok=True)

    ios_main = ios_dir / "iOSMain.swift"
    ios_main.write_text("""import Foundation

print("Running iOS version")
let model = SharedModel(message: "iOS App Started")
print(model.display())
SharedService.performTask()
print("iOS app completed")
""")

    # Create macOS-specific code
    macos_dir = template_dir / "macOS"
    os.makedirs(macos_dir, exist_ok=True)

    macos_main = macos_dir / "macOSMain.swift"
    macos_main.write_text("""import Foundation

print("Running macOS version")
let model = SharedModel(message: "macOS App Started")
print(model.display())
SharedService.performTask()
print("macOS app completed")
""")

    print("MultiPlatformApp structure created")
    return True

def create_xcode_projects():
    """Create actual Xcode project files using xcodegen or manual creation."""
    print("\n=== Generating Xcode Projects ===")

    # For each template directory, create an actual Xcode project
    templates = ["SimpleApp", "BrokenApp", "ConsoleApp"]

    for template in templates:
        template_path = Path(f"test_projects/templates/{template}")
        if not template_path.exists():
            continue

        print(f"\nCreating Xcode project for {template}...")

        # Create a simple xcodeproj manually (using Swift Package Manager as a helper)
        project_path = template_path / f"{template}.xcodeproj"
        os.makedirs(project_path, exist_ok=True)

        # Create project.pbxproj file with minimal content
        pbxproj_path = project_path / "project.pbxproj"

        # This is a minimal project file structure
        pbxproj_content = f"""// !$*UTF8*$!
{{
    archiveVersion = 1;
    classes = {{}};
    objectVersion = 56;
    objects = {{
        /* Begin PBXFileReference section */
        1234567890ABCDEF /* {template}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = {template}.app; sourceTree = BUILT_PRODUCTS_DIR; }};
        /* End PBXFileReference section */

        /* Begin PBXProject section */
        0987654321FEDCBA /* Project object */ = {{
            isa = PBXProject;
            attributes = {{
                LastSwiftUpdateCheck = 1500;
                LastUpgradeCheck = 1500;
                TargetAttributes = {{
                    1234567890ABCDEF = {{
                        CreatedOnToolsVersion = 15.0;
                    }};
                }};
            }};
            compatibilityVersion = "Xcode 14.0";
            developmentRegion = en;
            knownRegions = (
                en,
                Base,
            );
            mainGroup = FEDCBA0987654321;
            productRefGroup = ABCDEF1234567890 /* Products */;
            projectDirPath = "";
            projectRoot = "";
            targets = (
                1234567890ABCDEF /* {template} */,
            );
        }};
        /* End PBXProject section */

        /* Begin XCBuildConfiguration section */
        AAAABBBBCCCCDDDD /* Debug */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                PRODUCT_NAME = {template};
                SWIFT_VERSION = 5.0;
            }};
            name = Debug;
        }};
        EEEEFFFF00001111 /* Release */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                PRODUCT_NAME = {template};
                SWIFT_VERSION = 5.0;
            }};
            name = Release;
        }};
        /* End XCBuildConfiguration section */
    }};
    rootObject = 0987654321FEDCBA /* Project object */;
}}
"""
        pbxproj_path.write_text(pbxproj_content)
        print(f"Created {template}.xcodeproj")

    return True

def main():
    """Main function to create all test projects."""
    print("Creating test Xcode projects for xcode-mcp-server testing...")

    # Change to the repository root
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)
    print(f"Working directory: {os.getcwd()}")

    # Create all test projects
    success = True
    success = success and create_simple_app()
    success = success and create_broken_app()
    success = success and create_console_app()
    success = success and create_multiplatform_app()
    success = success and create_xcode_projects()

    if success:
        print("\n✅ All test projects created successfully!")
        print("\nTest projects are located in: test_projects/templates/")
    else:
        print("\n❌ Some projects failed to create")
        sys.exit(1)

if __name__ == "__main__":
    main()