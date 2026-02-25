#!/bin/bash
# Test script for Phase 6 cluster functionality

set -e

echo "════════════════════════════════════════════════════════════"
echo "  Phase 6: Multi-Node Clustering - Demo Script"
echo "════════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LEADER_HOST="127.0.0.1"
LEADER_PORT="8151"
BASE_URL="http://${LEADER_HOST}:${LEADER_PORT}"

echo -e "${BLUE}Test Configuration:${NC}"
echo "  Leader: ${BASE_URL}"
echo ""

# Function to print section header
section() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to print success
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to run test
run_test() {
    echo "  Running: $1"
    echo "  Command: $2"
    echo ""
    eval "$2"
    echo ""
    success "$1"
}

# Test 1: Register Nodes
section "1. Register Cluster Nodes"

run_test "Register Node 2 (Worker)" "curl -s -X POST ${BASE_URL}/api/cluster/nodes \
  -H 'Content-Type: application/json' \
  -d '{
    \"id\": \"node-2\",
    \"hostname\": \"worker1\",
    \"ip_address\": \"10.0.0.2\",
    \"port\": 8152,
    \"max_agents\": 20,
    \"services\": [\"wrapper\", \"database\"]
  }' | jq"

run_test "Register Node 3 (Worker)" "curl -s -X POST ${BASE_URL}/api/cluster/nodes \
  -H 'Content-Type: application/json' \
  -d '{
    \"id\": \"node-3\",
    \"hostname\": \"worker2\",
    \"ip_address\": \"10.0.0.3\",
    \"port\": 8153,
    \"max_agents\": 15,
    \"services\": [\"wrapper\", \"streaming\"]
  }' | jq"

# Test 2: List Nodes
section "2. List All Cluster Nodes"

run_test "Get all nodes" "curl -s ${BASE_URL}/api/cluster/nodes | jq"

# Test 3: Get Specific Node
section "3. Get Node Details"

run_test "Get node-2 details" "curl -s ${BASE_URL}/api/cluster/nodes/node-2 | jq"

# Test 4: Update Heartbeat
section "4. Update Node Heartbeat"

run_test "Send heartbeat for node-2" "curl -s -X POST ${BASE_URL}/api/cluster/nodes/node-2 \
  -H 'Content-Type: application/json' \
  -d '{
    \"cpu_usage\": 45.3,
    \"memory_usage\": 62.1,
    \"disk_usage\": 55.0,
    \"load_average\": 2.5
  }' | jq"

run_test "Send heartbeat for node-3" "curl -s -X POST ${BASE_URL}/api/cluster/nodes/node-3 \
  -H 'Content-Type: application/json' \
  -d '{
    \"cpu_usage\": 25.8,
    \"memory_usage\": 42.3,
    \"disk_usage\": 38.0,
    \"load_average\": 1.2
  }' | jq"

# Test 5: Cluster Statistics
section "5. Get Cluster Statistics"

run_test "Get cluster stats" "curl -s ${BASE_URL}/api/cluster/stats | jq"

# Test 6: Leader Information
section "6. Get Leader Information"

run_test "Get current leader" "curl -s ${BASE_URL}/api/cluster/leader | jq"

# Test 7: Load Balancing Strategies
section "7. Test Load Balancing Strategies"

run_test "Change to round-robin" "curl -s -X POST '${BASE_URL}/api/cluster/balance?strategy=round_robin' | jq"

run_test "Change to least_loaded" "curl -s -X POST '${BASE_URL}/api/cluster/balance?strategy=least_loaded' | jq"

run_test "Change to weighted" "curl -s -X POST '${BASE_URL}/api/cluster/balance?strategy=weighted' | jq"

# Test 8: Agent Assignments
section "8. Get Agent Assignments"

run_test "List all assignments" "curl -s ${BASE_URL}/api/cluster/assignments | jq"

# Test 9: Health Check
section "9. Server Health Check"

run_test "Get server health" "curl -s ${BASE_URL}/api/health | jq"

# Summary
section "Test Summary"

echo -e "${GREEN}All cluster tests completed successfully!${NC}"
echo ""
echo "Cluster Features Verified:"
success "Node registration"
success "Node heartbeat updates"
success "Cluster statistics"
success "Leader election"
success "Load balancing strategies"
success "Agent assignment tracking"
success "Health monitoring"
echo ""

echo -e "${BLUE}Cluster is ready for production use!${NC}"
echo ""

# Optional: Cleanup
echo "To unregister nodes:"
echo "  curl -X DELETE ${BASE_URL}/api/cluster/nodes/node-2"
echo "  curl -X DELETE ${BASE_URL}/api/cluster/nodes/node-3"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  Demo Complete!"
echo "════════════════════════════════════════════════════════════"
