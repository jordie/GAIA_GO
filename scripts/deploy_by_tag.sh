#!/bin/bash
#
# Tag-Based Deployment Script for Architect Dashboard
#
# Deployment Flow:
#   - dev branch push → DEV (port 8082) - automatic
#   - v*.*.* tag → QA (port 8081) - requires tests pass
#   - release-*.*.* tag → PROD (port 8080) - requires QA tests pass
#
# Usage:
#   ./deploy_by_tag.sh <tag> [environment]
#   ./deploy_by_tag.sh v1.0.0          # Deploy to QA
#   ./deploy_by_tag.sh release-1.0.0   # Deploy to PROD
#   ./deploy_by_tag.sh HEAD dev        # Deploy current HEAD to DEV
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ENVIRONMENTS=(
    "dev:8082:data/dev"
    "qa:8081:data/qa"
    "prod:8080:data/prod"
)

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "Tag-Based Deployment Script"
    echo ""
    echo "Usage: $0 <tag> [environment]"
    echo ""
    echo "Arguments:"
    echo "  tag          Git tag or ref to deploy (e.g., v1.0.0, release-1.0.0, HEAD)"
    echo "  environment  Target environment (dev, qa, prod) - auto-detected from tag if not specified"
    echo ""
    echo "Tag Conventions:"
    echo "  v*.*.*        → Deploy to QA (requires tests to pass)"
    echo "  release-*.*.*  → Deploy to PROD (requires QA deployment first)"
    echo "  HEAD, branch  → Deploy to DEV"
    echo ""
    echo "Examples:"
    echo "  $0 v1.2.3              # Deploy v1.2.3 to QA"
    echo "  $0 release-1.2.3       # Deploy release-1.2.3 to PROD"
    echo "  $0 HEAD dev            # Deploy current HEAD to DEV"
    echo "  $0 main qa             # Deploy main branch to QA"
}

get_env_config() {
    local env=$1
    for config in "${ENVIRONMENTS[@]}"; do
        IFS=':' read -r name port data_dir <<< "$config"
        if [ "$name" == "$env" ]; then
            echo "$port:$data_dir"
            return 0
        fi
    done
    return 1
}

detect_environment() {
    local tag=$1

    if [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        echo "qa"
    elif [[ "$tag" =~ ^release-[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        echo "prod"
    else
        echo "dev"
    fi
}

backup_database() {
    local env=$1
    local config=$(get_env_config "$env")
    local data_dir=$(echo "$config" | cut -d: -f2)
    local db_path="$PROJECT_DIR/$data_dir/architect.db"

    if [ -f "$db_path" ]; then
        local timestamp=$(date +%Y%m%d_%H%M%S)
        local backup_dir="$PROJECT_DIR/$data_dir/backups"
        mkdir -p "$backup_dir"
        cp "$db_path" "$backup_dir/architect_${timestamp}.db"
        log_info "Database backed up to: $backup_dir/architect_${timestamp}.db"
    fi
}

run_tests() {
    log_info "Running test suite..."

    if [ -f "$PROJECT_DIR/scripts/run_tests.sh" ]; then
        if "$PROJECT_DIR/scripts/run_tests.sh"; then
            log_success "All tests passed!"
            return 0
        else
            log_error "Tests failed!"
            return 1
        fi
    else
        # Fallback to direct pytest
        export APP_ENV=test
        if python3 -m pytest tests/ -v --tb=short; then
            log_success "All tests passed!"
            return 0
        else
            log_error "Tests failed!"
            return 1
        fi
    fi
}

run_migrations() {
    local env=$1
    local config=$(get_env_config "$env")
    local data_dir=$(echo "$config" | cut -d: -f2)
    local db_path="$PROJECT_DIR/$data_dir/architect.db"

    log_info "Running database migrations for $env..."

    export DB_PATH="$db_path"
    python3 -c "
from migrations.manager import run_migrations
result = run_migrations('$db_path', backup=True)
print(f\"Applied {len(result['applied'])} migrations\")
for m in result['applied']:
    print(f\"  - {m}\")
"

    log_success "Migrations complete"
}

restart_service() {
    local env=$1
    local config=$(get_env_config "$env")
    local port=$(echo "$config" | cut -d: -f1)
    local data_dir=$(echo "$config" | cut -d: -f2)

    log_info "Restarting $env service on port $port..."

    # Kill existing process on port
    local pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi

    # Start new process
    export APP_ENV="$env"
    export PORT="$port"
    export DATA_DIR="$PROJECT_DIR/$data_dir"

    nohup python3 app.py > "/tmp/architect_${env}.log" 2>&1 &

    sleep 2

    # Health check
    if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
        log_success "$env service started successfully on port $port"
        return 0
    else
        log_error "Failed to start $env service"
        return 1
    fi
}

deploy() {
    local tag=$1
    local env=$2

    log_info "Starting deployment of '$tag' to '$env'..."

    local config=$(get_env_config "$env")
    if [ -z "$config" ]; then
        log_error "Unknown environment: $env"
        exit 1
    fi

    local port=$(echo "$config" | cut -d: -f1)

    # Check if we need to run tests
    local run_tests_flag=false
    if [ "$env" == "qa" ] || [ "$env" == "prod" ]; then
        run_tests_flag=true
    fi

    # For prod deployments, check if QA was deployed successfully
    if [ "$env" == "prod" ]; then
        log_info "Checking QA deployment status..."
        if ! curl -s "http://localhost:8081/health" | grep -q "healthy"; then
            log_error "QA environment is not healthy. Deploy to QA first."
            exit 1
        fi
    fi

    # Checkout the tag/ref
    if [ "$tag" != "HEAD" ]; then
        log_info "Checking out $tag..."
        git fetch --all --tags
        git checkout "$tag" 2>/dev/null || git checkout -b "deploy-$tag" "$tag"
    fi

    # Run tests if required
    if [ "$run_tests_flag" = true ]; then
        if ! run_tests; then
            log_error "Deployment aborted: tests failed"
            exit 1
        fi
    fi

    # Backup database
    backup_database "$env"

    # Run migrations
    run_migrations "$env"

    # Restart service
    restart_service "$env"

    # For production releases, merge to main
    if [ "$env" == "prod" ] && [[ "$tag" =~ ^release- ]]; then
        merge_to_main "$tag"
    fi

    log_success "Deployment complete!"
    echo ""
    echo "  Environment: $env"
    echo "  Tag: $tag"
    echo "  Port: $port"
    echo "  URL: http://localhost:$port"
}

merge_to_main() {
    local tag=$1
    local current_branch=$(git rev-parse --abbrev-ref HEAD)

    log_info "Merging $tag to main branch..."

    git checkout main 2>/dev/null || git checkout -b main
    git merge "$tag" -m "Merge $tag to main"

    log_success "Merged $tag to main"

    # Return to original branch
    git checkout "$current_branch" 2>/dev/null || git checkout dev
}

# Main
if [ $# -lt 1 ]; then
    usage
    exit 1
fi

TAG=$1
ENV=${2:-$(detect_environment "$TAG")}

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           Tag-Based Deployment                             ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Tag: $TAG"
echo "║  Environment: $ENV"
echo "║  Project: $PROJECT_DIR"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Confirm for production
if [ "$ENV" == "prod" ]; then
    log_warning "You are about to deploy to PRODUCTION!"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Deployment cancelled"
        exit 0
    fi
fi

deploy "$TAG" "$ENV"
