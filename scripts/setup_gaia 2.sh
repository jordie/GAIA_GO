#!/bin/bash
#
# GAIA Setup Script
# Sets up gaia/GAIA/Gaia commands for global access
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GAIA_SCRIPT="$PROJECT_DIR/gaia.py"

echo "============================================================"
echo "GAIA - Generic AI Agent Setup"
echo "============================================================"
echo ""
echo "Script location: $GAIA_SCRIPT"
echo ""

# Check if script exists and is executable
if [[ ! -f "$GAIA_SCRIPT" ]]; then
    echo "Error: gaia.py not found at $GAIA_SCRIPT"
    exit 1
fi

chmod +x "$GAIA_SCRIPT"

# Determine installation method
echo "Select installation method:"
echo ""
echo "  1) Symlink to /usr/local/bin (requires sudo)"
echo "  2) Add aliases to shell profile"
echo "  3) Both"
echo "  4) Show manual instructions"
echo ""
read -p "Choice [1-4]: " choice

case $choice in
    1|3)
        echo ""
        echo "Creating symlinks in /usr/local/bin..."
        sudo ln -sf "$GAIA_SCRIPT" /usr/local/bin/gaia
        sudo ln -sf "$GAIA_SCRIPT" /usr/local/bin/GAIA
        sudo ln -sf "$GAIA_SCRIPT" /usr/local/bin/Gaia
        echo "  Created: /usr/local/bin/gaia"
        echo "  Created: /usr/local/bin/GAIA"
        echo "  Created: /usr/local/bin/Gaia"

        if [[ "$choice" == "1" ]]; then
            echo ""
            echo "Done! You can now run 'gaia', 'GAIA', or 'Gaia' from anywhere."
            exit 0
        fi
        ;;
esac

case $choice in
    2|3)
        echo ""
        # Detect shell
        SHELL_NAME=$(basename "$SHELL")
        if [[ "$SHELL_NAME" == "zsh" ]]; then
            PROFILE="$HOME/.zshrc"
        elif [[ "$SHELL_NAME" == "bash" ]]; then
            if [[ -f "$HOME/.bash_profile" ]]; then
                PROFILE="$HOME/.bash_profile"
            else
                PROFILE="$HOME/.bashrc"
            fi
        else
            PROFILE="$HOME/.profile"
        fi

        echo "Adding aliases to $PROFILE..."

        # Check if already exists
        if grep -q "alias gaia=" "$PROFILE" 2>/dev/null; then
            echo "  Aliases already exist in $PROFILE"
        else
            cat >> "$PROFILE" << EOF

# GAIA - Generic AI Agent
alias gaia='$GAIA_SCRIPT'
alias GAIA='$GAIA_SCRIPT'
alias Gaia='$GAIA_SCRIPT'
EOF
            echo "  Added aliases to $PROFILE"
        fi

        echo ""
        echo "Done! Restart your terminal or run: source $PROFILE"
        ;;
    4)
        echo ""
        echo "Manual Installation Instructions:"
        echo "=================================="
        echo ""
        echo "Option 1: Create symlinks (requires sudo)"
        echo "  sudo ln -sf $GAIA_SCRIPT /usr/local/bin/gaia"
        echo "  sudo ln -sf $GAIA_SCRIPT /usr/local/bin/GAIA"
        echo "  sudo ln -sf $GAIA_SCRIPT /usr/local/bin/Gaia"
        echo ""
        echo "Option 2: Add to shell profile (~/.zshrc or ~/.bashrc)"
        echo "  alias gaia='$GAIA_SCRIPT'"
        echo "  alias GAIA='$GAIA_SCRIPT'"
        echo "  alias Gaia='$GAIA_SCRIPT'"
        echo ""
        echo "Option 3: Add to PATH"
        echo "  export PATH=\"\$PATH:$PROJECT_DIR\""
        echo ""
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Usage:"
echo "  gaia                    # Start interactive session"
echo "  gaia --status           # Show session pool status"
echo "  gaia -p \"Hello\"         # Single prompt mode"
echo "  gaia --provider claude  # Force Claude provider"
echo "  gaia --help             # Show all options"
