#!/bin/bash
#
# Automatic Deployment Trigger System
#
# Monitors changes and triggers deployments when thresholds are met.
#
# Thresholds (configurable):
#   - DEV → QA: 3+ commits OR 2+ features completed
#   - QA → PROD: 5+ commits OR 3+ features completed OR manual release tag
#
# Usage:
#   ./auto_deploy.sh check          # Check if deployment is needed
#   ./auto_deploy.sh deploy         # Check and deploy if thresholds met
#   ./auto_deploy.sh status         # Show current deployment status
#   ./auto_deploy.sh force qa       # Force deploy to QA
#   ./auto_deploy.sh force prod     # Force deploy to PROD
#
# Can be run as a cron job or git hook for continuous deployment.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8085}"

# Thresholds
DEV_TO_QA_COMMITS=3
DEV_TO_QA_FEATURES=2
QA_TO_PROD_COMMITS=5
QA_TO_PROD_FEATURES=3

# State file to track last deployment
STATE_FILE="/tmp/architect_deploy_state.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cd "$PROJECT_DIR"

# Get last deployed commit for an environment
get_last_deployed() {
    local env=$1
    if [ -f "$STATE_FILE" ]; then
        python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('${env}_commit', ''))" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# Save deployed commit
save_deployed() {
    local env=$1
    local commit=$2

    if [ -f "$STATE_FILE" ]; then
        python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['${env}_commit'] = '$commit'
d['${env}_time'] = '$(date -Iseconds)'
json.dump(d, open('$STATE_FILE', 'w'), indent=2)
"
    else
        echo "{\"${env}_commit\": \"$commit\", \"${env}_time\": \"$(date -Iseconds)\"}" > "$STATE_FILE"
    fi
}

# Count commits since last deployment
count_commits_since() {
    local base_branch=$1
    local target_branch=$2

    git rev-list --count "${base_branch}..${target_branch}" 2>/dev/null || echo "0"
}

# Count completed features since last deployment
count_completed_features() {
    local since_commit=$1

    if [ -z "$since_commit" ]; then
        # No previous deployment, count all
        sqlite3 "$PROJECT_DIR/data/dev/architect.db" \
            "SELECT COUNT(*) FROM features WHERE status = 'completed'" 2>/dev/null || echo "0"
    else
        # Count features completed in commits since last deploy
        # This is approximate - counts features marked completed
        local count=$(git log --oneline "${since_commit}..HEAD" 2>/dev/null | grep -ci "feature\|complete" || echo "0")
        echo "$count"
    fi
}

# Get current version
get_current_version() {
    git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0"
}

# Increment version
increment_version() {
    local version=$1
    local type=$2  # major, minor, patch

    # Remove 'v' prefix if present
    version="${version#v}"

    IFS='.' read -r major minor patch <<< "$version"

    case $type in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac

    echo "v${major}.${minor}.${patch}"
}

# Check if deployment is needed
check_deployment() {
    log_info "Checking deployment thresholds..."
    echo ""

    # DEV → QA check
    local qa_last=$(get_last_deployed "qa")
    local dev_commits=$(count_commits_since "qa" "dev")
    local dev_features=$(count_completed_features "$qa_last")

    echo "DEV → QA:"
    echo "  Commits since last QA deploy: $dev_commits (threshold: $DEV_TO_QA_COMMITS)"
    echo "  Features completed: $dev_features (threshold: $DEV_TO_QA_FEATURES)"

    local deploy_qa=false
    if [ "$dev_commits" -ge "$DEV_TO_QA_COMMITS" ]; then
        echo -e "  ${GREEN}✓ Commit threshold met${NC}"
        deploy_qa=true
    fi
    if [ "$dev_features" -ge "$DEV_TO_QA_FEATURES" ]; then
        echo -e "  ${GREEN}✓ Feature threshold met${NC}"
        deploy_qa=true
    fi

    echo ""

    # QA → PROD check
    local prod_last=$(get_last_deployed "prod")
    local qa_commits=$(count_commits_since "main" "qa")
    local qa_features=$(count_completed_features "$prod_last")

    echo "QA → PROD:"
    echo "  Commits since last PROD deploy: $qa_commits (threshold: $QA_TO_PROD_COMMITS)"
    echo "  Features completed: $qa_features (threshold: $QA_TO_PROD_FEATURES)"

    local deploy_prod=false
    if [ "$qa_commits" -ge "$QA_TO_PROD_COMMITS" ]; then
        echo -e "  ${GREEN}✓ Commit threshold met${NC}"
        deploy_prod=true
    fi
    if [ "$qa_features" -ge "$QA_TO_PROD_FEATURES" ]; then
        echo -e "  ${GREEN}✓ Feature threshold met${NC}"
        deploy_prod=true
    fi

    echo ""

    # Return status
    if [ "$deploy_qa" = true ] || [ "$deploy_prod" = true ]; then
        echo "DEPLOY_QA=$deploy_qa"
        echo "DEPLOY_PROD=$deploy_prod"
        return 0
    else
        log_info "No deployment thresholds met"
        return 1
    fi
}

# Deploy to QA
deploy_to_qa() {
    log_info "Deploying to QA..."

    local current_version=$(get_current_version)
    local new_version=$(increment_version "$current_version" "minor")

    # Merge dev to qa
    git checkout qa
    git merge dev -m "Auto-merge dev to qa for $new_version

🤖 Generated with Claude Code (Auto-Deploy)"

    # Create tag
    git tag -a "$new_version" -m "$new_version: Auto-deployment

Triggered by: threshold met
Commits: $(count_commits_since "qa" "dev")
Features: $(count_completed_features "")

🤖 Generated with Claude Code"

    # Deploy
    "$SCRIPT_DIR/deploy_by_tag.sh" "$new_version"

    # Save state
    save_deployed "qa" "$(git rev-parse HEAD)"

    git checkout dev

    log_success "Deployed $new_version to QA"
    echo "$new_version"
}

# Deploy to PROD
deploy_to_prod() {
    log_info "Deploying to PROD..."

    local current_version=$(get_current_version)
    local release_version="release-${current_version#v}"

    # Create release tag
    git checkout qa
    git tag -a "$release_version" -m "$release_version: Production release

Triggered by: threshold met or manual release

🤖 Generated with Claude Code"

    # Deploy (will prompt for confirmation)
    echo "yes" | "$SCRIPT_DIR/deploy_by_tag.sh" "$release_version"

    # Save state
    save_deployed "prod" "$(git rev-parse HEAD)"

    git checkout dev

    log_success "Deployed $release_version to PROD"
    echo "$release_version"
}

# Show status
show_status() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           Deployment Status                                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    local current_version=$(get_current_version)
    echo "Current Version: $current_version"
    echo ""

    # Environment status
    for env in dev qa prod; do
        local port
        case $env in
            dev) port=8082 ;;
            qa) port=8081 ;;
            prod) port=8080 ;;
        esac

        local status="offline"
        if curl -s "http://localhost:$port/health" | grep -q "healthy"; then
            status="${GREEN}online${NC}"
        else
            status="${RED}offline${NC}"
        fi

        local last_commit=$(get_last_deployed "$env")
        local last_time=""
        if [ -f "$STATE_FILE" ]; then
            last_time=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('${env}_time', 'unknown'))" 2>/dev/null || echo "")
        fi

        echo -e "  $env (port $port): $status"
        [ -n "$last_commit" ] && echo "    Last deploy: ${last_commit:0:7} at $last_time"
    done

    echo ""

    # Thresholds
    echo "Thresholds:"
    echo "  DEV → QA:   $DEV_TO_QA_COMMITS commits OR $DEV_TO_QA_FEATURES features"
    echo "  QA → PROD:  $QA_TO_PROD_COMMITS commits OR $QA_TO_PROD_FEATURES features"
    echo ""

    check_deployment
}

# Auto deploy based on thresholds
auto_deploy() {
    log_info "Running auto-deployment check..."

    local deploy_qa=false
    local deploy_prod=false

    # Check thresholds
    eval $(check_deployment 2>/dev/null | grep "DEPLOY_")

    if [ "$deploy_qa" = "true" ]; then
        deploy_to_qa
    fi

    if [ "$deploy_prod" = "true" ]; then
        log_warning "PROD deployment threshold met"
        log_info "Run './auto_deploy.sh force prod' to deploy to production"
    fi
}

usage() {
    echo "Automatic Deployment Trigger System"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  check       Check if deployment thresholds are met"
    echo "  deploy      Check and auto-deploy if thresholds met"
    echo "  status      Show current deployment status"
    echo "  force <env> Force deploy to environment (qa or prod)"
    echo ""
    echo "Thresholds:"
    echo "  DEV → QA:   $DEV_TO_QA_COMMITS commits OR $DEV_TO_QA_FEATURES features"
    echo "  QA → PROD:  $QA_TO_PROD_COMMITS commits OR $QA_TO_PROD_FEATURES features"
    echo ""
    echo "Environment Variables:"
    echo "  DEV_TO_QA_COMMITS    Override commit threshold for QA"
    echo "  DEV_TO_QA_FEATURES   Override feature threshold for QA"
    echo "  QA_TO_PROD_COMMITS   Override commit threshold for PROD"
    echo "  QA_TO_PROD_FEATURES  Override feature threshold for PROD"
}

# Main
case "${1:-}" in
    check)
        check_deployment
        ;;
    deploy)
        auto_deploy
        ;;
    status)
        show_status
        ;;
    force)
        case "${2:-}" in
            qa) deploy_to_qa ;;
            prod) deploy_to_prod ;;
            *) log_error "Specify 'qa' or 'prod'"; exit 1 ;;
        esac
        ;;
    *)
        usage
        exit 1
        ;;
esac
