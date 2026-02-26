#!/bin/bash
# Send task to remote agent properly

NODE_IP="$1"
AGENT_NAME="$2"
TASK="$3"
WORK_DIR="$4"

# Create message file
MSG=$(cat <<MESSAGE
============================================================
NEW TASK: ${TASK}
Work Directory: ${WORK_DIR}
Node: ${NODE_IP}
============================================================

MESSAGE
)

# Send via SSH to tmux
ssh "$NODE_IP" "/opt/homebrew/bin/tmux send-keys -t $AGENT_NAME '$MSG' C-m"

echo "✅ Task sent to $AGENT_NAME on $NODE_IP"
