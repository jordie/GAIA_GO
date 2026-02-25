#!/bin/bash
# UI Endpoint Tests for Architect Dashboard
# Used by workers to verify interface functionality
# Run: ./scripts/tests/test_ui_endpoints.sh [base_url]

BASE_URL="${1:-https://127.0.0.1:8085}"
COOKIE_FILE="/tmp/ui_test_cookies_$$.txt"
VERBOSE="${VERBOSE:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "  Architect Dashboard UI Tests"
echo "  $(date)"
echo "  URL: $BASE_URL"
echo "=============================================="

cleanup() {
    rm -f "$COOKIE_FILE" /tmp/api_out_$$.json
}
trap cleanup EXIT

# Test 1: Health check
echo ""
echo "[1] Health Check..."
health_response=$(curl -k -s --max-time 10 "$BASE_URL/health" 2>&1)
if echo "$health_response" | grep -q '"status":"healthy"'; then
    echo -e "    ${GREEN}PASS${NC} Health endpoint responding"
else
    echo -e "    ${RED}FAIL${NC} Health check failed"
    echo "    Response: $health_response"
    exit 1
fi

# Test 2: Login
echo ""
echo "[2] Authentication..."
login_code=$(curl -k -s -c "$COOKIE_FILE" -X POST "$BASE_URL/login" \
    -d "username=architect&password=peace5" \
    -w "%{http_code}" -o /dev/null --max-time 10)
if [[ "$login_code" == "302" ]]; then
    echo -e "    ${GREEN}PASS${NC} Login successful (HTTP 302 redirect)"
else
    echo -e "    ${RED}FAIL${NC} Login failed (HTTP $login_code)"
    exit 1
fi

# Test 3: Main page loads
echo ""
echo "[3] Main Page..."
main_size=$(curl -k -s -b "$COOKIE_FILE" "$BASE_URL/" --max-time 30 | wc -c | tr -d ' ')
if [[ "$main_size" -gt 100000 ]]; then
    echo -e "    ${GREEN}PASS${NC} Main page loaded (${main_size} bytes)"
else
    echo -e "    ${RED}FAIL${NC} Main page too small (${main_size} bytes)"
    exit 1
fi

# Test 4: JavaScript functions present
echo ""
echo "[4] JavaScript Functions..."
js_check=$(curl -k -s -b "$COOKIE_FILE" "$BASE_URL/" --max-time 30)
js_errors=0

for func in "navigateToPanel" "attachNavigationHandlers" "loadPanelData" "showModal" "hideModal"; do
    if echo "$js_check" | grep -q "function $func"; then
        [[ "$VERBOSE" == "true" ]] && echo -e "    ${GREEN}OK${NC} $func"
    else
        echo -e "    ${RED}MISSING${NC} $func"
        ((js_errors++))
    fi
done

if [[ $js_errors -eq 0 ]]; then
    echo -e "    ${GREEN}PASS${NC} All core JS functions present"
else
    echo -e "    ${YELLOW}WARN${NC} $js_errors JS functions missing"
fi

# Test 5: API Endpoints
echo ""
echo "[5] API Endpoints..."

declare -A endpoints=(
    ["overview"]="/api/stats"
    ["projects"]="/api/projects"
    ["features"]="/api/features"
    ["bugs"]="/api/bugs"
    ["errors"]="/api/errors"
    ["tmux"]="/api/tmux/sessions"
    ["nodes"]="/api/nodes"
    ["tasks"]="/api/tasks"
    ["queue"]="/api/autopilot/runs"
    ["workers"]="/api/workers"
    ["apps"]="/api/apps"
    ["deployments"]="/api/deployments"
    ["milestones"]="/api/milestones"
    ["accounts"]="/api/accounts"
)

passed=0
failed=0
failed_list=""

for panel in "${!endpoints[@]}"; do
    endpoint="${endpoints[$panel]}"
    code=$(curl -k -s -b "$COOKIE_FILE" -w "%{http_code}" -o /tmp/api_out_$$.json \
        --max-time 10 "$BASE_URL$endpoint" 2>&1)
    size=$(wc -c < /tmp/api_out_$$.json 2>/dev/null | tr -d ' ')

    if [[ "$code" == "200" ]]; then
        [[ "$VERBOSE" == "true" ]] && echo -e "    ${GREEN}OK${NC} #$panel -> $endpoint (${size}b)"
        ((passed++))
    else
        echo -e "    ${RED}FAIL${NC} #$panel -> $endpoint (HTTP $code)"
        ((failed++))
        failed_list="$failed_list $panel"
    fi
done

echo -e "    ${GREEN}$passed passed${NC}, ${RED}$failed failed${NC}"

# Test 6: Static assets
echo ""
echo "[6] Static Assets..."
css_code=$(curl -k -s -b "$COOKIE_FILE" -w "%{http_code}" -o /dev/null \
    "$BASE_URL/static/css/dashboard.css" --max-time 10 2>&1)
if [[ "$css_code" == "200" ]]; then
    echo -e "    ${GREEN}PASS${NC} CSS loads (HTTP 200)"
else
    echo -e "    ${YELLOW}WARN${NC} CSS status (HTTP $css_code)"
fi

# Test 7: Navigation elements
echo ""
echo "[7] Navigation Elements..."
nav_check=$(curl -k -s -b "$COOKIE_FILE" "$BASE_URL/" --max-time 30)
nav_count=$(echo "$nav_check" | grep -c 'data-panel=')
if [[ "$nav_count" -gt 5 ]]; then
    echo -e "    ${GREEN}PASS${NC} Found $nav_count navigation elements"
else
    echo -e "    ${RED}FAIL${NC} Only $nav_count navigation elements found"
fi

# Summary
echo ""
echo "=============================================="
echo "  SUMMARY"
echo "=============================================="
total_tests=7
if [[ $failed -eq 0 && $js_errors -eq 0 ]]; then
    echo -e "  ${GREEN}ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "  ${YELLOW}SOME ISSUES DETECTED${NC}"
    [[ -n "$failed_list" ]] && echo "  Failed endpoints:$failed_list"
    exit 1
fi
