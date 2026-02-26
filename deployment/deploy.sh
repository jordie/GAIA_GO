#!/bin/bash
set -e

# GAIA_GO Staging Deployment Script
# This script handles building, deploying, and managing the GAIA_GO Phase 9+10 system in staging

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_DIR="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}===============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===============================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing=0

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        missing=1
    else
        print_success "Docker is installed"
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        missing=1
    else
        print_success "Docker Compose is installed"
    fi

    if [ $missing -eq 1 ]; then
        print_error "Please install missing prerequisites"
        exit 1
    fi
}

build_binary() {
    print_header "Building GAIA_GO Binary"

    cd "$PROJECT_ROOT"

    # Get version from git
    VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "dev")
    BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

    print_warning "Building version: $VERSION (commit: $COMMIT)"

    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
        -ldflags "-s -w -X main.Version=$VERSION -X main.BuildTime=$BUILD_TIME -X main.Commit=$COMMIT" \
        -o "$PROJECT_ROOT/bin/gaia_go_staging" \
        cmd/server/main.go

    if [ -f "$PROJECT_ROOT/bin/gaia_go_staging" ]; then
        SIZE=$(du -h "$PROJECT_ROOT/bin/gaia_go_staging" | cut -f1)
        print_success "Binary built successfully ($SIZE)"
    else
        print_error "Failed to build binary"
        exit 1
    fi
}

setup_env() {
    print_header "Setting Up Environment"

    if [ ! -f "$DEPLOYMENT_DIR/.env.staging" ]; then
        print_error ".env.staging file not found"
        print_warning "Creating from template..."
        cp "$DEPLOYMENT_DIR/.env.staging.template" "$DEPLOYMENT_DIR/.env.staging" 2>/dev/null || {
            print_error "No template found. Please create .env.staging manually"
            exit 1
        }
    fi

    # Check for ANTHROPIC_API_KEY
    if ! grep -q "ANTHROPIC_API_KEY=" "$DEPLOYMENT_DIR/.env.staging"; then
        print_warning "ANTHROPIC_API_KEY not set in .env.staging"
        print_warning "AI Agent fallback will use mock implementation"
    else
        print_success "Environment configured"
    fi
}

start_services() {
    print_header "Starting Services"

    cd "$DEPLOYMENT_DIR"

    print_warning "Starting PostgreSQL..."
    docker-compose -f docker-compose.staging.yml up -d postgres

    # Wait for database to be ready
    print_warning "Waiting for PostgreSQL to be ready..."
    sleep 10

    for i in {1..30}; do
        if docker-compose -f docker-compose.staging.yml exec -T postgres pg_isready -U gaia_user -d gaia_go_staging &>/dev/null; then
            print_success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "PostgreSQL failed to start"
            exit 1
        fi
        echo "Waiting... ($i/30)"
        sleep 1
    done

    print_warning "Starting GAIA_GO server..."
    docker-compose -f docker-compose.staging.yml up -d gaia_go

    # Wait for server to be ready
    print_warning "Waiting for GAIA_GO server to be ready..."
    for i in {1..30}; do
        if curl -sf http://localhost:8080/health &>/dev/null; then
            print_success "GAIA_GO server is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "GAIA_GO server failed to start"
            docker-compose -f docker-compose.staging.yml logs gaia_go
            exit 1
        fi
        echo "Waiting... ($i/30)"
        sleep 1
    done

    print_warning "Starting Prometheus (optional)..."
    docker-compose -f docker-compose.staging.yml up -d prometheus 2>/dev/null || true
}

run_tests() {
    print_header "Running Smoke Tests"

    # Test health endpoint
    print_warning "Testing health endpoint..."
    HEALTH=$(curl -s http://localhost:8080/health | jq -r '.status' 2>/dev/null)
    if [ "$HEALTH" = "healthy" ]; then
        print_success "Health check passed"
    else
        print_error "Health check failed"
        exit 1
    fi

    # Test auto-confirm endpoints
    print_warning "Testing auto-confirm endpoints..."

    # Set session preference
    PREF=$(curl -s -X POST http://localhost:8080/api/claude/confirm/preferences/staging_test \
        -H "Content-Type: application/json" \
        -d '{"allow_all":false,"use_ai_fallback":true}' | jq -r '.message' 2>/dev/null)
    if [ "$PREF" = "Preference updated successfully" ]; then
        print_success "Session preferences endpoint working"
    else
        print_error "Session preferences endpoint failed"
    fi

    # Create pattern
    PATTERN=$(curl -s -X POST http://localhost:8080/api/claude/confirm/patterns \
        -H "Content-Type: application/json" \
        -d '{"name":"Staging Test","permission_type":"read","resource_type":"file","path_pattern":"/test/**","decision_type":"approve","confidence":0.9,"enabled":true}' \
        | jq -r '.pattern_id' 2>/dev/null)
    if [ ! -z "$PATTERN" ] && [ "$PATTERN" != "null" ]; then
        print_success "Pattern creation endpoint working"
    else
        print_error "Pattern creation endpoint failed"
    fi

    # Test confirmation request
    DECISION=$(curl -s -X POST http://localhost:8080/api/claude/confirm/request \
        -H "Content-Type: application/json" \
        -d '{"session_id":"staging_test","permission_type":"read","resource_type":"file","resource_path":"/test/file.txt","context":"Testing"}' \
        | jq -r '.decision' 2>/dev/null)
    if [ "$DECISION" = "approve" ] || [ "$DECISION" = "deny" ]; then
        print_success "Confirmation request endpoint working"
    else
        print_error "Confirmation request endpoint failed"
    fi
}

print_summary() {
    print_header "Deployment Summary"

    echo "GAIA_GO Phase 9+10 Staging Deployment Complete!"
    echo ""
    echo "Service Endpoints:"
    echo "  API Server:      http://localhost:8080"
    echo "  Health Check:    http://localhost:8080/health"
    echo "  Prometheus:      http://localhost:9091"
    echo "  PostgreSQL:      localhost:5432"
    echo ""
    echo "Phase 10 Endpoints:"
    echo "  Confirm Request:     POST   http://localhost:8080/api/claude/confirm/request"
    echo "  Session Preferences: GET/POST http://localhost:8080/api/claude/confirm/preferences/{sessionID}"
    echo "  Patterns:            GET/POST http://localhost:8080/api/claude/confirm/patterns"
    echo "  Statistics:          GET    http://localhost:8080/api/claude/confirm/stats"
    echo ""
    echo "Database:"
    echo "  Host:     localhost"
    echo "  Port:     5432"
    echo "  Database: gaia_go_staging"
    echo "  User:     gaia_user"
    echo ""
    echo "Docker Commands:"
    echo "  View logs:     docker-compose -f deployment/docker-compose.staging.yml logs -f gaia_go"
    echo "  Stop services: docker-compose -f deployment/docker-compose.staging.yml down"
    echo "  Restart:       docker-compose -f deployment/docker-compose.staging.yml restart gaia_go"
    echo ""
    print_success "Ready for testing!"
}

# Main execution
main() {
    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            setup_env
            build_binary
            start_services
            run_tests
            print_summary
            ;;
        stop)
            print_header "Stopping Services"
            cd "$DEPLOYMENT_DIR"
            docker-compose -f docker-compose.staging.yml down
            print_success "Services stopped"
            ;;
        restart)
            print_header "Restarting Services"
            cd "$DEPLOYMENT_DIR"
            docker-compose -f docker-compose.staging.yml restart
            print_success "Services restarted"
            ;;
        logs)
            cd "$DEPLOYMENT_DIR"
            docker-compose -f docker-compose.staging.yml logs -f gaia_go
            ;;
        status)
            print_header "Service Status"
            cd "$DEPLOYMENT_DIR"
            docker-compose -f docker-compose.staging.yml ps
            ;;
        *)
            echo "Usage: $0 {deploy|stop|restart|logs|status}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Build and deploy to staging (default)"
            echo "  stop     - Stop all services"
            echo "  restart  - Restart services"
            echo "  logs     - Stream application logs"
            echo "  status   - Show service status"
            exit 1
            ;;
    esac
}

main "$@"
