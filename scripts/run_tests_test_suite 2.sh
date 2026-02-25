#!/bin/bash
# Auto-generated test runner for test_suite
# Created: 2026-02-10T08:15:15-08:00

set -e

# Colors
GREEN='\033[32m'
CYAN='\033[36m'
RESET='\033[0m'

echo -e "${CYAN}Running tests in test_suite environment...${RESET}"

# Set environment variables
export TEST_ENV="test_suite"
export TEST_PORT="5100"
export DATABASE_PATH="data/test_suite/architect.db"

# Run tests
if [ "$1" = "unit" ]; then
    echo "Running unit tests..."
    python3 -m pytest tests/ -m "not integration and not e2e and not slow" -v
elif [ "$1" = "integration" ]; then
    echo "Running integration tests..."
    python3 -m pytest tests/ -m integration -v
elif [ "$1" = "e2e" ]; then
    echo "Running E2E tests..."
    python3 -m pytest tests/ -m e2e -v
elif [ "$1" = "all" ]; then
    echo "Running all tests..."
    python3 -m pytest tests/ -v
else
    echo "Usage: $0 {unit|integration|e2e|all}"
    exit 1
fi

echo -e "${GREEN}✓ Tests complete${RESET}"
