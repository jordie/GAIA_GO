#!/bin/bash

# GAIA_GO Environment Switcher
# Easily switch between dev, staging, and production environments

set -e

ENV=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$ENV" ]; then
    echo "GAIA_GO Environment Switcher"
    echo "============================"
    echo ""
    echo "Usage: source switch_env.sh <environment>"
    echo ""
    echo "Available environments:"
    echo "  dev       - Development (local, SQLite, port 8090)"
    echo "  staging   - Staging (isolated, SQLite, port 8091)"
    echo "  prod      - Production (external DB, port 8080)"
    echo ""
    echo "Example:"
    echo "  source switch_env.sh dev"
    echo ""
    exit 1
fi

case "$ENV" in
    dev|development)
        ENV_FILE="$SCRIPT_DIR/.env.dev"
        ENV_NAME="development"
        PORT="8090"
        DB="gaia_dev.db"
        ;;
    staging|stage)
        ENV_FILE="$SCRIPT_DIR/.env.staging"
        ENV_NAME="staging"
        PORT="8091"
        DB="gaia_staging.db"
        ;;
    prod|production)
        ENV_FILE="$SCRIPT_DIR/.env.prod"
        ENV_NAME="production"
        PORT="8080"
        DB="external (PostgreSQL)"
        ;;
    *)
        echo "Unknown environment: $ENV"
        echo "Available: dev, staging, prod"
        exit 1
        ;;
esac

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file not found: $ENV_FILE"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Print confirmation
echo "✅ Switched to $ENV_NAME environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Environment: $ENV_NAME"
echo "Port: $PORT"
echo "Database: $DB"
echo "Debug: $DEBUG"
echo "Log Level: $LOG_LEVEL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Useful commands:"
echo "  go run ./cmd/gaia-server          # Start server"
echo "  go test ./...                     # Run tests"
echo "  go run ./cmd/migrate -env=$ENV    # Run migrations"
echo ""
