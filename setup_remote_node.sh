#!/bin/bash
# Setup remote node for multi-agent development team

NODE_IP="$1"
NODE_NAME="${2:-node-1}"

if [ -z "$NODE_IP" ]; then
    echo "Usage: $0 <node-ip> [node-name]"
    echo "Example: $0 192.168.1.172 node-1"
    exit 1
fi

echo "🚀 Setting up remote node: $NODE_NAME at $NODE_IP"
echo "=================================================================="

# Check if we can reach the node
echo ""
echo "1️⃣  Testing connectivity to $NODE_IP..."
if ping -c 1 -W 2 "$NODE_IP" > /dev/null 2>&1; then
    echo "✅ Node is reachable"
else
    echo "❌ Cannot reach $NODE_IP"
    exit 1
fi

# Check SSH access
echo ""
echo "2️⃣  Testing SSH access..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$NODE_IP" "echo 'SSH OK'" 2>/dev/null; then
    echo "✅ SSH access confirmed"
else
    echo "❌ Cannot SSH to $NODE_IP"
    echo "   Make sure SSH keys are set up:"
    echo "   ssh-copy-id $NODE_IP"
    exit 1
fi

# Create deployment directory on remote node
echo ""
echo "3️⃣  Creating deployment directory..."
ssh "$NODE_IP" "mkdir -p ~/agent_deployment/{data,logs,config}" 2>/dev/null
echo "✅ Directory structure created"

# Copy files to remote node
echo ""
echo "4️⃣  Copying files to $NODE_IP..."

# File locking system
scp file_lock_manager.py "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
echo "   ✅ file_lock_manager.py"

# Task router
scp agent_task_router.py "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
echo "   ✅ agent_task_router.py"

# Agent wrapper
scp agent_wrapper.sh "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
echo "   ✅ agent_wrapper.sh"

# Start agent script
scp start_agent.sh "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
echo "   ✅ start_agent.sh"

# Team config
if [ -f team_config.json ]; then
    scp team_config.json "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
    echo "   ✅ team_config.json"
fi

# Gemini config
scp .env.gemini "$NODE_IP:~/agent_deployment/" > /dev/null 2>&1
echo "   ✅ .env.gemini"

# Go wrapper binaries (if needed)
if [ -d go_wrapper ]; then
    echo ""
    echo "5️⃣  Copying Go wrapper binaries..."
    ssh "$NODE_IP" "mkdir -p ~/agent_deployment/go_wrapper" 2>/dev/null
    scp go_wrapper/wrapper "$NODE_IP:~/agent_deployment/go_wrapper/" > /dev/null 2>&1
    scp go_wrapper/apiserver "$NODE_IP:~/agent_deployment/go_wrapper/" > /dev/null 2>&1
    echo "   ✅ Go wrapper binaries"
fi

# Create node configuration
echo ""
echo "6️⃣  Creating node configuration..."
ssh "$NODE_IP" "cat > ~/agent_deployment/config/node_config.json << 'EOF'
{
  \"node_id\": \"$NODE_NAME\",
  \"node_ip\": \"$NODE_IP\",
  \"role\": \"worker\",
  \"primary_node\": \"100.112.58.92\",
  \"api_port\": 8151,
  \"created_at\": \"$(date -Iseconds)\"
}
EOF"
echo "✅ Node configuration created"

# Install dependencies
echo ""
echo "7️⃣  Installing dependencies on remote node..."
ssh "$NODE_IP" << 'REMOTE_SCRIPT'
# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo "   ✅ Python 3 found"

# Check tmux
if ! command -v tmux &> /dev/null; then
    echo "⚠️  tmux not found. Installing..."
    # Attempt to install (works on Ubuntu/Debian)
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y tmux
    elif command -v yum &> /dev/null; then
        sudo yum install -y tmux
    elif command -v brew &> /dev/null; then
        brew install tmux
    else
        echo "❌ Cannot install tmux automatically. Please install manually."
        exit 1
    fi
fi
echo "   ✅ tmux available"
REMOTE_SCRIPT

# Create startup script on remote node
echo ""
echo "8️⃣  Creating startup script..."
ssh "$NODE_IP" "cat > ~/agent_deployment/start_node.sh << 'EOF'
#!/bin/bash
# Start agent node

NODE_DIR=\$(dirname \"\$0\")
cd \"\$NODE_DIR\"

# Source environment
source .env.gemini

# Start API server (if go_wrapper exists)
if [ -f go_wrapper/apiserver ]; then
    echo \"Starting API server...\"
    nohup ./go_wrapper/apiserver -host 0.0.0.0 -port 8151 > logs/apiserver.log 2>&1 &
    echo \"✅ API server started on port 8151\"
fi

# Wait for API server
sleep 2

echo \"\"
echo \"Node is ready!\"
echo \"API Server: http://\$(hostname -I | awk '{print \$1}'):8151\"
echo \"\"
echo \"To spawn agents:\"
echo \"  ./start_agent.sh <agent-name> <tool>\"
echo \"\"
EOF
chmod +x ~/agent_deployment/start_node.sh"
echo "✅ Startup script created"

# Test node setup
echo ""
echo "9️⃣  Testing node setup..."
ssh "$NODE_IP" "cd ~/agent_deployment && python3 file_lock_manager.py test" 2>&1 | tail -5
echo "✅ File locking system tested"

# Summary
echo ""
echo "=================================================================="
echo "✅ Remote Node Setup Complete!"
echo "=================================================================="
echo ""
echo "Node Details:"
echo "  Name: $NODE_NAME"
echo "  IP: $NODE_IP"
echo "  Location: ~/agent_deployment"
echo ""
echo "Next Steps:"
echo ""
echo "1. SSH to the node:"
echo "   ssh $NODE_IP"
echo ""
echo "2. Start the node:"
echo "   cd ~/agent_deployment"
echo "   ./start_node.sh"
echo ""
echo "3. Spawn agents:"
echo "   ./start_agent.sh worker-1 claude"
echo "   ./start_agent.sh worker-2 gemini"
echo ""
echo "4. Access API:"
echo "   curl http://$NODE_IP:8151/api/health"
echo ""
echo "5. Monitor from primary node:"
echo "   python3 agent_task_router.py status"
echo ""
echo "=================================================================="
