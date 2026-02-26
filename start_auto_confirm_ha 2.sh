#!/bin/bash
# Start Auto-Confirm with HA Failover and Mutex Locking
#
# This script:
# 1. Kills any existing auto-confirm processes
# 2. Starts HA monitor (which manages two workers)
# 3. Both workers use shared mutex lock for coordination
#
# Usage:
#   ./start_auto_confirm_ha.sh
#
# Stop:
#   pkill -f auto_confirm_ha_monitor

cd /Users/jgirmay/Desktop/gitrepo/GAIA_HOME

echo "🛑 Stopping any existing auto-confirm processes..."
pkill -f "auto_confirm_worker" 2>/dev/null || true
pkill -f "auto_confirm_ha_monitor" 2>/dev/null || true
sleep 1

echo "🚀 Starting Auto-Confirm HA Monitor..."
nohup python3 workers/auto_confirm_ha_monitor.py > /tmp/auto_confirm_ha.log 2>&1 &

sleep 2

echo "✅ Auto-Confirm HA started!"
echo ""
echo "📊 Configuration:"
echo "   - Primary worker: auto_confirm_worker_1"
echo "   - Secondary worker: auto_confirm_worker_2"
echo "   - Shared lock: /tmp/auto_confirm_shared.lock"
echo "   - Monitor log: /tmp/auto_confirm_ha.log"
echo ""
echo "🔍 Monitor status:"
tail -5 /tmp/auto_confirm_ha.log
