#!/bin/bash

# TMUX Session Manager
# Manages all tmux sessions and jobs

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display menu
show_menu() {
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${GREEN}        TMUX Session Manager${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo "1) List all tmux sessions"
    echo "2) Create new tmux session"
    echo "3) Attach to tmux session"
    echo "4) Kill tmux session"
    echo "5) Kill all tmux sessions"
    echo "6) Send command to tmux session"
    echo "7) Show session details"
    echo "8) Rename tmux session"
    echo "9) List all panes in session"
    echo "10) Exit"
    echo -e "${BLUE}===========================================${NC}"
}

# List all tmux sessions
list_sessions() {
    echo -e "${YELLOW}Current tmux sessions:${NC}"
    tmux list-sessions 2>/dev/null || echo "No tmux sessions running"
}

# Create new tmux session
create_session() {
    read -p "Enter session name: " session_name
    if [ -z "$session_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    tmux new-session -d -s "$session_name"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Session '$session_name' created successfully${NC}"
    else
        echo -e "${RED}Failed to create session${NC}"
    fi
}

# Attach to tmux session
attach_session() {
    list_sessions
    echo ""
    read -p "Enter session name to attach: " session_name
    if [ -z "$session_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    tmux attach-session -t "$session_name"
}

# Kill tmux session
kill_session() {
    list_sessions
    echo ""
    read -p "Enter session name to kill: " session_name
    if [ -z "$session_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    read -p "Are you sure you want to kill session '$session_name'? (y/n): " confirm
    if [[ $confirm == [yY] ]]; then
        tmux kill-session -t "$session_name"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Session '$session_name' killed successfully${NC}"
        else
            echo -e "${RED}Failed to kill session${NC}"
        fi
    fi
}

# Kill all tmux sessions
kill_all_sessions() {
    read -p "Are you sure you want to kill ALL tmux sessions? (y/n): " confirm
    if [[ $confirm == [yY] ]]; then
        tmux kill-server 2>/dev/null
        echo -e "${GREEN}All tmux sessions killed${NC}"
    fi
}

# Send command to tmux session
send_command() {
    list_sessions
    echo ""
    read -p "Enter session name: " session_name
    if [ -z "$session_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    read -p "Enter command to send: " command
    if [ -z "$command" ]; then
        echo -e "${RED}Command cannot be empty${NC}"
        return
    fi

    tmux send-keys -t "$session_name" "$command" Enter
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Command sent to session '$session_name'${NC}"
    else
        echo -e "${RED}Failed to send command${NC}"
    fi
}

# Show session details
show_session_details() {
    list_sessions
    echo ""
    read -p "Enter session name for details: " session_name
    if [ -z "$session_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    echo -e "${YELLOW}Windows in session '$session_name':${NC}"
    tmux list-windows -t "$session_name" 2>/dev/null || echo "Session not found"

    echo -e "${YELLOW}Panes in session '$session_name':${NC}"
    tmux list-panes -t "$session_name" 2>/dev/null || echo "Session not found"
}

# Rename tmux session
rename_session() {
    list_sessions
    echo ""
    read -p "Enter current session name: " old_name
    if [ -z "$old_name" ]; then
        echo -e "${RED}Session name cannot be empty${NC}"
        return
    fi

    read -p "Enter new session name: " new_name
    if [ -z "$new_name" ]; then
        echo -e "${RED}New session name cannot be empty${NC}"
        return
    fi

    tmux rename-session -t "$old_name" "$new_name"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Session renamed from '$old_name' to '$new_name'${NC}"
    else
        echo -e "${RED}Failed to rename session${NC}"
    fi
}

# List all panes
list_all_panes() {
    echo -e "${YELLOW}All tmux panes with PIDs:${NC}"
    tmux list-panes -a -F "#{session_name}:#{window_index}.#{pane_index} PID:#{pane_pid} #{pane_current_command}" 2>/dev/null || echo "No tmux sessions running"
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice: " choice

    case $choice in
        1) list_sessions ;;
        2) create_session ;;
        3) attach_session ;;
        4) kill_session ;;
        5) kill_all_sessions ;;
        6) send_command ;;
        7) show_session_details ;;
        8) rename_session ;;
        9) list_all_panes ;;
        10) echo -e "${GREEN}Exiting...${NC}"; exit 0 ;;
        *) echo -e "${RED}Invalid option${NC}" ;;
    esac

    echo ""
    read -p "Press Enter to continue..."
    clear
done
