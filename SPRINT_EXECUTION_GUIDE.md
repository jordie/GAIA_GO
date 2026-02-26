# Sprint Execution Guide

**For:** Development teams executing the Rate Limiting Development Roadmap
**Version:** 1.0
**Last Updated:** 2026-02-25

---

## Sprint Structure

Each sprint is **2 weeks** with the following rhythm:

### Sprint Week 1
- **Monday, 9 AM:** Sprint Planning
- **Daily 10 AM:** Standup
- **Wednesday:** Mid-sprint checkpoint
- **Friday 4 PM:** Early demo / progress check

### Sprint Week 2
- **Daily 10 AM:** Standup
- **Wednesday:** Final review
- **Friday 2 PM:** Sprint Demo / Review
- **Friday 4 PM:** Sprint Retrospective

---

## Sprint Planning (Day 1, 9 AM)

### Duration: 2 hours

### Agenda
1. **Goal Review** (15 min)
   - What are we building this sprint?
   - Why does it matter?
   - How does it connect to the roadmap?

2. **Task Breakdown** (30 min)
   - Review all tasks for the sprint
   - Ask clarifying questions
   - Identify dependencies

3. **Estimation** (30 min)
   - Story points for each task
   - Realistic time estimates
   - Account for meetings, admin, etc.

4. **Assignment** (30 min)
   - Who does what?
   - Ensure balanced load
   - Consider skills and mentoring

5. **Risk Review** (15 min)
   - What could go wrong?
   - How will we mitigate?
   - What's our contingency?

### Output
```
Sprint Plan Document:
├─ Sprint goal
├─ List of tasks with estimates
├─ Owner assignments
├─ Dependencies mapped
├─ Known risks
└─ Success criteria
```

### Template

```markdown
# Sprint [NUMBER] Plan

## Sprint Goal
[One sentence: what we're building and why]

## Success Criteria
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Code reviewed and merged
- [ ] Documentation updated
- [ ] No critical bugs

## Tasks

### Task 1: [Name]
- Points: 8
- Owner: [Engineer]
- Depends: [Other tasks]
- Tests: 4 unit tests
- Status: Not Started

### Task 2: [Name]
- Points: 5
- Owner: [Engineer]
- Depends: Task 1
- Tests: 2 unit tests
- Status: Not Started

[... more tasks ...]

## Risks
- Risk 1: [Description] → Mitigation: [Action]
- Risk 2: [Description] → Mitigation: [Action]

## Notes
- Team vacation: [dates]
- Infrastructure needs: [details]
- External dependencies: [details]
```

---

## Daily Standup (10 AM, 15 minutes)

### Format
Each person answers (2 min max):

1. **What did I complete yesterday?**
   - Specific tasks/tests
   - Blockers encountered
   - Help needed

2. **What am I doing today?**
   - Specific tasks planned
   - Expected blockers
   - Help I can offer

3. **What's blocking me?**
   - Technical issues
   - Dependencies
   - Process issues

### Escalation Rule
- **Blocker lasting > 2 hours** → Escalate immediately
- **Risk realized** → Call emergency meeting
- **Scope question** → Clarify with PM/Tech Lead

### Standup Minutes Template
```
Date: [DATE]
Attendees: [Names]

[Engineer 1]
- Yesterday: [Task complete]
- Today: [Task plan]
- Blocker: [Any issues]

[Engineer 2]
- Yesterday: [Task complete]
- Today: [Task plan]
- Blocker: [Any issues]

...

Action Items:
- [ ] [Action] by [Owner] on [Date]
- [ ] [Action] by [Owner] on [Date]
```

---

## Mid-Sprint Checkpoint (Wednesday)

### Duration: 30 minutes

### Review Points
1. **Progress:** On track or behind?
   ```
   Tasks completed / Total tasks
   Points completed / Total points
   ```

2. **Quality:** Tests passing?
   ```
   Unit test pass rate
   Code review count
   Bugs found
   ```

3. **Blockers:** Any issues?
   ```
   List all current blockers
   Impact on timeline
   Mitigation in place
   ```

4. **Scope:** Anything changed?
   ```
   New requirements?
   Scope creep?
   Tasks removed?
   ```

5. **Next Steps:** What's needed?
   ```
   Resources needed
   Help required
   Any red flags
   ```

### Red Flag Criteria
- **Behind Schedule:** < 60% of tasks done by Wednesday
- **Test Failures:** < 90% of tests passing
- **Blockers:** Any open 4+ hours
- **Scope Creep:** > 20% additional work requested

### If Red Flag
```
1. Immediately notify Tech Lead
2. Identify root cause
3. Plan mitigation (reduce scope, add help, extend sprint)
4. Update stakeholders
5. Replan remaining work
```

---

## Sprint Demo (Friday, 2 PM, 30 minutes)

### Attendees
- Engineering team
- Product Manager
- Tech Lead
- Stakeholders (optional)

### Agenda
1. **Sprint Goal Review** (2 min)
   - Did we achieve it?

2. **Feature Demo** (15 min)
   - Live demo of working features
   - Show test results
   - Discuss design decisions

3. **Metrics** (5 min)
   - Velocity (points completed)
   - Quality (test coverage, bugs)
   - Performance (latency, memory)

4. **Q&A** (5 min)
   - Questions from audience
   - Feedback on features

5. **Next Sprint Preview** (3 min)
   - What's coming next
   - How it builds on this sprint

### Demo Checklist
```
Before Demo:
□ All tests passing
□ Code merged to main
□ Feature flags working
□ Demo script tested
□ Metrics collected

During Demo:
□ Show actual code/product
□ Explain design decisions
□ Answer questions clearly
□ Record feedback

After Demo:
□ Update documentation
□ Log feedback in backlog
□ Note tech debt items
□ Plan improvements
```

---

## Sprint Retrospective (Friday, 4 PM, 30 minutes)

### Format: "Start, Stop, Continue"

#### What should we START doing?
- New practices to try
- New tools to use
- New processes to implement

#### What should we STOP doing?
- Inefficient processes
- Unnecessary meetings
- Tools that slow us down

#### What should we CONTINUE doing?
- Practices working well
- Tools helping us
- Processes that are effective

### Output: Action Items
```
Action Items from Retro:
□ [Action] → Owner: [Person], Due: [Date]
□ [Action] → Owner: [Person], Due: [Date]
□ [Action] → Owner: [Person], Due: [Date]
```

### Template
```markdown
# Sprint [N] Retrospective

Date: [DATE]
Team: [Names]
Duration: [Hours]

## What Went Well
- [Item 1]
- [Item 2]
- [Item 3]

## What Could Be Better
- [Item 1]
- [Item 2]
- [Item 3]

## Action Items
- [ ] [Action] by [Owner] on [Date]
- [ ] [Action] by [Owner] on [Date]

## Velocity
- Planned: [Points]
- Completed: [Points]
- Trend: [↑/↓/→]

## Quality Metrics
- Test coverage: [%]
- Test pass rate: [%]
- Bugs found: [Number]
```

---

## Task Tracking

### Task States
```
Not Started
    ↓
In Progress
    ├─ In Review (waiting on code review)
    ├─ Blocked (waiting on dependency)
    └─ Testing (in test phase)
    ↓
Complete
```

### Daily Status Update

Each engineer updates task status daily:

```
Task: [Task name]
Owner: [Name]
Status: [Not Started / In Progress / In Review / Testing / Complete]
Progress: [X% done]
Remaining: [Estimated hours]
Blockers: [List any blockers]
Help Needed: [Any assistance needed?]
```

### Jira / Issue Tracker Setup

**Required Fields per Task:**
```
- Title: [Brief description]
- Description: [Full details, acceptance criteria]
- Assignee: [Engineer name]
- Status: [State above]
- Story Points: [Estimate]
- Sprint: [Sprint number]
- Labels: [reputation, adaptive, anomaly, etc]
- Blocked By: [List blocking tasks]
- Blocks: [List blocked tasks]
- Test Coverage: [Link to tests]
```

### Burndown Chart
```
Ideal burndown (example):
Points remaining
     100 |*
      80 |  *
      60 |    *
      40 |      *
      20 |        *
       0 |__________*
         0  2  4  6  8 10 (days)

- Blue line: Ideal progress
- Red line: Actual progress
- Green checkmarks: Completed tasks
```

---

## Code Review Process

### Pull Request Checklist
```
Code Review for: [PR number]

Functionality:
□ Code does what PR describes
□ Handles edge cases
□ No regression in other features
□ Tests validate functionality

Code Quality:
□ Follows project style guide
□ No code duplication
□ Functions are focused and small
□ Variable names are clear
□ Comments explain why, not what

Testing:
□ Unit tests included
□ Integration tests included
□ Test coverage > 85%
□ All tests passing
□ Edge cases covered

Documentation:
□ Inline comments for complex logic
□ Public APIs documented
□ Updated relevant docs
□ CHANGELOG updated

Performance:
□ No unnecessary allocations
□ Database queries optimized
□ Network calls efficient
□ Latency acceptable (< 10ms)

Security:
□ No hardcoded secrets
□ Input validation present
□ SQL injection prevention
□ CORS/CSRF handled
```

### Review SLA
- **Simple changes:** < 2 hours review time
- **Complex changes:** < 4 hours review time
- **Blocked reviews:** Escalate to Tech Lead

---

## Testing Requirements

### Phase 2 Testing Requirements

**Unit Tests:**
```
Reputation System:
- 4 score calculation tests
- 4 event recording tests
- 2 edge case tests
- 2 performance tests
TOTAL: 12 tests

Adaptive Limiting:
- 4 VIP tier tests
- 4 load adjustment tests
- 2 pattern learning tests
- 2 edge case tests
TOTAL: 12 tests

Anomaly Detection:
- 4 baseline learning tests
- 4 detection accuracy tests
- 2 false positive tests
- 2 performance tests
TOTAL: 12 tests
```

**Integration Tests:**
```
All Features:
- 4 reputation + adaptive tests
- 4 adaptive + anomaly tests
- 4 all 3 together tests
TOTAL: 12 tests
```

### Test Coverage Requirements
- **Minimum:** 85% code coverage
- **Target:** > 90% coverage
- **Must Cover:** All public APIs, all error paths

### Continuous Integration

**Every Commit:**
```
✓ Code compile check
✓ Style linting
✓ All unit tests pass
✓ Code coverage check
✓ Security scanning
✓ Performance benchmarks
```

**Every PR:**
```
✓ All above
✓ Integration tests pass
✓ Code review approved
✓ Commit message valid
✓ Ready to merge
```

---

## Deployment Checklist

### Before Merging to Main
```
□ All tests passing (100%)
□ Code reviewed and approved
□ Documentation updated
□ Feature flag created
□ Changelog updated
□ No performance regression
□ No security issues
```

### Before Deploying to Production
```
□ Sprint 7 checkpoint passed
□ Staging tests complete
□ Rollback procedure verified
□ Monitoring/alerts configured
□ On-call schedule confirmed
□ Feature flag strategy ready
□ Runbooks updated
```

### Deployment Process
```
1. Merge to main
2. Tag release
3. Build container
4. Deploy to staging (feature flag 0%)
5. Smoke test
6. Deploy to production
7. Enable feature flag (5%)
8. Monitor 6 hours
9. Increase to 25%
10. Monitor 12 hours
11. Increase to 100%
12. Final monitoring 24 hours
```

---

## Team Communication

### Slack Channels
```
#rate-limiting-dev    Main development discussion
#rate-limiting-ops    Operations and deployment
#rate-limiting-qa     Testing and QA coordination
#incidents            Production issues
#standups             Daily standup summaries
```

### Communication Norms
- **Standup:** Async in #standups channel daily 9 AM
- **Questions:** Ask immediately in Slack
- **Blockers:** Escalate within 1 hour
- **Urgent Issues:** Page on-call engineer
- **Code Review:** Respond within 2 hours

### Escalation Path
```
Issue Found
    ↓
Slack @engineer (1 hour)
    ↓
Slack @tech-lead (2 hours)
    ↓
Page on-call (4+ hours)
```

---

## Metrics to Track Weekly

### Development Metrics
```
Sprint [N] Metrics

Velocity:
- Planned points: [X]
- Completed points: [X]
- Velocity trend: [↑/↓/→]

Quality:
- Test pass rate: [%]
- Code coverage: [%]
- Bugs found: [N]
- Critical bugs: [N]

Delivery:
- Tasks completed: [N] / [Total]
- On-time tasks: [%]
- Tasks requiring rework: [N]
```

### Performance Metrics
```
Latency:
- P50: [Xms]
- P99: [Xms]
- Max: [Xms]
- Baseline: [Yms]

Resource Usage:
- Memory: [XMB]
- CPU: [X%]
- Database queries: [Xms avg]
- Error rate: [X%]
```

---

## Celebration & Momentum

### Sprint Wins
- Share successes in #wins channel
- Celebrate completed features
- Recognize quality/testing efforts
- Build morale and momentum

### Major Milestones
- **Phase 2 Kickoff:** Team sync + pizza
- **Reputation System Complete:** Demo celebration
- **All Features Ready:** Team sync
- **Production Rollout:** Celebration lunch
- **Phase 2 Complete:** Larger team celebration

---

## Resources & Support

### Documentation
- `DEVELOPMENT_ROADMAP.md` - Full sprint plan
- `PHASE_2_ADVANCED_FEATURES_PLAN.md` - Feature details
- `PHASE_2_QUICK_START.md` - Implementation guide
- `RATE_LIMITING_OPERATIONS.md` - Operations guide

### Tools
- Jira/Linear: Issue tracking
- GitHub: Code repository
- Slack: Communication
- Confluence: Documentation
- DataDog: Monitoring

### Getting Help
- **Technical Questions:** Slack + pair programming
- **Architecture Questions:** Tech lead office hours
- **Process Questions:** Scrum master / PM
- **Production Issues:** On-call engineer

---

## Success Indicators

### Sprint Success
- ✅ 100% of sprint goal achieved
- ✅ 100% of tests passing
- ✅ Code reviewed and merged
- ✅ Documentation complete
- ✅ Team satisfied (retro feedback positive)

### Phase 2 Success
- ✅ All 3 features deployed
- ✅ 40+ tests passing
- ✅ < 10ms latency added
- ✅ Production rollout complete
- ✅ A/B test positive

---

**Version:** 1.0
**Last Updated:** 2026-02-25
**Contact:** [Tech Lead Name]
