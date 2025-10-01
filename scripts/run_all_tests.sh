#!/bin/bash
# Run all tests for Xcode MCP Server

set -e  # Exit on error

echo "=========================================="
echo "Running Xcode MCP Server Test Suite"
echo "=========================================="

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Setup environment
echo "Setting up test environment..."
source scripts/setup_tests.sh

# Track test results
FAILED_TESTS=()
PASSED_TESTS=()

# Function to run a test and track results
run_test() {
    local test_file=$1
    local test_name=$(basename $test_file .py)

    echo ""
    echo "=========================================="
    echo "Running: $test_name"
    echo "=========================================="

    if python "$test_file"; then
        echo "✅ $test_name PASSED"
        PASSED_TESTS+=("$test_name")
    else
        echo "❌ $test_name FAILED"
        FAILED_TESTS+=("$test_name")
    fi
}

# Run all tests
run_test "tests/test_basic.py"
run_test "tests/test_build.py"

# Add more test files as they are created:
# run_test "tests/test_runtime.py"
# run_test "tests/test_errors.py"
# run_test "tests/test_security.py"

# Print summary
echo ""
echo "=========================================="
echo "TEST SUITE SUMMARY"
echo "=========================================="
echo ""
echo "Passed: ${#PASSED_TESTS[@]} tests"
for test in "${PASSED_TESTS[@]}"; do
    echo "  ✅ $test"
done

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo ""
    echo "Failed: ${#FAILED_TESTS[@]} tests"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  ❌ $test"
    done
fi

# Cleanup
echo ""
echo "Cleaning up..."
source scripts/cleanup_tests.sh

# Exit with appropriate code
if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ ALL TESTS PASSED!"
    echo "=========================================="
    exit 0
else
    echo ""
    echo "=========================================="
    echo "❌ SOME TESTS FAILED"
    echo "=========================================="
    exit 1
fi