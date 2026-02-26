# AI Usage Optimization Analysis

**Project**: Reduce AI token usage by automating recurring tasks with deterministic scripts

**Created**: 2026-02-07

**Goal**: Reduce AI usage by 30-50% by identifying and scripting recurring tasks with set patterns

---

## Current AI Usage Patterns

### 1. Session Health Monitoring ✅ AUTOMATED
- **Current**: AI-based monitoring (REPLACED)
- **Solution**: `workers/session_health_daemon.py`
- **Savings**: ~5,000 tokens per hour
- **Status**: COMPLETE - Pure Python scraping of tmux output

### 2. Task Status Checking 🔄 PARTIALLY AUTOMATED
- **Current**: Claude sessions querying task status
- **Opportunity**: Create `scripts/task_status.sh` for quick status checks
- **Pattern**:
  - Check pending tasks: `SELECT * FROM prompts WHERE status='pending'`
  - Check session availability: `SELECT * FROM sessions WHERE status='idle'`
  - Show queue depth and ETA
- **Estimated Savings**: 2,000 tokens per hour

### 3. Database Cleanup ❌ NEEDS AUTOMATION
- **Current**: Manual or AI-driven cleanup of old records
- **Opportunity**: Create `scripts/db_cleanup.py` with rules:
  - Delete prompts older than 30 days with status='completed'
  - Archive old activity logs (> 90 days)
  - Remove orphaned records
  - Vacuum databases
- **Pattern**: Runs daily via cron
- **Estimated Savings**: 1,500 tokens per week

### 4. Log File Management ❌ NEEDS AUTOMATION
- **Current**: Manual log inspection
- **Opportunity**: Create `scripts/log_analyzer.py`:
  - Rotate logs > 10MB
  - Extract error patterns
  - Generate summary reports
  - Alert on critical errors
- **Pattern**: Runs hourly
- **Estimated Savings**: 3,000 tokens per day

### 5. Git Operations ❌ NEEDS AUTOMATION
- **Current**: AI sessions running git commands
- **Opportunity**: Create `scripts/git_auto_sync.sh`:
  - Auto-pull on all active projects
  - Check for uncommitted changes
  - Auto-commit with template messages for specific patterns
  - Push to remote on schedule
- **Pattern**: Every 4 hours or on-demand
- **Estimated Savings**: 5,000 tokens per day

### 6. Performance Metrics Collection ❌ NEEDS AUTOMATION
- **Current**: Manual performance checks
- **Opportunity**: Create `scripts/metrics_collector.py`:
  - Collect CPU, memory, disk usage
  - Track API response times
  - Monitor session uptime
  - Generate performance reports
- **Pattern**: Every 15 minutes
- **Estimated Savings**: 2,000 tokens per hour

### 7. Session Restart Logic 🔄 PARTIALLY AUTOMATED
- **Current**: `scripts/session_restart.py` exists but not fully integrated
- **Opportunity**: Enhance with:
  - Auto-restart sessions at 5% context
  - Save session state before restart
  - Resume work after restart
  - Notify user of restarts
- **Pattern**: Triggered by health monitor
- **Estimated Savings**: 10,000 tokens per session restart (avoiding context overflow)

### 8. Task Assignment Routing ✅ AUTOMATED
- **Current**: `workers/assigner_worker.py` handles this
- **Status**: WORKING - No changes needed

### 9. Error Triage and Grouping ❌ NEEDS AUTOMATION
- **Current**: AI reads errors and creates bugs
- **Opportunity**: Create `scripts/error_triage.py`:
  - Group similar errors by regex patterns
  - Auto-create bugs for known error types
  - Link errors to existing bugs
  - Suggest fixes from error database
- **Pattern**: Triggered on new error
- **Estimated Savings**: 8,000 tokens per error batch

### 10. Backup and Archiving ❌ NEEDS AUTOMATION
- **Current**: Manual or AI-initiated backups
- **Opportunity**: Create `scripts/auto_backup.sh`:
  - Daily backup of all databases
  - Weekly backup of logs and configs
  - Archive old project data
  - Upload to remote storage
- **Pattern**: Daily at 2 AM
- **Estimated Savings**: 1,000 tokens per day

---

## High-Priority Automation Scripts to Create

### Priority 1 (Immediate Impact)
1. **Task Status Dashboard** (`scripts/task_status.sh`)
2. **Session Auto-Restart Enhancement** (`scripts/smart_restart.py`)
3. **Error Triage System** (`scripts/error_triage.py`)

### Priority 2 (Weekly Impact)
4. **Database Cleanup** (`scripts/db_cleanup.py`)
5. **Git Auto-Sync** (`scripts/git_auto_sync.sh`)
6. **Log Analyzer** (`scripts/log_analyzer.py`)

### Priority 3 (Long-term Benefits)
7. **Metrics Collector** (`scripts/metrics_collector.py`)
8. **Auto Backup System** (`scripts/auto_backup.sh`)

---

## Estimated Total Savings

| Category | Daily Token Savings |
|----------|---------------------|
| Session Health (DONE) | 120,000 |
| Task Status Checks | 48,000 |
| Error Triage | 56,000 |
| Git Operations | 5,000 |
| Log Management | 3,000 |
| Session Restarts | 20,000 (per restart avoided) |
| Database Cleanup | 214 (weekly/7) |
| Metrics Collection | 48,000 |
| **TOTAL** | **280,214 tokens/day** |

**Current Daily Usage Estimate**: 600,000 tokens/day
**Projected Usage After Automation**: 319,786 tokens/day
**Reduction**: 46.7% ✅ Exceeds 30-50% goal

---

## Implementation Plan

### Week 1
- [ ] Create task_status.sh
- [ ] Enhance session_restart.py
- [ ] Create error_triage.py

### Week 2
- [ ] Create db_cleanup.py
- [ ] Create git_auto_sync.sh
- [ ] Create log_analyzer.py

### Week 3
- [ ] Create metrics_collector.py
- [ ] Create auto_backup.sh
- [ ] Integration testing

### Week 4
- [ ] Deploy all scripts to production
- [ ] Monitor token usage reduction
- [ ] Fine-tune automation rules

---

## Success Metrics

1. **Token Usage**: Reduce by 30-50% within 30 days
2. **AI Session Availability**: Increase idle time by 40%
3. **Response Time**: Reduce average task completion time by 25%
4. **Error Resolution**: Auto-triage 70% of common errors
5. **System Uptime**: Increase to 99.5% through auto-restarts

---

## Next Steps

1. Create Priority 1 scripts (task_status.sh, smart_restart.py, error_triage.py)
2. Test in development environment
3. Deploy to production with monitoring
4. Measure token usage reduction
5. Iterate on automation rules based on results
