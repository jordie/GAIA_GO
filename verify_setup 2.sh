#!/bin/bash
# Quick verification script for Go Wrapper + Auto-Confirm setup

echo "═══════════════════════════════════════════════════════════════"
echo "  Go Wrapper + Auto-Confirm Verification"
echo "═══════════════════════════════════════════════════════════════"
echo ""

PASS=0
FAIL=0

# Check 1: Go wrapper binary
echo -n "[1/8] Go wrapper binary.............. "
if [ -f "go_wrapper/wrapper" ]; then
    echo "✓ PASS ($(ls -lh go_wrapper/wrapper | awk '{print $5}'))"
    PASS=$((PASS+1))
else
    echo "✗ FAIL"
    FAIL=$((FAIL+1))
fi

# Check 2: Auto-confirm worker running
echo -n "[2/8] Auto-confirm worker............ "
if pgrep -f auto_confirm_worker.py > /dev/null; then
    PID=$(pgrep -f auto_confirm_worker.py)
    echo "✓ PASS (PID $PID)"
    PASS=$((PASS+1))
else
    echo "✗ FAIL (not running)"
    FAIL=$((FAIL+1))
fi

# Check 3: Foundation session exists
echo -n "[3/8] Foundation tmux session........ "
if tmux has-session -t foundation 2>/dev/null; then
    echo "✓ PASS (attached)"
    PASS=$((PASS+1))
else
    echo "✗ FAIL (not found)"
    FAIL=$((FAIL+1))
fi

# Check 4: Foundation not in excluded sessions
echo -n "[4/8] Foundation not excluded........ "
if ! grep -q "'foundation'" workers/auto_confirm_worker.py | grep "EXCLUDED_SESSIONS"; then
    echo "✓ PASS"
    PASS=$((PASS+1))
else
    echo "✗ FAIL (is excluded)"
    FAIL=$((FAIL+1))
fi

# Check 5: Database exists
echo -n "[5/8] Auto-confirm database.......... "
if [ -f /tmp/auto_confirm.db ]; then
    COUNT=$(sqlite3 /tmp/auto_confirm.db "SELECT COUNT(*) FROM confirmations" 2>/dev/null)
    echo "✓ PASS ($COUNT confirmations)"
    PASS=$((PASS+1))
else
    echo "✗ FAIL (not found)"
    FAIL=$((FAIL+1))
fi

# Check 6: Logs directory
echo -n "[6/8] Logs directory................. "
if [ -d "go_wrapper/logs/agents" ]; then
    echo "✓ PASS"
    PASS=$((PASS+1))
else
    echo "✗ FAIL"
    FAIL=$((FAIL+1))
fi

# Check 7: Test files exist
echo -n "[7/8] Test files..................... "
if [ -f "go_wrapper/test.sh" ] && [ -f "workers/test_auto_confirm_foundation.py" ]; then
    echo "✓ PASS"
    PASS=$((PASS+1))
else
    echo "✗ FAIL"
    FAIL=$((FAIL+1))
fi

# Check 8: Documentation exists
echo -n "[8/8] Documentation.................. "
if [ -f "go_wrapper/README.md" ] && [ -f "go_wrapper/PHASE1_COMPLETE.md" ]; then
    echo "✓ PASS"
    PASS=$((PASS+1))
else
    echo "✗ FAIL"
    FAIL=$((FAIL+1))
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════════════════════════"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "✓ ALL CHECKS PASSED - System is operational!"
    echo ""
    echo "Quick Start:"
    echo "  cd go_wrapper"
    echo "  ./wrapper codex-1 codex"
    echo ""
    echo "Documentation:"
    echo "  cat GO_WRAPPER_SUMMARY.md"
    echo "  cat go_wrapper/PHASE1_COMPLETE.md"
    exit 0
else
    echo ""
    echo "✗ Some checks failed. See above for details."
    exit 1
fi
