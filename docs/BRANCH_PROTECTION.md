# Branch Protection & Pull Request Workflow

## Protected Branches

The following branches require pull requests for all changes:

- **main** - Production releases only
- **dev** - Integration and development
- **qa** - QA testing and validation
- **prod** - Production deployment (when created)

## Enforcement

### Pre-Push Hook (Active)

A git pre-push hook prevents direct pushes to protected branches. This works on all systems and doesn't require GitHub Pro.

**Setup (for new clones):**
```bash
./scripts/setup-git-hooks.sh
```

**What it does:**
- Blocks `git push origin main/dev/qa/prod`
- Displays helpful error message with workflow instructions
- Can be bypassed with `--no-verify` (not recommended)

### GitHub Branch Protection (Optional - Requires GitHub Pro)

For additional protection at the server level:

1. Go to **Settings** → **Branches** → **Add branch protection rule**
2. For each protected branch:
   - ☑️ Require a pull request before merging
   - ☑️ Require approvals: 1
   - ☑️ Dismiss stale pull request approvals when new commits are pushed
   - ☑️ Require status checks to pass (optional)
   - ☑️ Require conversation resolution before merging (optional)

## Pull Request Workflow

### 1. Create Feature Branch

```bash
# Use naming convention: <type>/<description>-MMDD
git checkout -b feature/user-auth-0210
git checkout -b fix/api-bug-0210
git checkout -b refactor/cleanup-0210
```

### 2. Make Changes and Commit

```bash
git add <files>
git commit -m "feat: add user authentication"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks

### 3. Push Feature Branch

```bash
git push -u origin feature/user-auth-0210
```

### 4. Create Pull Request

**Using GitHub CLI:**
```bash
# Target dev branch (default for feature development)
gh pr create --base dev --title "feat: Add user authentication" --body "Description..."

# Target main (for hotfixes)
gh pr create --base main --title "fix: Critical security patch" --body "Description..."
```

**Using GitHub Web UI:**
1. Go to repository on GitHub
2. Click "Compare & pull request" button
3. Select base branch (dev, qa, or main)
4. Fill in title and description
5. Click "Create pull request"

### 5. Code Review

- Address reviewer comments
- Make requested changes on your feature branch
- Push updates: `git push`
- PR automatically updates

### 6. Merge

Once approved:
- Click "Merge pull request" on GitHub
- Choose merge strategy:
  - **Squash and merge** - Recommended for feature branches
  - **Create a merge commit** - For preserving history
  - **Rebase and merge** - For clean linear history
- Delete the feature branch after merging

## Branch Flow

```
feature/fix branches → dev → qa → main
                       ↓      ↓     ↓
                    Testing  QA  Production
```

### Development Flow

1. **Feature Development** → `feature/*` branches
2. **Integration** → Merge to `dev` via PR
3. **QA Testing** → Merge `dev` to `qa` via PR
4. **Production** → Merge `qa` to `main` via PR

### Hotfix Flow

For critical production fixes:

```bash
git checkout -b fix/critical-bug-0210 main
# make fix
git push -u origin fix/critical-bug-0210
gh pr create --base main --title "fix: Critical bug"
# After merge to main, backport to dev/qa
```

## Multi-Session Work

When multiple Claude sessions or developers are working:

### Before Starting Work

```bash
# 1. Check for active locks
cat data/locks/active_sessions.json

# 2. Create your feature branch
git checkout -b feature/your-task-MMDD

# 3. Register your session (optional)
echo '{"session": "session-name", "branch": "feature/your-task-MMDD"}' >> data/locks/active_sessions.json
```

### After Completing Work

```bash
# 1. Push your branch
git push -u origin feature/your-task-MMDD

# 2. Create PR
gh pr create --base dev

# 3. Remove lock entry
# Edit data/locks/active_sessions.json
```

## Conflict Resolution

If your branch conflicts with the target branch:

```bash
# Update your feature branch with latest target
git checkout feature/your-branch
git fetch origin
git rebase origin/dev  # or origin/main

# Resolve conflicts
git add <resolved-files>
git rebase --continue

# Force push (your feature branch only!)
git push --force-with-lease
```

## Best Practices

### DO ✅

- Create feature branches for all work
- Use descriptive branch names with dates
- Write clear commit messages
- Keep PRs focused and small
- Request reviews before merging
- Delete branches after merging
- Update your branch with target before PR

### DON'T ❌

- Push directly to main/dev/qa/prod
- Use `--no-verify` to bypass hooks
- Force push to protected branches
- Create PRs with unrelated changes
- Leave stale branches around
- Merge without review/testing

## Emergency Bypass

In true emergencies only:

```bash
# Bypass pre-push hook
git push --no-verify origin main

# Document why in commit message and team chat
```

⚠️ **Use only for:**
- Critical production outages
- Security vulnerabilities
- When PR system is broken

## Troubleshooting

### "Direct push to 'main' is not allowed"

This is expected! Create a feature branch:
```bash
git checkout -b fix/my-fix-0210
git push -u origin fix/my-fix-0210
gh pr create --base dev
```

### Hook not installed after clone

Run setup script:
```bash
./scripts/setup-git-hooks.sh
```

### PR conflicts

Update your branch:
```bash
git fetch origin
git rebase origin/dev
# resolve conflicts
git push --force-with-lease
```

### Can't push feature branch

Make sure you're pushing the feature branch, not main:
```bash
git branch  # check current branch
git push -u origin <your-feature-branch>
```

## GitHub Actions (Future Enhancement)

When ready, add workflow to enforce PR requirements:

```yaml
# .github/workflows/branch-protection.yml
name: Branch Protection
on:
  pull_request:
    branches: [main, dev, qa, prod]

jobs:
  enforce:
    runs-on: ubuntu-latest
    steps:
      - name: Check PR from feature branch
        run: |
          if [[ ! "${{ github.head_ref }}" =~ ^(feature|fix|refactor)/ ]]; then
            echo "Branch must start with feature/, fix/, or refactor/"
            exit 1
          fi
```

## Summary

✅ Pre-push hook installed and active
✅ Blocks direct pushes to main/dev/qa/prod
✅ Requires feature branches and pull requests
✅ Setup script available for new clones
✅ Documentation complete

**Next Steps:**
1. Review and merge PR #13 (CLI fixes)
2. All future changes via PRs
3. Consider GitHub Pro for server-side protection
