#!/bin/bash
# Setup GAIA Status Command
#
# This script adds the "GAIA status" command to your shell configuration
# Usage: bash setup_gaia_command.sh

GAIA_HOME="${GAIA_HOME:-/Users/jgirmay/Desktop/gitrepo/GAIA_HOME}"
SHELL_CONFIG=""

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

# Fallback to checking shell
if [ -z "$SHELL_CONFIG" ]; then
    SHELL=$SHELL
    case "$SHELL" in
        */zsh)
            SHELL_CONFIG="$HOME/.zshrc"
            ;;
        */bash)
            SHELL_CONFIG="$HOME/.bashrc"
            ;;
        *)
            echo "Error: Could not detect shell. Please manually add:"
            echo "alias gaia_status='python3 $GAIA_HOME/orchestration/gaia_status.py'"
            exit 1
            ;;
    esac
fi

# Add alias if not already present
if ! grep -q "alias gaia_status" "$SHELL_CONFIG"; then
    echo "" >> "$SHELL_CONFIG"
    echo "# GAIA Status Command (added $(date))" >> "$SHELL_CONFIG"
    echo "alias gaia_status='python3 $GAIA_HOME/orchestration/gaia_status.py'" >> "$SHELL_CONFIG"
    echo "alias GAIA='python3 $GAIA_HOME/orchestration/gaia_status.py'" >> "$SHELL_CONFIG"
    echo "" >> "$SHELL_CONFIG"
    echo "✓ Added 'gaia_status' alias to $SHELL_CONFIG"
    echo ""
    echo "To use immediately, run:"
    echo "  source $SHELL_CONFIG"
    echo ""
    echo "Then use:"
    echo "  gaia_status           # Full status tree"
    echo "  gaia_status --brief   # Condensed view"
    echo "  gaia_status --watch   # Real-time updates"
else
    echo "✓ 'gaia_status' alias already configured in $SHELL_CONFIG"
fi
