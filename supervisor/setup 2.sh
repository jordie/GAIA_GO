#!/bin/bash
#
# Supervisor Setup Script
#
# Sets up and starts the process supervisor system
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

print_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Check Python
check_python() {
    print_status "Checking Python installation..."

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    python_version=$(python3 --version | awk '{print $2}')
    print_status "Python version: $python_version"
}

# Check and install dependencies
check_dependencies() {
    print_status "Checking dependencies..."

    missing_deps=()

    # Check psutil
    if ! python3 -c "import psutil" 2>/dev/null; then
        missing_deps+=("psutil")
    fi

    # Check requests
    if ! python3 -c "import requests" 2>/dev/null; then
        missing_deps+=("requests")
    fi

    # Check flask
    if ! python3 -c "import flask" 2>/dev/null; then
        missing_deps+=("flask")
    fi

    if [ ${#missing_deps[@]} -eq 0 ]; then
        print_status "All dependencies installed"
    else
        print_warning "Missing dependencies: ${missing_deps[*]}"
        print_status "Installing dependencies..."

        pip3 install "${missing_deps[@]}"

        if [ $? -eq 0 ]; then
            print_status "Dependencies installed successfully"
        else
            print_error "Failed to install dependencies"
            exit 1
        fi
    fi
}

# Create directories
create_directories() {
    print_status "Creating directories..."

    mkdir -p /tmp/supervisor_logs
    mkdir -p /tmp/supervisor_pids

    print_status "Directories created"
}

# Make scripts executable
make_executable() {
    print_status "Making scripts executable..."

    chmod +x "$SCRIPT_DIR/process_supervisor.py"
    chmod +x "$SCRIPT_DIR/supervisorctl.py"
    chmod +x "$SCRIPT_DIR/health_checks.py"

    print_status "Scripts are now executable"
}

# Verify configuration
verify_config() {
    print_status "Verifying configuration..."

    config_file="$SCRIPT_DIR/supervisor_config.json"

    if [ ! -f "$config_file" ]; then
        print_error "Configuration file not found: $config_file"
        exit 1
    fi

    # Validate JSON
    if python3 -c "import json; json.load(open('$config_file'))" 2>/dev/null; then
        print_status "Configuration file is valid JSON"
    else
        print_error "Configuration file is invalid JSON"
        exit 1
    fi
}

# Initialize database
init_database() {
    print_status "Initializing database..."

    python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from supervisor.supervisor_integration import SupervisorIntegration
integration = SupervisorIntegration()
print('Database initialized')
"

    if [ $? -eq 0 ]; then
        print_status "Database initialized successfully"
    else
        print_error "Failed to initialize database"
        exit 1
    fi
}

# Start supervisor
start_supervisor() {
    print_status "Starting process supervisor..."

    # Check if already running
    if [ -f "/tmp/process_supervisor.pid" ]; then
        pid=$(cat /tmp/process_supervisor.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            print_warning "Supervisor already running (PID: $pid)"
            return
        else
            print_warning "Stale PID file found, removing..."
            rm -f /tmp/process_supervisor.pid
        fi
    fi

    # Start as daemon
    cd "$PROJECT_ROOT"
    python3 "$SCRIPT_DIR/process_supervisor.py" --daemon

    # Wait and verify
    sleep 2

    if [ -f "/tmp/process_supervisor.pid" ]; then
        pid=$(cat /tmp/process_supervisor.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            print_status "Supervisor started successfully (PID: $pid)"
        else
            print_error "Supervisor failed to start"
            exit 1
        fi
    else
        print_error "Supervisor failed to start (no PID file)"
        exit 1
    fi
}

# Show status
show_status() {
    print_header "Process Supervisor Status"

    python3 "$SCRIPT_DIR/supervisorctl.py" status
}

# Main menu
show_menu() {
    print_header "Process Supervisor Setup"

    echo "1) Full setup (check dependencies, init, start)"
    echo "2) Install dependencies only"
    echo "3) Initialize database only"
    echo "4) Start supervisor"
    echo "5) Stop supervisor"
    echo "6) Restart supervisor"
    echo "7) Show status"
    echo "8) View logs"
    echo "9) Exit"
    echo ""
    read -p "Select option [1-9]: " choice

    case $choice in
        1)
            check_python
            check_dependencies
            create_directories
            make_executable
            verify_config
            init_database
            start_supervisor
            show_status
            ;;
        2)
            check_python
            check_dependencies
            ;;
        3)
            init_database
            ;;
        4)
            start_supervisor
            show_status
            ;;
        5)
            print_status "Stopping supervisor..."
            python3 "$SCRIPT_DIR/process_supervisor.py" --stop
            ;;
        6)
            print_status "Restarting supervisor..."
            python3 "$SCRIPT_DIR/process_supervisor.py" --stop
            sleep 2
            start_supervisor
            show_status
            ;;
        7)
            show_status
            ;;
        8)
            tail -f /tmp/process_supervisor.log
            ;;
        9)
            print_status "Exiting"
            exit 0
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac
}

# Auto-setup if run with --auto flag
if [ "$1" = "--auto" ]; then
    print_header "Automatic Setup"

    check_python
    check_dependencies
    create_directories
    make_executable
    verify_config
    init_database
    start_supervisor
    show_status

    print_header "Setup Complete"
    echo "Supervisor is now running and monitoring services."
    echo ""
    echo "Useful commands:"
    echo "  ./supervisor/supervisorctl.py status       - Show service status"
    echo "  ./supervisor/supervisorctl.py logs <id>    - View service logs"
    echo "  ./supervisor/supervisorctl.py summary      - Show summary"
    echo "  tail -f /tmp/process_supervisor.log        - View supervisor log"
    echo ""
else
    # Interactive menu
    show_menu
fi
