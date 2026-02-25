#!/bin/bash
# DEV Server Startup Script
# Binds to 0.0.0.0 for Tailscale accessibility
export PATH=~/homebrew/bin:$PATH
export HOST=0.0.0.0
export USE_HTTPS=true
export APP_ENV=dev
export PORT=5051
cd ~/basic_edu_apps/environments
exec python3 unified_app.py
