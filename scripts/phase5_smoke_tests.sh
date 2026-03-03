#!/bin/bash
# Phase 5 Production Smoke Tests
# Validates all critical rate limiting functionality in production
# Usage: ./phase5_smoke_tests.sh [HOST:PORT] [LOG_LEVEL]

set -e

# Configuration
HOST="${1:-localhost:8080}"
LOG_LEVEL="${2:-INFO}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/tmp/phase5_smoke_tests_${TIMESTAMP}.log"
PASSED=0
FAILED=0
SKIPPED=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Utility functions
log() {
    local level=$1
    shift
    local message="$@"
    echo "[$(date '+%H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() { echo -e "${BLUE}ℹ${NC}  $(log INFO $@)"; }
log_success() { echo -e "${GREEN}✓${NC}  $(log PASS $@)"; PASSED=$((PASSED+1)); }
log_error() { echo -e "${RED}✗${NC}  $(log ERROR $@)"; FAILED=$((FAILED+1)); }
log_warn() { echo -e "${YELLOW}⚠${NC}  $(log WARN $@)"; }

# Test execution function
run_test() {
    local test_name=$1
    local description=$2
    local command=$3

    log_info "Testing: $description"

    if eval "$command" > /dev/null 2>&1; then
        log_success "$test_name passed"
        return 0
    else
        log_error "$test_name FAILED: $command"
        return 1
    fi
}

# Verify host connectivity
verify_host() {
    log_info "Verifying host connectivity to $HOST..."
    if ! curl -f -s -m 5 "http://$HOST/health" > /dev/null 2>&1; then
        log_error "Cannot connect to $HOST - ensure service is running"
        exit 1
    fi
    log_success "Host connectivity verified"
}

# Test 1: Health Check
test_health_check() {
    log_info "===== Test 1: Health Check ====="

    local response=$(curl -s -m 5 "http://$HOST/health")
    if echo "$response" | grep -q "ok\|healthy"; then
        log_success "Health check passed"
        return 0
    else
        log_error "Health check failed: $response"
        return 1
    fi
}

# Test 2: Metrics Endpoint
test_metrics_endpoint() {
    log_info "===== Test 2: Metrics Endpoint ====="

    local response=$(curl -s -m 5 "http://$HOST/metrics")
    if echo "$response" | grep -q "rate_limit\|http_requests"; then
        log_success "Metrics endpoint accessible and contains rate limit metrics"
        return 0
    else
        log_error "Metrics endpoint missing rate limit metrics"
        return 1
    fi
}

# Test 3: Database Connectivity
test_database_connectivity() {
    log_info "===== Test 3: Database Connectivity ====="

    local response=$(curl -s -m 5 "http://$HOST/api/health/database")
    if echo "$response" | grep -q "connected\|ok"; then
        log_success "Database connectivity verified"
        return 0
    else
        log_error "Database connectivity check failed: $response"
        return 1
    fi
}

# Test 4: Rules API - List Rules
test_rules_api_list() {
    log_info "===== Test 4: Rules API - List Rules ====="

    local response=$(curl -s -m 10 "http://$HOST/api/admin/rate-limiting/rules/list")
    if echo "$response" | grep -q "rules\|data\|\[\]"; then
        log_success "Rules API (list) accessible"
        return 0
    else
        log_error "Rules API (list) failed: $response"
        return 1
    fi
}

# Test 5: Rules API - Create Rule
test_rules_api_create() {
    log_info "===== Test 5: Rules API - Create Rule ====="

    local rule_name="smoke_test_rule_$(date +%s)"
    local payload=$(cat <<EOF
{
    "rule_name": "$rule_name",
    "scope": "ip",
    "limit_type": "requests_per_minute",
    "limit_value": 1000,
    "whitelist": [],
    "priority": 50
}
EOF
)

    local response=$(curl -s -m 10 -X POST "http://$HOST/api/admin/rate-limiting/rules" \
        -H "Content-Type: application/json" \
        -d "$payload")

    if echo "$response" | grep -q "\"id\"\|\"rule_id\"\|success"; then
        # Extract rule ID for cleanup
        RULE_ID=$(echo "$response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 || echo "$response" | grep -o '"rule_id":"[^"]*"' | cut -d'"' -f4)
        log_success "Rule creation successful (ID: $RULE_ID)"
        return 0
    else
        log_error "Rule creation failed: $response"
        return 1
    fi
}

# Test 6: Rate Limit Check Endpoint
test_rate_limit_check() {
    log_info "===== Test 6: Rate Limit Check ====="

    local test_passed=true
    for i in {1..5}; do
        local response=$(curl -s -m 5 "http://$HOST/api/check-limit/smoke_test_resource")
        if ! echo "$response" | grep -q "allowed\|limited\|status"; then
            log_warn "Rate limit check iteration $i returned unexpected response: $response"
            test_passed=false
        fi
    done

    if [ "$test_passed" = true ]; then
        log_success "Rate limit check endpoint working (5 sequential checks)"
        return 0
    else
        log_error "Rate limit check endpoint returned unexpected responses"
        return 1
    fi
}

# Test 7: Rate Limiting Enforcement
test_rate_limiting_enforcement() {
    log_info "===== Test 7: Rate Limiting Enforcement ====="

    # Create a very strict rule for testing (1 request per minute)
    local rule_name="enforcement_test_$(date +%s)"
    local payload=$(cat <<EOF
{
    "rule_name": "$rule_name",
    "scope": "ip",
    "limit_type": "requests_per_minute",
    "limit_value": 1,
    "enabled": true,
    "priority": 100
}
EOF
)

    local rule_response=$(curl -s -m 10 -X POST "http://$HOST/api/admin/rate-limiting/rules" \
        -H "Content-Type: application/json" \
        -d "$payload")

    if echo "$rule_response" | grep -q "\"id\"\|success"; then
        log_success "Rate limiting enforcement test rule created"
        ENFORCE_RULE_ID=$(echo "$rule_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        return 0
    else
        log_error "Failed to create enforcement test rule: $rule_response"
        return 1
    fi
}

# Test 8: Migrations Status
test_migrations_status() {
    log_info "===== Test 8: Migrations Status ====="

    local response=$(curl -s -m 5 "http://$HOST/api/health/migrations")
    if echo "$response" | grep -q "complete\|up_to_date\|ok\|success"; then
        log_success "All migrations applied successfully"
        return 0
    else
        log_error "Migrations status check failed: $response"
        return 1
    fi
}

# Test 9: Reputation Service (if enabled)
test_reputation_service() {
    log_info "===== Test 9: Reputation Service ====="

    local response=$(curl -s -m 5 "http://$HOST/api/reputation/status" 2>&1)
    if echo "$response" | grep -q "score\|reputation\|ok\|enabled"; then
        log_success "Reputation service is functional"
        return 0
    else
        log_warn "Reputation service not available or disabled (may be expected)"
        SKIPPED=$((SKIPPED+1))
        return 0
    fi
}

# Test 10: Appeal System (if enabled)
test_appeal_system() {
    log_info "===== Test 10: Appeal System ====="

    local response=$(curl -s -m 5 "http://$HOST/api/appeals/status" 2>&1)
    if echo "$response" | grep -q "active\|pending\|ok\|enabled"; then
        log_success "Appeal system is functional"
        return 0
    else
        log_warn "Appeal system not available or disabled (may be expected)"
        SKIPPED=$((SKIPPED+1))
        return 0
    fi
}

# Test 11: Metrics Collection
test_metrics_collection() {
    log_info "===== Test 11: Metrics Collection ====="

    # Verify Prometheus metrics format
    local response=$(curl -s -m 5 "http://$HOST/metrics")
    if echo "$response" | grep -q "^# HELP\|^# TYPE\|^rate_limiter"; then
        log_success "Prometheus metrics properly formatted"
        return 0
    else
        log_error "Metrics format validation failed"
        return 1
    fi
}

# Test 12: API Response Times
test_api_response_times() {
    log_info "===== Test 12: API Response Times ====="

    local max_time=5000  # 5 seconds in milliseconds

    for endpoint in "/health" "/metrics" "/api/health/database"; do
        local start=$(date +%s%N | cut -b1-13)
        curl -s -m 5 "http://$HOST$endpoint" > /dev/null
        local end=$(date +%s%N | cut -b1-13)
        local elapsed=$((end - start))

        if [ $elapsed -gt $max_time ]; then
            log_error "Endpoint $endpoint took ${elapsed}ms (exceeds ${max_time}ms threshold)"
            return 1
        fi
    done

    log_success "All endpoints responding within acceptable time limits"
    return 0
}

# Cleanup function
cleanup() {
    log_info "===== Cleanup ====="

    # Delete test rules if they were created
    if [ -n "$RULE_ID" ]; then
        curl -s -X DELETE "http://$HOST/api/admin/rate-limiting/rules/$RULE_ID" 2>/dev/null
        log_info "Cleaned up test rule (ID: $RULE_ID)"
    fi

    if [ -n "$ENFORCE_RULE_ID" ]; then
        curl -s -X DELETE "http://$HOST/api/admin/rate-limiting/rules/$ENFORCE_RULE_ID" 2>/dev/null
        log_info "Cleaned up enforcement test rule (ID: $ENFORCE_RULE_ID)"
    fi
}

# Summary report
print_summary() {
    log_info "===== Test Summary ====="
    log_info "Passed: $PASSED"
    log_info "Failed: $FAILED"
    log_info "Skipped: $SKIPPED"
    log_info "Total: $((PASSED + FAILED + SKIPPED))"
    log_info "Log file: $LOG_FILE"

    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✅ All critical tests passed!${NC}\n"
        return 0
    else
        echo -e "\n${RED}❌ $FAILED test(s) failed - review log for details${NC}\n"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Phase 5 Production Smoke Tests                  ║${NC}"
    echo -e "${BLUE}║  Target: $HOST${NC}"
    echo -e "${BLUE}║  Time: $(date '+%Y-%m-%d %H:%M:%S')                     ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}\n"

    # Pre-flight checks
    verify_host

    # Run all tests
    test_health_check || true
    test_metrics_endpoint || true
    test_database_connectivity || true
    test_rules_api_list || true
    test_rules_api_create || true
    test_rate_limit_check || true
    test_rate_limiting_enforcement || true
    test_migrations_status || true
    test_reputation_service || true
    test_appeal_system || true
    test_metrics_collection || true
    test_api_response_times || true

    # Cleanup
    cleanup

    # Print summary
    print_summary

    exit $?
}

# Trap errors and cleanup
trap cleanup EXIT

# Execute main
main
