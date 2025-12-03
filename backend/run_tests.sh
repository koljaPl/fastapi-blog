#!/bin/bash

# Run tests with coverage
# Usage: ./run_tests.sh [options]

set -e

echo "=================================="
echo "Running Blog Platform Tests"
echo "=================================="

# Set test mode
export TESTING=true

# Default options
PARALLEL=false
COVERAGE=true
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -nc|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  -p, --parallel      Run tests in parallel"
            echo "  -nc, --no-coverage  Skip coverage report"
            echo "  -v, --verbose       Verbose output"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"

if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
    echo "Running tests in parallel..."
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term-missing --cov-report=html"
    echo "Running with coverage report..."
fi

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
fi

# Clean previous test artifacts
echo "Cleaning previous test artifacts..."
rm -f test.db
rm -rf htmlcov
rm -f .coverage

# Run tests
echo ""
echo "Running tests..."
echo "Command: $PYTEST_CMD"
echo ""

$PYTEST_CMD

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=================================="
    echo "✅ All tests passed!"
    echo "=================================="

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo "📊 Coverage report: htmlcov/index.html"
    fi
else
    echo ""
    echo "=================================="
    echo "❌ Tests failed!"
    echo "=================================="
    exit 1
fi