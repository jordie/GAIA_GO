#!/bin/bash
# Rate Limit Configuration Script
# Configure custom rate limits for different endpoints

echo "==========================================="
echo "Rate Limit Configuration Tool"
echo "==========================================="
echo ""

# Get session cookie - in real setup, would use actual login
SESSION_COOKIE="user=admin"

BASE_URL="http://localhost:8080/api/rate-limiting"

echo "Current Configurations:"
echo "----------------------"
curl -s "$BASE_URL/config" \
  -H "Cookie: $SESSION_COOKIE" \
  | python3 -c "import sys,json; data=json.load(sys.stdin); configs=data.get('configs',[]); [print(f\"  - {c['rule_name']}: {c['limit_value']} {c['limit_type']}\") for c in configs]" 2>/dev/null || echo "  (Unable to fetch - app may need authentication setup)"

echo ""
echo "System Health:"
echo "--------------"
curl -s "$BASE_URL/resource-health" \
  -H "Cookie: $SESSION_COOKIE" \
  | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'current' in data:
        c = data['current']
        print(f\"  CPU: {c.get('cpu_percent', 0):.1f}%\")
        print(f\"  Memory: {c.get('memory_percent', 0):.1f}%\")
        print(f\"  Disk: {c.get('disk_percent', 0):.1f}%\")
        print(f\"  Throttling: {'YES' if data.get('throttling') else 'NO'}\")
except:
    print('  (Unable to fetch health data)')
" 2>/dev/null

echo ""
echo "Rate Limit Statistics:"
echo "---------------------"
curl -s "$BASE_URL/stats?days=1" \
  -H "Cookie: $SESSION_COOKIE" \
  | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    s = data.get('stats', {})
    print(f\"  Total Requests: {s.get('total_requests', 0)}\")
    violations = s.get('violations_by_scope', {})
    print(f\"  Total Violations: {sum(violations.values())}\")
    for scope, count in violations.items():
        print(f\"    - {scope}: {count} violations\")
except:
    print('  (Unable to fetch statistics)')
" 2>/dev/null

echo ""
echo "Recent Violations:"
echo "------------------"
curl -s "$BASE_URL/violations?hours=1" \
  -H "Cookie: $SESSION_COOKIE" \
  | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    viols = data.get('violations', {}).get('violations', [])
    if viols:
        for v in viols[:5]:
            print(f\"  - {v['scope_value']}: {v['scope_value']} ({v.get('resource_type', 'unknown')})\")
    else:
        print('  (No violations in the last hour)')
except:
    print('  (Unable to fetch violations)')
" 2>/dev/null

echo ""
echo "Example: Create New Rate Limit Rule"
echo "-----------------------------------"
echo "To add a custom rate limit, use:"
echo ""
echo "curl -X POST http://localhost:8080/api/rate-limiting/config \\"
echo "  -H 'Cookie: user=admin' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo "    \"rule_name\": \"api_strict_limit\","
echo "    \"scope\": \"ip\","
echo "    \"limit_type\": \"requests_per_minute\","
echo "    \"limit_value\": 50,"
echo "    \"resource_type\": \"api_call\""
echo "  }'"
echo ""
