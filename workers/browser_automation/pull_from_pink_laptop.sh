#!/bin/bash
# Pull tab groups from pink laptop

PINK_LAPTOP_HOST="${PINK_LAPTOP_HOST:-pink-laptop.local}"
PINK_LAPTOP_USER="${PINK_LAPTOP_USER:-jgirmay}"

echo "========================================================================"
echo "PULLING TAB GROUPS FROM PINK LAPTOP"
echo "========================================================================"
echo ""
echo "Connecting to: $PINK_LAPTOP_USER@$PINK_LAPTOP_HOST"
echo ""

# Copy script to pink laptop if needed
scp -q list_tab_groups.py "$PINK_LAPTOP_USER@$PINK_LAPTOP_HOST:~/browser_automation/" 2>/dev/null || {
    echo "Creating directory on pink laptop..."
    ssh "$PINK_LAPTOP_USER@$PINK_LAPTOP_HOST" "mkdir -p ~/browser_automation"
    scp list_tab_groups.py "$PINK_LAPTOP_USER@$PINK_LAPTOP_HOST:~/browser_automation/"
}

# Run on pink laptop
echo "Running list_tab_groups.py on pink laptop..."
echo ""
ssh "$PINK_LAPTOP_USER@$PINK_LAPTOP_HOST" "cd ~/browser_automation && python3 list_tab_groups.py"
