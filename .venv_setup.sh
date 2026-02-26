#!/bin/bash
# GAIA_GO Python Virtual Environment Setup
# Usage: bash .venv_setup.sh [python-version]

set -e

PYTHON_VERSION=${1:-3.11}
VENV_DIR="venv"

echo "Setting up Python virtual environment for GAIA_GO..."
echo "Python version: $PYTHON_VERSION"
echo ""

# Check if Python is installed
if ! command -v python${PYTHON_VERSION} &> /dev/null; then
    echo "Error: Python $PYTHON_VERSION is not installed"
    echo "Please install Python $PYTHON_VERSION and try again"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python${PYTHON_VERSION} -m venv $VENV_DIR

# Activate virtual environment
echo "Activating virtual environment..."
source $VENV_DIR/bin/activate

# Upgrade pip, setuptools, wheel
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install production dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing production dependencies..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found"
fi

# Install development dependencies
if [ -f "requirements-dev.txt" ]; then
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
else
    echo "Note: requirements-dev.txt not found, skipping development dependencies"
fi

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    echo "Setting up pre-commit hooks..."
    pre-commit install 2>/dev/null || echo "Note: pre-commit hooks not configured"
fi

echo ""
echo "✓ Virtual environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "To deactivate, run:"
echo "  deactivate"
