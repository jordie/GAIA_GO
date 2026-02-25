#!/bin/bash
# Verification script for Rate Limiting and Resource Monitoring Enhancement

set -e

echo "=========================================="
echo "Rate Limiting Implementation Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check migration file exists
echo "1. Checking migration files..."
if [ -f "migrations/050_rate_limiting_enhancement.sql" ]; then
    pass "Migration file exists"
    LINES=$(wc -l < migrations/050_rate_limiting_enhancement.sql)
    pass "Migration file has $LINES lines"
else
    fail "Migration file not found"
fi

# 2. Check service files exist
echo ""
echo "2. Checking service files..."
SERVICES=(
    "services/rate_limiting.py"
    "services/resource_monitor.py"
    "services/background_tasks.py"
    "services/rate_limiting_routes.py"
)

for service in "${SERVICES[@]}"; do
    if [ -f "$service" ]; then
        pass "$service exists"
        LINES=$(wc -l < "$service")
        echo "   └─ $LINES lines"
    else
        fail "$service not found"
    fi
done

# 3. Check test file
echo ""
echo "3. Checking test files..."
if [ -f "tests/unit/test_rate_limiting.py" ]; then
    pass "Test file exists"
    LINES=$(wc -l < tests/unit/test_rate_limiting.py)
    echo "   └─ $LINES lines of test code"
else
    fail "Test file not found"
fi

# 4. Check documentation
echo ""
echo "4. Checking documentation..."
DOCS=(
    "RATE_LIMITING_ENHANCEMENT.md"
    "RATE_LIMITING_IMPLEMENTATION_GUIDE.md"
    "RATE_LIMITING_DELIVERY_SUMMARY.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        pass "$doc exists"
        LINES=$(wc -l < "$doc")
        echo "   └─ $LINES lines"
    else
        fail "$doc not found"
    fi
done

# 5. Verify imports in services/__init__.py
echo ""
echo "5. Checking service imports..."
if grep -q "RateLimitService" services/__init__.py; then
    pass "RateLimitService imported in services/__init__.py"
else
    fail "RateLimitService not imported"
fi

if grep -q "ResourceMonitor" services/__init__.py; then
    pass "ResourceMonitor imported in services/__init__.py"
else
    fail "ResourceMonitor not imported"
fi

# 6. Check Python syntax
echo ""
echo "6. Checking Python syntax..."
for pyfile in services/rate_limiting.py services/resource_monitor.py services/background_tasks.py services/rate_limiting_routes.py; do
    if python3 -m py_compile "$pyfile" 2>/dev/null; then
        pass "$pyfile syntax OK"
    else
        fail "$pyfile has syntax errors"
    fi
done

# 7. Check for main classes
echo ""
echo "7. Checking class definitions..."
CLASSES=(
    "RateLimitService:services/rate_limiting.py"
    "ResourceMonitor:services/resource_monitor.py"
    "BackgroundTaskManager:services/background_tasks.py"
)

for class_def in "${CLASSES[@]}"; do
    IFS=: read CLASS FILE <<< "$class_def"
    if grep -q "class $CLASS" "$FILE"; then
        pass "Class $CLASS defined in $FILE"
    else
        fail "Class $CLASS not found in $FILE"
    fi
done

# 8. Check for key methods
echo ""
echo "8. Checking key methods..."
METHODS=(
    "check_limit:services/rate_limiting.py"
    "create_config:services/rate_limiting.py"
    "should_throttle:services/resource_monitor.py"
    "record_snapshot:services/resource_monitor.py"
    "register_task:services/background_tasks.py"
    "start:services/background_tasks.py"
)

for method_def in "${METHODS[@]}"; do
    IFS=: read METHOD FILE <<< "$method_def"
    if grep -q "def $METHOD" "$FILE"; then
        pass "Method $METHOD found in $FILE"
    else
        fail "Method $METHOD not found in $FILE"
    fi
done

# 9. Check git commits
echo ""
echo "9. Checking git history..."
if git log --oneline | grep -q "rate limiting"; then
    pass "Rate limiting commits found in git history"
    COUNT=$(git log --oneline | grep -c "rate limiting" || true)
    echo "   └─ Found $COUNT related commits"
else
    warn "No recent rate limiting commits found"
fi

# 10. Database schema check (if DB exists)
echo ""
echo "10. Checking database..."
if [ -f "data/architect.db" ]; then
    pass "Database file exists"

    # Check if tables would be created
    TABLES=$(sqlite3 "data/architect.db" ".tables" 2>/dev/null | grep -c rate_limit || true)
    if [ "$TABLES" -gt 0 ]; then
        pass "Rate limit tables found in database"
        sqlite3 "data/architect.db" "SELECT COUNT(*) as table_count FROM sqlite_master WHERE type='table' AND name LIKE 'rate_limit%';" 2>/dev/null
    else
        warn "Rate limit tables not yet created (migration not applied)"
    fi
else
    warn "Database file not found (create with migration when ready)"
fi

# Summary
echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
echo -e "${RED}Failed:${NC} $FAIL_COUNT"

if [ $FAIL_COUNT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Apply migration: sqlite3 data/architect.db < migrations/050_rate_limiting_enhancement.sql"
    echo "2. Review RATE_LIMITING_IMPLEMENTATION_GUIDE.md"
    echo "3. Integrate services into app.py"
    echo "4. Run pytest tests/unit/test_rate_limiting.py"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Some checks failed. Please review the errors above.${NC}"
    exit 1
fi
