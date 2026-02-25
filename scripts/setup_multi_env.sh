#!/bin/bash

#################################################################################
# Multi-Environment Setup Script - Phase 1
# Creates 5 isolated development environments with separate branches/DBs/ports
#################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NUM_ENVIRONMENTS=5
PORTS_START=8081

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

check_prerequisites() {
    log_info "Checking prerequisites..."
    [ ! -d "$BASE_DIR/architect/.git" ] && { log_error "architect repo not found"; exit 1; }
    log_success "Prerequisites met"
}

create_environment() {
    local env_num=$1
    local env_name="dev$env_num"
    local env_dir="$BASE_DIR/architect-$env_name"
    local port=$((PORTS_START + env_num - 1))

    echo ""
    log_info "Creating environment: architect-$env_name (port $port)"

    [ -d "$env_dir" ] && { log_warning "Already exists: $env_dir"; return 0; }

    git clone "$BASE_DIR/architect" "$env_dir" --quiet
    cd "$env_dir"
    git checkout -b "env/$env_name" --quiet
    log_success "Repository cloned"

    # Create sub-environment databases
    log_info "Setting up dev/qa/staging..."
    for sub_env in dev qa staging; do
        mkdir -p "data/$sub_env"
        python3 << PYEOF
import sqlite3, os
db_path = "data/$sub_env/architect.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY, value TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute("INSERT OR IGNORE INTO app_config (key, value) VALUES (?, ?)", ("env_type", "$sub_env"))
conn.commit()
conn.close()
PYEOF
    done
    log_success "Sub-environments configured"

    # Create launch scripts
    cat > "launch.sh" << 'LAUNCHER'
#!/bin/bash
SUB_ENV="${1:-dev}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT_MAP="8081:dev 8091:qa 8101:staging"
PORT=$(echo "$PORT_MAP" | grep ":$SUB_ENV" | cut -d: -f1)
PID_FILE="/tmp/architect_ENVNAME_$SUB_ENV.pid"
[ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null && { echo "Already running"; exit 0; }
echo "Starting architect-ENVNAME ($SUB_ENV) on port $PORT..."
cd "$DIR"
APP_ENV=$SUB_ENV PORT=$PORT python3 app.py > /tmp/architect_ENVNAME_$SUB_ENV.log 2>&1 &
echo $! > "$PID_FILE"
sleep 2
echo "Started (PID: $(cat $PID_FILE))"
LAUNCHER

    cat > "stop.sh" << 'STOPPER'
#!/bin/bash
for pf in /tmp/architect_ENVNAME_*.pid; do
    [ -f "$pf" ] && kill $(cat "$pf") 2>/dev/null && rm "$pf"
done
echo "Stopped"
STOPPER

    cat > "status.sh" << 'STATUS'
#!/bin/bash
PID_FILE="/tmp/architect_ENVNAME_dev.pid"
[ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null && { echo "RUNNING"; exit 0; }
echo "NOT RUNNING"
exit 1
STATUS

    chmod +x launch.sh stop.sh status.sh
    sed -i.bak "s/ENVNAME/$env_name/g" launch.sh stop.sh status.sh
    rm -f launch.sh.bak stop.sh.bak status.sh.bak

    git add -A
    git commit -m "chore: Initialize environment $env_name" --quiet
    log_success "Environment created"
    echo -e "  ${CYAN}Port: $port${NC} | ${CYAN}Branch: env/$env_name${NC}"
}

setup_all() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ Phase 1: Development Environment Setup                            ║${NC}"
    echo -e "${BLUE}║ Creating 5 isolated development environments                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"

    check_prerequisites

    for i in $(seq 1 $NUM_ENVIRONMENTS); do
        create_environment $i
    done

    # Create status database
    log_info "Creating status database..."
    mkdir -p "$BASE_DIR/architect/data/multi_env"
    python3 << 'PYEOF'
import sqlite3, os
db_path = "data/multi_env/status.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS directories (
    name TEXT PRIMARY KEY, working_dir TEXT, git_branch TEXT,
    branch_ahead INTEGER, branch_behind INTEGER, is_dirty BOOLEAN, last_sync TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS environments (
    id INTEGER PRIMARY KEY, directory TEXT, env_type TEXT,
    status TEXT, port INTEGER, pid INTEGER, url TEXT, last_activity TIMESTAMP)''')
conn.commit()
conn.close()
PYEOF
    log_success "Status database created"

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║ ✓ Phase 1 Complete: 5 Environments Created                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Created:"
    for i in $(seq 1 $NUM_ENVIRONMENTS); do
        port=$((PORTS_START + i - 1))
        echo "  • architect-dev$i (port $port, branch: env/dev$i)"
    done
    echo ""
    echo "Test: cd architect-dev1 && ./launch.sh && ./status.sh && ./stop.sh"
    echo ""
}

clean_all() {
    echo -e "${YELLOW}⚠️  Delete all development environments? (yes/no)${NC}"
    read -p "> " confirm
    [ "$confirm" != "yes" ] && return 0
    for i in $(seq 1 $NUM_ENVIRONMENTS); do
        [ -d "$BASE_DIR/architect-dev$i" ] && rm -rf "$BASE_DIR/architect-dev$i"
    done
    rm -f "$BASE_DIR/architect/data/multi_env"/*
    log_success "Cleanup complete"
}

show_status() {
    echo ""
    echo -e "${BLUE}Multi-Environment Status${NC}"
    for i in $(seq 1 $NUM_ENVIRONMENTS); do
        env_dir="$BASE_DIR/architect-dev$i"
        port=$((PORTS_START + i - 1))
        [ ! -d "$env_dir" ] && { echo -e "${YELLOW}dev$i${NC}: NOT CREATED"; continue; }
        cd "$env_dir"
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
        ./status.sh &>/dev/null && status="${GREEN}RUNNING${NC}" || status="${YELLOW}STOPPED${NC}"
        echo -e "${CYAN}dev$i${NC} (port $port): $status [$branch]"
    done
    echo ""
}

case "${1:-setup}" in
    setup) setup_all ;;
    clean) clean_all ;;
    status) show_status ;;
    *) echo "Usage: $0 [setup|clean|status]" && exit 1 ;;
esac
