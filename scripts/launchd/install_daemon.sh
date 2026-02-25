#!/bin/bash
# Install EDU Apps LaunchDaemon for auto-start without user login
# Requires: sudo access on the target machine
#
# Usage: sudo ./install_daemon.sh

set -e

PLIST_NAME="com.eduapps.servers.plist"
PLIST_SRC="$(dirname "$0")/$PLIST_NAME"
PLIST_DEST="/Library/LaunchDaemons/$PLIST_NAME"
STARTUP_SCRIPT="/Users/server/start_edu_servers.sh"

echo "=== EDU Apps LaunchDaemon Installer ==="

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with sudo"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if plist source exists
if [ ! -f "$PLIST_SRC" ]; then
    echo "Error: $PLIST_SRC not found"
    exit 1
fi

# Check if startup script exists
if [ ! -f "$STARTUP_SCRIPT" ]; then
    echo "Warning: $STARTUP_SCRIPT not found on target machine"
    echo "Make sure to create it before the daemon runs"
fi

# Unload existing daemon if present
if launchctl list | grep -q "com.eduapps.servers"; then
    echo "Stopping existing daemon..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist to LaunchDaemons
echo "Installing $PLIST_NAME to $PLIST_DEST..."
cp "$PLIST_SRC" "$PLIST_DEST"

# Set correct permissions
echo "Setting permissions..."
chown root:wheel "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

# Load the daemon
echo "Loading daemon..."
launchctl load "$PLIST_DEST"

# Verify
if launchctl list | grep -q "com.eduapps.servers"; then
    echo ""
    echo "=== SUCCESS ==="
    echo "LaunchDaemon installed and loaded."
    echo "Servers will start automatically on system boot."
    echo ""
    echo "Commands:"
    echo "  Start now:  sudo launchctl start com.eduapps.servers"
    echo "  Stop:       sudo launchctl stop com.eduapps.servers"
    echo "  Unload:     sudo launchctl unload $PLIST_DEST"
    echo "  Status:     sudo launchctl list | grep eduapps"
else
    echo "Error: Daemon failed to load"
    exit 1
fi
