#!/bin/bash
# Setup script for git hooks
# Run this after cloning the repository

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "🔧 Setting up git hooks..."

# Pre-push hook to prevent direct pushes to protected branches
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
# Pre-push hook to prevent direct pushes to protected branches

PROTECTED_BRANCHES="^(main|dev|qa|prod)$"
CURRENT_BRANCH=$(git symbolic-ref HEAD | sed -e 's,.*/\(.*\),\1,')

if [[ $CURRENT_BRANCH =~ $PROTECTED_BRANCHES ]]; then
    echo "❌ ERROR: Direct push to '$CURRENT_BRANCH' is not allowed."
    echo ""
    echo "Protected branches: main, dev, qa, prod"
    echo ""
    echo "Please use the following workflow:"
    echo "  1. Create a feature branch: git checkout -b feature/your-feature-MMDD"
    echo "  2. Make your changes and commit"
    echo "  3. Push feature branch: git push -u origin feature/your-feature-MMDD"
    echo "  4. Create a pull request on GitHub"
    echo "  5. After approval, merge via GitHub PR interface"
    echo ""
    echo "To bypass this check (NOT RECOMMENDED): git push --no-verify"
    exit 1
fi

exit 0
EOF

chmod +x "$HOOKS_DIR/pre-push"

echo "✅ Pre-push hook installed"
echo ""
echo "Protected branches: main, dev, qa, prod"
echo "All pushes to these branches must go through pull requests."
echo ""
echo "Example workflow:"
echo "  git checkout -b fix/my-bugfix-0210"
echo "  # make changes"
echo "  git commit -m 'fix: description'"
echo "  git push -u origin fix/my-bugfix-0210"
echo "  gh pr create --base dev"
