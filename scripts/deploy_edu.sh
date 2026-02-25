#!/bin/bash
#
# Deploy Script for Educational Apps Platform
#
# Usage:
#   ./deploy.sh qa [VERSION]           Deploy to QA (DEV_PORT + 1)
#   ./deploy.sh qa --latest            Deploy latest tag to QA
#   ./deploy.sh qa --migrate           Run migrations on QA only
#   ./deploy.sh qa --port=5064 v1.0.2  Deploy to specific QA port
#
# Examples:
#   ./deploy.sh qa v1.0.2              Deploy tag v1.0.2 to QA
#   ./deploy.sh qa --port=5064 v1.0.2  Deploy to QA port 5064
#   ./deploy.sh qa --latest            Deploy the most recent tag
#   ./deploy.sh qa --migrate           Run pending migrations on QA

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_LOG="$SCRIPT_DIR/deployment_history.json"

# Initialize deployment log if it doesn't exist
init_deployment_log() {
    if [ ! -f "$DEPLOYMENT_LOG" ]; then
        echo '{"deployments": []}' > "$DEPLOYMENT_LOG"
    fi
}

# Log deployment to history file
log_deployment() {
    local version=$1
    local env=$2
    local status=$3
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local git_sha=$(git rev-parse --short "$version" 2>/dev/null || echo "unknown")
    local deployer=$(whoami)

    init_deployment_log

    # Create new deployment entry
    local entry=$(cat <<JSONEOF
{
    "timestamp": "$timestamp",
    "version": "$version",
    "git_sha": "$git_sha",
    "environment": "$env",
    "port": "$QA_PORT",
    "status": "$status",
    "deployer": "$deployer"
}
JSONEOF
)

    # Use Python to safely append to JSON (handles edge cases)
    python3 -c "
import json
import sys

log_file = '$DEPLOYMENT_LOG'
new_entry = $entry

try:
    with open(log_file, 'r') as f:
        data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    data = {'deployments': []}

data['deployments'].insert(0, new_entry)
# Keep only last 50 deployments
data['deployments'] = data['deployments'][:50]

with open(log_file, 'w') as f:
    json.dump(data, f, indent=2)
"
}

# Parse optional --port argument
QA_PORT=""
for arg in "$@"; do
    if [[ "$arg" == --port=* ]]; then
        QA_PORT="${arg#--port=}"
    fi
done

# Default QA port is DEV port + 1 (read from current env or default to 5050+1)
if [ -z "$QA_PORT" ]; then
    DEV_PORT="${PORT:-5050}"
    QA_PORT=$((DEV_PORT + 1))
fi

QA_DATA_DIR="$SCRIPT_DIR/qa_data_${QA_PORT}"
QA_ENV_NAME="QA:${QA_PORT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "Usage: $0 qa [VERSION|--latest|--migrate]"
    echo ""
    echo "Commands:"
    echo "  qa VERSION    Deploy specific git tag to QA (e.g., v1.0.2)"
    echo "  qa --latest   Deploy the latest git tag to QA"
    echo "  qa --migrate  Run database migrations on QA only"
    echo ""
    echo "Examples:"
    echo "  $0 qa v1.0.2"
    echo "  $0 qa --latest"
    echo "  $0 qa --migrate"
    exit 1
}

stop_qa_server() {
    echo_info "Stopping QA server..."
    lsof -ti :$QA_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
}

start_qa_server() {
    echo_info "Starting QA server on port $QA_PORT..."

    # Set up separate database paths for QA to avoid locking issues with DEV
    mkdir -p "$QA_DATA_DIR"

    # Copy DEV databases to QA if they don't exist
    [ ! -f "$QA_DATA_DIR/education_central.db" ] && [ -f "$SCRIPT_DIR/education_central.db" ] && \
        cp "$SCRIPT_DIR/education_central.db" "$QA_DATA_DIR/"
    [ ! -f "$QA_DATA_DIR/typing.db" ] && [ -f "$SCRIPT_DIR/typing/typing.db" ] && \
        cp "$SCRIPT_DIR/typing/typing.db" "$QA_DATA_DIR/"
    [ ! -f "$QA_DATA_DIR/math_practice.db" ] && [ -f "$SCRIPT_DIR/math/math_practice.db" ] && \
        cp "$SCRIPT_DIR/math/math_practice.db" "$QA_DATA_DIR/"
    [ ! -f "$QA_DATA_DIR/application.db" ] && [ -f "$SCRIPT_DIR/reading/application.db" ] && \
        cp "$SCRIPT_DIR/reading/application.db" "$QA_DATA_DIR/"
    [ ! -f "$QA_DATA_DIR/piano.db" ] && [ -f "$SCRIPT_DIR/piano/piano.db" ] && \
        cp "$SCRIPT_DIR/piano/piano.db" "$QA_DATA_DIR/"

    # Start QA server with separate database paths
    USE_HTTPS=true APP_ENV=qa PORT=$QA_PORT \
        CENTRAL_DB_PATH="$QA_DATA_DIR/education_central.db" \
        TYPING_DB_PATH="$QA_DATA_DIR/typing.db" \
        MATH_DB_PATH="$QA_DATA_DIR/math_practice.db" \
        READING_DB_PATH="$QA_DATA_DIR/application.db" \
        PIANO_DB_PATH="$QA_DATA_DIR/piano.db" \
        python3 "$SCRIPT_DIR/unified_app.py" &
    sleep 2

    # Verify server started
    if curl -sk "https://localhost:$QA_PORT/" > /dev/null 2>&1; then
        echo_info "QA server started successfully on port $QA_PORT"
    else
        echo_warn "QA server may not have started correctly"
    fi
}

run_migrations() {
    echo_info "Running migrations on QA databases..."
    python3 "$SCRIPT_DIR/migrations/run_migrations.py" qa
}

deploy_version() {
    local VERSION=$1

    # Validate we're in a git repo
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo_error "Not in a git repository"
        exit 1
    fi

    # Get latest tag if requested
    if [ "$VERSION" == "--latest" ]; then
        VERSION=$(git describe --tags --abbrev=0 2>/dev/null)
        if [ -z "$VERSION" ]; then
            echo_error "No tags found in repository"
            exit 1
        fi
        echo_info "Latest tag: $VERSION"
    fi

    # Validate tag exists
    if ! git rev-parse "$VERSION" > /dev/null 2>&1; then
        echo_error "Tag '$VERSION' not found"
        echo ""
        echo "Available tags:"
        git tag -l | tail -10
        exit 1
    fi

    echo ""
    echo "========================================="
    echo " DEPLOYING $VERSION TO QA"
    echo "========================================="
    echo ""

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo_warn "You have uncommitted changes!"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo_info "Deployment cancelled"
            exit 0
        fi
    fi

    # Store current branch/commit
    CURRENT_REF=$(git rev-parse HEAD)
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")

    echo_info "Current position: $CURRENT_BRANCH ($CURRENT_REF)"
    echo_info "Deploying: $VERSION"

    # Log deployment start
    log_deployment "$VERSION" "qa" "deploying"

    # Stop QA server
    stop_qa_server

    # Checkout the version
    echo_info "Checking out $VERSION..."
    git checkout "$VERSION"

    # Run migrations
    run_migrations

    # Start QA server
    start_qa_server

    # Return to previous branch
    echo_info "Returning to $CURRENT_BRANCH..."
    git checkout "$CURRENT_BRANCH" 2>/dev/null || git checkout "$CURRENT_REF"

    # Log deployment success
    log_deployment "$VERSION" "qa" "success"

    echo ""
    echo "========================================="
    echo " DEPLOYMENT COMPLETE"
    echo "========================================="
    echo ""
    echo "QA is now running version: $VERSION"
    echo "Access at: https://192.168.1.231:$QA_PORT/"
    echo ""
}

# Main
if [ $# -lt 1 ]; then
    usage
fi

ENV=$1
shift

if [ "$ENV" != "qa" ]; then
    echo_error "Only 'qa' environment is supported for deployment"
    echo "DEV environment runs from working directory directly"
    exit 1
fi

if [ $# -lt 1 ]; then
    usage
fi

COMMAND=$1

case "$COMMAND" in
    --migrate)
        run_migrations
        ;;
    --latest|v*)
        deploy_version "$COMMAND"
        ;;
    *)
        usage
        ;;
esac
