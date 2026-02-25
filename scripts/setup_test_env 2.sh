#!/bin/bash
# Test Environment Setup Script
#
# Automates creation and configuration of isolated test environments.
#
# Usage:
#   ./scripts/setup_test_env.sh <env_name> <port>
#
# Example:
#   ./scripts/setup_test_env.sh test_suite 5100
#
# Created for: P07 - Create Testing Infrastructure

set -e  # Exit on error

# Colors
BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
RESET='\033[0m'

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing arguments${RESET}"
    echo "Usage: $0 <env_name> <port>"
    echo "Example: $0 test_suite 5100"
    exit 1
fi

ENV_NAME=$1
PORT=$2

echo -e "${BOLD}=== Test Environment Setup ===${RESET}"
echo -e "Environment: ${CYAN}${ENV_NAME}${RESET}"
echo -e "Port: ${CYAN}${PORT}${RESET}\n"

# Step 1: Create environment via env_manager
echo -e "${BOLD}[1/7]${RESET} Creating environment..."
if ./env_manager.py create "${ENV_NAME}" "${PORT}"; then
    echo -e "${GREEN}✓ Environment created${RESET}\n"
else
    echo -e "${RED}✗ Failed to create environment${RESET}"
    exit 1
fi

# Step 2: Create data directory structure
echo -e "${BOLD}[2/7]${RESET} Setting up data directories..."
mkdir -p "data/${ENV_NAME}/backups"
mkdir -p "data/${ENV_NAME}/logs"
echo -e "${GREEN}✓ Data directories created${RESET}\n"

# Step 3: Initialize test database
echo -e "${BOLD}[3/7]${RESET} Initializing test database..."
DB_PATH="data/${ENV_NAME}/architect.db"

if [ -f "${DB_PATH}" ]; then
    echo -e "${YELLOW}⚠ Database already exists, skipping initialization${RESET}\n"
else
    # Copy schema from main database or run migrations
    if [ -f "data/architect.db" ]; then
        # Copy schema (not data) from main database, excluding internal tables
        sqlite3 data/architect.db ".schema" | grep -v "sqlite_sequence" | sqlite3 "${DB_PATH}"
        echo -e "${GREEN}✓ Database schema initialized${RESET}\n"
    else
        echo -e "${YELLOW}⚠ No main database found for schema reference${RESET}\n"
    fi
fi

# Step 4: Install test dependencies
echo -e "${BOLD}[4/7]${RESET} Checking test dependencies..."
MISSING_DEPS=()

# Check pytest
if ! python3 -c "import pytest" 2>/dev/null; then
    MISSING_DEPS+=("pytest")
fi

# Check playwright
if ! python3 -c "import playwright" 2>/dev/null; then
    MISSING_DEPS+=("playwright")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Missing dependencies: ${MISSING_DEPS[*]}${RESET}"
    echo "Install with: pip install ${MISSING_DEPS[*]}"
    echo -e "${YELLOW}⚠ Some tests may not run without these dependencies${RESET}\n"
else
    echo -e "${GREEN}✓ All test dependencies available${RESET}\n"
fi

# Step 5: Create test configuration
echo -e "${BOLD}[5/7]${RESET} Creating test configuration..."
TEST_CONFIG="data/${ENV_NAME}/test_config.json"

cat > "${TEST_CONFIG}" <<EOF
{
  "environment": "${ENV_NAME}",
  "port": ${PORT},
  "base_url": "https://localhost:${PORT}",
  "database": "${DB_PATH}",
  "created_at": "$(date -Iseconds)",
  "test_categories": {
    "unit": true,
    "integration": true,
    "e2e": false
  },
  "test_markers": {
    "slow": false,
    "requires_browser": false
  }
}
EOF

echo -e "${GREEN}✓ Test configuration created: ${TEST_CONFIG}${RESET}\n"

# Step 6: Create test run script
echo -e "${BOLD}[6/7]${RESET} Creating test run script..."
RUN_SCRIPT="scripts/run_tests_${ENV_NAME}.sh"

cat > "${RUN_SCRIPT}" <<EOF
#!/bin/bash
# Auto-generated test runner for ${ENV_NAME}
# Created: $(date -Iseconds)

set -e

# Colors
GREEN='\033[32m'
CYAN='\033[36m'
RESET='\033[0m'

echo -e "\${CYAN}Running tests in ${ENV_NAME} environment...\${RESET}"

# Set environment variables
export TEST_ENV="${ENV_NAME}"
export TEST_PORT="${PORT}"
export DATABASE_PATH="${DB_PATH}"

# Run tests
if [ "\$1" = "unit" ]; then
    echo "Running unit tests..."
    python3 -m pytest tests/ -m "not integration and not e2e and not slow" -v
elif [ "\$1" = "integration" ]; then
    echo "Running integration tests..."
    python3 -m pytest tests/ -m integration -v
elif [ "\$1" = "e2e" ]; then
    echo "Running E2E tests..."
    python3 -m pytest tests/ -m e2e -v
elif [ "\$1" = "all" ]; then
    echo "Running all tests..."
    python3 -m pytest tests/ -v
else
    echo "Usage: \$0 {unit|integration|e2e|all}"
    exit 1
fi

echo -e "\${GREEN}✓ Tests complete\${RESET}"
EOF

chmod +x "${RUN_SCRIPT}"
echo -e "${GREEN}✓ Test run script created: ${RUN_SCRIPT}${RESET}\n"

# Step 7: Verify setup
echo -e "${BOLD}[7/7]${RESET} Verifying setup..."

# Check environment exists
if ./env_manager.py list | grep -q "${ENV_NAME}"; then
    echo -e "${GREEN}✓ Environment registered${RESET}"
else
    echo -e "${RED}✗ Environment not found in registry${RESET}"
fi

# Check data directory
if [ -d "data/${ENV_NAME}" ]; then
    echo -e "${GREEN}✓ Data directory exists${RESET}"
else
    echo -e "${RED}✗ Data directory missing${RESET}"
fi

# Check database
if [ -f "${DB_PATH}" ]; then
    echo -e "${GREEN}✓ Database initialized${RESET}"
else
    echo -e "${YELLOW}⚠ Database not initialized${RESET}"
fi

# Summary
echo -e "\n${BOLD}=== Setup Complete ===${RESET}\n"
echo -e "${BOLD}Next Steps:${RESET}"
echo -e "  1. Start environment:    ${CYAN}./env_manager.py start ${ENV_NAME}${RESET}"
echo -e "  2. Check status:         ${CYAN}./env_manager.py status${RESET}"
echo -e "  3. Run tests:            ${CYAN}./${RUN_SCRIPT} all${RESET}"
echo -e "  4. Create test campaign: ${CYAN}./scripts/test_campaign.py create my_campaign ${ENV_NAME}${RESET}"
echo -e "  5. View logs:            ${CYAN}./env_manager.py logs ${ENV_NAME}${RESET}"
echo -e "  6. Stop environment:     ${CYAN}./env_manager.py stop ${ENV_NAME}${RESET}\n"

echo -e "${BOLD}Test Runner:${RESET}"
echo -e "  ${CYAN}./${RUN_SCRIPT} unit${RESET}        - Run unit tests"
echo -e "  ${CYAN}./${RUN_SCRIPT} integration${RESET} - Run integration tests"
echo -e "  ${CYAN}./${RUN_SCRIPT} e2e${RESET}         - Run E2E tests"
echo -e "  ${CYAN}./${RUN_SCRIPT} all${RESET}         - Run all tests\n"

echo -e "${BOLD}Configuration:${RESET}"
echo -e "  Config file: ${TEST_CONFIG}"
echo -e "  Database:    ${DB_PATH}"
echo -e "  Base URL:    https://localhost:${PORT}\n"

echo -e "${GREEN}✓ Test environment ready!${RESET}"
