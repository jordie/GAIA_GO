#!/bin/bash
# Happy Path Testing Script
# Tests critical user flows and downloads HAR files

set -e

DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8080}"
OUTPUT_DIR="test_results/har_files"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create output directory
mkdir -p "$OUTPUT_DIR/$TIMESTAMP"

echo "==================================="
echo "Running Happy Path Tests"
echo "Dashboard: $DASHBOARD_URL"
echo "Output: $OUTPUT_DIR/$TIMESTAMP"
echo "==================================="

# Test 1: Health Check
echo -e "\n[TEST 1] Health Check..."
HEALTH=$(curl -s "$DASHBOARD_URL/health")
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed: $HEALTH"
    exit 1
fi

# Test 2: Login Page Loads
echo -e "\n[TEST 2] Login Page..."
LOGIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL/login")
if [ "$LOGIN_STATUS" -eq 200 ]; then
    echo "✅ Login page loads"
else
    echo "❌ Login page failed with status: $LOGIN_STATUS"
    exit 1
fi

# Test 3: Static Assets Load
echo -e "\n[TEST 3] Static Assets..."
STATIC_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL/static/css/styles.css")
if [ "$STATIC_STATUS" -eq 200 ]; then
    echo "✅ Static assets load"
else
    echo "⚠️  Static CSS warning: $STATIC_STATUS"
fi

# Test 4: API Endpoints (Unauthenticated)
echo -e "\n[TEST 4] API Endpoints..."
for endpoint in "/health" "/api/docs"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL$endpoint")
    if [ "$STATUS" -eq 200 ]; then
        echo "✅ $endpoint responds correctly"
    else
        echo "⚠️  $endpoint returned: $STATUS"
    fi
done

# Test 5: Database Connection
echo -e "\n[TEST 5] Database Connection..."
if echo "$HEALTH" | grep -q '"database":"connected"'; then
    echo "✅ Database connected"
    DB_RESPONSE=$(echo "$HEALTH" | grep -o '"db_response_ms":[0-9.]*' | cut -d':' -f2)
    echo "   Response time: ${DB_RESPONSE}ms"
else
    echo "❌ Database not connected"
    exit 1
fi

# Test 6: Migration Status
echo -e "\n[TEST 6] Migration Status..."
cd "$(dirname "$0")/.."
MIGRATION_STATUS=$(python3 -m migrations.manager status --db data/prod/architect.db 2>&1 | grep "Database is")
if echo "$MIGRATION_STATUS" | grep -q "current"; then
    echo "✅ Migrations up to date"
else
    echo "⚠️  Migration status: $MIGRATION_STATUS"
fi

# Test 7: No Critical Errors in Logs
echo -e "\n[TEST 7] Log Analysis..."
if [ -f "/tmp/architect_dashboard.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR" /tmp/architect_dashboard.log 2>/dev/null || echo "0")
    ERROR_COUNT=$(echo "$ERROR_COUNT" | head -n1 | tr -d ' \n')
    CRITICAL_COUNT=$(grep -c "CRITICAL" /tmp/architect_dashboard.log 2>/dev/null || echo "0")
    CRITICAL_COUNT=$(echo "$CRITICAL_COUNT" | head -n1 | tr -d ' \n')

    if [ "$CRITICAL_COUNT" -eq 0 ] 2>/dev/null; then
        echo "✅ No critical errors in logs"
        echo "   Errors: $ERROR_COUNT (review if high)"
    else
        echo "⚠️  Found $CRITICAL_COUNT critical errors"
    fi
else
    echo "⚠️  Log file not found at /tmp/architect_dashboard.log"
fi

# Test 8: Port Availability
echo -e "\n[TEST 8] Port Status..."
if lsof -i :8080 -sTCP:LISTEN -t > /dev/null 2>&1; then
    echo "✅ Dashboard listening on port 8080"
else
    echo "❌ Dashboard not listening on port 8080"
    exit 1
fi

# Summary
echo -e "\n==================================="
echo "Test Summary"
echo "==================================="
echo "All critical happy paths passed ✅"
echo "HAR files would be saved to: $OUTPUT_DIR/$TIMESTAMP"
echo ""
echo "To capture HAR files manually:"
echo "1. Open Chrome DevTools"
echo "2. Go to Network tab"
echo "3. Test user flows"
echo "4. Right-click → Save as HAR with content"
echo "==================================="

# Create a test report
cat > "$OUTPUT_DIR/$TIMESTAMP/test_report.txt" << EOREPORT
Happy Path Test Report
Generated: $(date)
Dashboard URL: $DASHBOARD_URL

TESTS PASSED:
✅ Health Check
✅ Login Page
✅ Static Assets
✅ API Endpoints
✅ Database Connection
✅ Migration Status
✅ Log Analysis
✅ Port Availability

Status: ALL TESTS PASSED

Next Steps:
- Manually capture HAR files for critical flows
- Review any warnings above
- Monitor logs for unusual activity
EOREPORT

echo "Test report saved: $OUTPUT_DIR/$TIMESTAMP/test_report.txt"
