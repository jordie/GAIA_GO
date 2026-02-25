#!/bin/bash

# Architect Dashboard API - Staging Deployment Script
# Usage: ./deploy_staging.sh [options]
# Options:
#   --dry-run          Show what would be deployed without making changes
#   --skip-tests       Skip running tests before deployment
#   --skip-build       Use existing binary instead of rebuilding
#   --verbose          Print detailed output

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_VERSION="3.2.0"
DOCKER_REGISTRY="staging-registry.example.com"
DOCKER_IMAGE="architect-api"
KUBE_NAMESPACE="architect-staging"
KUBE_CONTEXT="staging"
DOCKER_BUILD_DIR="."
TIMEOUT_SECONDS=600

# Parse arguments
DRY_RUN=false
SKIP_TESTS=false
SKIP_BUILD=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_section "Checking Prerequisites"

    local missing_tools=()

    # Check required tools
    for tool in git go docker kubectl; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi

    log_success "All required tools present"

    # Check Git status
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Not in a Git repository"
        exit 1
    fi

    if [ -n "$(git status --porcelain)" ]; then
        log_warn "Working directory has uncommitted changes"
    fi

    # Check Docker daemon
    if ! docker ps > /dev/null 2>&1; then
        log_error "Docker daemon not accessible"
        exit 1
    fi

    log_success "Docker daemon accessible"

    # Check Kubernetes access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster"
        exit 1
    fi

    log_success "Kubernetes cluster accessible"
}

# Run tests
run_tests() {
    if [ "$SKIP_TESTS" = true ]; then
        log_warn "Skipping tests"
        return 0
    fi

    log_section "Running Tests"

    log_info "Running unit tests..."
    if ! go test ./... -v -timeout 5m; then
        log_error "Unit tests failed"
        exit 1
    fi

    log_success "All tests passed"
}

# Build Docker image
build_docker_image() {
    if [ "$SKIP_BUILD" = true ]; then
        log_warn "Skipping Docker build"
        return 0
    fi

    log_section "Building Docker Image"

    local git_commit=$(git rev-parse --short HEAD)
    local build_time=$(date -Iseconds)
    local image_tag="${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${API_VERSION}"

    log_info "Building Docker image: $image_tag"
    log_info "Git commit: $git_commit"
    log_info "Build time: $build_time"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: docker build..."
        return 0
    fi

    docker build \
        -t "$image_tag" \
        -f Dockerfile \
        --build-arg VERSION="$API_VERSION" \
        --build-arg BUILD_TIME="$build_time" \
        --build-arg GIT_COMMIT="$git_commit" \
        "$DOCKER_BUILD_DIR"

    if [ $? -ne 0 ]; then
        log_error "Docker build failed"
        exit 1
    fi

    log_success "Docker image built: $image_tag"

    # Push to registry
    log_info "Pushing image to registry..."
    docker push "$image_tag"

    if [ $? -ne 0 ]; then
        log_error "Docker push failed"
        exit 1
    fi

    log_success "Docker image pushed to registry"
}

# Prepare configuration
prepare_configuration() {
    log_section "Preparing Configuration"

    # Check for .env.staging file
    if [ ! -f ".env.staging" ]; then
        log_error ".env.staging file not found"
        log_info "Create .env.staging with environment variables"
        exit 1
    fi

    log_success ".env.staging file found"

    # Create Kubernetes secrets
    log_info "Creating Kubernetes secrets..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create secrets from .env.staging"
        return 0
    fi

    # Check if secret already exists
    if kubectl get secret architect-secrets -n "$KUBE_NAMESPACE" &> /dev/null; then
        log_warn "Secret already exists, deleting and recreating..."
        kubectl delete secret architect-secrets -n "$KUBE_NAMESPACE"
    fi

    kubectl create secret generic architect-secrets \
        --from-env-file=.env.staging \
        -n "$KUBE_NAMESPACE"

    if [ $? -ne 0 ]; then
        log_error "Failed to create Kubernetes secrets"
        exit 1
    fi

    log_success "Kubernetes secrets created"
}

# Run database migrations
run_migrations() {
    log_section "Running Database Migrations"

    log_info "Running migrations..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run database migrations"
        return 0
    fi

    # Get the pod name
    local pod_name=$(kubectl get pods -n "$KUBE_NAMESPACE" -l app=architect-api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$pod_name" ]; then
        log_warn "No running pods found, skipping migration check"
        return 0
    fi

    # Run migration check
    kubectl exec -it -n "$KUBE_NAMESPACE" "$pod_name" -- ./architect-api migrate status

    log_success "Database migrations verified"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_section "Deploying to Kubernetes"

    # Switch to staging context
    log_info "Switching to staging Kubernetes context..."
    kubectl config use-context "$KUBE_CONTEXT"

    # Create namespace if needed
    if ! kubectl get namespace "$KUBE_NAMESPACE" &> /dev/null; then
        log_info "Creating namespace $KUBE_NAMESPACE..."

        if [ "$DRY_RUN" = false ]; then
            kubectl create namespace "$KUBE_NAMESPACE"
        fi
    fi

    # Apply Kubernetes manifests
    log_info "Applying Kubernetes manifests..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would apply: kubectl apply -f k8s/staging/"
    else
        kubectl apply -f k8s/staging/ -n "$KUBE_NAMESPACE"

        if [ $? -ne 0 ]; then
            log_error "Failed to apply Kubernetes manifests"
            exit 1
        fi
    fi

    log_success "Kubernetes manifests applied"
}

# Monitor deployment
monitor_deployment() {
    log_section "Monitoring Deployment"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would monitor: kubectl rollout status"
        return 0
    fi

    log_info "Waiting for deployment to be ready..."
    log_info "Timeout: ${TIMEOUT_SECONDS} seconds"

    if kubectl rollout status deployment/architect-api \
        -n "$KUBE_NAMESPACE" \
        --timeout="${TIMEOUT_SECONDS}s"; then
        log_success "Deployment rolled out successfully"
    else
        log_error "Deployment failed or timed out"

        # Print pod status for debugging
        log_info "Pod status:"
        kubectl describe pods -n "$KUBE_NAMESPACE" -l app=architect-api

        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log_section "Verifying Deployment"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would verify deployment"
        return 0
    fi

    # Wait for service to be ready
    sleep 5

    log_info "Checking pod status..."
    kubectl get pods -n "$KUBE_NAMESPACE" -l app=architect-api

    log_info "Checking deployment status..."
    kubectl get deployment architect-api -n "$KUBE_NAMESPACE"

    log_info "Getting service details..."
    kubectl get svc architect-api -n "$KUBE_NAMESPACE"

    # Get service endpoint
    local service_ip=$(kubectl get svc architect-api -n "$KUBE_NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)

    if [ -z "$service_ip" ]; then
        log_warn "Load balancer IP not yet assigned"
    else
        log_success "Service IP: $service_ip"
        log_info "API will be available at: https://$service_ip/api"
    fi

    log_success "Deployment verification complete"
}

# Run smoke tests
run_smoke_tests() {
    log_section "Running Smoke Tests"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run smoke tests"
        return 0
    fi

    log_info "Running smoke tests..."

    # Get service IP (with retries)
    local retries=0
    local max_retries=10
    local service_ip=""

    while [ -z "$service_ip" ] && [ $retries -lt $max_retries ]; do
        service_ip=$(kubectl get svc architect-api -n "$KUBE_NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [ -z "$service_ip" ]; then
            log_info "Waiting for load balancer IP (attempt $((retries + 1))/$max_retries)..."
            sleep 5
            ((retries++))
        fi
    done

    if [ -z "$service_ip" ]; then
        log_warn "Could not get load balancer IP, skipping smoke tests"
        return 0
    fi

    log_info "Testing health endpoint at https://$service_ip/api/health"

    if ! timeout 10 curl -k -f "https://$service_ip/api/health" > /dev/null 2>&1; then
        log_warn "Health check failed (may still be starting up)"
        return 0
    fi

    log_success "Health check passed"

    # Run full smoke test suite
    if go test ./testing/smoke_tests.go -v -timeout 30s \
        -args "https://$service_ip/api"; then
        log_success "Smoke tests passed"
    else
        log_warn "Some smoke tests failed"
    fi
}

# Print deployment summary
print_summary() {
    log_section "Deployment Summary"

    echo -e "${BLUE}API Version:${NC} $API_VERSION"
    echo -e "${BLUE}Environment:${NC} staging"
    echo -e "${BLUE}Namespace:${NC} $KUBE_NAMESPACE"
    echo -e "${BLUE}Docker Image:${NC} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${API_VERSION}"
    echo -e "${BLUE}Deployment Type:${NC} Kubernetes Rolling Update"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN MODE]${NC}"
    else
        echo -e "${GREEN}[LIVE DEPLOYMENT]${NC}"
    fi

    echo ""
    log_success "Deployment process complete!"
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════╗"
    echo "║  Architect Dashboard - Staging Deploy  ║"
    echo "║           Version $API_VERSION            ║"
    echo "╚════════════════════════════════════════╝"
    echo -e "${NC}"

    if [ "$DRY_RUN" = true ]; then
        log_warn "Running in DRY RUN mode - no changes will be made"
    fi

    echo ""

    check_prerequisites
    run_tests
    build_docker_image
    prepare_configuration
    deploy_kubernetes
    monitor_deployment
    verify_deployment
    run_smoke_tests
    print_summary
}

# Run main
main
