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
