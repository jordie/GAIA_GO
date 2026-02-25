#!/bin/bash
#
# Supervisor System Verification Script
#
# Verifies that all components are properly installed and configured
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_check() {
    echo -n "  Checking $1... "
}

print_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC} - $1"
}

print_warn() {
    echo -e "${YELLOW}⚠ WARN${NC} - $1"
}

# Track results
PASSED=0
FAILED=0
WARNINGS=0

# Check file exists
check_file() {
    local file="$1"
    local name="$2"

    print_check "$name"

    if [ -f "$file" ]; then
        if [ -x "$file" ]; then
            print_pass
            ((PASSED++))
        else
            print_warn "Not executable"
            ((WARNINGS++))
        fi
    else
        print_fail "File not found"
        ((FAILED++))
    fi
}

# Check Python module
check_python_module() {
    local module="$1"

    print_check "$module"

    if python3 -c "import $module" 2>/dev/null; then
        print_pass
        ((PASSED++))
    else
        print_fail "Not installed"
        ((FAILED++))
    fi
}

# Check JSON file
check_json() {
    local file="$1"
    local name="$2"

    print_check "$name"

    if [ ! -f "$file" ]; then
        print_fail "File not found"
        ((FAILED++))
        return
    fi

    if python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
        print_pass
        ((PASSED++))
    else
        print_fail "Invalid JSON"
        ((FAILED++))
    fi
}

# Check directory
check_directory() {
    local dir="$1"
    local name="$2"

    print_check "$name"

    if [ -d "$dir" ]; then
        print_pass
        ((PASSED++))
    else
        print_warn "Does not exist (will be created)"
        ((WARNINGS++))
    fi
}

# Main verification
print_header "Process Supervisor System Verification"

echo "Project Root: $PROJECT_ROOT"
echo "Supervisor Dir: $SCRIPT_DIR"
echo ""

# 1. Check core files
print_header "1. Core Files"

check_file "$SCRIPT_DIR/process_supervisor.py" "Process Supervisor"
check_file "$SCRIPT_DIR/health_checks.py" "Health Checks"
check_file "$SCRIPT_DIR/supervisor_integration.py" "Dashboard Integration"
check_file "$SCRIPT_DIR/api_routes.py" "API Routes"
check_file "$SCRIPT_DIR/supervisorctl.py" "CLI Tool"
check_file "$SCRIPT_DIR/setup.sh" "Setup Script"
check_file "$SCRIPT_DIR/__init__.py" "Module Init"

# 2. Check configuration
print_header "2. Configuration Files"

check_json "$SCRIPT_DIR/supervisor_config.json" "Supervisor Config"

# 3. Check documentation
print_header "3. Documentation"

check_file "$SCRIPT_DIR/README.md" "README"
check_file "$SCRIPT_DIR/IMPLEMENTATION_SUMMARY.md" "Implementation Summary"

# 4. Check Python dependencies
print_header "4. Python Dependencies"

check_python_module "psutil"
check_python_module "requests"
check_python_module "flask"
check_python_module "sqlite3"

# 5. Check directories
print_header "5. Required Directories"

check_directory "/tmp/supervisor_logs" "Log Directory"
check_directory "/tmp/supervisor_pids" "PID Directory"
check_directory "$PROJECT_ROOT/data" "Data Directory"

# 6. Check database
print_header "6. Database"

print_check "Architect Database"
if [ -f "$PROJECT_ROOT/data/architect.db" ]; then
    if sqlite3 "$PROJECT_ROOT/data/architect.db" "SELECT 1" 2>/dev/null; then
        print_pass
        ((PASSED++))
    else
        print_fail "Database corrupt"
        ((FAILED++))
    fi
else
    print_warn "Database not found (will be created)"
    ((WARNINGS++))
fi

# 7. Check supervisor status
print_header "7. Supervisor Status"

print_check "Supervisor Process"
if [ -f "/tmp/process_supervisor.pid" ]; then
    pid=$(cat /tmp/process_supervisor.pid)
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ RUNNING${NC} (PID: $pid)"
        ((PASSED++))
    else
        print_warn "Not running (stale PID file)"
        ((WARNINGS++))
    fi
else
    print_warn "Not running"
    ((WARNINGS++))
fi

# 8. Check supervised services
print_header "8. Configured Services"

services=$(python3 -c "
import json
with open('$SCRIPT_DIR/supervisor_config.json') as f:
    config = json.load(f)
    for sid, svc in config.get('services', {}).items():
        enabled = '✓' if svc.get('enabled') else '✗'
        print(f\"  [{enabled}] {sid:<20} - {svc.get('name', sid)}\")
" 2>/dev/null)

if [ -n "$services" ]; then
    echo "$services"
else
    print_fail "Could not read services"
    ((FAILED++))
fi

# Summary
print_header "Verification Summary"

total=$((PASSED + FAILED + WARNINGS))

echo "  Total Checks: $total"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
if [ $WARNINGS -gt 0 ]; then
    echo -e "  ${YELLOW}Warnings: $WARNINGS${NC}"
fi
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Failed: $FAILED${NC}"
fi

echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run setup: ./supervisor/setup.sh --auto"
    echo "  2. Check status: ./supervisor/supervisorctl.py status"
    echo "  3. View logs: tail -f /tmp/process_supervisor.log"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix the issues above.${NC}"
    echo ""
    echo "To fix:"
    echo "  1. Install dependencies: pip3 install psutil requests flask"
    echo "  2. Run setup: ./supervisor/setup.sh --auto"
    echo ""
    exit 1
fi
