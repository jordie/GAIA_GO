#!/bin/bash
# Install Milestone Worker as systemd service
#
# Usage: sudo ./install_milestone_service.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/milestone-worker.service"

echo "Installing milestone worker systemd service..."

# Copy service file
cp "$SERVICE_FILE" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable service
systemctl enable milestone-worker.service

echo "Service installed!"
echo ""
echo "Commands:"
echo "  sudo systemctl start milestone-worker    # Start service"
echo "  sudo systemctl stop milestone-worker     # Stop service"
echo "  sudo systemctl status milestone-worker   # Check status"
echo "  sudo systemctl restart milestone-worker  # Restart service"
echo "  journalctl -u milestone-worker -f        # View logs"
