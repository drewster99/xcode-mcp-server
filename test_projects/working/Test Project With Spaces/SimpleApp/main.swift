import Foundation

print("Hello from SimpleApp!")
print("Current time: \(Date())")

for i in 1...5 {
    print("Count: \(i)")
    Thread.sleep(forTimeInterval: 0.1)
}

print("SimpleApp completed successfully")
