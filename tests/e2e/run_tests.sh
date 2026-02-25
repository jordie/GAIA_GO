#!/bin/bash
# E2E Test Runner Script
# Usage: ./tests/e2e/run_tests.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default settings
BROWSER="chromium"
HEADLESS="true"
PARALLEL=""
REPORT=""
MARKERS=""
VERBOSE=""

# Help message
show_help() {
    cat << EOF
E2E Test Runner for Architect Dashboard

Usage: $0 [OPTIONS]

Options:
    -b, --browser BROWSER    Browser to use: chromium, firefox, webkit (default: chromium)
    -h, --headed             Run with browser visible (not headless)
    -p, --parallel           Run tests in parallel
    -r, --report             Generate HTML report
    -s, --smoke              Run only smoke tests
    -m, --markers MARKERS    Run tests matching markers (e.g., "smoke or auth")
    -v, --verbose            Verbose output
    --install                Install dependencies and browsers
    --help                   Show this help message

Examples:
    $0                       # Run all tests headless in chromium
    $0 -h                    # Run with visible browser
    $0 -b firefox            # Run in Firefox
    $0 -s                    # Run smoke tests only
    $0 -p -r                 # Run in parallel with HTML report
    $0 --install             # Install dependencies

Environment Variables:
    E2E_PORT                 Server port (default: 8099)
    E2E_USER                 Test username (default: architect)
    E2E_PASSWORD             Test password (default: peace5)
    E2E_HEADLESS             Run headless (default: true)
    E2E_SLOW_MO              Slow down actions by ms (default: 0)
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--browser)
            BROWSER="$2"
            shift 2
            ;;
        -h|--headed)
            HEADLESS="false"
            shift
            ;;
        -p|--parallel)
            PARALLEL="-n auto"
            shift
            ;;
        -r|--report)
            REPORT="--html=tests/e2e/artifacts/report.html --self-contained-html"
            shift
            ;;
        -s|--smoke)
            MARKERS="-m smoke"
            shift
            ;;
        -m|--markers)
            MARKERS="-m \"$2\""
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        --install)
            echo -e "${YELLOW}Installing E2E test dependencies...${NC}"
            pip install -r "$SCRIPT_DIR/requirements.txt"
            echo -e "${YELLOW}Installing Playwright browsers...${NC}"
            playwright install chromium firefox webkit
            echo -e "${GREEN}Installation complete!${NC}"
            exit 0
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Set environment
export E2E_HEADLESS="$HEADLESS"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Create artifacts directory
mkdir -p "$SCRIPT_DIR/artifacts"

# Build pytest command
CMD="python -m pytest"
CMD="$CMD $SCRIPT_DIR"
CMD="$CMD --browser $BROWSER"
CMD="$CMD $PARALLEL"
CMD="$CMD $REPORT"
CMD="$CMD $MARKERS"
CMD="$CMD $VERBOSE"
CMD="$CMD --tb=short"
CMD="$CMD -x"  # Stop on first failure

echo -e "${YELLOW}Running E2E tests...${NC}"
echo -e "Browser: ${GREEN}$BROWSER${NC}"
echo -e "Headless: ${GREEN}$HEADLESS${NC}"
echo ""

# Run tests
cd "$PROJECT_ROOT"
eval $CMD
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
else
    echo -e "\n${RED}Some tests failed.${NC}"
fi

exit $EXIT_CODE
