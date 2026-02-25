#!/bin/bash
# Install script for wrapper-cli

set -e

echo "=== wrapper-cli Installation ==="
echo

# Build the CLI
echo "Building wrapper-cli..."
go build -o wrapper-cli cmd/cli/main.go

# Check if build was successful
if [ ! -f "./wrapper-cli" ]; then
    echo "Error: Build failed"
    exit 1
fi

echo "✓ Build successful"

# Determine install location
if [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
elif [ -d "$HOME/bin" ]; then
    INSTALL_DIR="$HOME/bin"
else
    mkdir -p "$HOME/bin"
    INSTALL_DIR="$HOME/bin"
fi

echo
echo "Installing to $INSTALL_DIR..."

# Install
cp wrapper-cli "$INSTALL_DIR/wrapper-cli"
chmod +x "$INSTALL_DIR/wrapper-cli"

echo "✓ Installed to $INSTALL_DIR/wrapper-cli"

# Check if install dir is in PATH
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "✓ $INSTALL_DIR is in PATH"
else
    echo
    echo "⚠ Warning: $INSTALL_DIR is not in your PATH"
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\$PATH:$INSTALL_DIR"
fi

echo
echo "=== Installation Complete ==="
echo
echo "Try it out:"
echo "  wrapper-cli version"
echo "  wrapper-cli help"
echo "  wrapper-cli agents list"
echo
