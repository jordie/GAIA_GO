#!/bin/bash

# GAIA_GO Project Session Setup Script
# Creates tmux sessions for 4 concurrent projects following the naming convention:
# {project_slug}_{purpose}_{environment}

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Usage information
usage() {
    cat << EOF
${BLUE}GAIA_GO Project Session Setup${NC}

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    setup       Create all project sessions (default)
    cleanup     Kill all project sessions
    list        List all project sessions
    help        Show this help message

Options:
    --project   Create sessions for specific project only
                Options: basic_edu, rando, architect, gaia_improvements

Examples:
    $0 setup                              # Create all sessions
    $0 setup --project basic_edu          # Create only basic_edu sessions
    $0 cleanup                            # Kill all sessions
    $0 list                               # List all sessions

EOF
    exit 0
}

# Function to create a tmux session
create_session() {
    local session_name=$1
    local window_name=${2:-"main"}

    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo -e "${YELLOW}[SKIP]${NC} Session '$session_name' already exists"
        return 0
    fi

    tmux new-session -d -s "$session_name" -n "$window_name"
    echo -e "${GREEN}[CREATED]${NC} Session '$session_name'"
}

# Function to kill a tmux session
kill_session() {
    local session_name=$1

    if ! tmux has-session -t "$session_name" 2>/dev/null; then
        echo -e "${YELLOW}[SKIP]${NC} Session '$session_name' does not exist"
        return 0
    fi

    tmux kill-session -t "$session_name"
    echo -e "${GREEN}[KILLED]${NC} Session '$session_name'"
}

# Function to setup basic_edu project sessions
setup_basic_edu() {
    echo -e "${BLUE}Setting up basic_edu project...${NC}"
    create_session "basic_edu_server_dev" "server"
    create_session "basic_edu_tests_dev" "tests"
    create_session "basic_edu_editor_dev" "editor"
    echo -e "${GREEN}✓ basic_edu project setup complete${NC}\n"
}

# Function to setup rando project sessions
setup_rando() {
    echo -e "${BLUE}Setting up rando project...${NC}"
    create_session "rando_shell_dev" "shell"
    create_session "rando_experiment_dev" "experiment"
    echo -e "${GREEN}✓ rando project setup complete${NC}\n"
}

# Function to setup architect project sessions
setup_architect() {
    echo -e "${BLUE}Setting up architect project...${NC}"
    create_session "architect_dashboard_prod" "dashboard"
    create_session "architect_api_dev" "api"
    echo -e "${GREEN}✓ architect project setup complete${NC}\n"
}

# Function to setup gaia_improvements project sessions
setup_gaia_improvements() {
    echo -e "${BLUE}Setting up gaia_improvements project...${NC}"
    create_session "gaia_improvements_build_dev" "build"
    create_session "gaia_improvements_tests_staging" "tests"
    echo -e "${GREEN}✓ gaia_improvements project setup complete${NC}\n"
}

# Function to setup worker sessions
setup_workers() {
    echo -e "${BLUE}Setting up worker sessions...${NC}"
    create_session "worker_queue_1" "queue"
    echo -e "${GREEN}✓ worker sessions setup complete${NC}\n"
}

# Function to setup all sessions
setup_all() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}GAIA_GO Project Sessions Setup${NC}"
    echo -e "${BLUE}========================================${NC}\n"

    setup_basic_edu
    setup_rando
    setup_architect
    setup_gaia_improvements
    setup_workers

    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}All project sessions created successfully!${NC}"
    echo -e "${BLUE}========================================${NC}\n"

    echo "Listing all sessions:"
    tmux list-sessions || true
}

# Function to cleanup all sessions
cleanup_all() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Cleaning up project sessions...${NC}"
    echo -e "${BLUE}========================================${NC}\n"

    # Kill all project-related sessions
    kill_session "basic_edu_server_dev"
    kill_session "basic_edu_tests_dev"
    kill_session "basic_edu_editor_dev"
    kill_session "rando_shell_dev"
    kill_session "rando_experiment_dev"
    kill_session "architect_dashboard_prod"
    kill_session "architect_api_dev"
    kill_session "gaia_improvements_build_dev"
    kill_session "gaia_improvements_tests_staging"
    kill_session "worker_queue_1"

    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}All project sessions cleaned up${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to list all project sessions
list_sessions() {
    echo -e "${BLUE}Project Sessions:${NC}\n"

    # Get all tmux sessions and filter for project sessions
    tmux list-sessions -F "#{session_name}" 2>/dev/null | while read -r session; do
        if [[ "$session" =~ ^(basic_edu|rando|architect|gaia_improvements|worker)_ ]]; then
            # Count windows in session
            window_count=$(tmux list-windows -t "$session" -F "#{window_index}" 2>/dev/null | wc -l)

            # Check if attached
            attached=$(tmux list-sessions -F "#{session_name}:#{session_attached}" 2>/dev/null | grep "^$session:" | cut -d: -f2)
            attach_status=$([ "$attached" -eq 1 ] && echo "attached" || echo "detached")

            printf "  ${GREEN}%-45s${NC} windows: ${YELLOW}%d${NC}  status: ${BLUE}%s${NC}\n" \
                "$session" "$window_count" "$attach_status"
        fi
    done

    echo ""
}

# Main script logic
main() {
    local command="${1:-setup}"
    local project="${3:-}"

    case "$command" in
        help|-h|--help)
            usage
            ;;
        setup)
            if [ -n "$project" ] && [ "$3" = "--project" ]; then
                project="$4"
            fi

            if [ -z "$project" ]; then
                setup_all
            else
                case "$project" in
                    basic_edu)
                        setup_basic_edu
                        ;;
                    rando)
                        setup_rando
                        ;;
                    architect)
                        setup_architect
                        ;;
                    gaia_improvements)
                        setup_gaia_improvements
                        ;;
                    *)
                        echo -e "${RED}Error: Unknown project '$project'${NC}"
                        echo "Valid projects: basic_edu, rando, architect, gaia_improvements"
                        exit 1
                        ;;
                esac
            fi
            ;;
        cleanup|clean|delete)
            cleanup_all
            ;;
        list|ls)
            list_sessions
            ;;
        *)
            echo -e "${RED}Error: Unknown command '$command'${NC}\n"
            usage
            ;;
    esac
}

# Run main function with all arguments
main "$@"
