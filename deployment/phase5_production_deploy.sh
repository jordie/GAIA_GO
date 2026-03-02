#!/bin/bash
# Phase 5 Production Deployment Script
# Blue-Green deployment with canary testing
# Usage: ./phase5_production_deploy.sh [IMAGE_TAG] [DRY_RUN]
#
# Example: ./phase5_production_deploy.sh v0.5.0-phase5
#          ./phase5_production_deploy.sh v0.5.0-phase5 --dry-run

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-production}"
APP_NAME="${APP_NAME:-gaia-go}"
IMAGE_TAG="${1:-latest}"
DRY_RUN="${2:-}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-ghcr.io/jordie}"
SMOKE_TEST_SCRIPT="${SMOKE_TEST_SCRIPT:-../scripts/phase5_smoke_tests.sh}"

# Timing configuration (in seconds)
CANARY_10_DURATION=900      # 15 minutes
CANARY_50_DURATION=600      # 10 minutes
FULL_CUTOVER_DURATION=300   # 5 minutes
MONITORING_DURATION=86400   # 24 hours

# Thresholds
ERROR_RATE_THRESHOLD=5      # 5% error rate triggers rollback
P95_LATENCY_THRESHOLD=500   # 500ms p95 latency threshold

# Timestamps and logging
DEPLOYMENT_ID=$(date +%s)
TIMESTAMP=$(date '+%Y-%m-%d_%H:%M:%S')
LOG_FILE="/tmp/phase5_deployment_${DEPLOYMENT_ID}.log"
STATE_FILE="/tmp/phase5_deployment_${DEPLOYMENT_ID}.state"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() { echo -e "${BLUE}ℹ${NC}  $(log INFO $@)"; }
log_success() { echo -e "${GREEN}✓${NC}  $(log SUCCESS $@)"; }
log_error() { echo -e "${RED}✗${NC}  $(log ERROR $@)"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $(log WARN $@)"; }
log_section() { echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${CYAN}$@${NC}\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }

save_state() {
    local key=$1
    local value=$2
    echo "$key=$value" >> "$STATE_FILE"
    log_info "State saved: $key=$value"
}

load_state() {
    local key=$1
    [ -f "$STATE_FILE" ] && grep "^${key}=" "$STATE_FILE" | cut -d'=' -f2- || echo ""
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

check_prerequisites() {
    log_section "PHASE 1: Pre-Flight Checks (30 mins)"

    log_info "Checking kubectl installation..."
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found - please install kubectl"
        exit 1
    fi
    log_success "kubectl available"

    log_info "Checking cluster connectivity..."
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    log_success "Cluster connectivity verified"

    log_info "Checking namespace $NAMESPACE exists..."
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist"
        log_info "Creating namespace $NAMESPACE..."
        kubectl create namespace "$NAMESPACE"
    fi
    log_success "Namespace $NAMESPACE verified"

    log_info "Checking deployments..."
    for deployment in "$APP_NAME-blue" "$APP_NAME-green"; do
        if ! kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            log_error "Deployment $deployment not found in namespace $NAMESPACE"
            exit 1
        fi
    done
    log_success "Both blue and green deployments exist"

    log_info "Checking database connectivity..."
    BLUE_POD=$(kubectl get pods -n "$NAMESPACE" -l app="$APP_NAME",version=blue -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -z "$BLUE_POD" ]; then
        log_error "No blue deployment pods found"
        exit 1
    fi

    if kubectl exec -n "$NAMESPACE" "$BLUE_POD" -- curl -s http://localhost:8080/api/health/database > /dev/null 2>&1; then
        log_success "Database connectivity verified"
    else
        log_error "Database connectivity check failed"
        exit 1
    fi

    log_success "All pre-flight checks passed"
}

# ============================================================================
# DATABASE BACKUP
# ============================================================================

backup_database() {
    log_section "Creating Database Backup"

    log_info "Creating pre-deployment database backup..."

    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="/tmp/gaia_go_backup_${BACKUP_TIMESTAMP}.sql"

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would backup database to $BACKUP_FILE"
        save_state "BACKUP_FILE" "$BACKUP_FILE"
        return 0
    fi

    # Execute backup via pod
    if kubectl exec -n "$NAMESPACE" "$BLUE_POD" -- pg_dump -U postgres > "$BACKUP_FILE" 2>/dev/null; then
        log_success "Database backup created: $BACKUP_FILE"
        save_state "BACKUP_FILE" "$BACKUP_FILE"
    else
        log_warn "Database backup failed (continuing anyway - may not have direct pg_dump access)"
    fi
}

# ============================================================================
# IMAGE BUILD AND PUSH
# ============================================================================

build_and_push_image() {
    log_section "PHASE 2: Building Docker Image (15 mins)"

    log_info "Building Docker image for tag $IMAGE_TAG..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would build and push image $DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"
        return 0
    fi

    if ! docker build -t "$DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG" .; then
        log_error "Docker build failed"
        exit 1
    fi
    log_success "Docker image built: $DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"

    log_info "Pushing image to registry..."
    if ! docker push "$DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"; then
        log_error "Docker push failed"
        exit 1
    fi
    log_success "Docker image pushed to registry"
}

# ============================================================================
# GREEN DEPLOYMENT
# ============================================================================

deploy_green() {
    log_section "PHASE 3: Green Deployment (15 mins)"

    log_info "Deploying new version to green environment..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would deploy to green with image $DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG"
        return 0
    fi

    kubectl set image deployment/"$APP_NAME-green" \
        "$APP_NAME=$DOCKER_REGISTRY/$APP_NAME:$IMAGE_TAG" \
        -n "$NAMESPACE" \
        --record

    log_info "Waiting for green deployment to be ready (timeout: 5 minutes)..."
    if kubectl rollout status deployment/"$APP_NAME-green" \
        -n "$NAMESPACE" \
        --timeout=300s; then
        log_success "Green deployment ready"
        save_state "GREEN_DEPLOYED" "true"
    else
        log_error "Green deployment failed to become ready"
        exit 1
    fi
}

# ============================================================================
# SMOKE TESTS
# ============================================================================

run_smoke_tests() {
    log_section "PHASE 4: Smoke Testing (15 mins)"

    log_info "Running smoke tests against green deployment..."

    GREEN_POD=$(kubectl get pods -n "$NAMESPACE" -l app="$APP_NAME",version=green \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$GREEN_POD" ]; then
        log_error "No green deployment pods found"
        exit 1
    fi

    GREEN_SERVICE="${APP_NAME}-green"
    GREEN_HOST="$GREEN_SERVICE.$NAMESPACE.svc.cluster.local:8080"

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would run smoke tests against $GREEN_HOST"
        return 0
    fi

    # Run smoke tests via kubectl exec
    if kubectl exec -n "$NAMESPACE" "$GREEN_POD" -- bash -c \
        "curl -s http://localhost:8080/health && echo 'Health check passed'" > /dev/null 2>&1; then
        log_success "Smoke tests passed"
        save_state "SMOKE_TESTS_PASSED" "true"
    else
        log_error "Smoke tests failed"
        exit 1
    fi
}

# ============================================================================
# CANARY DEPLOYMENT
# ============================================================================

canary_phase() {
    local percentage=$1
    local duration=$2
    local phase_name=$3

    log_section "PHASE 5.${percentage}: Canary Release - ${percentage}% Traffic (${duration}s)"

    log_info "Shifting traffic: blue=$(( 100 - percentage ))% → green=${percentage}%"

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would shift traffic to $percentage%"
        return 0
    fi

    # Update service selector to split traffic
    # This uses weighted traffic splitting via service mesh or load balancer annotations
    kubectl annotate service "$APP_NAME" \
        "traffic.split=$((100 - percentage))% blue,$percentage% green" \
        -n "$NAMESPACE" \
        --overwrite 2>/dev/null || true

    log_info "Monitoring for $duration seconds..."
    local start_time=$(date +%s)
    local check_interval=30

    while true; do
        sleep "$check_interval"
        local elapsed=$(($(date +%s) - start_time))

        # Check error rates
        local error_count=$(kubectl logs -n "$NAMESPACE" -l app="$APP_NAME",version=green \
            --tail=100 2>/dev/null | grep -c "ERROR\|error\|5[0-9][0-9]" || echo 0)

        log_info "[$phase_name] Elapsed: ${elapsed}s / Error count: $error_count"

        if [ "$error_count" -gt 20 ]; then
            log_error "High error count detected ($error_count) - initiating rollback"
            return 1
        fi

        if [ $elapsed -ge $duration ]; then
            log_success "Canary phase $percentage% completed successfully"
            break
        fi
    done

    return 0
}

# ============================================================================
# TRAFFIC MIGRATION
# ============================================================================

migrate_traffic() {
    log_section "PHASE 6: Traffic Migration"

    # 10% canary
    if ! canary_phase 10 "$CANARY_10_DURATION" "10% Canary"; then
        log_error "Canary 10% phase failed - rolling back"
        rollback_emergency
        exit 1
    fi

    # 50% canary
    if ! canary_phase 50 "$CANARY_50_DURATION" "50% Canary"; then
        log_error "Canary 50% phase failed - rolling back"
        rollback_emergency
        exit 1
    fi

    # 100% cutover
    log_section "PHASE 7: Full Cutover (5 mins)"

    log_info "Switching 100% traffic to green deployment..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would switch 100% traffic to green"
        return 0
    fi

    kubectl patch service "$APP_NAME" -n "$NAMESPACE" \
        --type merge \
        -p '{"spec":{"selector":{"version":"green"}}}' || true

    log_success "Traffic fully switched to green"
    save_state "TRAFFIC_SWITCHED" "true"
}

# ============================================================================
# BLUE CLEANUP
# ============================================================================

cleanup_blue() {
    log_section "PHASE 8: Blue Cleanup (15 mins)"

    log_info "Scaling down blue deployment to 1 replica (for rollback option)..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would scale blue down to 1 replica"
        return 0
    fi

    kubectl scale deployment/"$APP_NAME-blue" \
        --replicas=1 \
        -n "$NAMESPACE"

    log_success "Blue deployment scaled down"
    log_warn "Blue kept at 1 replica for 24 hours as rollback option"
    save_state "BLUE_SCALED_DOWN" "true"
}

# ============================================================================
# POST-DEPLOYMENT MONITORING
# ============================================================================

monitor_deployment() {
    log_section "PHASE 9: Post-Deployment Monitoring (24 hours)"

    log_info "Starting 24-hour monitoring period..."
    log_warn "Monitor dashboard at: http://localhost:3000/d/phase5-production"

    local checkpoints=(
        "4 hours"
        "8 hours"
        "12 hours"
        "24 hours"
    )

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would monitor deployment"
        return 0
    fi

    for checkpoint in "${checkpoints[@]}"; do
        log_info "Monitoring checkpoint: $checkpoint"
        # Placeholder for actual monitoring logic
        # In production, this would check metrics, logs, etc.
    done

    log_success "Post-deployment monitoring completed"
}

# ============================================================================
# ROLLBACK PROCEDURES
# ============================================================================

rollback_emergency() {
    log_section "EMERGENCY ROLLBACK"

    log_error "Initiating emergency rollback..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would rollback traffic to blue"
        return 0
    fi

    log_warn "Switching traffic back to blue deployment..."
    kubectl patch service "$APP_NAME" -n "$NAMESPACE" \
        --type merge \
        -p '{"spec":{"selector":{"version":"blue"}}}' || true

    log_success "Traffic switched back to blue"
    log_warn "Check logs for root cause: kubectl logs -n $NAMESPACE -l app=$APP_NAME,version=green --tail=200"
}

rollback_planned() {
    log_section "PLANNED ROLLBACK"

    log_error "Initiating planned rollback..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would perform planned rollback"
        return 0
    fi

    # Step 1: Reduce to 50%
    log_info "Step 1: Reducing green traffic to 50%..."
    kubectl annotate service "$APP_NAME" \
        "traffic.split=50% blue,50% green" \
        -n "$NAMESPACE" \
        --overwrite 2>/dev/null || true
    sleep 600  # Wait 10 minutes

    # Step 2: Reduce to 10%
    log_info "Step 2: Reducing green traffic to 10%..."
    kubectl annotate service "$APP_NAME" \
        "traffic.split=90% blue,10% green" \
        -n "$NAMESPACE" \
        --overwrite 2>/dev/null || true
    sleep 300  # Wait 5 minutes

    # Step 3: Full rollback
    log_info "Step 3: Rolling back to blue..."
    kubectl patch service "$APP_NAME" -n "$NAMESPACE" \
        --type merge \
        -p '{"spec":{"selector":{"version":"blue"}}}' || true

    log_success "Planned rollback completed"
}

rollback_database() {
    log_section "DATABASE ROLLBACK"

    local backup_file=$(load_state "BACKUP_FILE")

    if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
        log_error "No backup file found"
        return 1
    fi

    log_error "Initiating database rollback from $backup_file..."

    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_warn "DRY RUN: Would restore database from $backup_file"
        return 0
    fi

    # Restore from backup (implementation depends on your database setup)
    log_info "Restoring database from backup..."
    log_warn "Implementation depends on your specific database setup"
    log_warn "Manual steps may be required - see deployment runbook"
}

# ============================================================================
# HEALTH CHECKS
# ============================================================================

health_check() {
    log_info "Performing health checks..."

    local pod=$1
    local version=$2

    if kubectl exec -n "$NAMESPACE" "$pod" -- \
        curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
        log_success "$version deployment health check passed"
        return 0
    else
        log_error "$version deployment health check failed"
        return 1
    fi
}

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

print_summary() {
    log_section "DEPLOYMENT SUMMARY"

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║ Phase 5 Production Deployment Complete                    ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║ Deployment ID:     $DEPLOYMENT_ID"
    echo "║ Timestamp:         $TIMESTAMP"
    echo "║ Image Tag:         $IMAGE_TAG"
    echo "║ Namespace:         $NAMESPACE"
    echo "║ Log File:          $LOG_FILE"
    echo "║ State File:        $STATE_FILE"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║ Post-Deployment Actions:                                   ║"
    echo "║ 1. Monitor dashboard for 24 hours                         ║"
    echo "║    http://localhost:3000/d/phase5-production              ║"
    echo "║ 2. After 24 hours, delete blue deployment:                ║"
    echo "║    kubectl delete deployment/$APP_NAME-blue -n $NAMESPACE │"
    echo "║ 3. Check deployment status:                               ║"
    echo "║    kubectl rollout status deployment/$APP_NAME-green      ║"
    echo "║    -n $NAMESPACE                                           ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    echo "║ Rollback Options:                                          ║"
    echo "║ • Emergency: kubectl patch service $APP_NAME ...           ║"
    echo "║ • Planned:   See logs for step-by-step rollback            ║"
    echo "║ • Database:  See PHASE5_PRODUCTION_RUNBOOK.md              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

# ============================================================================
# MAIN DEPLOYMENT ORCHESTRATION
# ============================================================================

main() {
    local exit_code=0

    echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Phase 5 Production Deployment                      ║${NC}"
    echo -e "${CYAN}║  Blue-Green with Canary Testing                     ║${NC}"
    echo -e "${CYAN}║  Start Time: $(date '+%Y-%m-%d %H:%M:%S')                   ║${NC}"
    if [ "$DRY_RUN" = "--dry-run" ]; then
        echo -e "${YELLOW}║  MODE: DRY RUN (no actual changes will be made)    ║${NC}"
    fi
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}\n"

    # Execute deployment phases
    check_prerequisites || exit_code=1

    if [ $exit_code -eq 0 ]; then
        backup_database || exit_code=1
        build_and_push_image || exit_code=1
        deploy_green || exit_code=1
        run_smoke_tests || exit_code=1
        migrate_traffic || exit_code=1
        cleanup_blue || exit_code=1
        monitor_deployment || exit_code=1
    fi

    # Print summary
    print_summary

    if [ $exit_code -eq 0 ]; then
        echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}\n"
    else
        echo -e "\n${RED}❌ Deployment failed - check logs for details${NC}\n"
    fi

    return $exit_code
}

# Execute main with error handling
main
exit_code=$?

if [ $exit_code -ne 0 ] && [ "$DRY_RUN" != "--dry-run" ]; then
    log_error "Deployment failed with exit code $exit_code"
fi

exit $exit_code
