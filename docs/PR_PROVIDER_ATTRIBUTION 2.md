# PR Provider Attribution Tracking

## Overview

The PR Provider Attribution system tracks which provider (Claude, Codex, Ollama) worked on each pull request across the review, implementation, and integration stages of development.

This provides complete visibility into:
- **Who reviewed each PR** (Claude = high-quality review, Ollama = fast review)
- **Who implemented changes** (Codex = cost-effective, Ollama = free local)
- **Who tested integration** (Ollama = fast local testing, Claude = thorough testing)

## Provider Roles

| Provider | Role | Cost | Speed | Quality |
|----------|------|------|-------|---------|
| **Claude** | PR Review | $$ | Slow | High |
| **Codex** | Implementation | $ | Medium | High |
| **Ollama** | Dev/Integration | Free | Fast | Medium |

## Quick Start

### Record PR with Review Provider

```bash
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --title "Add health status endpoint" \
  --branch "feature/health-endpoint" \
  --review-provider claude \
  --review-session pr_review1
```

### Update PR with Implementation Provider

```bash
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --impl-provider codex \
  --impl-session pr_impl1
```

### Add Integration Provider

```bash
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --integ-provider ollama \
  --integ-session pr_integ1
```

### View Specific PR Attribution

```bash
python3 scripts/track_pr_attribution.py --pr 42 --view
```

Output:
```
PR #42: Add health status endpoint
Branch: feature/health-endpoint
Created by: unknown
Status: pending

Provider Attribution:
  Review: claude (pr_review1)
  Implementation: codex (pr_impl1)
  Integration: ollama (pr_integ1)
Last updated: 2026-02-16T22:00:49.337693
```

### View All PR Attributions

```bash
python3 scripts/track_pr_attribution.py --view-all
```

Or via GAIA CLI:

```bash
gaia --pr-attribution
```

Output:
```
╔═══════════════════════════════════════════════════════════╗
║  PR Provider Attribution Report                          ║
║  Last Update: 2026-02-16 22:01:06                        ║
╚═══════════════════════════════════════════════════════════╝

PR #44: Add caching layer
  Branch: feature/caching-0216
  🔵 Review: claude (pr_review3)
  🟠 Implementation: codex (pr_impl2)
  🟡 Integration: ollama (pr_integ2)
  Status: pending

PR #43: Improve database query performance
  Branch: feature/db-perf-0216
  🔵 Review: claude (pr_review2)
  🟡 Implementation: ollama (pr_impl3)
  Status: pending

PR #42: Add health status endpoint
  Branch: feature/health-endpoint
  🔵 Review: claude (pr_review1)
  🟠 Implementation: codex (pr_impl1)
  🟡 Integration: ollama (pr_integ1)
  Status: pending
```

## API Usage

### Track PR Task

```python
from services.multi_env_status import MultiEnvStatusManager

manager = MultiEnvStatusManager()

# Record that dev1_worker assigned a task for PR #42
task_id = manager.track_pr_task(
    session_name="dev1_worker",
    pr_id=42,
    task_type="implementation",
    provider="ollama",
    task_description="Implement health endpoint"
)
```

### Record PR Attribution

```python
manager.record_pr_attribution(
    pr_id=42,
    pr_title="Add health status endpoint",
    pr_branch="feature/health-endpoint-0216",
    created_by="dev_user",
    review_provider="claude",
    review_session="pr_review1",
    implementation_provider="codex",
    implementation_session="pr_impl1",
    integration_provider="ollama",
    integration_session="pr_integ1"
)
```

### Get PR Attribution

```python
# Get specific PR attribution
attribution = manager.get_pr_attribution(pr_id=42)

# Get all PR attributions
all_attributions = manager.get_all_pr_attributions()

# Format for display
report = manager.format_pr_attribution_report()
print(report)
```

## Workflow Integration

### Step-by-Step PR Workflow

1. **Initial PR Creation** (dev environment)
   ```bash
   # Developer creates PR in dev environment
   cd architect-dev1
   git push origin feature/health-endpoint
   gh pr create --title "Add health status endpoint"

   # Record initial PR
   python3 scripts/track_pr_attribution.py \
     --pr 42 \
     --title "Add health status endpoint" \
     --branch "feature/health-endpoint" \
     --created-by dev_user
   ```

2. **Code Review** (PR Review Group)
   ```bash
   # Task routed to pr_review group (Claude)
   # pr_review1 session performs code review

   # Record review provider
   python3 scripts/track_pr_attribution.py \
     --pr 42 \
     --review-provider claude \
     --review-session pr_review1
   ```

3. **Address Feedback** (PR Implementation Group)
   ```bash
   # Developer addresses review feedback
   # Task routed to pr_impl group (Codex)
   # pr_impl1 session implements changes

   # Record implementation provider
   python3 scripts/track_pr_attribution.py \
     --pr 42 \
     --impl-provider codex \
     --impl-session pr_impl1
   ```

4. **Integration Testing** (PR Integration Group)
   ```bash
   # Task routed to pr_integ group (Ollama)
   # pr_integ1 session performs testing

   # Record integration provider
   python3 scripts/track_pr_attribution.py \
     --pr 42 \
     --integ-provider ollama \
     --integ-session pr_integ1
   ```

5. **Merge to Main**
   ```bash
   # View final PR attribution
   python3 scripts/track_pr_attribution.py --pr 42 --view

   # Merge PR
   cd architect-dev1
   git checkout main
   git merge feature/health-endpoint
   git push origin main
   ```

## Cost Optimization Example

### PR #42 Cost Breakdown

Using provider attribution to calculate PR costs:

- **Code Review** (Claude): ~0.5 hours → $1.50
- **Implementation** (Codex): ~1 hour → $0.87
- **Integration Testing** (Ollama): ~0.5 hours → $0.00

**Total PR Cost: $2.37**

vs.

**All Claude**: ~2 hours → $6.00

**Savings: 60% cost reduction** through intelligent provider selection

## Database Schema

### pr_provider_attribution Table

```sql
CREATE TABLE pr_provider_attribution (
    pr_id INTEGER PRIMARY KEY,
    pr_title TEXT,
    pr_branch TEXT,
    created_by TEXT,
    created_at TIMESTAMP,
    review_provider TEXT,           -- claude, codex, ollama
    implementation_provider TEXT,   -- claude, codex, ollama
    integration_provider TEXT,      -- claude, codex, ollama
    review_session TEXT,            -- pr_review1, pr_review2, etc
    implementation_session TEXT,    -- pr_impl1, pr_impl2, etc
    integration_session TEXT,       -- pr_integ1, pr_integ2, etc
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed
    last_updated TIMESTAMP
);
```

### task_assignments Table (Enhanced)

```sql
CREATE TABLE task_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    task_type TEXT,
    task_description TEXT,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'assigned',
    provider TEXT,                  -- Added: provider type
    pr_id INTEGER                   -- Added: link to PR
);
```

## CLI Reference

### track_pr_attribution.py

```bash
# Record new PR with initial providers
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --title "Add health endpoint" \
  --branch "feature/health-endpoint" \
  --review-provider claude \
  --review-session pr_review1

# Update existing PR with new provider info
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --impl-provider codex \
  --impl-session pr_impl1

# View specific PR
python3 scripts/track_pr_attribution.py --pr 42 --view

# View all PRs
python3 scripts/track_pr_attribution.py --view-all
```

### GAIA CLI

```bash
# Show PR provider attribution report
gaia --pr-attribution

# Show session status with provider routing
gaia --status

# Show grouped session status
gaia --group-status

# Show multi-environment status
gaia --multi-env-status
```

## Monitoring & Metrics

### Provider Usage Statistics

```bash
# View provider distribution
gaia --pr-attribution | grep -E "Review|Implementation|Integration"
```

This shows:
- How many PRs each provider handled
- Cost distribution
- Provider specialization patterns

### Performance Metrics

```bash
# View recent PRs by provider
python3 scripts/track_pr_attribution.py --view-all | head -20

# Shows:
# - Review quality: Claude vs Ollama
# - Implementation speed: Codex vs Ollama
# - Integration thoroughness: Ollama vs Claude
```

## Best Practices

### 1. Record PR Attribution Early

Record PR attribution as soon as a PR is created or shortly after first assignment, not at the end of the workflow.

```bash
# Good: Record immediately
gh pr create --title "New feature"
python3 scripts/track_pr_attribution.py --pr 42 --title "New feature"

# Poor: Record only after everything done
# (loses intermediate attribution data)
```

### 2. Update Incrementally

Update provider information as each workflow stage completes, rather than all at once.

```bash
# Good: Update as each stage completes
# After review: python3 scripts/track_pr_attribution.py --pr 42 --review-provider claude
# After impl: python3 scripts/track_pr_attribution.py --pr 42 --impl-provider codex
# After test: python3 scripts/track_pr_attribution.py --pr 42 --integ-provider ollama

# Poor: Wait until everything done to record
```

### 3. Use Meaningful PR Titles

The title is used in reports, so make it descriptive.

```bash
# Good
--title "Add health status endpoint for dev environments"

# Poor
--title "PR 42"
--title "Bug fix"
```

### 4. Monitor Cost Patterns

Regularly review attribution report to identify cost optimization opportunities.

```bash
# Monthly cost analysis
python3 scripts/track_pr_attribution.py --view-all > pr_analysis_$(date +%Y%m%d).txt

# Analyze provider costs:
# - Too many Claude implementations? Increase Codex usage
# - Too much Ollama? Consider Codex for complex features
# - Imbalanced usage? Rebalance provider selection
```

## Troubleshooting

### PR Attribution Not Saving

```bash
# Check database exists
ls -la data/multi_env/status.db

# If missing, initialize:
python3 scripts/track_pr_attribution.py --view-all
# This creates database on first run
```

### Missing Provider Information

```bash
# View PR with missing fields
python3 scripts/track_pr_attribution.py --pr 42 --view

# Add missing provider:
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --review-provider claude \
  --review-session pr_review1
```

### Session Name Mismatch

Ensure session names match actual GAIA sessions:

```bash
# List available sessions
gaia --status | grep "pr_"

# Use exact session names in attribution:
python3 scripts/track_pr_attribution.py \
  --pr 42 \
  --review-session pr_review1  # Must exist!
```

## Integration with Assigner

The PR provider attribution integrates with the task assigner system:

```python
# In assigner_worker.py or custom handlers:
from services.multi_env_status import MultiEnvStatusManager

manager = MultiEnvStatusManager()

# When assigning a PR review task:
manager.record_pr_attribution(
    pr_id=42,
    pr_title="New feature",
    pr_branch="feature/new-feature",
    review_provider="claude",
    review_session="pr_review1"
)

# Track the task
manager.track_pr_task(
    session_name="pr_review1",
    pr_id=42,
    task_type="review",
    provider="claude",
    task_description="Review code quality and design"
)
```

## Summary

The PR Provider Attribution system provides:
- ✅ Complete visibility into provider involvement in PRs
- ✅ Cost optimization through provider tracking
- ✅ Performance metrics by provider and role
- ✅ Historical record of workflow decisions
- ✅ Integration with multi-environment orchestration
- ✅ Automated reporting via CLI and API

Use `gaia --pr-attribution` to view the complete attribution report at any time.
