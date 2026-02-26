#!/bin/bash

# GAIA_GO Deployment Script
# This script automates the deployment of GAIA_GO to production

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_TYPE=${1:-docker-compose}
ENVIRONMENT=${2:-staging}

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if [ "$DEPLOYMENT_TYPE" == "docker-compose" ] && ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    if [ "$DEPLOYMENT_TYPE" == "kubernetes" ] && ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Generate SSL certificates
generate_certificates() {
    log_info "Generating SSL certificates..."

    CERT_DIR="$PROJECT_ROOT/certs"
    mkdir -p "$CERT_DIR"

    if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
        log_warn "Certificates already exist, skipping generation"
        return
    fi

    openssl req -x509 -newkey rsa:4096 \
        -keyout "$CERT_DIR/server.key" \
        -out "$CERT_DIR/server.crt" \
        -days 365 -nodes \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$ENVIRONMENT.gaia_go.local"

    log_info "SSL certificates generated in $CERT_DIR"
}

# Build Docker image
build_docker_image() {
    log_info "Building Docker image for $ENVIRONMENT..."

    docker build -f "$PROJECT_ROOT/Dockerfile.prod" \
        -t "gaia_go:1.0.0" \
        -t "gaia_go:latest" \
        "$PROJECT_ROOT"

    log_info "Docker image built successfully"
}

# Deploy using Docker Compose
deploy_docker_compose() {
    log_info "Deploying with Docker Compose to $ENVIRONMENT..."

    cd "$PROJECT_ROOT"

    # Set up environment variables
    export COMPOSE_PROJECT_NAME="gaia_${ENVIRONMENT}"

    # Start services
    docker-compose -f docker-compose.prod.yml up -d

    log_info "Waiting for services to become healthy..."

    # Wait for database
    for i in {1..30}; do
        if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U gaia_user &> /dev/null; then
            log_info "Database is ready"
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for GAIA_GO nodes
    for node in gaia_node_1 gaia_node_2 gaia_node_3; do
        for i in {1..30}; do
            if docker-compose -f docker-compose.prod.yml exec -T "$node" curl -f http://localhost:8080/health &> /dev/null; then
                log_info "$node is ready"
                break
            fi
            echo -n "."
            sleep 2
        done
    done

    log_info "Docker Compose deployment completed"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes cluster..."

    NAMESPACE="gaia-go"

    # Create namespace
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Create secrets
    kubectl create secret generic postgres-secret \
        -n "$NAMESPACE" \
        --from-literal=username=gaia_user \
        --from-literal=password=gaia_secure_password_change_in_prod \
        --dry-run=client -o yaml | kubectl apply -f -

    # Apply manifests
    for manifest in "$PROJECT_ROOT/k8s"/*.yaml; do
        log_info "Applying $manifest..."
        kubectl apply -f "$manifest"
    done

    # Wait for rollout
    log_info "Waiting for StatefulSet rollout..."
    kubectl rollout status statefulset/gaia-go -n "$NAMESPACE" --timeout=5m

    log_info "Kubernetes deployment completed"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."

    if [ "$DEPLOYMENT_TYPE" == "docker-compose" ]; then
        # Check services are running
        docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps

        # Check health
        log_info "Checking cluster health..."
        if curl -s http://localhost:8080/health > /dev/null; then
            log_info "Health check passed"
        else
            log_error "Health check failed"
            exit 1
        fi
    else
        # Kubernetes checks
        kubectl get pods -n gaia-go

        log_info "Checking cluster health via port-forward..."
        kubectl port-forward -n gaia-go svc/gaia-go-lb 8080:8080 &
        PF_PID=$!
        sleep 2

        if curl -s http://localhost:8080/health > /dev/null; then
            log_info "Health check passed"
            kill $PF_PID
        else
            log_error "Health check failed"
            kill $PF_PID
            exit 1
        fi
    fi

    log_info "Deployment verification completed"
}

# Show status
show_status() {
    log_info "Deployment Status"
    log_info "=================="

    if [ "$DEPLOYMENT_TYPE" == "docker-compose" ]; then
        echo "Deployment Type: Docker Compose"
        echo "Environment: $ENVIRONMENT"
        echo ""
        echo "Services:"
        docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps

        echo ""
        echo "Access Points:"
        echo "  API: https://localhost"
        echo "  Grafana: http://localhost:3000 (admin/admin)"
        echo "  Prometheus: http://localhost:9090"
    else
        echo "Deployment Type: Kubernetes"
        echo "Environment: $ENVIRONMENT"
        echo ""
        echo "Pods:"
        kubectl get pods -n gaia-go

        echo ""
        echo "Services:"
        kubectl get svc -n gaia-go
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up..."

    if [ "$DEPLOYMENT_TYPE" == "docker-compose" ]; then
        docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" down
        log_info "Docker Compose services stopped"
    fi
}

# Main
main() {
    case "$DEPLOYMENT_TYPE" in
        docker-compose)
            log_info "GAIA_GO Deployment Script (Docker Compose)"
            check_prerequisites
            generate_certificates
            build_docker_image
            deploy_docker_compose
            verify_deployment
            show_status
            ;;
        kubernetes)
            log_info "GAIA_GO Deployment Script (Kubernetes)"
            check_prerequisites
            deploy_kubernetes
            verify_deployment
            show_status
            ;;
        stop)
            log_info "Stopping deployment..."
            cleanup
            ;;
        *)
            echo "Usage: $0 [docker-compose|kubernetes|stop] [environment]"
            echo ""
            echo "Examples:"
            echo "  $0 docker-compose staging    # Deploy with Docker Compose to staging"
            echo "  $0 docker-compose production # Deploy with Docker Compose to production"
            echo "  $0 kubernetes staging        # Deploy to Kubernetes staging"
            echo "  $0 stop                      # Stop Docker Compose deployment"
            exit 1
            ;;
    esac
}

main
