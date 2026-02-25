#!/bin/bash
# GAIA Status Command Wrapper
# Provides "GAIA status" shell command capability

GAIA_HOME="${GAIA_HOME:-/Users/jgirmay/Desktop/gitrepo/GAIA_HOME}"
SCRIPT="${GAIA_HOME}/orchestration/gaia_status.py"

# Make script executable if it isn't
if [ -f "$SCRIPT" ] && [ ! -x "$SCRIPT" ]; then
    chmod +x "$SCRIPT"
fi

# Run the Python script with all arguments
python3 "$SCRIPT" "$@"
