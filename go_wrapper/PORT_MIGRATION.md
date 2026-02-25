# Port Migration - Go Wrapper API

**Date**: 2026-02-09
**Migration**: Port 8080 → Standardized Ports (8151/8152/8163)

---

## Overview

Migrated Go Wrapper API to use standardized port scheme following the PORT_STANDARDIZATION.md pattern established for the architect project.

## Port Assignments

| Environment | Old Port | New Port | Usage |
|-------------|----------|----------|-------|
| DEV | 8080 | 8151 | Development environment |
| QA | N/A | 8152 | QA testing environment |
| PROD | N/A | 8163 | Production environment |

## Standardization Pattern

Following the pattern from PORT_STANDARDIZATION.md:
- **Base Port**: 8100 (API Services range: 8000-8999)
- **DEV**: Base + 51 = 8151
- **QA**: Base + 52 = 8152
- **PROD**: Base + 63 = 8163

This aligns with:
- Main Apps: 5000-5999 (Architect: 5051/5052/5063)
- API Services: 8000-8999 (Go Wrapper: 8151/8152/8163)
- Worker Services: 9000-9999

## Files Modified

### Configuration & Scripts (7 files)

1. **cmd/apiserver/main.go**
   - Changed default port from 8080 to 8151
   - Updated flag description to indicate DEV default

2. **start_dashboard.sh**
   - Completely rewritten to support environment-aware ports
   - Reads `APP_ENV` variable (dev/qa/prod)
   - Dynamically selects correct port

3. **test_api.sh**
   - Changed PORT variable from 8080 to 8151
   - Updated manual start instructions

4. **test_sse.sh**
   - Changed PORT variable from 8080 to 8151
   - Added port display in test output
   - Updated manual start instructions

5. **prometheus.yml**
   - Changed scrape target from localhost:8080 to localhost:8151

6. **test_sse.html**
   - Changed default API URL from localhost:8080 to localhost:8151

7. **dashboard.html**
   - Changed default API URL from localhost:8080 to localhost:8151

8. **dashboard_enhanced.html**
   - Changed default API URL from localhost:8080 to localhost:8151

### Documentation (5 files)

Updated port references in all phase documentation:

1. **PHASE2_COMPLETE.md** - Updated examples and commands
2. **PHASE3A_SSE.md** - Updated SSE streaming examples
3. **PHASE3B_DASHBOARD.md** - Updated dashboard URLs
4. **PHASE4A_ADVANCED_VIZ.md** - Updated visualization examples
5. **PHASE_SUMMARY.md** - Updated all port references

All occurrences of `:8080`, `port 8080`, and `Port 8080` were replaced with `:8151`, `port 8151`, and `Port 8151` respectively.

### Binary

- **apiserver** - Recompiled with new default port 8151

## Changes Summary

| Category | Files Changed |
|----------|--------------|
| Go Source | 1 |
| Shell Scripts | 3 |
| Configuration | 1 |
| HTML/UI | 3 |
| Documentation | 5 |
| **Total** | **13** |

## Testing

All port references have been updated. To verify:

```bash
# Verify no lingering 8080 references (excluding CSS colors)
grep -r "8080" . --include="*.go" --include="*.sh" --include="*.yml" | grep -v ".git"

# Expected: No results (CSS colors #808080 are intentionally excluded)
```

## Usage

### Development (Port 8151)

```bash
# Start server
./apiserver --port 8151
# Or use environment-aware script
APP_ENV=dev ./start_dashboard.sh

# Test
./test_api.sh
./test_sse.sh

# Access dashboards
http://localhost:8151/
http://localhost:8151/enhanced
http://localhost:8151/test-sse
```

### QA (Port 8152)

```bash
# Start server
./apiserver --port 8152
# Or use environment-aware script
APP_ENV=qa ./start_dashboard.sh

# Access dashboards
http://localhost:8152/
```

### Production (Port 8163)

```bash
# Start server
./apiserver --port 8163
# Or use environment-aware script
APP_ENV=prod ./start_dashboard.sh

# Access dashboards
http://localhost:8163/
```

## Migration Checklist

- [x] Update Go source default port
- [x] Update test scripts (test_api.sh, test_sse.sh)
- [x] Update start script (start_dashboard.sh)
- [x] Update monitoring config (prometheus.yml)
- [x] Update HTML clients (dashboard.html, dashboard_enhanced.html, test_sse.html)
- [x] Update documentation (PHASE*.md)
- [x] Rebuild binary
- [x] Verify no lingering 8080 references
- [x] Document migration

## Rollback Plan

If issues arise, rollback by:

```bash
git revert <commit-hash>
go build -o apiserver ./cmd/apiserver
```

Alternatively, manually override port at runtime:

```bash
./apiserver --port 8080  # Use old port temporarily
```

## Notes

- All HTML clients retain editable API URL input, allowing manual override if needed
- CSS color codes (#808080) were intentionally NOT changed
- The old port 8080 is no longer referenced in any functional code
- All environments can run simultaneously on different ports without conflict

---

**Migration Completed**: ✅
**Status**: Ready for deployment
**Next Steps**: Test in DEV (8151), QA (8152), and PROD (8163) environments
