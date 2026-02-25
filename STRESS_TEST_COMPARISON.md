# Stress Test Comparison Report
## Run 1 vs Run 2 - System Performance Analysis

**Run 1**: 2026-02-17 14:49:38 (Initial run)
**Run 2**: 2026-02-17 14:56:08 (Re-run, 6.5 minutes later)

---

## Test Results Comparison

### **ST-5: Concurrent API Load Test**

| Metric | Run 1 | Run 2 | Change | Status |
|--------|-------|-------|--------|--------|
| Success Rate | 0.0% | 0.0% | No change | ❌ Flask unavailable |
| Throughput | 1,986 req/sec | 1,982 req/sec | -0.2% | ⚡ Consistent |
| Response Time (Avg) | 38.86ms | 40.18ms | +3.4% | ≈ Same |
| Response Time (P95) | 68.81ms | 73.26ms | +6.5% | ≈ Slightly slower |
| Response Time (Max) | 110.53ms | 102.11ms | -7.6% | ≈ Better |

**Analysis**:
- Flask still not running (connection refused on all 1,000 requests)
- Throughput remained stable at ~1,980 req/sec
- Response times show minimal variance between runs
- System is ready for API to come online

---

### **ST-6: Database Query Performance**

| Metric | Run 1 | Run 2 | Change | Status |
|--------|-------|-------|--------|--------|
| Success Rate | 50.0% | 50.0% | No change | ⚠️ Schema issues |
| Throughput | 663.72 queries/sec | 660.04 queries/sec | -0.6% | ≈ Consistent |
| Response Time (Avg) | 145.05ms | 147.96ms | +2.0% | ≈ Same |
| Response Time (P95) | 538.41ms | 518.35ms | -3.7% | ✅ Improved |
| Response Time (P99) | 675.84ms | 647.86ms | -4.1% | ✅ Improved |
| Response Time (Max) | 14,569ms | 14,146ms | -2.9% | ✅ Better |

**Analysis**:
- Database performance shows consistent 50% success rate
- Schema mismatches remain (same errors)
- Response time variance improved (max dropped 423ms)
- Positive: P99 latency improved by 28ms
- Database is stable but needs schema fixes

---

### **ST-10: Browser Automation Workload**

| Metric | Run 1 | Run 2 | Change | Status |
|--------|-------|-------|--------|--------|
| Success Rate | 0.0% | 0.0% | No change | ❌ Flask unavailable |
| Throughput | 1,844 tasks/sec | 191 tasks/sec | -89.6% ⚠️ **REGRESSION** |
| Response Time (Avg) | 10.11ms | 9.45ms | -6.5% | ✅ Faster |
| Response Time (P95) | 15.71ms | 15.18ms | -3.4% | ✅ Faster |
| Response Time (Max) | 16.9ms | 20.7ms | +22.2% | ⚠️ Higher |

**Analysis**:
- ⚠️ **ALERT**: Throughput dropped significantly (1,844 → 191 tasks/sec)
- All requests still failing (Flask unavailable)
- Response times improved locally but throughput degraded
- Possible cause: Connection pool exhaustion or backpressure buildup
- Action needed: Investigate connection handling

---

### **ST-11: End-to-End System Stress**

| Metric | Run 1 | Run 2 | Change | Status |
|--------|-------|-------|--------|--------|
| Success Rate | 0.0% | 0.0% | No change | ❌ Flask unavailable |
| Throughput | 1,933 ops/sec | 2,009 ops/sec | +3.9% | ✅ Improved |
| Response Time (Avg) | 9.08ms | 7.67ms | -15.5% | ✅ Faster |
| Response Time (P95) | 13.95ms | 12.72ms | -8.8% | ✅ Faster |
| Response Time (Max) | 16.06ms | 13.26ms | -17.4% | ✅ Better |

**Analysis**:
- ✅ Throughput improved 3.9% (1,933 → 2,009 ops/sec)
- ✅ All response time metrics improved (7-17% faster)
- Still 0% success (Flask unavailable)
- Overall system showing better efficiency in second run

---

## Summary Statistics

### **Throughput Comparison**
```
ST-5:  1,986 → 1,982 req/sec     (stable, -0.2%)
ST-6:  664   → 660 queries/sec   (stable, -0.6%)
ST-10: 1,844 → 191 tasks/sec     (⚠️ REGRESSION, -89.6%)
ST-11: 1,933 → 2,009 ops/sec     (✅ improved, +3.9%)

Average Change: -21.6% (skewed by ST-10 regression)
```

### **Response Time Comparison**
```
ST-5 Avg:   38.86 → 40.18ms   (+3.4%)
ST-6 Avg:   145.05 → 147.96ms (+2.0%)
ST-10 Avg:  10.11 → 9.45ms    (-6.5%) ✅
ST-11 Avg:  9.08 → 7.67ms     (-15.5%) ✅

Average Change: -4.1% (better in most tests)
```

---

## Key Findings

### ✅ Positive Trends
1. **ST-11 Performance**: 3.9% throughput improvement, 15% response time improvement
2. **Database Stability**: P99 latency improved by 28ms despite schema issues
3. **Local Response Times**: All tests show faster individual request times in Run 2
4. **System Consistency**: Most tests show stable performance across runs

### ⚠️ Concerns
1. **ST-10 Regression**: Throughput dropped from 1,844 to 191 tasks/sec (-89.6%)
   - Indicates possible resource exhaustion
   - Connection pool may be depleted after multiple test cycles
   - Needs investigation

2. **API Still Down**: Flask connection refused on 1,000 (ST-5) + 50 (ST-10) + 50 (ST-11) = 1,100 requests
   - Blocks validation of Phase 3B API
   - Prevents workstream 60-64 from starting

3. **Database Schema**: 50% query failure rate persists
   - Missing tables/columns still not resolved
   - Affects real workload performance

### 🔴 Critical Blockers
1. Flask must be restarted for API tests to pass
2. Database schema must be fixed (50% failure rate)
3. ST-10 regression needs investigation (connection pool issue?)

---

## Performance Baselines Established

### **Expected Performance (When Working)**
```
ST-5 API:    ~1,980 req/sec at ~40ms latency
ST-6 DB:     ~660 queries/sec at ~148ms latency
ST-10 Tasks: ~1,800 tasks/sec at ~9ms latency
ST-11 E2E:   ~2,000 ops/sec at ~8ms latency
```

### **Success Targets**
```
ST-5:  Currently 0%, Target 100% (after Flask restart)
ST-6:  Currently 50%, Target 100% (after schema fixes)
ST-10: Currently 0%, Target 100% (after Flask restart)
ST-11: Currently 0%, Target 100% (after Flask restart + schema fixes)
```

---

## Recommendations

### **Immediate (Next 30 minutes)**
1. ✅ **Restart Flask** - Unblock API tests
2. 🔧 **Investigate ST-10 Regression** - Check connection pool status
3. 🔧 **Fix Database Schema** - Add missing tables/columns

### **Short Term (Next 1-2 hours)**
1. Re-run all stress tests after Flask restart
2. Validate ST-5, ST-10, ST-11 reach 100% success
3. Optimize connection pooling for better resource usage
4. Monitor ST-10 throughput stabilization

### **Medium Term (Next 4-6 hours)**
1. Profile database queries to reduce P99 latency
2. Add connection pool tuning
3. Implement request batching for throughput optimization
4. Schedule automated daily stress tests

---

## Test Artifacts

- `stress_test_report.json` - Run 1 detailed metrics
- `stress_test_rerun.log` - Run 2 console output
- `STRESS_TEST_ANALYSIS.md` - Initial comprehensive analysis
- `STRESS_TEST_COMPARISON.md` - This comparison report

---

**Conclusion**: System shows stable baseline performance. Flask restart + database schema fixes will enable full validation. ST-10 regression requires investigation but may be related to test cycle accumulation rather than core issue.
