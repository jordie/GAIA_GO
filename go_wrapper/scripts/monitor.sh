#!/bin/bash

# Go Wrapper Monitoring Script
# Shows: running processes, active agents, API health

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
API_SERVER_PORT=8151
MANAGER_PORT=8163
MANAGER_HOST="localhost"

# Helper functions
print_header() {
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}

print_section() {
    echo -e "\n${BOLD}${BLUE}▶ $1${NC}"
    echo -e "${BLUE}───────────────────────────────────────────────────────────────${NC}"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✗${NC} Command '$1' not found"
        return 1
    fi
    return 0
}

# Main monitoring
print_header "Go Wrapper System Monitor"

# 1. Check for running wrapper processes
print_section "Running Wrapper Processes"

# Find wrapper processes (main binary and manager)
# Look for: ./go_wrapper, ./apiserver, ./manager, or go_wrapper binaries
wrapper_procs=$(ps aux | grep -E '(\./go_wrapper|\./apiserver|\./manager/main|go_wrapper/cmd)' | grep -v grep | grep -v monitor.sh)

if [ -z "$wrapper_procs" ]; then
    echo -e "${YELLOW}⚠${NC}  No wrapper processes found"
else
    echo -e "${GREEN}✓${NC} Found wrapper processes:\n"
    echo -e "${BOLD}%-10s %-8s %-8s %-8s %-8s %s${NC}" "USER" "PID" "%CPU" "%MEM" "VSZ" "COMMAND"
    echo "$wrapper_procs" | while IFS= read -r line; do
        user=$(echo "$line" | awk '{print $1}')
        pid=$(echo "$line" | awk '{print $2}')
        cpu=$(echo "$line" | awk '{print $3}')
        mem=$(echo "$line" | awk '{print $4}')
        vsz=$(echo "$line" | awk '{print $5}')
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')

        # Color code based on CPU usage
        if (( $(echo "$cpu > 50" | bc -l 2>/dev/null || echo 0) )); then
            cpu_color="${RED}"
        elif (( $(echo "$cpu > 20" | bc -l 2>/dev/null || echo 0) )); then
            cpu_color="${YELLOW}"
        else
            cpu_color="${GREEN}"
        fi

        echo -e "${BOLD}%-10s${NC} %-8s ${cpu_color}%-8s${NC} %-8s %-8s %s" \
            "$user" "$pid" "$cpu%" "$mem%" "$vsz" "$cmd"
    done
fi

# 2. Check API Server (port 8151)
print_section "API Server Health (Port $API_SERVER_PORT)"

if check_command "curl"; then
    health_response=$(curl -s -w "\n%{http_code}" "http://localhost:$API_SERVER_PORT/api/health" 2>/dev/null)
    http_code=$(echo "$health_response" | tail -n 1)
    body=$(echo "$health_response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓${NC} API Server is ${GREEN}HEALTHY${NC}"
        if [ -n "$body" ]; then
            echo -e "  Response: $body"
        fi
    else
        echo -e "${RED}✗${NC} API Server returned code: $http_code"
    fi
else
    # Fallback to checking if port is listening
    if lsof -i:$API_SERVER_PORT &> /dev/null || netstat -an 2>/dev/null | grep -q ":$API_SERVER_PORT.*LISTEN"; then
        echo -e "${GREEN}✓${NC} API Server port $API_SERVER_PORT is ${GREEN}LISTENING${NC}"
    else
        echo -e "${RED}✗${NC} API Server is ${RED}NOT RUNNING${NC} (port $API_SERVER_PORT closed)"
    fi
fi

# 3. Check Manager API (port 8163)
print_section "Manager API Health (Port $MANAGER_PORT)"

if check_command "curl"; then
    manager_response=$(curl -s -w "\n%{http_code}" "http://$MANAGER_HOST:$MANAGER_PORT/api/manager/status" 2>/dev/null)
    http_code=$(echo "$manager_response" | tail -n 1)
    body=$(echo "$manager_response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓${NC} Manager API is ${GREEN}HEALTHY${NC}"
        if [ -n "$body" ] && check_command "jq"; then
            echo -e "\n${BOLD}Manager Status:${NC}"
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
        elif [ -n "$body" ]; then
            echo -e "  Response: $body"
        fi
    else
        echo -e "${RED}✗${NC} Manager API returned code: $http_code"
    fi
else
    # Fallback to checking if port is listening
    if lsof -i:$MANAGER_PORT &> /dev/null || netstat -an 2>/dev/null | grep -q ":$MANAGER_PORT.*LISTEN"; then
        echo -e "${GREEN}✓${NC} Manager port $MANAGER_PORT is ${GREEN}LISTENING${NC}"
    else
        echo -e "${RED}✗${NC} Manager is ${RED}NOT RUNNING${NC} (port $MANAGER_PORT closed)"
    fi
fi

# 4. List active agents
print_section "Active Agents"

if check_command "curl"; then
    agents_response=$(curl -s "http://localhost:$API_SERVER_PORT/api/agents" 2>/dev/null)

    if [ -n "$agents_response" ]; then
        if check_command "jq"; then
            agent_count=$(echo "$agents_response" | jq '. | length' 2>/dev/null)

            if [ "$agent_count" = "0" ] || [ -z "$agent_count" ]; then
                echo -e "${YELLOW}⚠${NC}  No active agents found"
            else
                echo -e "${GREEN}✓${NC} Found $agent_count active agent(s):\n"
                echo "$agents_response" | jq -r '.[] | "  • \(.name) [\(.status)] - \(.type) agent"' 2>/dev/null
            fi
        else
            echo -e "${YELLOW}⚠${NC}  jq not available, showing raw response:"
            echo "$agents_response"
        fi
    else
        echo -e "${YELLOW}⚠${NC}  Could not fetch agents (API Server may be down)"
    fi

    # Also check manager for registered agents
    manager_agents=$(curl -s "http://$MANAGER_HOST:$MANAGER_PORT/api/manager/agents" 2>/dev/null)
    if [ -n "$manager_agents" ]; then
        echo -e "\n${BOLD}Manager Registered Agents:${NC}"
        if check_command "jq"; then
            agent_count=$(echo "$manager_agents" | jq '. | length' 2>/dev/null)
            if [ "$agent_count" = "0" ] || [ -z "$agent_count" ]; then
                echo -e "${YELLOW}⚠${NC}  No agents registered with manager"
            else
                echo "$manager_agents" | jq -r '.[] | "  • \(.name) [\(.status)] - Tasks completed: \(.tasks_completed)"' 2>/dev/null
            fi
        else
            echo "$manager_agents"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC}  curl not available - cannot check agents"
fi

# 5. Check for listening ports
print_section "Listening Ports"

echo -e "${BOLD}Port    Status      Service${NC}"
for port in $API_SERVER_PORT $MANAGER_PORT; do
    if lsof -i:$port &> /dev/null || netstat -an 2>/dev/null | grep -q ":$port.*LISTEN"; then
        status="${GREEN}LISTENING${NC}"
    else
        status="${RED}CLOSED${NC}   "
    fi

    service=""
    case $port in
        $API_SERVER_PORT) service="API Server" ;;
        $MANAGER_PORT) service="Manager" ;;
    esac

    echo -e "$port    $status    $service"
done

# 6. System resource summary
print_section "System Resources"

# Memory
total_mem=$(free -h 2>/dev/null | awk '/^Mem:/ {print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
used_mem=$(free -h 2>/dev/null | awk '/^Mem:/ {print $3}' || vm_stat 2>/dev/null | awk '/Pages active/ {print $3}' | sed 's/\.//')

if [ -n "$total_mem" ]; then
    echo -e "  Memory: ${total_mem} total"
fi

# CPU load
load_avg=$(uptime | awk -F'load average:' '{print $2}' | xargs)
echo -e "  Load Average: ${load_avg}"

# Disk space for logs directory
if [ -d "logs" ]; then
    disk_usage=$(du -sh logs 2>/dev/null | awk '{print $1}')
    echo -e "  Logs Directory: ${disk_usage}"
fi

# Footer
echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Monitoring complete at $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
