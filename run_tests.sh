#!/bin/bash

################################################################################
# Test Suite Runner for Architect Dashboard
#
# Comprehensive test automation script supporting unit, integration, and E2E tests
# with coverage reporting, parallel execution, and CI/CD integration.
#
# Usage: ./run_tests.sh [OPTIONS]
#
################################################################################

set -e

# Script Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
TEST_TYPE="all"           # all, unit, integration, e2e, smoke
PARALLEL=""               # Enable parallel execution with -n auto
COVERAGE=true             # Generate coverage report
REPORT=false              # Generate HTML test report
MARKERS=""                # Custom markers filter
VERBOSE=""                # Verbose output
HEADLESS=true             # Run E2E in headless mode
BROWSER="chromium"        # Browser for E2E tests
TIMEOUT=300               # Test timeout in seconds
INSTALL_DEPS=false        # Install dependencies
WATCH_MODE=false          # Watch mode for development

# Help message
show_help() {
    cat << EOF
${BLUE}Architect Dashboard Test Suite Runner${NC}

${YELLOW}USAGE:${NC}
    $0 [OPTIONS]

${YELLOW}OPTIONS:${NC}
    -t, --type TYPE              Test type: all, unit, integration, e2e, smoke
                                 (default: all)
    -p, --parallel              Run tests in parallel using all CPU cores
    --no-coverage               Skip coverage report generation
    -r, --report                Generate HTML test report
    -m, --markers MARKERS       Run tests matching markers (e.g., "not slow")
    -v, --verbose               Verbose output
    --headless                  Run E2E tests headless (default: true)
    -h, --headed                Run E2E tests with visible browser
    -b, --browser BROWSER       Browser for E2E: chromium, firefox, webkit
                                (default: chromium)
    --timeout SECONDS           Test timeout in seconds (default: 300)
    --install                   Install test dependencies
    --watch                     Watch mode for development
    --help                      Show this help message

${YELLOW}EXAMPLES:${NC}
    # Run all tests
    $0

    # Run unit tests only
    $0 --type unit

    # Run integration tests in parallel with report
    $0 --type integration --parallel --report

    # Run E2E tests with Firefox
    $0 --type e2e --browser firefox --headed

    # Run slow tests only
    $0 --markers "slow"

    # Install dependencies
    $0 --install

${YELLOW}ENVIRONMENT VARIABLES:${NC}
    PYTEST_OPTIONS      Additional pytest options
    TEST_TIMEOUT        Test timeout (overrides --timeout)
    E2E_PORT           Server port for E2E tests (default: 8099)
    E2E_USER           Test username (default: architect)
    E2E_PASSWORD       Test password (default: peace5)

${YELLOW}TEST TYPES:${NC}
    - unit             Fast, isolated unit tests
    - integration      Multi-component integration tests
    - e2e              Full application end-to-end tests
    - smoke            Critical functionality smoke tests
    - all              Run all test types (default)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL="-n auto"
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        -r|--report)
            REPORT=true
            shift
            ;;
        -m|--markers)
            MARKERS="-m \"$2\""
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="-vv"
            shift
            ;;
        --headless)
            HEADLESS=true
            shift
            ;;
        -h|--headed)
            HEADLESS=false
            shift
            ;;
        -b|--browser)
            BROWSER="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --install)
            INSTALL_DEPS=true
            shift
            ;;
        --watch)
            WATCH_MODE=true
            shift
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

# Install dependencies if requested
if [ "$INSTALL_DEPS" = true ]; then
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    if [ -f "requirements-test.txt" ]; then
        pip install -r requirements-test.txt
    else
        pip install pytest pytest-cov pytest-html pytest-xdist pytest-timeout \
                    playwright pytest-playwright selenium webdriver-manager
    fi

    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    playwright install chromium firefox webkit

    echo -e "${GREEN}Installation complete!${NC}"
    exit 0
fi

# Setup environment
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export TEST_ENV="test"
export PYTEST_TIMEOUT="$TIMEOUT"

# Create directories for artifacts
mkdir -p "$PROJECT_ROOT/htmlcov"
mkdir -p "$PROJECT_ROOT/test-reports"
mkdir -p "$PROJECT_ROOT/.pytest_cache"

# Clean previous coverage
rm -f "$PROJECT_ROOT/.coverage"
rm -f "$PROJECT_ROOT/coverage.xml"

# Build pytest command
build_pytest_cmd() {
    local cmd="python -m pytest"

    cmd="$cmd $PARALLEL"
    cmd="$cmd $VERBOSE"
    cmd="$cmd --tb=short"
    cmd="$cmd --timeout=$TIMEOUT"

    # Add coverage if enabled
    if [ "$COVERAGE" = true ]; then
        cmd="$cmd --cov=src --cov=tests --cov=workers --cov=services"
        cmd="$cmd --cov-report=html --cov-report=term-missing"
        cmd="$cmd --cov-report=xml"
    fi

    # Add HTML report if requested
    if [ "$REPORT" = true ]; then
        cmd="$cmd --html=test-reports/report.html --self-contained-html"
    fi

    # Add markers
    if [ -n "$MARKERS" ]; then
        cmd="$cmd $MARKERS"
    fi

    echo "$cmd"
}

# Run tests based on type
run_tests() {
    local test_type="$1"
    local cmd

    case "$test_type" in
        unit)
            echo -e "${BLUE}Running Unit Tests${NC}"
            cmd="$(build_pytest_cmd) tests -m 'unit or not (integration or e2e or slow)'"
            ;;
        integration)
            echo -e "${BLUE}Running Integration Tests${NC}"
            cmd="$(build_pytest_cmd) tests -m integration"
            ;;
        e2e)
            echo -e "${BLUE}Running E2E Tests${NC}"
            export E2E_HEADLESS="$HEADLESS"
            cmd="$(build_pytest_cmd) tests/e2e --browser $BROWSER"
            ;;
        smoke)
            echo -e "${BLUE}Running Smoke Tests${NC}"
            cmd="$(build_pytest_cmd) tests -m smoke"
            ;;
        all)
            echo -e "${BLUE}Running All Tests${NC}"
            cmd="$(build_pytest_cmd) tests"
            ;;
        *)
            echo -e "${RED}Unknown test type: $test_type${NC}"
            exit 1
            ;;
    esac

    # Add any additional pytest options from environment
    if [ -n "$PYTEST_OPTIONS" ]; then
        cmd="$cmd $PYTEST_OPTIONS"
    fi

    echo -e "${YELLOW}Command: $cmd${NC}"
    echo ""

    # Run the tests
    eval "$cmd"
    local exit_code=$?

    return $exit_code
}

# Watch mode for development
watch_mode() {
    echo -e "${YELLOW}Entering Watch Mode${NC}"
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
    echo ""

    local last_modified=""
    while true; do
        local current_modified=$(find tests -name "*.py" -o -name "conftest.py" | xargs ls -t | head -1)

        if [ "$current_modified" != "$last_modified" ]; then
            last_modified="$current_modified"
            clear
            echo -e "${YELLOW}Running tests (triggered by: $current_modified)${NC}"
            run_tests "unit"
            echo -e "${YELLOW}Watching for changes...${NC}"
        fi

        sleep 1
    done
}

# Main execution
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Architect Dashboard Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Test Type:      ${GREEN}$TEST_TYPE${NC}"
echo -e "Coverage:       ${GREEN}$COVERAGE${NC}"
echo -e "Reports:        ${GREEN}$REPORT${NC}"
echo -e "Parallel:       ${GREEN}$([ -n "$PARALLEL" ] && echo "yes" || echo "no")${NC}"
echo -e "Headless:       ${GREEN}$HEADLESS${NC}"
if [ "$TEST_TYPE" = "e2e" ] || [ "$TEST_TYPE" = "all" ]; then
    echo -e "E2E Browser:    ${GREEN}$BROWSER${NC}"
fi
echo ""

# Execute tests or watch mode
if [ "$WATCH_MODE" = true ]; then
    watch_mode
else
    run_tests "$TEST_TYPE"
    EXIT_CODE=$?

    # Print results
    echo ""
    echo -e "${BLUE}========================================${NC}"

    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"

        if [ "$COVERAGE" = true ]; then
            echo -e "${GREEN}Coverage report: htmlcov/index.html${NC}"
        fi

        if [ "$REPORT" = true ]; then
            echo -e "${GREEN}Test report: test-reports/report.html${NC}"
        fi
    else
        echo -e "${RED}✗ Some tests failed!${NC}"
        echo -e "${RED}Exit code: $EXIT_CODE${NC}"

        if [ "$COVERAGE" = true ]; then
            echo -e "${YELLOW}Coverage report: htmlcov/index.html${NC}"
        fi

        if [ "$REPORT" = true ]; then
            echo -e "${YELLOW}Test report: test-reports/report.html${NC}"
        fi
    fi

    echo -e "${BLUE}========================================${NC}"
    echo ""

    exit $EXIT_CODE
fi
