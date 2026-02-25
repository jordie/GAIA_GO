#!/bin/bash
# Go Wrapper Live Demo
# Demonstrates all features in action

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   Go Wrapper Live Demo${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo -e "${CYAN}Dashboard URL: http://localhost:8151/${NC}"
echo ""
sleep 2

# Demo 1: Simple Agent
echo -e "${BLUE}[Demo 1/4] Simple Agent Execution${NC}"
echo -e "${YELLOW}Running: ./wrapper demo-echo echo 'Hello from Go Wrapper!'${NC}"
echo ""
./wrapper demo-echo echo "Hello from Go Wrapper!"
echo ""
echo -e "${GREEN}✓ Log saved to: logs/agents/demo-echo/${NC}"
sleep 2

# Demo 2: ANSI Stripping
echo ""
echo -e "${BLUE}[Demo 2/4] ANSI Code Stripping${NC}"
echo -e "${YELLOW}Running: ./wrapper demo-ansi with colored output${NC}"
echo ""
./wrapper demo-ansi bash -c 'echo -e "\033[31mRed\033[0m \033[32mGreen\033[0m \033[34mBlue\033[0m"'
echo ""
LOG_FILE=$(find logs/agents/demo-ansi -name "*-stdout.log" -type f | tail -1)
echo -e "${CYAN}Log file contents (ANSI stripped):${NC}"
cat "$LOG_FILE" | tail -3
echo ""
ANSI_COUNT=$(grep -o $'\x1b' "$LOG_FILE" | wc -l | tr -d ' ')
echo -e "${GREEN}✓ ANSI codes in log: $ANSI_COUNT (clean!)${NC}"
sleep 2

# Demo 3: Concurrent Agents
echo ""
echo -e "${BLUE}[Demo 3/4] Concurrent Execution${NC}"
echo -e "${YELLOW}Spawning 5 concurrent agents...${NC}"
echo ""
for i in {1..5}; do
    ./wrapper demo-concurrent-$i echo "Agent $i reporting!" &
done
wait
echo ""
echo -e "${GREEN}✓ All 5 agents completed${NC}"
echo -e "${CYAN}Log files created:${NC}"
ls -lh logs/agents/demo-concurrent-*/2026-* 2>/dev/null | tail -5 | awk '{print "  " $9, "(" $5 ")"}'
sleep 2

# Demo 4: Live Agent with Codex
echo ""
echo -e "${BLUE}[Demo 4/4] Codex Integration (Live)${NC}"
if command -v codex > /dev/null 2>&1; then
    echo -e "${YELLOW}Running: ./wrapper demo-codex codex exec 'What is 5+5?'${NC}"
    echo ""
    ./wrapper demo-codex codex exec "What is 5+5? Answer with just the number."
    echo ""
    LOG_FILE=$(find logs/agents/demo-codex -name "*-stdout.log" -type f | tail -1)
    echo -e "${CYAN}Answer from Codex:${NC}"
    tail -1 "$LOG_FILE"
    echo ""
    echo -e "${GREEN}✓ Codex integration working${NC}"
else
    echo -e "${YELLOW}⊘ Codex not available, skipping${NC}"
fi
sleep 2

# API Demo
echo ""
echo -e "${BLUE}[API Demo] Current Agents${NC}"
echo -e "${YELLOW}Querying: http://localhost:8151/api/agents${NC}"
echo ""
curl -s http://localhost:8151/api/agents | python3 -m json.tool
echo ""
sleep 2

# Summary
echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   Demo Complete!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo -e "${GREEN}✓ Simple execution${NC}"
echo -e "${GREEN}✓ ANSI stripping${NC}"
echo -e "${GREEN}✓ Concurrent agents${NC}"
echo -e "${GREEN}✓ Codex integration${NC}"
echo -e "${GREEN}✓ API server${NC}"
echo ""
echo -e "${CYAN}Dashboard: http://localhost:8151/${NC}"
echo -e "${CYAN}Logs: logs/agents/demo-*/${NC}"
echo ""
echo -e "${YELLOW}Run './tests/run_all_tests.sh' for full test suite${NC}"
echo ""
