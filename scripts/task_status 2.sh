#!/bin/bash
# Task Status Dashboard - Quick view of queue and session availability
# Usage: ./scripts/task_status.sh [--watch]

DB="/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/assigner/assigner.db"
WATCH_MODE=false

if [[ "$1" == "--watch" ]]; then
    WATCH_MODE=true
fi

show_status() {
    clear
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           ARCHITECT TASK STATUS DASHBOARD                     ║"
    echo "║           $(date '+%Y-%m-%d %H:%M:%S')                              ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    # Queue Stats
    echo "┌─ QUEUE STATISTICS ─────────────────────────────────────────────┐"
    pending=$(sqlite3 "$DB" "SELECT COUNT(*) FROM prompts WHERE status='pending'")
    assigned=$(sqlite3 "$DB" "SELECT COUNT(*) FROM prompts WHERE status='assigned'")
    in_progress=$(sqlite3 "$DB" "SELECT COUNT(*) FROM prompts WHERE status='in_progress'")
    completed=$(sqlite3 "$DB" "SELECT COUNT(*) FROM prompts WHERE status='completed'")
    failed=$(sqlite3 "$DB" "SELECT COUNT(*) FROM prompts WHERE status='failed'")

    echo "  Pending:     $pending"
    echo "  Assigned:    $assigned"
    echo "  In Progress: $in_progress"
    echo "  Completed:   $completed"
    echo "  Failed:      $failed"
    echo "└────────────────────────────────────────────────────────────────┘"
    echo ""

    # Session Availability
    echo "┌─ SESSION AVAILABILITY ─────────────────────────────────────────┐"
    sqlite3 "$DB" "SELECT printf('  %-20s %s', name, status) FROM sessions ORDER BY name" | while read line; do
        if echo "$line" | grep -q "idle"; then
            echo "  ✅ $line"
        else
            echo "  🔴 $line"
        fi
    done
    echo "└────────────────────────────────────────────────────────────────┘"
    echo ""

    # Recent Pending Tasks
    if [ $pending -gt 0 ]; then
        echo "┌─ PENDING TASKS (Top 5) ────────────────────────────────────────┐"
        sqlite3 "$DB" "
            SELECT printf('  #%-3d [P%d] %s', id, priority, substr(content, 1, 50))
            FROM prompts
            WHERE status='pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 5
        "
        echo "└────────────────────────────────────────────────────────────────┘"
        echo ""
    fi

    # Active Tasks
    if [ $in_progress -gt 0 ]; then
        echo "┌─ ACTIVE TASKS ─────────────────────────────────────────────────┐"
        sqlite3 "$DB" "
            SELECT printf('  #%-3d %-15s %s', p.id, p.assigned_to, substr(p.content, 1, 40))
            FROM prompts p
            WHERE p.status='in_progress'
        "
        echo "└────────────────────────────────────────────────────────────────┘"
        echo ""
    fi

    # Recent Failures
    if [ $failed -gt 0 ]; then
        echo "┌─ RECENT FAILURES (Last 3) ─────────────────────────────────────┐"
        sqlite3 "$DB" "
            SELECT printf('  #%-3d %s', id, substr(content, 1, 50))
            FROM prompts
            WHERE status='failed'
            ORDER BY id DESC
            LIMIT 3
        "
        echo "└────────────────────────────────────────────────────────────────┘"
        echo ""
    fi

    # System Health
    echo "┌─ SYSTEM HEALTH ────────────────────────────────────────────────┐"

    # Check health monitor
    if pgrep -f "session_health_daemon" > /dev/null; then
        echo "  ✅ Health Monitor: Running (PID: $(pgrep -f session_health_daemon | head -1))"
    else
        echo "  ❌ Health Monitor: Not Running"
    fi

    # Check assigner worker
    if pgrep -f "assigner_worker.py.*daemon" > /dev/null; then
        echo "  ✅ Assigner Worker: Running (PID: $(pgrep -f 'assigner_worker.py.*daemon' | head -1))"
    else
        echo "  ❌ Assigner Worker: Not Running"
    fi

    # Check auto-confirm
    if pgrep -f "auto_confirm_worker" > /dev/null; then
        echo "  ✅ Auto-Confirm: Running (PID: $(pgrep -f auto_confirm_worker | head -1))"
    else
        echo "  ⚠️  Auto-Confirm: Not Running"
    fi

    # Memory usage
    mem_usage=$(ps aux | grep -E '(assigner_worker|session_health|auto_confirm)' | grep -v grep | awk '{sum+=$4} END {printf "%.1f%%", sum}')
    echo "  📊 Worker Memory: $mem_usage"

    echo "└────────────────────────────────────────────────────────────────┘"
    echo ""

    # Quick Actions
    echo "QUICK ACTIONS:"
    echo "  ./scripts/task_status.sh --watch    # Auto-refresh every 5s"
    echo "  python3 workers/assigner_worker.py --prompts  # Detailed prompt list"
    echo "  python3 workers/assigner_worker.py --send \"task\"  # Queue new task"
    echo ""
}

if [ "$WATCH_MODE" = true ]; then
    while true; do
        show_status
        echo "Refreshing in 5 seconds... (Ctrl+C to exit)"
        sleep 5
    done
else
    show_status
fi
