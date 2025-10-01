#!/bin/bash
# Setup test projects by copying from Xcode-created templates

set -e

echo "Setting up test projects from Xcode templates..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Clean existing templates (except fromXcode)
rm -rf test_projects/templates
mkdir -p test_projects/templates

echo ""
echo "=== Creating SimpleApp ==="
# Copy the command line app as base for SimpleApp
cp -r test_projects/fromXcode/macosEmptyCommandLineApp test_projects/templates/SimpleApp

# Rename the project folder and files
cd test_projects/templates/SimpleApp
mv macosEmptyCommandLineApp.xcodeproj SimpleApp.xcodeproj
mv macosEmptyCommandLineApp SimpleApp

# Update the project file to use new name
sed -i '' 's/macosEmptyCommandLineApp/SimpleApp/g' SimpleApp.xcodeproj/project.pbxproj

# Update main.swift with our test code
cat > SimpleApp/main.swift << 'EOF'
import Foundation

print("Hello from SimpleApp!")
print("Current time: \(Date())")

for i in 1...5 {
    print("Count: \(i)")
    Thread.sleep(forTimeInterval: 0.1)
}

print("SimpleApp completed successfully")
EOF

echo "✅ Created SimpleApp"

echo ""
echo "=== Creating BrokenApp ==="
# Copy SimpleApp as base for BrokenApp
cd "$REPO_ROOT"
cp -r test_projects/templates/SimpleApp test_projects/templates/BrokenApp

# Rename for BrokenApp
cd test_projects/templates/BrokenApp
mv SimpleApp.xcodeproj BrokenApp.xcodeproj
mv SimpleApp BrokenApp

# Update the project file
sed -i '' 's/SimpleApp/BrokenApp/g' BrokenApp.xcodeproj/project.pbxproj

# Create main.swift with errors
cat > BrokenApp/main.swift << 'EOF'
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

echo "✅ Created BrokenApp"

echo ""
echo "=== Creating ConsoleApp ==="
# Copy SimpleApp as base for ConsoleApp
cd "$REPO_ROOT"
cp -r test_projects/templates/SimpleApp test_projects/templates/ConsoleApp

# Rename for ConsoleApp
cd test_projects/templates/ConsoleApp
mv SimpleApp.xcodeproj ConsoleApp.xcodeproj
mv SimpleApp ConsoleApp

# Update the project file
sed -i '' 's/SimpleApp/ConsoleApp/g' ConsoleApp.xcodeproj/project.pbxproj

# Create main.swift with extensive console output
cat > ConsoleApp/main.swift << 'EOF'
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
    Thread.sleep(forTimeInterval: 0.05)
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

echo "✅ Created ConsoleApp"

echo ""
echo "=== Creating SwiftUITestApp ==="
# Copy the SwiftUI app for UI testing
cd "$REPO_ROOT"
cp -r test_projects/fromXcode/macosEmptySwiftUIApp test_projects/templates/SwiftUITestApp
cd test_projects/templates/SwiftUITestApp
mv macosEmptySwiftUIApp.xcodeproj SwiftUITestApp.xcodeproj
mv macosEmptySwiftUIApp SwiftUITestApp

# Update the project file
sed -i '' 's/macosEmptySwiftUIApp/SwiftUITestApp/g' SwiftUITestApp.xcodeproj/project.pbxproj

# Modify the ContentView to add some test output
if [ -f SwiftUITestApp/ContentView.swift ]; then
    cat > SwiftUITestApp/ContentView.swift << 'EOF'
import SwiftUI

struct ContentView: View {
    @State private var counter = 0

    var body: some View {
        VStack {
            Image(systemName: "globe")
                .imageScale(.large)
                .foregroundStyle(.tint)
            Text("Test SwiftUI App")
            Text("Counter: \(counter)")
            Button("Increment") {
                counter += 1
                print("Button clicked! Counter is now: \(counter)")
            }
        }
        .padding()
        .onAppear {
            print("SwiftUI ContentView appeared")
        }
    }
}

#Preview {
    ContentView()
}
EOF
fi

echo "✅ Created SwiftUITestApp"

echo ""
echo "=== Creating iOSTestApp ==="
# Copy the iOS SwiftUI app
cd "$REPO_ROOT"
cp -r test_projects/fromXcode/iosEmptySwiftUIApp test_projects/templates/iOSTestApp

cd test_projects/templates/iOSTestApp
mv iosEmptySwiftUIApp.xcodeproj iOSTestApp.xcodeproj
mv iosEmptySwiftUIApp iOSTestApp

# Update the project file
sed -i '' 's/iosEmptySwiftUIApp/iOSTestApp/g' iOSTestApp.xcodeproj/project.pbxproj

echo "✅ Created iOSTestApp"

echo ""
echo "=========================================="
echo "✅ All test projects created successfully!"
echo "=========================================="
echo ""
echo "Test projects created in: test_projects/templates/"
echo ""
echo "Available projects:"
echo "  - SimpleApp (macOS command line, builds cleanly)"
echo "  - BrokenApp (macOS command line, has errors)"
echo "  - ConsoleApp (macOS command line, extensive output)"
echo "  - SwiftUITestApp (macOS SwiftUI app)"
echo "  - iOSTestApp (iOS SwiftUI app)"