#!/bin/bash
#
# Install git hooks for deployment automation
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

echo "Installing deployment git hooks..."

# Copy hooks
for hook in post-merge post-commit pre-push pre-commit; do
    if [ -f "$SCRIPT_DIR/$hook" ]; then
        cp "$SCRIPT_DIR/$hook" "$GIT_HOOKS_DIR/$hook"
        chmod +x "$GIT_HOOKS_DIR/$hook"
        echo "  Installed: $hook"
    fi
done

# Also install branch enforcer hooks if not already there
if [ -f "$SCRIPT_DIR/../branch_enforcer.py" ]; then
    python3 "$SCRIPT_DIR/../branch_enforcer.py" install-hooks
fi

echo ""
echo "Git hooks installed!"
echo ""
echo "Branch protection (pre-push):"
echo "  - Direct pushes to 'main', 'qa', 'dev' are BLOCKED"
echo "  - All work must happen in feature/* branches"
echo "  - PRs: feature/* -> dev -> qa -> main"
echo ""
echo "Feature environment enforcement (pre-commit):"
echo "  - Feature branches can only modify feature_environments/"
echo "  - Root app files are protected from direct changes"
echo ""
echo "Deployment triggers:"
echo "  - Merge to dev    -> DEV deployment (auto)"
echo "  - Tag v*.*.*      -> QA deployment (auto)"
echo "  - Tag release-*   -> PROD deployment (manual approval required)"
echo ""
