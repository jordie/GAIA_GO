#!/bin/bash
# QA Server Startup Script
# Binds to 0.0.0.0 for Tailscale accessibility
export PATH=~/homebrew/bin:$PATH
export HOST=0.0.0.0
export USE_HTTPS=true
export APP_ENV=qa
export PORT=5052
cd ~/basic_edu_apps/environments
exec python3 unified_app.py
