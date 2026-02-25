#!/bin/bash
#
# Deploy script for Architect Dashboard
#
# Usage:
#   ./deploy.sh                    # Start server on port 8080 (runs tests first)
#   ./deploy.sh --ssl              # Start with HTTPS
#   ./deploy.sh --daemon           # Run as daemon
#   ./deploy.sh --skip-tests       # Skip pre-deployment tests (not recommended)
#   ./deploy.sh stop               # Stop daemon
#   ./deploy.sh status             # Check status
#   ./deploy.sh worker             # Start task worker
#   ./deploy.sh agent              # Start node agent
#   ./deploy.sh backup             # Backup database
#   ./deploy.sh restore <file>     # Restore database from backup
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect environment from git branch if not set
if [ -z "$APP_ENV" ]; then
    BRANCH=$(cd "$SCRIPT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "dev")
    case "$BRANCH" in
        main) APP_ENV="prod" ;;
        qa*) APP_ENV="qa" ;;
        *) APP_ENV="dev" ;;
    esac
fi
export APP_ENV

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
PID_FILE="/tmp/architect_dashboard_${APP_ENV}.pid"
LOG_FILE="/tmp/architect_dashboard_${APP_ENV}.log"
SERVICES_FILE="$SCRIPT_DIR/data/services.json"

# Tailscale configuration
TAILSCALE_ENABLED="${TAILSCALE_ENABLED:-false}"
TAILSCALE_IP=""
TAILSCALE_HOSTNAME=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# Tailscale Functions
# ============================================================================

detect_tailscale() {
    # Check if Tailscale is installed and running
    if ! command -v tailscale &> /dev/null; then
        print_warning "Tailscale not installed"
        return 1
    fi

    # Check Tailscale status
    local status=$(tailscale status --json 2>/dev/null)
    if [ $? -ne 0 ]; then
        print_warning "Tailscale not running or not logged in"
        return 1
    fi

    # Get Tailscale IP
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null)
    if [ -z "$TAILSCALE_IP" ]; then
        print_warning "Could not get Tailscale IPv4 address"
        return 1
    fi

    # Get Tailscale hostname
    TAILSCALE_HOSTNAME=$(tailscale status --json 2>/dev/null | grep -o '"Self":{[^}]*"HostName":"[^"]*"' | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
    if [ -z "$TAILSCALE_HOSTNAME" ]; then
        TAILSCALE_HOSTNAME=$(hostname -s)
    fi

    print_status "Tailscale detected: $TAILSCALE_IP ($TAILSCALE_HOSTNAME)"
    return 0
}

get_tailscale_ip() {
    # Return cached IP or detect
    if [ -n "$TAILSCALE_IP" ]; then
        echo "$TAILSCALE_IP"
        return 0
    fi

    # Try to get from tailscale command
    local ip=$(tailscale ip -4 2>/dev/null)
    if [ -n "$ip" ]; then
        echo "$ip"
        return 0
    fi

    # Fallback: try to read from services.json
    if [ -f "$SERVICES_FILE" ]; then
        local saved_ip=$(grep -o '"tailscale"[[:space:]]*:[[:space:]]*"[^"]*"' "$SERVICES_FILE" | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+')
        if [ -n "$saved_ip" ]; then
            echo "$saved_ip"
            return 0
        fi
    fi

    return 1
}

update_services_tailscale() {
    # Update services.json with current Tailscale IP
    if [ ! -f "$SERVICES_FILE" ]; then
        print_warning "Services file not found: $SERVICES_FILE"
        return 1
    fi

    local ts_ip=$(get_tailscale_ip)
    if [ -z "$ts_ip" ]; then
        print_warning "Could not determine Tailscale IP"
        return 1
    fi

    # Update the Tailscale IP in services.json using Python for proper JSON handling
    python3 << EOF
import json
import sys

try:
    with open("$SERVICES_FILE", 'r') as f:
        data = json.load(f)

    # Update hosts section
    if 'hosts' not in data:
        data['hosts'] = {}

    old_ip = data['hosts'].get('tailscale', 'not set')
    data['hosts']['tailscale'] = "$ts_ip"
    data['hosts']['tailscale_hostname'] = "$TAILSCALE_HOSTNAME"

    # Add Tailscale-specific service entries if not present
    if 'services' in data:
        for svc_id, svc in list(data['services'].items()):
            if svc.get('env') == 'prod':
                ts_svc_id = svc_id.replace('-prod', '-tailscale')
                if ts_svc_id not in data['services']:
                    data['services'][ts_svc_id] = {
                        'app': svc['app'],
                        'env': 'tailscale',
                        'port': svc['port'],
                        'protocol': svc.get('protocol', 'http'),
                        'host': "$ts_ip"
                    }

    with open("$SERVICES_FILE", 'w') as f:
        json.dump(data, f, indent=2)

    if old_ip != "$ts_ip":
        print(f"Updated Tailscale IP: {old_ip} -> $ts_ip")
    else:
        print(f"Tailscale IP unchanged: $ts_ip")

except Exception as e:
    print(f"Error updating services.json: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

show_tailscale_info() {
    echo ""
    echo "=== Tailscale Network Info ==="
    echo ""

    if ! command -v tailscale &> /dev/null; then
        echo -e "Tailscale: ${RED}Not installed${NC}"
        echo ""
        echo "Install Tailscale: https://tailscale.com/download"
        return 1
    fi

    local status=$(tailscale status 2>&1)
    if echo "$status" | grep -q "not logged in\|stopped"; then
        echo -e "Tailscale: ${YELLOW}Not connected${NC}"
        echo ""
        echo "Run: tailscale up"
        return 1
    fi

    local ts_ip=$(get_tailscale_ip)
    local ts_hostname=$(tailscale status --json 2>/dev/null | grep -o '"Self":{[^}]*"HostName":"[^"]*"' | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)

    echo -e "Tailscale: ${GREEN}Connected${NC}"
    echo "IP:        $ts_ip"
    echo "Hostname:  $ts_hostname"
    echo ""

    # Show accessible URLs
    echo "Service URLs via Tailscale:"
    echo "  Dashboard: http://$ts_ip:$PORT/"
    if [ -f "$SERVICES_FILE" ]; then
        # List other services
        python3 << EOF
import json
try:
    with open("$SERVICES_FILE", 'r') as f:
        data = json.load(f)
    for svc_id, svc in data.get('services', {}).items():
        if svc.get('host') == "$ts_ip" or svc.get('env') == 'tailscale':
            proto = svc.get('protocol', 'http')
            port = svc.get('port', 8080)
            print(f"  {svc_id}: {proto}://$ts_ip:{port}/")
except:
    pass
EOF
    fi
    echo ""

    # Show peers
    echo "Connected peers:"
    tailscale status 2>/dev/null | grep -v "^#" | head -10 || echo "  (none)"
    echo ""
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
}

backup_database() {
    local db_file="$SCRIPT_DIR/data/architect.db"
    local backup_dir="$SCRIPT_DIR/data/backups"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/architect_${timestamp}.db"

    if [ ! -f "$db_file" ]; then
        print_error "Database not found: $db_file"
        exit 1
    fi

    # Create backup directory if it doesn't exist
    mkdir -p "$backup_dir"

    # Create backup using SQLite's backup command for consistency
    if command -v sqlite3 &> /dev/null; then
        print_status "Creating database backup..."
        sqlite3 "$db_file" ".backup '$backup_file'"
    else
        # Fallback to file copy
        print_warning "sqlite3 not found, using file copy (ensure no writes during backup)"
        cp "$db_file" "$backup_file"
    fi

    if [ -f "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        print_status "Backup created: $backup_file ($size)"

        # Clean up old backups (keep last 10)
        local backup_count=$(ls -1 "$backup_dir"/architect_*.db 2>/dev/null | wc -l)
        if [ "$backup_count" -gt 10 ]; then
            print_status "Cleaning up old backups (keeping last 10)..."
            ls -1t "$backup_dir"/architect_*.db | tail -n +11 | xargs rm -f
        fi
    else
        print_error "Backup failed"
        exit 1
    fi
}

restore_database() {
    local backup_file="$1"
    local db_file="$SCRIPT_DIR/data/architect.db"

    if [ -z "$backup_file" ]; then
        print_error "Usage: $0 restore <backup_file>"
        echo ""
        echo "Available backups:"
        ls -lh "$SCRIPT_DIR/data/backups"/architect_*.db 2>/dev/null || echo "  No backups found"
        exit 1
    fi

    # Handle relative paths
    if [[ ! "$backup_file" = /* ]]; then
        # Check in backups directory first
        if [ -f "$SCRIPT_DIR/data/backups/$backup_file" ]; then
            backup_file="$SCRIPT_DIR/data/backups/$backup_file"
        elif [ -f "$backup_file" ]; then
            backup_file="$(pwd)/$backup_file"
        fi
    fi

    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi

    # Verify it's a valid SQLite database
    if command -v sqlite3 &> /dev/null; then
        if ! sqlite3 "$backup_file" "SELECT 1;" &> /dev/null; then
            print_error "Invalid SQLite database: $backup_file"
            exit 1
        fi
    fi

    # Check if server is running
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_error "Server is running. Please stop it first: $0 stop"
            exit 1
        fi
    fi

    # Create a backup of current database before restoring
    if [ -f "$db_file" ]; then
        local pre_restore_backup="$db_file.pre_restore_$(date +%Y%m%d_%H%M%S)"
        print_status "Backing up current database to: $pre_restore_backup"
        cp "$db_file" "$pre_restore_backup"
    fi

    # Restore the database
    print_status "Restoring database from: $backup_file"
    cp "$backup_file" "$db_file"

    if [ -f "$db_file" ]; then
        local size=$(du -h "$db_file" | cut -f1)
        print_status "Database restored successfully ($size)"
    else
        print_error "Restore failed"
        exit 1
    fi
}

check_dependencies() {
    print_status "Checking dependencies..."

    # Check Flask
    python3 -c "import flask" 2>/dev/null || {
        print_warning "Flask not found, installing..."
        pip3 install flask
    }

    # Check requests (optional but recommended)
    python3 -c "import requests" 2>/dev/null || {
        print_warning "requests not found, installing..."
        pip3 install requests
    }

    # Check psutil (optional but recommended for metrics)
    python3 -c "import psutil" 2>/dev/null || {
        print_warning "psutil not found, installing..."
        pip3 install psutil
    }
}

update_documentation() {
    # Update documentation before deployment
    local target_url="${1:-http://localhost:$PORT}"
    local max_retries=5
    local retry_count=0

    print_status "Updating documentation before deployment..."

    # Wait for server to be ready
    while [ $retry_count -lt $max_retries ]; do
        if curl -s "$target_url/health" | grep -q "healthy"; then
            break
        fi
        retry_count=$((retry_count + 1))
        print_warning "Waiting for server to be ready... ($retry_count/$max_retries)"
        sleep 2
    done

    if [ $retry_count -eq $max_retries ]; then
        print_warning "Server not ready, skipping documentation update"
        return 1
    fi

    # Call the documentation update API
    # First, we need to login to get a session
    local cookie_file="/tmp/architect_deploy_cookies.txt"
    local user="${ARCHITECT_USER:-architect}"
    local pass="${ARCHITECT_PASSWORD:-peace5}"

    # Login
    curl -s -c "$cookie_file" -X POST "$target_url/login" \
        -d "username=$user&password=$pass" \
        -L > /dev/null 2>&1

    # Update documentation
    local result=$(curl -s -b "$cookie_file" -X POST "$target_url/api/documentation/update" \
        -H "Content-Type: application/json" \
        -d '{"trigger_type": "pre_deploy", "environment": "'"${APP_ENV:-prod}"'"}')

    if echo "$result" | grep -q '"success"'; then
        local old_ver=$(echo "$result" | grep -o '"old_version":"[^"]*"' | cut -d'"' -f4)
        local new_ver=$(echo "$result" | grep -o '"new_version":"[^"]*"' | cut -d'"' -f4)
        print_status "Documentation updated: $old_ver → $new_ver"
    else
        print_warning "Documentation update failed: $result"
    fi

    rm -f "$cookie_file"
}

run_tests() {
    # Run happy path tests before deployment
    print_status "Running pre-deployment tests..."
    if [ -f "$SCRIPT_DIR/scripts/test_happy_paths.sh" ]; then
        if bash "$SCRIPT_DIR/scripts/test_happy_paths.sh"; then
            print_status "All tests passed ✅"
            return 0
        else
            print_error "Tests failed ❌"
            echo ""
            echo "Deployment blocked - fix errors before deploying"
            echo "Review test output above for details"
            return 1
        fi
    else
        print_warning "Test script not found, skipping tests"
        return 0
    fi
}

start_server() {
    local ssl_flag=""
    local daemon_flag=""
    local tailscale_flag=""
    local skip_tests=""

    for arg in "$@"; do
        case $arg in
            --ssl) ssl_flag="--ssl" ;;
            --daemon) daemon_flag="true" ;;
            --tailscale) tailscale_flag="true" ;;
            --skip-tests) skip_tests="true" ;;
        esac
    done

    check_python
    check_dependencies

    # Run tests before deployment (unless --skip-tests flag is used)
    if [ -z "$skip_tests" ]; then
        if ! run_tests; then
            return 1
        fi
    else
        print_warning "Skipping tests (--skip-tests flag used)"
    fi

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_warning "Server already running (PID $pid)"
            return 1
        fi
        rm -f "$PID_FILE"
    fi

    # Handle Tailscale configuration
    if [ -n "$tailscale_flag" ] || [ "$TAILSCALE_ENABLED" = "true" ]; then
        if detect_tailscale; then
            TAILSCALE_ENABLED="true"
            update_services_tailscale
            print_status "Tailscale mode enabled - accessible at $TAILSCALE_IP:$PORT"
        else
            print_warning "Tailscale requested but not available, continuing with standard config"
        fi
    fi

    print_status "Starting Architect Dashboard on port $PORT..."

    if [ -n "$daemon_flag" ]; then
        # Run as daemon
        nohup python3 "$SCRIPT_DIR/app.py" --port "$PORT" --host "$HOST" $ssl_flag > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        print_status "Server started in background (PID $(cat $PID_FILE))"
        print_status "Logs: $LOG_FILE"

        # Show access URLs
        echo ""
        echo "Access URLs:"
        echo "  Local:     http://localhost:$PORT/"
        if [ -n "$TAILSCALE_IP" ]; then
            echo "  Tailscale: http://$TAILSCALE_IP:$PORT/"
        fi
        echo ""

        # Update documentation after server starts
        sleep 3
        update_documentation "http://localhost:$PORT"
    else
        # Show access info before starting
        echo ""
        echo "Access URLs:"
        echo "  Local:     http://localhost:$PORT/"
        if [ -n "$TAILSCALE_IP" ]; then
            echo "  Tailscale: http://$TAILSCALE_IP:$PORT/"
        fi
        echo ""

        # Run in foreground
        python3 "$SCRIPT_DIR/app.py" --port "$PORT" --host "$HOST" $ssl_flag
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_status "Stopping server (PID $pid)..."
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                print_warning "Server did not stop, sending SIGKILL..."
                kill -9 "$pid"
            fi
            rm -f "$PID_FILE"
            print_status "Server stopped"
        else
            print_warning "Server not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        print_warning "Server not running"
    fi
}

show_status() {
    echo ""
    echo "=== Architect Dashboard Status ==="
    echo ""

    # Check main server
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "Server:  ${GREEN}Running${NC} (PID $pid)"
            echo "  Local:     http://localhost:$PORT/"
            # Check Tailscale
            local ts_ip=$(get_tailscale_ip 2>/dev/null)
            if [ -n "$ts_ip" ]; then
                echo "  Tailscale: http://$ts_ip:$PORT/"
            fi
        else
            echo -e "Server:  ${RED}Not running${NC} (stale PID)"
        fi
    else
        echo -e "Server:  ${YELLOW}Not running${NC}"
    fi

    # Check worker
    if [ -f "/tmp/architect_worker.pid" ]; then
        pid=$(cat "/tmp/architect_worker.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "Worker:  ${GREEN}Running${NC} (PID $pid)"
        else
            echo -e "Worker:  ${RED}Not running${NC} (stale PID)"
        fi
    else
        echo -e "Worker:  ${YELLOW}Not running${NC}"
    fi

    # Check node agent
    if [ -f "/tmp/architect_node_agent.pid" ]; then
        pid=$(cat "/tmp/architect_node_agent.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "Agent:   ${GREEN}Running${NC} (PID $pid)"
        else
            echo -e "Agent:   ${RED}Not running${NC} (stale PID)"
        fi
    else
        echo -e "Agent:   ${YELLOW}Not running${NC}"
    fi

    # Check Tailscale
    echo ""
    if command -v tailscale &> /dev/null; then
        local ts_ip=$(get_tailscale_ip 2>/dev/null)
        if [ -n "$ts_ip" ]; then
            echo -e "Tailscale: ${GREEN}Connected${NC} ($ts_ip)"
        else
            echo -e "Tailscale: ${YELLOW}Not connected${NC}"
        fi
    else
        echo -e "Tailscale: ${YELLOW}Not installed${NC}"
    fi

    echo ""
}

start_worker() {
    print_status "Starting task worker..."
    python3 "$SCRIPT_DIR/workers/task_worker.py" --daemon --dashboard-url "http://localhost:$PORT"
}

start_agent() {
    print_status "Starting node agent..."
    python3 "$SCRIPT_DIR/distributed/node_agent.py" --daemon --dashboard "http://localhost:$PORT"
}

# Main
case "${1:-}" in
    stop)
        stop_server
        ;;
    status)
        show_status
        ;;
    worker)
        shift
        if [ "${1:-}" = "stop" ]; then
            python3 "$SCRIPT_DIR/workers/task_worker.py" --stop
        elif [ "${1:-}" = "status" ]; then
            python3 "$SCRIPT_DIR/workers/task_worker.py" --status
        else
            start_worker
        fi
        ;;
    agent)
        shift
        if [ "${1:-}" = "stop" ]; then
            python3 "$SCRIPT_DIR/distributed/node_agent.py" --stop
        elif [ "${1:-}" = "status" ]; then
            python3 "$SCRIPT_DIR/distributed/node_agent.py" --status
        else
            start_agent
        fi
        ;;
    docs)
        # Update documentation
        update_documentation "http://localhost:$PORT"
        ;;
    tailscale|ts)
        # Tailscale management
        shift
        case "${1:-info}" in
            info|status)
                show_tailscale_info
                ;;
            update)
                if detect_tailscale; then
                    update_services_tailscale
                    print_status "Services configuration updated with Tailscale IP"
                fi
                ;;
            ip)
                get_tailscale_ip
                ;;
            *)
                echo "Usage: $0 tailscale [info|update|ip]"
                echo ""
                echo "Commands:"
                echo "  info    Show Tailscale network info (default)"
                echo "  update  Update services.json with current Tailscale IP"
                echo "  ip      Print Tailscale IP address"
                ;;
        esac
        ;;
    backup)
        backup_database
        ;;
    restore)
        shift
        restore_database "$1"
        ;;
    help|--help|-h)
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  (none)          Start the server"
        echo "  stop            Stop the server"
        echo "  status          Show status of all components"
        echo "  worker          Start/stop/status task worker"
        echo "  agent           Start/stop/status node agent"
        echo "  docs            Update documentation"
        echo "  tailscale       Tailscale network info and management"
        echo "  backup          Backup database to data/backups/"
        echo "  restore <file>  Restore database from backup file"
        echo ""
        echo "Options:"
        echo "  --ssl           Enable HTTPS"
        echo "  --daemon        Run as daemon"
        echo "  --tailscale     Enable Tailscale mode (auto-detect IP)"
        echo ""
        echo "Environment variables:"
        echo "  PORT              Server port (default: 8080)"
        echo "  HOST              Server host (default: 0.0.0.0)"
        echo "  TAILSCALE_ENABLED Enable Tailscale by default (true/false)"
        echo "  ARCHITECT_USER    Admin username (default: admin)"
        echo "  ARCHITECT_PASSWORD  Admin password (default: architect2025)"
        echo ""
        echo "Tailscale:"
        echo "  When --tailscale is used or TAILSCALE_ENABLED=true, the script will:"
        echo "  - Auto-detect your Tailscale IP address"
        echo "  - Update data/services.json with Tailscale endpoints"
        echo "  - Show Tailscale URLs in status output"
        ;;
    *)
        start_server "$@"
        ;;
esac
