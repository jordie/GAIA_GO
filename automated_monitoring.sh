#!/bin/bash

##############################################################################
# Automated Post-Deployment Monitoring Script
# Runs continuously during 7-day validation period
# Tracks all critical metrics and generates hourly reports
##############################################################################

set -e

# Configuration
MONITORING_DIR="/tmp/rate_limiting_monitoring"
LOG_FILE="$MONITORING_DIR/monitoring.log"
METRICS_FILE="$MONITORING_DIR/metrics.json"
ALERTS_FILE="$MONITORING_DIR/alerts.log"
API_BASE="http://localhost:8080/api/rate-limiting"
AUTH_COOKIE="user=admin"
ADMIN_EMAIL="admin@example.com"

# Thresholds
CPU_WARNING_THRESHOLD=80
CPU_CRITICAL_THRESHOLD=95
MEMORY_WARNING_THRESHOLD=80
MEMORY_CRITICAL_THRESHOLD=95
ERROR_LOG_WARNING_THRESHOLD=5
ERROR_LOG_CRITICAL_THRESHOLD=10
VIOLATION_RATE_THRESHOLD=1  # per hour

##############################################################################
# Setup
##############################################################################

setup_monitoring() {
    mkdir -p "$MONITORING_DIR"

    # Initialize log files
    echo "$(date) - Monitoring initialized" >> "$LOG_FILE"
    echo "{}" > "$METRICS_FILE"
    echo "$(date) - Monitoring started" >> "$ALERTS_FILE"

    echo "✓ Monitoring setup complete"
    echo "  Logs: $LOG_FILE"
    echo "  Metrics: $METRICS_FILE"
    echo "  Alerts: $ALERTS_FILE"
}

##############################################################################
# Data Collection
##############################################################################

collect_health_metrics() {
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Fetch health data
    local health=$(curl -s -H "Cookie: $AUTH_COOKIE" "$API_BASE/resource-health")

    if [ -z "$health" ]; then
        log_error "Failed to fetch health data"
        return 1
    fi

    # Extract metrics
    local cpu=$(echo "$health" | jq '.current.cpu_percent // 0')
    local memory=$(echo "$health" | jq '.current.memory_percent // 0')
    local throttling=$(echo "$health" | jq '.throttling // false')

    # Store metrics
    local metrics=$(jq -n \
        --arg ts "$timestamp" \
        --arg cpu "$cpu" \
        --arg mem "$memory" \
        --arg throttle "$throttling" \
        '{timestamp: $ts, cpu: $cpu, memory: $mem, throttling: $throttle}')

    echo "$metrics" >> "$METRICS_FILE"

    echo "$(date) - CPU: ${cpu}%, Memory: ${memory}%, Throttling: ${throttling}" >> "$LOG_FILE"

    # Check thresholds
    check_resource_thresholds "$cpu" "$memory"
}

collect_statistics() {
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Fetch stats
    local stats=$(curl -s -H "Cookie: $AUTH_COOKIE" "$API_BASE/stats?days=1")

    if [ -z "$stats" ]; then
        log_error "Failed to fetch statistics"
        return 1
    fi

    # Extract metrics
    local requests=$(echo "$stats" | jq '.stats.total_requests // 0')
    local violations=$(echo "$stats" | jq '.stats.total_violations // 0')

    # Calculate violation rate
    local violation_rate=0
    if [ "$requests" -gt 0 ]; then
        violation_rate=$(echo "scale=2; ($violations / $requests) * 100" | bc 2>/dev/null || echo "0")
    fi

    echo "$(date) - Requests: $requests, Violations: $violations (${violation_rate}%)" >> "$LOG_FILE"

    # Check violation thresholds
    check_violation_thresholds "$violations" "$violation_rate"
}

collect_error_metrics() {
    # Count errors in log file
    local error_count=$(grep -c "ERROR" /tmp/monitoring.log 2>/dev/null || echo "0")
    local warning_count=$(grep -c "WARN" /tmp/monitoring.log 2>/dev/null || echo "0")

    echo "$(date) - Errors: $error_count, Warnings: $warning_count" >> "$LOG_FILE"

    # Check error thresholds
    check_error_thresholds "$error_count"
}

##############################################################################
# Threshold Checking & Alerting
##############################################################################

check_resource_thresholds() {
    local cpu=$1
    local memory=$2

    # CPU checks
    if (( $(echo "$cpu > $CPU_CRITICAL_THRESHOLD" | bc -l) )); then
        alert_critical "CPU usage critical: ${cpu}%"
    elif (( $(echo "$cpu > $CPU_WARNING_THRESHOLD" | bc -l) )); then
        alert_warning "CPU usage elevated: ${cpu}%"
    fi

    # Memory checks
    if (( $(echo "$memory > $MEMORY_CRITICAL_THRESHOLD" | bc -l) )); then
        alert_critical "Memory usage critical: ${memory}%"
    elif (( $(echo "$memory > $MEMORY_WARNING_THRESHOLD" | bc -l) )); then
        alert_warning "Memory usage elevated: ${memory}%"
    fi
}

check_violation_thresholds() {
    local violations=$1
    local rate=$2

    if (( $(echo "$violations > 100" | bc -l) )); then
        alert_warning "High violation count: $violations"
    fi

    if (( $(echo "$rate > $VIOLATION_RATE_THRESHOLD" | bc -l) )); then
        alert_warning "Violation rate elevated: ${rate}%"
    fi
}

check_error_thresholds() {
    local error_count=$1

    if [ "$error_count" -gt "$ERROR_LOG_CRITICAL_THRESHOLD" ]; then
        alert_critical "Critical error count: $error_count errors"
    elif [ "$error_count" -gt "$ERROR_LOG_WARNING_THRESHOLD" ]; then
        alert_warning "Elevated error count: $error_count errors"
    fi
}

##############################################################################
# Alerting
##############################################################################

alert_critical() {
    local message=$1
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] CRITICAL: $message" >> "$ALERTS_FILE"

    # Print to console
    echo "🚨 CRITICAL: $message"

    # TODO: Send to monitoring system
    # send_slack_alert "CRITICAL: $message"
    # send_email_alert "$ADMIN_EMAIL" "CRITICAL ALERT: $message"
    # trigger_pagerduty "CRITICAL: $message"
}

alert_warning() {
    local message=$1
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] WARNING: $message" >> "$ALERTS_FILE"

    # Print to console
    echo "⚠️  WARNING: $message"

    # TODO: Send to monitoring system
    # send_slack_alert "WARNING: $message"
}

log_error() {
    local message=$1
    echo "$(date) - ERROR: $message" >> "$LOG_FILE"
}

##############################################################################
# Reporting
##############################################################################

generate_hourly_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hour=$(date '+%H')

    echo ""
    echo "========================================"
    echo "Hourly Report - $timestamp"
    echo "========================================"

    # Get last hour of logs
    echo ""
    echo "Recent Metrics:"
    tail -12 "$LOG_FILE" | grep "$(date '+%H')"

    # Get alerts
    echo ""
    echo "Alerts (Last Hour):"
    grep "$(date '+%Y-%m-%d %H')" "$ALERTS_FILE" || echo "  (None)"

    echo ""
    echo "========================================"

    # Save to file
    cat >> "$MONITORING_DIR/hourly_report_${hour}.log" << EOF
======================================
Hourly Report - $timestamp
======================================

Recent Metrics:
$(tail -12 "$LOG_FILE" | grep "$(date '+%H')")

Alerts:
$(grep "$(date '+%Y-%m-%d %H')" "$ALERTS_FILE" || echo "(None)")

======================================
EOF
}

generate_daily_report() {
    local timestamp=$(date '+%Y-%m-%d')
    local report_file="$MONITORING_DIR/daily_report_${timestamp}.md"

    # Fetch final statistics
    local stats=$(curl -s -H "Cookie: $AUTH_COOKIE" "$API_BASE/stats?days=1")
    local health=$(curl -s -H "Cookie: $AUTH_COOKIE" "$API_BASE/resource-health")

    cat > "$report_file" << 'EOF'
# Daily Monitoring Report

Date: $(date '+%Y-%m-%d')

## Statistics (24h)
- Total Requests: $(echo "$stats" | jq '.stats.total_requests')
- Total Violations: $(echo "$stats" | jq '.stats.total_violations')
- Violation Rate: $(echo "scale=2; ($(echo "$stats" | jq '.stats.total_violations') / $(echo "$stats" | jq '.stats.total_requests')) * 100" | bc)%

## System Health
- Current CPU: $(echo "$health" | jq '.current.cpu_percent')%
- Current Memory: $(echo "$health" | jq '.current.memory_percent')%
- Throttling: $(echo "$health" | jq '.throttling')

## Error Summary
- Total Errors: $(grep -c "ERROR" /tmp/monitoring.log || echo "0")
- Total Warnings: $(grep -c "WARN" /tmp/monitoring.log || echo "0")

## Alerts
$(grep "$(date '+%Y-%m-%d')" "$ALERTS_FILE" | head -20 || echo "None")

## Top Issues
EOF

    # Analyze violation sources
    curl -s -H "Cookie: $AUTH_COOKIE" "$API_BASE/violations?hours=24" | \
        jq '.violations | group_by(.scope_value) | sort_by(length) | reverse | .[0:5]' >> "$report_file" 2>/dev/null || echo "N/A" >> "$report_file"

    echo "Generated daily report: $report_file"
}

##############################################################################
# API Health Check
##############################################################################

check_api_health() {
    local endpoints=(
        "config"
        "stats"
        "violations"
        "resource-health"
        "dashboard"
    )

    for endpoint in "${endpoints[@]}"; do
        local response=$(curl -s -w "\n%{http_code}" -H "Cookie: $AUTH_COOKIE" "$API_BASE/$endpoint")
        local http_code=$(echo "$response" | tail -1)

        if [ "$http_code" != "200" ]; then
            alert_critical "API endpoint failed: GET $API_BASE/$endpoint (HTTP $http_code)"
        fi
    done
}

##############################################################################
# Main Loop
##############################################################################

run_continuous_monitoring() {
    echo "Starting continuous monitoring..."
    echo "Press Ctrl+C to stop"
    echo ""

    local iteration=0
    local hour_tracker=""

    while true; do
        iteration=$((iteration + 1))
        local current_hour=$(date '+%H')

        # Every 5 minutes: collect metrics
        if [ $((iteration % 1)) -eq 0 ]; then
            echo "$(date '+%H:%M:%S') - Collecting metrics..."
            collect_health_metrics
            collect_statistics
            collect_error_metrics
            check_api_health
        fi

        # Every hour: generate report
        if [ "$current_hour" != "$hour_tracker" ]; then
            echo "$(date '+%H:%M:%S') - Generating hourly report..."
            generate_hourly_report
            hour_tracker=$current_hour
        fi

        # Sleep 5 minutes before next check
        sleep 300
    done
}

run_once() {
    echo "Running single monitoring cycle..."
    collect_health_metrics
    collect_statistics
    collect_error_metrics
    check_api_health
    generate_hourly_report
    generate_daily_report
}

##############################################################################
# CLI
##############################################################################

main() {
    case "${1:-run}" in
        setup)
            setup_monitoring
            ;;
        run)
            setup_monitoring
            run_continuous_monitoring
            ;;
        once)
            setup_monitoring
            run_once
            ;;
        report)
            generate_daily_report
            ;;
        status)
            echo "Monitoring Status:"
            echo "  Log file: $LOG_FILE ($(wc -l < "$LOG_FILE" 2>/dev/null || echo "0") lines)"
            echo "  Alerts: $(grep -c "CRITICAL\|WARNING" "$ALERTS_FILE" 2>/dev/null || echo "0")"
            echo "  Latest: $(tail -1 "$LOG_FILE")"
            ;;
        *)
            cat << 'USAGE'
Usage: automated_monitoring.sh [command]

Commands:
  setup          Initialize monitoring directories and files
  run            Start continuous monitoring (recommended)
  once           Run single monitoring cycle
  report         Generate daily report
  status         Show monitoring status

Examples:
  ./automated_monitoring.sh setup
  ./automated_monitoring.sh run &
  ./automated_monitoring.sh status
  ./automated_monitoring.sh report

For continuous monitoring, run in background:
  nohup ./automated_monitoring.sh run > /tmp/monitoring.out 2>&1 &
USAGE
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
