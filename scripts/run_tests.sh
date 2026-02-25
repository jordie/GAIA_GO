#!/bin/bash
#
# Test Runner Script for Architect Dashboard
# Runs pytest with various options and reports results
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
VERBOSE=0
CATEGORY=""
OUTPUT_FORMAT="text"
JUNIT_FILE=""
COVERAGE=0

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -v, --verbose       Verbose output"
    echo "  -c, --category CAT  Run only specific test category (api, database, auth)"
    echo "  -j, --junit FILE    Output JUnit XML to file"
    echo "  --coverage          Run with coverage reporting"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                  Run all tests"
    echo "  $0 -c api           Run API tests only"
    echo "  $0 -v --coverage    Run with verbose and coverage"
    echo "  $0 -j results.xml   Output JUnit format"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -c|--category)
            CATEGORY="$2"
            shift 2
            ;;
        -j|--junit)
            JUNIT_FILE="$2"
            shift 2
            ;;
        --coverage)
            COVERAGE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check for pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}Installing pytest...${NC}"
    pip3 install pytest pytest-cov --quiet
fi

# Build pytest command
PYTEST_CMD="python3 -m pytest"

if [ $VERBOSE -eq 1 ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$CATEGORY" ]; then
    case $CATEGORY in
        api)
            PYTEST_CMD="$PYTEST_CMD tests/test_api.py"
            ;;
        database|db)
            PYTEST_CMD="$PYTEST_CMD tests/test_database.py"
            ;;
        auth)
            PYTEST_CMD="$PYTEST_CMD tests/test_api.py::TestAuthEndpoints"
            ;;
        *)
            PYTEST_CMD="$PYTEST_CMD -k $CATEGORY"
            ;;
    esac
else
    PYTEST_CMD="$PYTEST_CMD tests/"
fi

if [ -n "$JUNIT_FILE" ]; then
    PYTEST_CMD="$PYTEST_CMD --junit-xml=$JUNIT_FILE"
fi

if [ $COVERAGE -eq 1 ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=. --cov-report=term-missing"
fi

# Run tests
echo -e "${GREEN}Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

# Set test environment
export APP_ENV=test
export ARCHITECT_USER=testuser
export ARCHITECT_PASSWORD=testpass

# Run and capture exit code
set +e
$PYTEST_CMD
EXIT_CODE=$?
set -e

# Report result
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed (exit code: $EXIT_CODE)${NC}"
fi

exit $EXIT_CODE
