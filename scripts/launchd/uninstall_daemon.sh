#!/bin/bash
# Uninstall EDU Apps LaunchDaemon
# Requires: sudo access
#
# Usage: sudo ./uninstall_daemon.sh

set -e

PLIST_NAME="com.eduapps.servers.plist"
PLIST_DEST="/Library/LaunchDaemons/$PLIST_NAME"

echo "=== EDU Apps LaunchDaemon Uninstaller ==="

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with sudo"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if installed
if [ ! -f "$PLIST_DEST" ]; then
    echo "LaunchDaemon not installed at $PLIST_DEST"
    exit 0
fi

# Unload daemon
echo "Stopping daemon..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Remove plist
echo "Removing $PLIST_DEST..."
rm -f "$PLIST_DEST"

echo ""
echo "=== SUCCESS ==="
echo "LaunchDaemon uninstalled."
echo "Servers will no longer auto-start on boot."
