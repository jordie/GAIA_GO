# Multi-Session Orchestration Plan
**Created**: 2026-02-02 22:40
**Status**: Active

## Session Allocation Strategy

### Development Pool (3 Codex Sessions)
- **codex**: Architecture & backend development
- **codex2**: Frontend & UI development
- **codex3**: Database & data layer work

### Testing Pool (3 Comet Sessions)
- **comet**: UI/UX testing & bug discovery
- **comet2**: Integration testing & API validation
- **edu_dev**: End-to-end user flow testing

### Code Review Pool (2 Claude Sessions)
- **arch_prod**: Production code review & deployment
- **arch_qa**: QA environment testing & validation

### Worker Pool (Claude Sessions)
- **concurrent_worker1-3**: Background tasks, migrations, refactoring
- **edu_worker1**: Educational apps maintenance

## Workflow Pipeline

### 1. Development Phase (Codex)
```yaml
workflow:
  - session: codex
    task: "Implement feature X"
    output: feature branch

  - session: codex2
    task: "Create UI for feature X"
    output: frontend components

  - session: codex3
    task: "Add database migrations for feature X"
    output: migration scripts
```

### 2. Testing Phase (Comet)
```yaml
workflow:
  - session: comet
    task: "Test UI for feature X - find bugs"
    triggers_on: codex2 completion

  - session: comet2
    task: "Test API endpoints for feature X"
    triggers_on: codex completion

  - session: edu_dev
    task: "Test full user flow for feature X"
    triggers_on: all development complete
```

### 3. Review & Deploy Phase (Claude)
```yaml
workflow:
  - session: arch_qa
    task: "Review code quality, run tests"
    triggers_on: all testing complete

  - session: arch_prod
    task: "Deploy to production if approved"
    triggers_on: QA approval
```

## LLM Provider Failover Chain

### Priority Order
1. **Primary**: Claude (Anthropic) - arch_* sessions
2. **Secondary**: Codex (OpenAI) - codex* sessions
3. **Tertiary**: Comet (Custom) - comet* sessions
4. **Fallback**: Ollama (Local) - when all providers rate-limited

### Cost Optimization
- Route simple tasks → Ollama (free)
- Route UI testing → Comet (specialized)
- Route complex logic → Claude/Codex (quality)

## Task Queue Priorities

### High Priority (Immediate)
- Production bugs
- Security issues
- Performance degradation

### Medium Priority (24h)
- Feature development
- UI improvements
- Test coverage

### Low Priority (Weekly)
- Code refactoring
- Documentation
- Tech debt

## Continuous Deployment Pipeline

```
Codex Development → Comet Testing → Claude Review → Deploy
     ↓                  ↓                ↓             ↓
  feature/*         test results     approval?      prod
  branches          →bugs filed      →merge         →live
```

## Monitoring & Alerts

### Session Health Checks (Every 5min)
- Check if sessions are responsive
- Detect stuck/blocked sessions
- Auto-restart failed sessions

### Cost Tracking
- Monitor API usage per provider
- Alert at 80% budget threshold
- Switch to Ollama when over budget

## Implementation Commands

### Start Orchestration
```bash
python3 workers/orchestration_manager.py start \
  --codex-pool codex,codex2,codex3 \
  --comet-pool comet,comet2,edu_dev \
  --claude-pool arch_prod,arch_qa \
  --fallback ollama
```

### Queue Development Task
```bash
python3 workers/assigner_worker.py --send \
  "Implement reading app progress tracking" \
  --target codex --priority 5
```

### Queue Testing Task
```bash
python3 workers/assigner_worker.py --send \
  "Test reading app UI for Eden user - find all bugs" \
  --target comet --priority 8
```

### Queue Deployment
```bash
python3 workers/assigner_worker.py --send \
  "Review and deploy reading app fixes to production" \
  --target arch_prod --priority 10
```

## Next Steps

1. ✅ Session infrastructure verified
2. ⏳ Create orchestration_manager.py
3. ⏳ Implement failover logic with Ollama
4. ⏳ Set up continuous testing loops
5. ⏳ Configure auto-deployment gates
6. ⏳ Add cost monitoring dashboard

## Current Active Tasks

### Eden's Reading App (In Progress)
- ✅ Fixed mastered words display bug
- ⏳ Queue UI testing to Comet
- ⏳ Queue deployment to arch_prod
- ⏳ Monitor for regression
