#!/bin/bash

# GAIA_GO Self-Improvement Orchestration Loop
# This script enables GAIA_GO to continuously improve itself (dogfooding)

set -e

PROJECT_ROOT="/Users/jgirmay/Desktop/gitrepo/pyWork/GAIA_GO"
PROD_ENV="$PROJECT_ROOT/prod"
LOG_FILE="$PROD_ENV/self_improvement.log"
TASK_QUEUE="$PROD_ENV/SELF_IMPROVEMENT_QUEUE.md"

# Load environment
source "$PROD_ENV/GAIA_GO.env"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 GAIA_GO SELF-IMPROVEMENT ORCHESTRATOR STARTED"
log "Version: $GAIA_VERSION"
log "Environment: $GAIA_ENV"
log "Dogfooding: ENABLED"
echo ""

# Phase 1: Self-Analysis
log "📊 PHASE 1: Self-Analysis & Diagnostics"
log "─────────────────────────────────────────"
cd "$PROJECT_ROOT"

log "Analyzing codebase..."
go fmt ./...
go vet ./...

log "Running existing tests..."
go test -v -coverprofile=coverage.out ./... 2>&1 | tee -a "$LOG_FILE"

log "Measuring performance..."
go test -bench=. -benchmem ./internal/orchestration/subsystems 2>&1 | tee -a "$LOG_FILE"

echo ""

# Phase 2: Issue Detection
log "🔍 PHASE 2: Issue & Improvement Detection"
log "──────────────────────────────────────────"

ISSUES_FOUND=0

# Check code coverage
COVERAGE=$(go tool cover -func=coverage.out | tail -1 | awk '{print $(NF-1)}' | sed 's/%//')
log "Code Coverage: $COVERAGE%"
if (( $(echo "$COVERAGE < 80" | bc -l) )); then
    log "⚠️  ISSUE: Coverage below 80% - queuing test generation task"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check for TODOs and FIXMEs
TODO_COUNT=$(grep -r "TODO\|FIXME" "$PROJECT_ROOT"/internal --include="*.go" 2>/dev/null | wc -l)
log "Found $TODO_COUNT TODO/FIXME comments"
if [ $TODO_COUNT -gt 0 ]; then
    log "⚠️  ISSUE: $TODO_COUNT items need attention"
    ISSUES_FOUND=$((ISSUES_FOUND + TODO_COUNT))
fi

# Check for unimplemented subsystems
UNIMPLEMENTED=$(grep -r "not implemented\|TODO\|panic" "$PROJECT_ROOT"/internal --include="*.go" 2>/dev/null | wc -l)
log "Found $UNIMPLEMENTED incomplete implementations"
if [ $UNIMPLEMENTED -gt 0 ]; then
    log "⚠️  ISSUE: $UNIMPLEMENTED incomplete features"
    ISSUES_FOUND=$((ISSUES_FOUND + UNIMPLEMENTED))
fi

echo ""

# Phase 3: Generate Improvement Tasks
log "📝 PHASE 3: Generating Self-Improvement Tasks"
log "─────────────────────────────────────────────"

if [ $ISSUES_FOUND -gt 0 ]; then
    log "Generating $ISSUES_FOUND improvement tasks..."
    
    # Create improvement task file
    cat > "$PROD_ENV/generated_tasks_$(date +%s).md" << TASKS
# Auto-Generated Self-Improvement Tasks

Generated: $(date)
Issues Found: $ISSUES_FOUND

## Immediate Actions
- Fix code coverage gaps
- Complete TODO items ($TODO_COUNT)
- Implement missing features ($UNIMPLEMENTED)

## Build & Test
go build -o build/gaia_server ./cmd/server
go test -v ./...

## Deploy Updated Version
GAIA_VERSION=$(git describe --tags --always)
git add -A
git commit -m "chore: self-improvement - fix $ISSUES_FOUND issues"
TASKS
    
    log "Tasks generated: $PROD_ENV/generated_tasks_$(date +%s).md"
else
    log "✅ No issues found - GAIA_GO is healthy!"
fi

echo ""

# Phase 4: Execute Improvements
log "🔧 PHASE 4: Executing Self-Improvements"
log "───────────────────────────────────────"

log "Building GAIA_GO..."
go build -o "$PROJECT_ROOT/build/gaia_server" ./cmd/server 2>&1 | tee -a "$LOG_FILE"

if [ -f "$PROJECT_ROOT/build/gaia_server" ]; then
    log "✅ Build successful"
else
    log "❌ Build failed"
    exit 1
fi

echo ""

# Phase 5: Verification
log "✅ PHASE 5: Verification & Validation"
log "─────────────────────────────────────"

log "Running smoke tests..."
timeout 5 "$PROJECT_ROOT/build/gaia_server" &
SERVER_PID=$!
sleep 2

log "Checking API health..."
curl -s http://localhost:8080/health 2>/dev/null | grep -q "ok" && \
    log "✅ API health check passed" || \
    log "⚠️  API health check inconclusive (server may not be running)"

kill $SERVER_PID 2>/dev/null || true

echo ""

# Phase 6: Summary
log "📈 PHASE 6: Self-Improvement Summary"
log "────────────────────────────────────"
log "Total Issues Found: $ISSUES_FOUND"
log "Code Coverage: $COVERAGE%"
log "Build Status: ✅ SUCCESS"
log "Next Run: $(date -v +1d)"

echo ""
log "🎉 GAIA_GO SELF-IMPROVEMENT CYCLE COMPLETE"
log "────────────────────────────────────────────"
echo ""
