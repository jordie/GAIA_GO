#!/bin/bash

#################################################################################
# Phase 6: Session Startup Script
#
# Starts all 15 new sessions for the multi-environment orchestration system:
# - 5 dev environment workers (dev1_worker through dev5_worker)
# - 3 PR review sessions (pr_review1, pr_review2, pr_review3)
# - 4 PR implementation sessions (pr_impl1 through pr_impl4)
# - 3 PR integration sessions (pr_integ1 through pr_integ3)
#
# Usage:
#   ./start_all_sessions.sh              # Start all sessions
#   ./start_all_sessions.sh dev          # Start only dev workers
#   ./start_all_sessions.sh pr-review    # Start only PR review sessions
#   ./start_all_sessions.sh pr-impl      # Start only PR implementation
#   ./start_all_sessions.sh pr-integ     # Start only PR integration
#   ./start_all_sessions.sh status       # Check session status
#   ./start_all_sessions.sh stop         # Stop all sessions
#   ./start_all_sessions.sh stop-all     # Force kill all sessions
#################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_REPO="$BASE_DIR"

# Log functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check if tmux is installed
check_tmux() {
    if ! command -v tmux &> /dev/null; then
        log_error "tmux not found. Please install tmux first."
        exit 1
    fi
}

# Start dev environment worker
start_dev_worker() {
    local worker_num=$1
    local worker_name="dev${worker_num}_worker"
    local env_dir="$BASE_DIR/architect-dev${worker_num}"

    if [ ! -d "$env_dir" ]; then
        log_warning "Dev environment directory not found: $env_dir"
        return 1
    fi

    # Check if session already exists
    if tmux has-session -t "$worker_name" 2>/dev/null; then
        log_warning "Session already exists: $worker_name"
        return 0
    fi

    log_info "Starting dev worker: $worker_name"

    # Create new session
    tmux new-session -d -s "$worker_name" -c "$env_dir"

    # Send startup command (using gaia with ollama provider)
    tmux send-keys -t "$worker_name" "python3 gaia.py --provider ollama --worker" Enter

    sleep 1
    log_success "Started: $worker_name"
}

# Start PR review session
start_pr_review() {
    local review_num=$1
    local session_name="pr_review${review_num}"
    local provider="claude"

    # pr_review3 uses ollama instead of claude
    if [ "$review_num" = "3" ]; then
        provider="ollama"
    fi

    if tmux has-session -t "$session_name" 2>/dev/null; then
        log_warning "Session already exists: $session_name"
        return 0
    fi

    log_info "Starting PR review session: $session_name (provider: $provider)"

    # Create new session in main repo
    tmux new-session -d -s "$session_name" -c "$MAIN_REPO"

    # Send startup command
    if [ "$provider" = "claude" ]; then
        tmux send-keys -t "$session_name" "python3 gaia.py --provider claude" Enter
    else
        tmux send-keys -t "$session_name" "python3 gaia.py --provider ollama" Enter
    fi

    sleep 1
    log_success "Started: $session_name ($provider)"
}

# Start PR implementation session
start_pr_impl() {
    local impl_num=$1
    local session_name="pr_impl${impl_num}"
    local provider="codex"

    # pr_impl3 and pr_impl4 use ollama instead of codex
    if [ "$impl_num" -ge "3" ]; then
        provider="ollama"
    fi

    if tmux has-session -t "$session_name" 2>/dev/null; then
        log_warning "Session already exists: $session_name"
        return 0
    fi

    log_info "Starting PR implementation: $session_name (provider: $provider)"

    # Create new session
    tmux new-session -d -s "$session_name" -c "$MAIN_REPO"

    # Send startup command
    if [ "$provider" = "codex" ]; then
        tmux send-keys -t "$session_name" "python3 codex_chat.py --worker" Enter
    else
        tmux send-keys -t "$session_name" "python3 gaia.py --provider ollama" Enter
    fi

    sleep 1
    log_success "Started: $session_name ($provider)"
}

# Start PR integration session
start_pr_integ() {
    local integ_num=$1
    local session_name="pr_integ${integ_num}"
    local provider="ollama"

    if tmux has-session -t "$session_name" 2>/dev/null; then
        log_warning "Session already exists: $session_name"
        return 0
    fi

    log_info "Starting PR integration: $session_name (provider: $provider)"

    # Create new session
    tmux new-session -d -s "$session_name" -c "$MAIN_REPO"

    # Send startup command
    tmux send-keys -t "$session_name" "python3 gaia.py --provider ollama --worker" Enter

    sleep 1
    log_success "Started: $session_name ($provider)"
}

# Show status of all sessions
show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Session Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Dev workers
    echo -e "${CYAN}Dev Environment Workers:${NC}"
    for i in {1..5}; do
        if tmux has-session -t "dev${i}_worker" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} dev${i}_worker (running)"
        else
            echo -e "  ${RED}✗${NC} dev${i}_worker (stopped)"
        fi
    done

    echo ""
    echo -e "${CYAN}PR Review Group (PRR):${NC}"
    for i in {1..3}; do
        if tmux has-session -t "pr_review${i}" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} pr_review${i} (running)"
        else
            echo -e "  ${RED}✗${NC} pr_review${i} (stopped)"
        fi
    done

    echo ""
    echo -e "${CYAN}PR Implementation Group (PRI):${NC}"
    for i in {1..4}; do
        if tmux has-session -t "pr_impl${i}" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} pr_impl${i} (running)"
        else
            echo -e "  ${RED}✗${NC} pr_impl${i} (stopped)"
        fi
    done

    echo ""
    echo -e "${CYAN}PR Integration Group (PRIG):${NC}"
    for i in {1..3}; do
        if tmux has-session -t "pr_integ${i}" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} pr_integ${i} (running)"
        else
            echo -e "  ${RED}✗${NC} pr_integ${i} (stopped)"
        fi
    done

    echo ""
    echo "Total sessions:"
    tmux list-sessions 2>/dev/null | wc -l
    echo ""
}

# Stop all sessions gracefully
stop_sessions() {
    echo ""
    log_info "Stopping all multi-environment sessions..."

    for i in {1..5}; do
        if tmux has-session -t "dev${i}_worker" 2>/dev/null; then
            log_info "Stopping dev${i}_worker..."
            tmux send-keys -t "dev${i}_worker" "C-c"
            sleep 1
            tmux kill-session -t "dev${i}_worker" 2>/dev/null || true
        fi
    done

    for i in {1..3}; do
        if tmux has-session -t "pr_review${i}" 2>/dev/null; then
            tmux kill-session -t "pr_review${i}" 2>/dev/null || true
        fi
    done

    for i in {1..4}; do
        if tmux has-session -t "pr_impl${i}" 2>/dev/null; then
            tmux kill-session -t "pr_impl${i}" 2>/dev/null || true
        fi
    done

    for i in {1..3}; do
        if tmux has-session -t "pr_integ${i}" 2>/dev/null; then
            tmux kill-session -t "pr_integ${i}" 2>/dev/null || true
        fi
    done

    log_success "All sessions stopped"
    echo ""
}

# Start all sessions
start_all() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Phase 6: Session Startup                                          ║${NC}"
    echo -e "${BLUE}║  Starting 15 new sessions for multi-environment orchestration      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_tmux

    log_info "Starting 5 dev environment workers..."
    for i in {1..5}; do
        start_dev_worker $i || true
    done

    echo ""
    log_info "Starting 3 PR review sessions (PRR)..."
    for i in {1..3}; do
        start_pr_review $i || true
    done

    echo ""
    log_info "Starting 4 PR implementation sessions (PRI)..."
    for i in {1..4}; do
        start_pr_impl $i || true
    done

    echo ""
    log_info "Starting 3 PR integration sessions (PRIG)..."
    for i in {1..3}; do
        start_pr_integ $i || true
    done

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ Phase 6: Session Startup Complete                              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    show_status
}

# Main
main() {
    case "${1:-all}" in
        all)
            start_all
            ;;
        dev)
            log_info "Starting dev environment workers only..."
            for i in {1..5}; do
                start_dev_worker $i || true
            done
            show_status
            ;;
        pr-review)
            log_info "Starting PR review sessions only..."
            for i in {1..3}; do
                start_pr_review $i || true
            done
            show_status
            ;;
        pr-impl)
            log_info "Starting PR implementation sessions only..."
            for i in {1..4}; do
                start_pr_impl $i || true
            done
            show_status
            ;;
        pr-integ)
            log_info "Starting PR integration sessions only..."
            for i in {1..3}; do
                start_pr_integ $i || true
            done
            show_status
            ;;
        status)
            show_status
            ;;
        stop)
            stop_sessions
            show_status
            ;;
        stop-all)
            log_warning "Force stopping all tmux sessions..."
            tmux kill-server
            log_success "All tmux sessions killed"
            ;;
        *)
            echo "Usage: $0 [all|dev|pr-review|pr-impl|pr-integ|status|stop|stop-all]"
            exit 1
            ;;
    esac
}

main "$@"
