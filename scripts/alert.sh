#!/bin/bash
# Alert system for service monitoring
# Supports: desktop notification, sound, log, webhook

ALERT_LOG="/tmp/service_alerts.log"

# Configuration
ENABLE_DESKTOP=true
ENABLE_SOUND=true
ENABLE_LOG=true
WEBHOOK_URL=""  # Set to Slack/Discord webhook URL if desired

send_alert() {
    local level="$1"    # CRITICAL, WARNING, INFO, RECOVERED
    local service="$2"
    local message="$3"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Log alert
    if [ "$ENABLE_LOG" = true ]; then
        echo "[$timestamp] [$level] $service: $message" >> "$ALERT_LOG"
    fi

    # Desktop notification (macOS)
    if [ "$ENABLE_DESKTOP" = true ]; then
        case "$level" in
            CRITICAL)
                osascript -e "display notification \"$message\" with title \"🔴 CRITICAL: $service\" sound name \"Basso\"" 2>/dev/null
                ;;
            WARNING)
                osascript -e "display notification \"$message\" with title \"🟡 WARNING: $service\" sound name \"Ping\"" 2>/dev/null
                ;;
            RECOVERED)
                osascript -e "display notification \"$message\" with title \"🟢 RECOVERED: $service\" sound name \"Glass\"" 2>/dev/null
                ;;
            INFO)
                osascript -e "display notification \"$message\" with title \"ℹ️ $service\"" 2>/dev/null
                ;;
        esac
    fi

    # Sound alert for critical
    if [ "$ENABLE_SOUND" = true ] && [ "$level" = "CRITICAL" ]; then
        afplay /System/Library/Sounds/Sosumi.aiff 2>/dev/null &
    fi

    # Webhook (Slack/Discord)
    if [ -n "$WEBHOOK_URL" ]; then
        local color="danger"
        [ "$level" = "RECOVERED" ] && color="good"
        [ "$level" = "WARNING" ] && color="warning"

        curl -s -X POST "$WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"[$level] $service: $message\"}" \
            >/dev/null 2>&1 &
    fi

    # Print to stdout
    echo "[$timestamp] [$level] $service: $message"
}

# Command line interface
case "${1:-}" in
    --critical)
        send_alert "CRITICAL" "$2" "$3"
        ;;
    --warning)
        send_alert "WARNING" "$2" "$3"
        ;;
    --recovered)
        send_alert "RECOVERED" "$2" "$3"
        ;;
    --info)
        send_alert "INFO" "$2" "$3"
        ;;
    --test)
        echo "Testing alerts..."
        send_alert "CRITICAL" "Test Service" "This is a test critical alert"
        sleep 2
        send_alert "RECOVERED" "Test Service" "Service has recovered"
        ;;
    --log)
        echo "Recent alerts from $ALERT_LOG:"
        tail -20 "$ALERT_LOG" 2>/dev/null || echo "No alerts yet"
        ;;
    *)
        echo "Usage: alert.sh [--critical|--warning|--recovered|--info] <service> <message>"
        echo "       alert.sh --test    Test alert system"
        echo "       alert.sh --log     Show recent alerts"
        ;;
esac
