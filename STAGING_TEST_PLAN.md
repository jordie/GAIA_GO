# Staging Test Plan - Multi-Environment Orchestration System

## Test Overview

This document outlines the complete staging test plan for the multi-environment orchestration system. Tests will be executed in a controlled staging environment before production deployment.

## Test Environment Setup

**Staging Location**: `/tmp/architect-staging-test-$(date +%s)`

**Test Scope**:
- Single environment (dev1 only) for initial testing
- Full 5-environment test after dev1 passes
- Session creation and management
- Git operations
- Health monitoring
- Status reporting

## Phase 1: Script Validation (Pre-Execution)

### 1.1 Script Syntax Check
- [x] Verify all scripts are valid bash
- [x] Verify all scripts are executable
- [x] Check for syntax errors

### 1.2 File Integrity
- [x] Verify all files created
- [x] Verify file permissions
- [x] Check gaia.py modifications

## Phase 2: Isolated Component Testing

### 2.1 Setup Script Testing

**Test 2.1.1: Script Execution (Single Environment)**
- Run setup script with single environment creation
- Verify directory creation
- Verify git branch creation
- Verify database initialization
- Verify launch scripts generation

**Expected Results**:
- ✅ architect-dev1 directory created
- ✅ env/dev1 git branch exists
- ✅ data/dev/architect.db directory exists
- ✅ launch.sh, stop.sh, status.sh, sync.sh created
- ✅ .env.local generated with unique SECRET_KEY

### 2.2 Session Start/Stop Testing

**Test 2.2.1: Manual Session Creation**
- Create tmux session manually
- Verify GAIA recognizes it
- Check pattern matching
- Verify provider detection

**Expected Results**:
- ✅ Session appears in `tmux list-sessions`
- ✅ `gaia --status` shows the session
- ✅ Provider correctly identified

### 2.3 Git Workflow Testing

**Test 2.3.1: Git Status Check**
- Run status command in dev1
- Verify git branch shown
- Verify branch status correct

**Expected Results**:
- ✅ Branch name displayed correctly
- ✅ Ahead/behind counts accurate
- ✅ Dirty file detection works

### 2.4 Health Monitoring Testing

**Test 2.4.1: Monitor Script Execution**
- Run monitoring script
- Verify all checks pass
- Check output formatting

**Expected Results**:
- ✅ Script completes without errors
- ✅ Health status reported for dev1
- ✅ Color coding displays correctly

## Phase 3: Integration Testing

### 3.1 Multi-Environment Setup

**Test 3.1.1: Full Setup Execution**
- Run complete setup script
- Verify all 5 environments created
- Verify all git branches created
- Verify all databases initialized
- Verify environments.json created correctly

**Expected Results**:
- ✅ 5 directories: architect-dev1 through dev5
- ✅ 5 git branches: env/dev1 through env/dev5
- ✅ All launch scripts present and executable
- ✅ environments.json contains all 5 environments

### 3.2 Session Pool Testing

**Test 3.2.1: Session Creation and Recognition**
- Create test sessions matching new patterns
- Verify GAIA recognizes them
- Check grouped display works
- Verify multi-env status display

**Test Sessions to Create**:
- dev1_worker (Ollama pattern)
- pr_review1 (Claude pattern)
- pr_impl1 (Codex pattern)
- pr_integ1 (Ollama pattern)

**Expected Results**:
- ✅ All test sessions appear in tmux
- ✅ `gaia --group-status` shows correct groups
- ✅ `gaia --multi-env-status` displays all info
- ✅ Provider detection accurate

### 3.3 Status Service Testing

**Test 3.3.1: Database Creation**
- Verify multi_env_status.py creates database
- Check database tables exist
- Verify queries work

**Expected Results**:
- ✅ data/multi_env/status.db created
- ✅ All 4 tables created (directories, environments, pr_groups, task_assignments)
- ✅ Database queries return expected results

## Phase 4: Full System Testing

### 4.1 End-to-End Workflow

**Test 4.1.1: Complete Setup Flow**
```bash
# 1. Setup environments
./scripts/setup_multi_env.sh
# Verify: 5 directories exist

# 2. Test single environment
cd architect-dev1
./status.sh
# Verify: Not running
./launch.sh
# Verify: Starts on port 8081
curl -k https://localhost:8081/health
# Verify: Returns 200
./stop.sh
# Verify: Stops cleanly

# 3. Test git operations
./scripts/dev_env_git_workflow.sh status dev1
# Verify: Shows git status
./scripts/dev_env_git_workflow.sh sync dev1
# Verify: Syncs with main

# 4. Test monitoring
./scripts/dev_env_monitor.sh
# Verify: Shows healthy status

# 5. Test GAIA integration
gaia --group-status
# Verify: Sessions displayed correctly
gaia --multi-env-status
# Verify: All environments shown
```

### 4.2 Session Management Testing

**Test 4.2.1: Start All Sessions**
- Run start_all_sessions.sh
- Verify all 26 sessions start
- Check for any failures
- Verify session organization

**Expected Results**:
- ✅ All 26 sessions created
- ✅ No errors during startup
- ✅ `gaia --group-status` shows all groups
- ✅ Session counts match expected

### 4.3 Cleanup and Rollback Testing

**Test 4.3.1: Stop All Sessions**
- Run start_all_sessions.sh --stop
- Verify all sessions stopped
- Check no orphaned processes

**Expected Results**:
- ✅ All new sessions killed
- ✅ No errors during shutdown
- ✅ No orphaned tmux sessions

**Test 4.3.2: Clean Setup**
- Run setup --clean
- Verify all directories removed
- Verify environments.json removed

**Expected Results**:
- ✅ All architect-dev* directories removed
- ✅ environments.json removed
- ✅ No orphaned databases

## Phase 5: Performance and Load Testing

### 5.1 Concurrent Operations

**Test 5.1.1: Parallel Script Execution**
- Run multiple git operations simultaneously
- Verify no conflicts
- Check all complete successfully

**Expected Results**:
- ✅ All operations complete
- ✅ No database locks
- ✅ No race conditions

### 5.2 Health Check Performance

**Test 5.2.1: Monitor Script Speed**
- Measure execution time
- Verify acceptable performance
- Check resource usage

**Expected Results**:
- ✅ Completes in < 10 seconds
- ✅ CPU usage < 20%
- ✅ Memory usage < 100MB

## Phase 6: Error Handling and Recovery

### 6.1 Failure Scenarios

**Test 6.1.1: Missing Directory**
- Delete an environment directory
- Run status command
- Verify graceful handling

**Expected Results**:
- ✅ Script doesn't crash
- ✅ Error message displayed
- ✅ Other environments still work

**Test 6.1.2: Port Conflict**
- Kill environment process mid-operation
- Try to start another on same port
- Verify error handling

**Expected Results**:
- ✅ Appropriate error message
- ✅ Port cleanup attempted
- ✅ Can restart after cleanup

**Test 6.1.3: Git Conflicts**
- Create merge conflict scenario
- Run sync operation
- Verify conflict detection and reporting

**Expected Results**:
- ✅ Conflict detected
- ✅ User instructed on resolution
- ✅ System stable after conflict

### 6.2 Recovery Procedures

**Test 6.2.1: Rollback Test**
- Perform full setup
- Run cleanup
- Verify complete restoration to original state

**Expected Results**:
- ✅ All new files removed
- ✅ No orphaned processes
- ✅ System back to original state

## Phase 7: Documentation Validation

### 7.1 Quick Start Verification

**Test 7.1.1: Follow Quick Start Guide**
- Use README_MULTI_ENV.md
- Follow MULTI_ENV_QUICKSTART.md
- Verify all steps work as documented

**Expected Results**:
- ✅ All commands execute successfully
- ✅ Output matches documentation
- ✅ No missing steps

### 7.2 Script Help Testing

**Test 7.2.1: Help Command**
- Run ./scripts/dev_env_git_workflow.sh help
- Verify help information complete
- Check all commands documented

**Expected Results**:
- ✅ Help displays
- ✅ All commands listed
- ✅ Examples provided

## Test Execution Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Script Validation | 5 min | ⏳ |
| Phase 2: Component Testing | 15 min | ⏳ |
| Phase 3: Integration Testing | 20 min | ⏳ |
| Phase 4: Full System Testing | 25 min | ⏳ |
| Phase 5: Performance Testing | 10 min | ⏳ |
| Phase 6: Error Handling | 15 min | ⏳ |
| Phase 7: Documentation | 10 min | ⏳ |
| **Total** | **100 min** | ⏳ |

## Test Success Criteria

### Must Pass
- ✅ All scripts execute without errors
- ✅ All 5 environments can be created
- ✅ All 26 sessions can be started
- ✅ GAIA recognizes all session patterns
- ✅ Git operations complete successfully
- ✅ Health monitoring works
- ✅ Cleanup/rollback successful
- ✅ Documentation is accurate

### Should Pass
- ✅ Performance within acceptable limits
- ✅ No resource leaks
- ✅ Graceful error handling
- ✅ Clear error messages

### Nice to Have
- ✅ Parallel operation support
- ✅ Advanced recovery options
- ✅ Extended monitoring capabilities

## Known Limitations for Testing

1. **Port Availability**: Tests assume ports 8081-8085 are available
2. **Tmux Installation**: Requires tmux to be installed
3. **Git Installed**: Requires git command
4. **Python 3**: Requires Python 3.6+
5. **Network**: Tests assume localhost only

## Reporting Template

```
TEST RESULT REPORT
==================

Date: [Date]
Tester: [Name]
Environment: [Description]

Summary:
--------
Phases Passed: X/7
Total Tests: Y
Passed: Z
Failed: W
Blocked: V

Critical Issues:
- [List any critical failures]

Major Issues:
- [List major issues]

Minor Issues:
- [List minor issues]

Recommendations:
- [List recommendations]

Approved for Production: YES/NO
Comments: [Additional notes]
```

## Next Steps After Testing

**If All Tests Pass**:
1. Generate final test report
2. Document any customizations
3. Schedule production deployment
4. Brief operations team
5. Create runbooks for common operations

**If Tests Fail**:
1. Document all failures with details
2. Create issues in tracking system
3. Schedule fixes
4. Re-test affected components
5. Repeat until all tests pass

**If Tests Are Blocked**:
1. Resolve blocking issues
2. Document resolution
3. Resume testing
4. Complete blocked phase

## Sign-Off

- [ ] Test Plan Reviewed
- [ ] Test Environment Prepared
- [ ] All Tests Executed
- [ ] Test Report Generated
- [ ] Issues Resolved
- [ ] Approved for Production

---

This test plan ensures comprehensive validation of the multi-environment orchestration system before production deployment.
