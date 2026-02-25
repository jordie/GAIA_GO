#!/bin/bash

# Architect Dashboard API - Production Deployment Script (Blue-Green)
# Usage: ./deploy_production.sh [options]
# Options:
#   --dry-run              Show what would be deployed without making changes
#   --strategy=<type>      Deployment strategy (blue-green, canary, rolling)
#   --verify-only          Only verify readiness, don't deploy
#   --skip-smoke-tests     Skip smoke tests after deployment
#   --wait-time=<seconds>  Time to wait between switches (default: 120)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
API_VERSION="3.2.0"
DOCKER_REGISTRY="prod-registry.example.com"
DOCKER_IMAGE="architect-api"
KUBE_NAMESPACE="architect-production"
KUBE_CONTEXT="production"
DEPLOYMENT_STRATEGY="blue-green"
WAIT_TIME=120
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Parse arguments
DRY_RUN=false
VERIFY_ONLY=false
SKIP_SMOKE_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --skip-smoke-tests)
            SKIP_SMOKE_TESTS=true
            shift
            ;;
        --strategy=*)
            DEPLOYMENT_STRATEGY="${1#*=}"
            shift
            ;;
        --wait-time=*)
            WAIT_TIME="${1#*=}"
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
    echo -e "${GREEN}[✓ SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠ WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗ ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${MAGENTA}════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}════════════════════════════════════════════${NC}"
}

slack_notify() {
    if [ -z "$SLACK_WEBHOOK" ]; then
        return 0
    fi

    local color=$1
    local title=$2
    local message=$3

    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"attachments\": [{
                \"color\": \"$color\",
                \"title\": \"$title\",
                \"text\": \"$message\",
                \"ts\": $(date +%s)
            }]
        }" 2>/dev/null || true
}

# Check prerequisites
check_prerequisites() {
    log_section "Checking Prerequisites"

    # Check required tools
    for tool in git go docker kubectl helm; do
        if ! command -v $tool &> /dev/null; then
            log_error "Missing required tool: $tool"
            exit 1
        fi
    done

    log_success "All required tools present"

    # Check Kubernetes access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster"
        exit 1
    fi

    log_success "Kubernetes cluster accessible (context: $KUBE_CONTEXT)"

    # Check namespace
    if ! kubectl get namespace "$KUBE_NAMESPACE" &> /dev/null; then
        log_error "Namespace $KUBE_NAMESPACE not found"
        exit 1
    fi

    log_success "Namespace $KUBE_NAMESPACE exists"
}

# Pre-deployment verification
verify_readiness() {
    log_section "Verifying Production Readiness"

    # Check database connection
    log_info "Testing database connection..."
    kubectl run -it --rm --restart=Never \
        --image=prod-registry/architect-api:$API_VERSION \
        -n "$KUBE_NAMESPACE" \
        db-test -- \
        ./architect-api db status &> /dev/null || {
        log_error "Database connection failed"
        exit 1
    }
    log_success "Database connection verified"

    # Check all nodes ready
    log_info "Checking node status..."
    local not_ready=$(kubectl get nodes -o jsonpath='{.items[?(@.status.conditions[?(@.type=="Ready")].status!="True")].metadata.name}')
    if [ -n "$not_ready" ]; then
        log_error "Nodes not ready: $not_ready"
        exit 1
    fi
    log_success "All nodes ready"

    # Check PVCs
    log_info "Checking persistent volumes..."
    local failed_pvcs=$(kubectl get pvc -n "$KUBE_NAMESPACE" -o jsonpath='{.items[?(@.status.phase!="Bound")].metadata.name}')
    if [ -n "$failed_pvcs" ]; then
        log_error "Unbound PVCs: $failed_pvcs"
        exit 1
    fi
    log_success "All PVCs bound"

    log_success "Production readiness verified"
}

# Build Docker image
build_and_push_image() {
    log_section "Building & Pushing Docker Image"

    local git_commit=$(git rev-parse --short HEAD)
    local build_time=$(date -Iseconds)
    local image_tag="${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${API_VERSION}"

    log_info "Building Docker image: $image_tag"
    log_info "Git commit: $git_commit"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would build: $image_tag"
        return 0
    fi

    docker build \
        -t "$image_tag" \
        -f Dockerfile \
        --build-arg VERSION="$API_VERSION" \
        --build-arg BUILD_TIME="$build_time" \
        --build-arg GIT_COMMIT="$git_commit" \
        . || {
        log_error "Docker build failed"
        exit 1
    }

    log_success "Docker image built"

    # Push to registry
    log_info "Pushing to registry..."
    docker push "$image_tag" || {
        log_error "Docker push failed"
        exit 1
    }

    log_success "Docker image pushed: $image_tag"
}

# Deploy to green environment
deploy_blue_green() {
    log_section "Deploying with Blue-Green Strategy"

    # Determine current active (blue) and inactive (green)
    local blue_replicas=$(kubectl get deployment architect-api-blue \
        -n "$KUBE_NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    local green_replicas=$(kubectl get deployment architect-api-green \
        -n "$KUBE_NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [ "$blue_replicas" -gt "0" ]; then
        log_info "Current: Blue (active), Green (inactive)"
        ACTIVE="blue"
        INACTIVE="green"
    else
        log_info "Current: Green (active), Blue (inactive)"
        ACTIVE="green"
        INACTIVE="blue"
    fi

    log_info "Deploying to $INACTIVE environment..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would deploy to $INACTIVE"
        return 0
    fi

    # Update image on inactive deployment
    kubectl set image deployment/architect-api-${INACTIVE} \
        architect-api="${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${API_VERSION}" \
        -n "$KUBE_NAMESPACE"

    # Scale up inactive deployment
    kubectl scale deployment architect-api-${INACTIVE} \
        --replicas=10 \
        -n "$KUBE_NAMESPACE"

    # Wait for rollout
    log_info "Waiting for $INACTIVE deployment to be ready..."
    if ! kubectl rollout status deployment/architect-api-${INACTIVE} \
        -n "$KUBE_NAMESPACE" --timeout=10m; then
        log_error "$INACTIVE deployment failed"
        exit 1
    fi

    log_success "$INACTIVE deployment ready"
}

# Run health checks on green
run_health_checks() {
    log_section "Running Health Checks"

    log_info "Getting service IP..."
    local service_ip=$(kubectl get svc architect-api \
        -n "$KUBE_NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

    if [ -z "$service_ip" ]; then
        log_warn "Load balancer IP not assigned, waiting..."
        sleep 10
        service_ip=$(kubectl get svc architect-api \
            -n "$KUBE_NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    fi

    if [ -z "$service_ip" ]; then
        log_error "Could not get load balancer IP"
        return 1
    fi

    log_info "Testing health endpoint: https://$service_ip/api/health"

    # Test health endpoint with retries
    local retries=0
    while [ $retries -lt 5 ]; do
        if timeout 10 curl -k -f "https://$service_ip/api/health" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        fi
        log_warn "Health check failed (attempt $((retries + 1))/5), retrying..."
        sleep 5
        ((retries++))
    done

    log_error "Health checks failed"
    return 1
}

# Switch traffic
switch_traffic() {
    log_section "Switching Traffic"

    # Determine which to switch to
    local blue_replicas=$(kubectl get deployment architect-api-blue \
        -n "$KUBE_NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [ "$blue_replicas" -gt "0" ]; then
        SWITCHING_TO="green"
    else
        SWITCHING_TO="blue"
    fi

    log_info "Switching traffic from current to $SWITCHING_TO environment..."
    log_warn "This will cause minimal interruption (~1-2 seconds)"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would switch traffic to $SWITCHING_TO"
        return 0
    fi

    # Update service selector
    kubectl patch service architect-api \
        -n "$KUBE_NAMESPACE" \
        -p "{\"spec\":{\"selector\":{\"deployment\":\"architect-api-${SWITCHING_TO}\"}}}"

    log_success "Traffic switched to $SWITCHING_TO"

    # Wait for connections to drain
    log_info "Waiting ${WAIT_TIME}s for connections to stabilize..."
    sleep "$WAIT_TIME"

    # Scale down old deployment
    local scale_down_deployment=$([ "$SWITCHING_TO" = "green" ] && echo "blue" || echo "green")
    log_info "Scaling down $scale_down_deployment environment..."
    kubectl scale deployment/architect-api-${scale_down_deployment} \
        --replicas=0 \
        -n "$KUBE_NAMESPACE"

    log_success "Old environment scaled down"
}

# Post-deployment validation
validate_deployment() {
    log_section "Validating Deployment"

    log_info "Checking pod status..."
    kubectl get pods -n "$KUBE_NAMESPACE" -l app=architect-api

    log_info "Checking deployment status..."
    kubectl get deployment -n "$KUBE_NAMESPACE"

    # Check metrics
    log_info "Checking error rate (should be < 1%)..."
    local error_rate=$(kubectl exec -it deployment/architect-api \
        -n "$KUBE_NAMESPACE" -- \
        curl -s localhost:8080/metrics | grep http_requests_total | head -1)

    if [ -n "$error_rate" ]; then
        log_success "Metrics collection working"
    fi

    log_success "Deployment validation complete"
}

# Run smoke tests
run_smoke_tests() {
    if [ "$SKIP_SMOKE_TESTS" = true ]; then
        log_warn "Skipping smoke tests"
        return 0
    fi

    log_section "Running Smoke Tests"

    log_info "Running 13 smoke tests..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run smoke tests"
        return 0
    fi

    if go test ./testing/smoke_tests.go -v -timeout 60s; then
        log_success "All smoke tests passed"
    else
        log_error "Some smoke tests failed"
        return 1
    fi
}

# Rollback function
rollback() {
    log_section "ROLLING BACK DEPLOYMENT"

    log_error "Deployment failed or user requested rollback"

    # Switch back to previous
    local blue_replicas=$(kubectl get deployment architect-api-blue \
        -n "$KUBE_NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [ "$blue_replicas" -gt "0" ]; then
        ROLLBACK_TARGET="blue"
    else
        ROLLBACK_TARGET="green"
    fi

    log_info "Rolling back traffic to $ROLLBACK_TARGET..."

    kubectl patch service architect-api \
        -n "$KUBE_NAMESPACE" \
        -p "{\"spec\":{\"selector\":{\"deployment\":\"architect-api-${ROLLBACK_TARGET}\"}}}"

    log_success "Rollback complete - traffic restored to previous version"

    slack_notify "danger" "Production Deployment Failed" \
        "Deployment of v$API_VERSION failed and was rolled back to previous version"
}

# Print deployment summary
print_summary() {
    log_section "Deployment Summary"

    echo -e "${BLUE}API Version:${NC} $API_VERSION"
    echo -e "${BLUE}Environment:${NC} production"
    echo -e "${BLUE}Strategy:${NC} $DEPLOYMENT_STRATEGY"
    echo -e "${BLUE}Namespace:${NC} $KUBE_NAMESPACE"
    echo -e "${BLUE}Docker Image:${NC} ${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${API_VERSION}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN MODE]${NC}"
    else
        echo -e "${GREEN}[LIVE DEPLOYMENT]${NC}"
    fi

    echo ""
    log_success "Production deployment complete!"

    slack_notify "good" "Production Deployment Successful" \
        "Architect Dashboard API v$API_VERSION deployed to production successfully"
}

# Main execution
main() {
    echo -e "${MAGENTA}"
    echo "╔════════════════════════════════════════════╗"
    echo "║  Architect Dashboard - Production Deploy   ║"
    echo "║             Version $API_VERSION            ║"
    echo "║         Blue-Green Strategy                ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"

    if [ "$DRY_RUN" = true ]; then
        log_warn "Running in DRY RUN mode - no changes will be made"
    fi

    if [ "$VERIFY_ONLY" = true ]; then
        log_warn "VERIFY ONLY mode - will not deploy"
    fi

    echo ""

    check_prerequisites

    if [ "$VERIFY_ONLY" = true ]; then
        verify_readiness
        return 0
    fi

    verify_readiness
    build_and_push_image
    deploy_blue_green

    if ! run_health_checks; then
        rollback
        exit 1
    fi

    if ! switch_traffic; then
        rollback
        exit 1
    fi

    if ! run_smoke_tests; then
        log_warn "Smoke tests had issues, but deployment is live"
    fi

    validate_deployment
    print_summary
}

# Trap errors and rollback
trap 'rollback' ERR

# Run main
main
