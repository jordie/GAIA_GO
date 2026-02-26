#!/bin/bash
#
# Feature Development Workflow Script
#
# This script manages the complete lifecycle of a feature:
#   1. Create/checkout feature branch
#   2. Assign task to Claude in tmux session
#   3. Monitor for completion
#   4. Merge to dev branch
#   5. Clean up feature branch
#   6. Update feature status in dashboard
#
# Usage:
#   ./feature_workflow.sh create <feature_id> <branch_name>
#   ./feature_workflow.sh assign <feature_id> <tmux_session>
#   ./feature_workflow.sh complete <feature_id>
#   ./feature_workflow.sh merge <feature_id>
#   ./feature_workflow.sh demo  # Run a full demo workflow
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:8085}"

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

# Cookie jar for session
COOKIE_JAR="/tmp/architect_workflow_cookies.txt"

# Login to get session
login() {
    local user=${DASHBOARD_USER:-architect}
    local pass=${DASHBOARD_PASSWORD:-peace5}

    curl -s -c "$COOKIE_JAR" -X POST \
        -d "username=${user}&password=${pass}" \
        "${DASHBOARD_URL}/login" > /dev/null

    if [ -f "$COOKIE_JAR" ]; then
        log_success "Logged in successfully"
        return 0
    else
        log_error "Failed to login"
        return 1
    fi
}

# API helper
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3

    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -b "$COOKIE_JAR" \
            -d "$data" \
            "${DASHBOARD_URL}/api${endpoint}"
    else
        curl -s -X "$method" \
            -b "$COOKIE_JAR" \
            "${DASHBOARD_URL}/api${endpoint}"
    fi
}

create_feature_branch() {
    local feature_id=$1
    local branch_name=${2:-"feature/${feature_id}"}

    log_info "Creating feature branch: $branch_name"

    # Make sure we're on dev
    git checkout dev
    git pull origin dev 2>/dev/null || true

    # Create feature branch
    git checkout -b "$branch_name" 2>/dev/null || git checkout "$branch_name"

    # Update feature in dashboard
    api_call PUT "/features/$feature_id" "{\"status\": \"in_progress\", \"branch_name\": \"$branch_name\"}"

    log_success "Feature branch created: $branch_name"
}

assign_to_tmux() {
    local feature_id=$1
    local session=${2:-"arch_dev"}

    log_info "Assigning feature $feature_id to tmux session: $session"

    # Get feature details
    local feature=$(api_call GET "/features?id=$feature_id")
    local name=$(echo "$feature" | python3 -c "import sys,json; f=json.load(sys.stdin); print(f[0]['name'] if f else 'Unknown')" 2>/dev/null || echo "Feature $feature_id")
    local desc=$(echo "$feature" | python3 -c "import sys,json; f=json.load(sys.stdin); print(f[0]['description'] if f else '')" 2>/dev/null || echo "")

    # Create task message
    local message="Work on feature: $name\n\n$desc\n\nWhen complete, commit your changes and let me know."

    # Send to tmux
    tmux send-keys -t "$session" "$message" Enter

    # Update feature
    api_call PUT "/features/$feature_id" "{\"tmux_session\": \"$session\", \"status\": \"in_progress\"}"

    log_success "Feature assigned to $session"
}

complete_feature() {
    local feature_id=$1
    local branch_name=${2:-"feature/${feature_id}"}

    log_info "Completing feature $feature_id"

    # Make sure we're on the feature branch
    git checkout "$branch_name" 2>/dev/null || {
        log_error "Could not checkout branch: $branch_name"
        return 1
    }

    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "Uncommitted changes detected, committing..."
        git add -A
        git commit -m "Feature $feature_id: Work in progress

🤖 Generated with Claude Code"
    fi

    # Update feature status
    api_call PUT "/features/$feature_id" "{\"status\": \"review\"}"

    log_success "Feature marked for review"
}

merge_feature() {
    local feature_id=$1
    local branch_name=${2:-"feature/${feature_id}"}

    log_info "Merging feature $feature_id to dev"

    # Checkout dev
    git checkout dev
    git pull origin dev 2>/dev/null || true

    # Merge feature branch
    git merge "$branch_name" -m "Merge feature $feature_id

🤖 Generated with Claude Code"

    # Delete feature branch
    git branch -d "$branch_name"

    # Update feature status
    api_call PUT "/features/$feature_id" "{\"status\": \"completed\", \"branch_name\": null}"

    log_success "Feature merged to dev and branch cleaned up"
}

run_demo() {
    log_info "Running feature workflow demo..."
    echo ""

    # Login first
    login || { log_error "Login failed"; return 1; }

    # Create a test feature via API
    log_info "Creating test feature..."
    local result=$(api_call POST "/features" '{
        "project_id": 38,
        "name": "Test Feature Workflow",
        "description": "This is a test feature to demonstrate the workflow automation.",
        "priority": 1
    }')

    local feature_id=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

    if [ -z "$feature_id" ]; then
        log_error "Failed to create feature"
        echo "$result"
        return 1
    fi

    log_success "Created feature ID: $feature_id"

    # Create feature branch
    local branch_name="feature/test-workflow-$feature_id"
    create_feature_branch "$feature_id" "$branch_name"

    # Simulate some work
    log_info "Simulating feature work..."
    echo "# Test Feature Work" > /tmp/test_feature_work.txt
    echo "Feature $feature_id demonstration" >> /tmp/test_feature_work.txt

    # If there are actual changes to make in the project, we could do:
    # echo "// Feature $feature_id test" >> some_file.js

    # For demo, we'll just touch a test file
    touch "$PROJECT_DIR/data/.feature_demo_$feature_id"
    git add -A
    git commit -m "Demo: Feature $feature_id test work

🤖 Generated with Claude Code" 2>/dev/null || log_info "No changes to commit"

    # Complete and merge
    log_info "Completing feature..."
    api_call PUT "/features/$feature_id" '{"status": "review"}'

    log_info "Merging to dev..."
    merge_feature "$feature_id" "$branch_name"

    # Clean up demo file
    rm -f "$PROJECT_DIR/data/.feature_demo_$feature_id"
    git add -A
    git commit -m "Clean up demo files" 2>/dev/null || true

    echo ""
    log_success "Demo complete! Feature $feature_id has been:"
    echo "  1. Created in dashboard"
    echo "  2. Branch created: $branch_name"
    echo "  3. Work simulated and committed"
    echo "  4. Merged to dev"
    echo "  5. Branch cleaned up"
    echo "  6. Status updated to completed"
    echo ""
    echo "View in dashboard: ${DASHBOARD_URL}/#focus/38/feature/${feature_id}"
}

usage() {
    echo "Feature Development Workflow"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create <feature_id> [branch_name]  Create feature branch"
    echo "  assign <feature_id> [tmux_session] Assign feature to Claude session"
    echo "  complete <feature_id> [branch]     Mark feature complete, commit changes"
    echo "  merge <feature_id> [branch]        Merge to dev, clean up branch"
    echo "  demo                               Run full demo workflow"
    echo ""
    echo "Environment Variables:"
    echo "  DASHBOARD_URL  Dashboard API URL (default: http://localhost:8085)"
    echo ""
    echo "Examples:"
    echo "  $0 create 42                       # Create feature/42 branch"
    echo "  $0 create 42 feature/new-ui        # Create custom branch name"
    echo "  $0 assign 42 arch_dev              # Assign to arch_dev tmux session"
    echo "  $0 complete 42                     # Complete feature 42"
    echo "  $0 merge 42                        # Merge feature 42 to dev"
    echo "  $0 demo                            # Run demo workflow"
}

# Main
case "${1:-}" in
    create)
        [ -z "$2" ] && { log_error "Feature ID required"; exit 1; }
        create_feature_branch "$2" "$3"
        ;;
    assign)
        [ -z "$2" ] && { log_error "Feature ID required"; exit 1; }
        assign_to_tmux "$2" "${3:-arch_dev}"
        ;;
    complete)
        [ -z "$2" ] && { log_error "Feature ID required"; exit 1; }
        complete_feature "$2" "${3:-feature/$2}"
        ;;
    merge)
        [ -z "$2" ] && { log_error "Feature ID required"; exit 1; }
        merge_feature "$2" "${3:-feature/$2}"
        ;;
    demo)
        run_demo
        ;;
    *)
        usage
        exit 1
        ;;
esac
