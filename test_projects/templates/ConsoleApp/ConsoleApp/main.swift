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
