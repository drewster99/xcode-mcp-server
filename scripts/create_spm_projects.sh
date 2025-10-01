#!/bin/bash
# Create test projects using Swift Package Manager (SPM)
# These can be opened directly in Xcode without conversion

set -e

echo "Creating SPM-based test projects..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Clean templates directory
rm -rf test_projects/templates
mkdir -p test_projects/templates

echo ""
echo "=== Creating SimpleApp (SPM executable) ==="
cd test_projects/templates
mkdir SimpleApp && cd SimpleApp

# Create Package.swift
cat > Package.swift << 'EOF'
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SimpleApp",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "SimpleApp",
            dependencies: []
        ),
    ]
)
EOF

# Create source directory and main.swift
mkdir -p Sources/SimpleApp
cat > Sources/SimpleApp/main.swift << 'EOF'
import Foundation

print("Hello from SimpleApp!")
print("Current time: \(Date())")

for i in 1...5 {
    print("Count: \(i)")
    Thread.sleep(forTimeInterval: 0.1)
}

print("SimpleApp completed successfully")
EOF

# Build to verify it works
swift build || true

echo "✅ Created SimpleApp"

echo ""
echo "=== Creating BrokenApp (SPM with errors) ==="
cd "$REPO_ROOT/test_projects/templates"
mkdir BrokenApp && cd BrokenApp

# Create Package.swift
cat > Package.swift << 'EOF'
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BrokenApp",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "BrokenApp",
            dependencies: []
        ),
    ]
)
EOF

# Create source with errors
mkdir -p Sources/BrokenApp
cat > Sources/BrokenApp/main.swift << 'EOF'
import Foundation

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
EOF

# Create file with warnings
cat > Sources/BrokenApp/Warnings.swift << 'EOF'
import Foundation

// Warning: Variable never mutated
var neverMutated = 10

// Warning: Result is unused
func returnsValue() -> Int {
    return 42
}

// Unused result
_ = returnsValue()

// Warning: Unreachable code
func unreachableExample() {
    return
    print("This is unreachable")
}
EOF

echo "✅ Created BrokenApp"

echo ""
echo "=== Creating ConsoleApp (SPM with output) ==="
cd "$REPO_ROOT/test_projects/templates"
mkdir ConsoleApp && cd ConsoleApp

# Create Package.swift
cat > Package.swift << 'EOF'
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "ConsoleApp",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "ConsoleApp",
            dependencies: []
        ),
    ]
)
EOF

# Create source with console output
mkdir -p Sources/ConsoleApp
cat > Sources/ConsoleApp/main.swift << 'EOF'
import Foundation

print("=== ConsoleApp Started ===")
print("Process ID: \(ProcessInfo.processInfo.processIdentifier)")

// Different log levels
print("[INFO] Application initialized")
print("[DEBUG] Debug mode is enabled")
print("[WARNING] This is a warning message")
print("[ERROR] This is an error message (not a real error)")

// Generate some predictable output
for i in 1...10 {
    print("Processing item \(i) of 10")
    if i % 2 == 0 {
        print("  -> Even number detected: \(i)")
    }
}

// Test regex filtering
print("TEST_MARKER: Special test output 1")
print("Regular output without marker")
print("TEST_MARKER: Special test output 2")

// Generate numbered output for testing max_lines
for i in 1...30 {
    print("Line \(String(format: "%03d", i)): This is line number \(i)")
}

print("=== ConsoleApp Completed ===")
EOF

# Build to verify it works
swift build || true

echo "✅ Created ConsoleApp"

echo ""
echo "=== Creating MultiScheme (SPM with multiple targets) ==="
cd "$REPO_ROOT/test_projects/templates"
mkdir MultiScheme && cd MultiScheme

# Create Package.swift with multiple targets
cat > Package.swift << 'EOF'
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MultiScheme",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "Debug", targets: ["Debug"]),
        .executable(name: "Release", targets: ["Release"]),
    ],
    targets: [
        .executableTarget(
            name: "Debug",
            dependencies: []
        ),
        .executableTarget(
            name: "Release",
            dependencies: []
        ),
    ]
)
EOF

# Create Debug target
mkdir -p Sources/Debug
cat > Sources/Debug/main.swift << 'EOF'
import Foundation
print("Running MultiScheme in DEBUG mode")
print("Optimization: None")
print("Debug symbols: Enabled")
EOF

# Create Release target
mkdir -p Sources/Release
cat > Sources/Release/main.swift << 'EOF'
import Foundation
print("Running MultiScheme in RELEASE mode")
print("Optimization: Speed")
print("Debug symbols: Stripped")
EOF

echo "✅ Created MultiScheme"

echo ""
echo "=========================================="
echo "✅ All SPM test projects created!"
echo "=========================================="
echo ""
echo "These projects can be:"
echo "  1. Built with: swift build"
echo "  2. Opened in Xcode: open [ProjectName]/Package.swift"
echo "  3. Used with xcodebuild after Xcode generates the workspace"
echo ""
echo "Note: When opening in Xcode for the first time, it will"
echo "      automatically create the necessary workspace files."