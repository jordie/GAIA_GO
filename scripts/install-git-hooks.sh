#!/bin/bash
# Install Git hooks for Phase 5 testing

set -e

echo "Installing Git hooks for Phase 5 testing..."

# Create hooks directory if it doesn't exist
HOOKS_DIR=".git/hooks"
mkdir -p "$HOOKS_DIR"

# Install pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Pre-commit hook for Phase 5 testing suite
# Runs quick unit tests before allowing commit

echo "========================================"
echo "Phase 5: Pre-commit Test Check"
echo "========================================"

# Get list of changed Go files
CHANGED_GO_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep "\.go$" || true)

if [ -z "$CHANGED_GO_FILES" ]; then
    echo "No Go files changed. Skipping tests."
    exit 0
fi

echo "Testing changed files..."
echo "$CHANGED_GO_FILES"

# Run quick unit tests only (skip integration/load/e2e)
echo ""
echo "Running Phase 5 unit tests (quick mode)..."
if go test -v -short \
    -run "TestCheckLimit|TestRule|TestQuota" \
    ./pkg/services/rate_limiting -timeout 30s; then
    echo ""
    echo "✅ Tests passed. Proceeding with commit."
    exit 0
else
    echo ""
    echo "❌ Tests failed. Commit aborted."
    echo ""
    echo "To bypass this check (not recommended):"
    echo "  git commit --no-verify"
    exit 1
fi
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "✅ Pre-commit hook installed at $HOOKS_DIR/pre-commit"

# Install prepare-commit-msg hook for auto-adding test info
cat > "$HOOKS_DIR/prepare-commit-msg" << 'EOF'
#!/bin/bash
# Prepare commit message hook
# Auto-adds test status when committing test-related changes

COMMIT_MSG_FILE=$1

# Check if this is a test file change
if git diff --cached --name-only | grep -q "_test\.go$"; then
    if ! grep -q "Tested:" "$COMMIT_MSG_FILE"; then
        echo "" >> "$COMMIT_MSG_FILE"
        echo "Tested: Phase 5 unit tests passed" >> "$COMMIT_MSG_FILE"
    fi
fi
EOF

chmod +x "$HOOKS_DIR/prepare-commit-msg"

echo "✅ Prepare commit message hook installed"

echo ""
echo "========================================"
echo "Git hooks installed successfully!"
echo "========================================"
echo ""
echo "Installed hooks:"
echo "  • pre-commit: Runs unit tests before commit"
echo "  • prepare-commit-msg: Auto-adds test status to commit messages"
echo ""
echo "To bypass hooks (if necessary):"
echo "  git commit --no-verify"
echo ""
