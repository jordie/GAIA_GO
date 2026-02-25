#!/bin/bash

#################################################################################
# Phase 7: Development Environment Git Workflow Script
#
# Provides utilities for managing multi-environment git operations:
# - Sync environments with main branch
# - Create and manage feature branches
# - Commit and push changes
# - Clean up merged branches
# - Show git status and history
#
# Usage:
#   ./dev_env_git_workflow.sh <command> <env> [options]
#
# Commands:
#   status <env>        - Show git status
#   sync <env>          - Sync with main branch
#   feature <env> <name>- Create feature branch
#   commit <env> <msg>  - Commit changes
#   push <env>          - Push to remote
#   pull <env>          - Pull from remote
#   clean <env>         - Clean merged branches
#   rebase <env>        - Rebase on main
#   diff <env> <file>   - Show file diff
#   log <env> [count]   - Show commit history
#   reset <env>         - Reset to HEAD (DESTRUCTIVE)
#   summary             - Show status of all environments
#
#################################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BASE_DIR="$(dirname "$PROJECT_ROOT")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Function to show help
show_help() {
    cat << 'EOF'
Development Environment Git Workflow Script

Usage:
    ./scripts/dev_env_git_workflow.sh <command> <env> [options]

Commands:
    status <env>              Show git status (branch, ahead/behind, dirty files)
    sync <env>                Sync environment with main branch
    feature <env> <name>      Create a new feature branch
    commit <env> <message>    Commit changes to current branch
    push <env>                Push environment branch to remote
    pull <env>                Pull latest from environment branch
    clean <env>               Clean merged branches
    rebase <env>              Rebase environment branch on main
    diff <env> <file>         Show diff for specific file
    log <env> [count]         Show commit log (default: 5)
    reset <env>               Reset to last committed state (DESTRUCTIVE)

Arguments:
    <env>       Environment name (dev1-dev5)
    <name>      Feature branch name
    <message>   Commit message
    <file>      File path to diff
    <count>     Number of commits to show

Examples:
    ./scripts/dev_env_git_workflow.sh status dev1
    ./scripts/dev_env_git_workflow.sh sync dev2
    ./scripts/dev_env_git_workflow.sh feature dev1 add-cache-layer
    ./scripts/dev_env_git_workflow.sh commit dev1 "Implement caching"
    ./scripts/dev_env_git_workflow.sh push dev1
    ./scripts/dev_env_git_workflow.sh log dev1 10
EOF
}

# Function to validate environment name
validate_env() {
    local env=$1
    if ! [[ $env =~ ^dev[1-5]$ ]]; then
        log_error "Invalid environment: $env (must be dev1-dev5)"
        return 1
    fi
    return 0
}

# Function to get environment path
get_env_path() {
    local env=$1
    echo "$BASE_DIR/architect-$env"
}

# Function to show git status
cmd_status() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    log_info "Git status for $env"
    echo ""

    # Current branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "Branch: $BRANCH"

    # Ahead/behind
    TRACKING=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "")
    if [ -n "$TRACKING" ]; then
        AHEAD_BEHIND=$(git rev-list --left-right --count @{u}...HEAD 2>/dev/null || echo "0 0")
        BEHIND=$(echo $AHEAD_BEHIND | cut -d' ' -f1)
        AHEAD=$(echo $AHEAD_BEHIND | cut -d' ' -f2)
        echo "Status: ahead $AHEAD, behind $BEHIND commits"
    fi

    # Dirty status
    if [ -z "$(git status --porcelain)" ]; then
        echo "Working tree: clean"
    else
        echo "Working tree: dirty"
        DIRTY_COUNT=$(git status --porcelain | wc -l)
        echo "  Modified files: $DIRTY_COUNT"
        git status --short | head -5
        if [ $(git status --porcelain | wc -l) -gt 5 ]; then
            echo "  ... and $((DIRTY_COUNT - 5)) more"
        fi
    fi

    echo ""
    log_success "Status check complete"
}

# Function to sync with main
cmd_sync() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    log_info "Syncing $env with main..."

    # Fetch latest
    git fetch origin
    log_success "Fetched latest from origin"

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

    if [ "$CURRENT_BRANCH" = "main" ]; then
        log_warn "Already on main branch, pulling latest"
        git pull origin main
    else
        log_info "Merging main into $CURRENT_BRANCH..."
        git merge origin/main --no-edit || {
            log_error "Merge conflict detected!"
            echo "Resolve conflicts manually, then run:"
            echo "  cd $(pwd)"
            echo "  git add ."
            echo "  git commit -m 'Merge main into $CURRENT_BRANCH'"
            return 1
        }
    fi

    log_success "Sync complete"
}

# Function to create feature branch
cmd_feature() {
    local env=$1
    local feature_name=$2

    if [ -z "$feature_name" ]; then
        log_error "Feature name required"
        return 1
    fi

    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    # Create branch name with date
    DATE=$(date +%m%d)
    BRANCH_NAME="feature/$feature_name-$DATE"

    log_info "Creating feature branch: $BRANCH_NAME"

    git checkout -b "$BRANCH_NAME"
    git push -u origin "$BRANCH_NAME"

    log_success "Feature branch created: $BRANCH_NAME"
    echo "You're now on: $(git rev-parse --abbrev-ref HEAD)"
}

# Function to commit changes
cmd_commit() {
    local env=$1
    local message=$2

    if [ -z "$message" ]; then
        log_error "Commit message required"
        return 1
    fi

    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    log_info "Committing to $env..."

    # Stage all changes
    git add -A
    STAGED=$(git status --porcelain | wc -l)

    if [ $STAGED -eq 0 ]; then
        log_warn "No changes to commit"
        return 0
    fi

    echo "Staging $STAGED changes"

    # Commit with timestamp
    TIMESTAMP=$(date '+%H:%M:%S')
    FULL_MESSAGE="$message [$TIMESTAMP]"

    git commit -m "$FULL_MESSAGE"

    log_success "Committed: $FULL_MESSAGE"
}

# Function to push changes
cmd_push() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log_info "Pushing $CURRENT_BRANCH to remote..."

    git push -u origin "$CURRENT_BRANCH"

    log_success "Pushed to origin/$CURRENT_BRANCH"
}

# Function to pull changes
cmd_pull() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log_info "Pulling $CURRENT_BRANCH from remote..."

    git pull origin "$CURRENT_BRANCH"

    log_success "Pulled latest from origin/$CURRENT_BRANCH"
}

# Function to show commit log
cmd_log() {
    local env=$1
    local count=${2:-5}

    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log_info "Recent commits on $BRANCH (showing $count)"
    echo ""

    git log --oneline -n "$count"

    echo ""
    log_success "Log displayed"
}

# Function to clean merged branches
cmd_clean() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    log_info "Cleaning merged branches in $env..."

    git fetch origin

    # Delete local merged branches
    git branch -vv | grep '\[origin.*gone\]' | awk '{print $1}' | xargs -r git branch -D || true

    log_success "Cleanup complete"
}

# Function to show diff
cmd_diff() {
    local env=$1
    local file=$2

    if [ -z "$file" ]; then
        log_error "File path required"
        return 1
    fi

    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    log_info "Diff for $file"
    echo ""

    git diff "$file"
}

# Function to rebase on main
cmd_rebase() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    cd "$env_path"

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

    if [ "$CURRENT_BRANCH" = "main" ]; then
        log_warn "Already on main branch"
        return 1
    fi

    log_info "Rebasing $CURRENT_BRANCH on main..."

    git fetch origin
    git rebase origin/main || {
        log_error "Rebase conflict detected!"
        echo "Resolve conflicts, then continue with:"
        echo "  cd $(pwd)"
        echo "  git rebase --continue"
        return 1
    }

    log_success "Rebase complete"
}

# Function to reset changes
cmd_reset() {
    local env=$1
    validate_env "$env" || return 1

    local env_path=$(get_env_path "$env")
    if [ ! -d "$env_path" ]; then
        log_error "Directory not found: $env_path"
        return 1
    fi

    log_warn "RESET WILL DISCARD ALL UNCOMMITTED CHANGES!"
    read -p "Are you sure? Type 'yes' to confirm: " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Reset cancelled"
        return 0
    fi

    cd "$env_path"

    log_info "Resetting $env to HEAD..."
    git reset --hard HEAD

    log_success "Reset complete"
}

# Function to show summary of all environments
cmd_summary() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Development Environment Git Summary                          ║${NC}"
    echo -e "${BLUE}║  $(date '+%Y-%m-%d %H:%M:%S')                                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    for i in {1..5}; do
        env="dev$i"
        env_path=$(get_env_path "$env")

        if [ ! -d "$env_path" ]; then
            echo -e "${CYAN}${env}${NC}: ${RED}NOT CREATED${NC}"
            continue
        fi

        cd "$env_path" || continue

        # Get branch info
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

        # Get dirty status
        dirty_count=$(git status --porcelain 2>/dev/null | wc -l || echo "0")
        dirty_status=""
        if [ "$dirty_count" -gt 0 ]; then
            dirty_status=" ${YELLOW}dirty ($dirty_count files)${NC}"
        else
            dirty_status=" ${GREEN}clean${NC}"
        fi

        # Get ahead/behind
        ahead_behind=$(git rev-list --left-right --count @{u}...HEAD 2>/dev/null || echo "0 0")
        behind=$(echo "$ahead_behind" | cut -d' ' -f1)
        ahead=$(echo "$ahead_behind" | cut -d' ' -f2)

        sync_status=""
        if [ "$behind" -gt 0 ] || [ "$ahead" -gt 0 ]; then
            sync_status=" ${YELLOW}ahead $ahead behind $behind${NC}"
        else
            sync_status=" ${GREEN}in sync${NC}"
        fi

        echo -e "${CYAN}${env}${NC}: ${MAGENTA}${branch}${NC}$dirty_status$sync_status"
    done

    echo ""
}

# Main script
if [ $# -lt 1 ]; then
    show_help
    exit 1
fi

COMMAND=$1
shift

case "$COMMAND" in
    status) cmd_status "$@" ;;
    sync) cmd_sync "$@" ;;
    feature) cmd_feature "$@" ;;
    commit) cmd_commit "$@" ;;
    push) cmd_push "$@" ;;
    pull) cmd_pull "$@" ;;
    log) cmd_log "$@" ;;
    clean) cmd_clean "$@" ;;
    diff) cmd_diff "$@" ;;
    rebase) cmd_rebase "$@" ;;
    reset) cmd_reset "$@" ;;
    summary) cmd_summary ;;
    help) show_help ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
