# Piano App: Performance Benchmark - Python vs Go

## Objective

Demonstrate 20-30x performance improvement by comparing the Python/Flask Piano app with the Go/Gin implementation across key metrics.

## Benchmark Methodology

### Hardware
- **CPU**: Multi-core processor (standardize across runs)
- **Memory**: At least 2GB available
- **Database**: PostgreSQL 15 (same version for both)
- **Load Generator**: Apache JMeter or similar

### Test Scenarios

#### 1. Startup Time
**Test**: Measure time from process start to accepting requests

**Python/Flask**:
```bash
time python3 piano/app.py
```

**Go/Gin**:
```bash
time ./unified-app
```

**Expected Improvement**: 20x (2000ms → <100ms)

#### 2. Memory Usage (Idle)
**Test**: Measure process memory 30 seconds after startup

**Python/Flask**:
```bash
ps aux | grep python | grep piano
# RSS column
```

**Go/Gin**:
```bash
ps aux | grep unified-app
# RSS column
```

**Expected Improvement**: 3-5x (50MB → 10-15MB)

#### 3. Single Request Latency
**Test**: GET /api/piano/exercises with 100 concurrent connections, 1000 requests

**Load Test (Apache JMeter)**:
```xml
<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup">
  <elementProp name="ThreadGroup.main_controller"/>
  <stringProp name="ThreadGroup.num_threads">100</stringProp>
  <stringProp name="ThreadGroup.ramp_time">10</stringProp>
  <stringProp name="ThreadGroup.duration">60</stringProp>
</ThreadGroup>
```

**Metrics**:
- Response time percentiles (p50, p95, p99)
- Error rate
- Throughput (requests/second)

**Expected Results**:

| Metric | Python | Go | Improvement |
|--------|--------|-----|------------|
| p50 latency | 100ms | <10ms | 10x |
| p95 latency | 250ms | <30ms | 8x |
| p99 latency | 500ms | <50ms | 10x |
| Throughput | 1,000 req/s | 25,000 req/s | 25x |

#### 4. Database Query Performance
**Test**: Measure query execution time for common operations

**Queries Tested**:
- GET /api/piano/exercises (list, filtered)
- GET /api/piano/exercises/:id (single record)
- POST /api/piano/attempts (insert)
- GET /api/piano/leaderboard (aggregate with ORDER BY)

**Measurement**:
```bash
# Python Flask
ab -c 50 -n 1000 http://localhost:5000/api/exercises

# Go Gin
ab -c 50 -n 1000 http://localhost:8080/api/piano/exercises
```

#### 5. Memory Usage Under Load
**Test**: Memory during sustained 1000 req/s load

**Expected Improvement**: 5-10x (lower garbage collection overhead)

#### 6. CPU Usage
**Test**: CPU utilization during load tests

**Python/Flask**:
```bash
# Single-threaded: high CPU usage
# Flask with gunicorn: multiple workers

gunicorn --workers=4 piano/app.py
```

**Go/Gin**:
```bash
# Go runtime: automatic goroutine scheduling
./unified-app
```

**Expected**: Go uses significantly less CPU due to:
- Compiled language (no interpreter overhead)
- Efficient goroutines vs OS threads
- Better concurrency model

## Benchmark Results Template

### Run: [Date] [Environment]

#### Startup Time
- **Python**: _____ ms
- **Go**: _____ ms
- **Improvement**: _____x

#### Idle Memory
- **Python**: _____ MB
- **Go**: _____ MB
- **Improvement**: _____x

#### Request Latency (100 concurrent, 1000 requests)
**Python/Flask**:
- p50: _____ ms
- p95: _____ ms
- p99: _____ ms
- Throughput: _____ req/s
- Error Rate: _____%

**Go/Gin**:
- p50: _____ ms
- p95: _____ ms
- p99: _____ ms
- Throughput: _____ req/s
- Error Rate: _____%

**Improvement**:
- p50: _____x
- Throughput: _____x

#### Memory Under Load
- **Python**: _____ MB
- **Go**: _____ MB
- **Improvement**: _____x

#### CPU Usage
- **Python**: _____%
- **Go**: _____%
- **Reduction**: _____%

## Benchmarking Tools

### Apache JMeter Script
```jmeter
HTTP Request Defaults:
- Protocol: HTTP
- Server: localhost
- Port: 8080/5000

Thread Group:
- Number of threads: 100
- Ramp-up: 10s
- Duration: 60s

HTTP Sampler:
- Path: /api/piano/exercises
- Method: GET

Result Tree Listener:
- Log all responses
- Generate HTML report
```

### Go Benchmark Code
```go
func BenchmarkGetExercises(b *testing.B) {
    router := setupTestRouter()
    req, _ := http.NewRequest("GET", "/api/piano/exercises", nil)
    w := httptest.NewRecorder()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        w = httptest.NewRecorder()
        router.ServeHTTP(w, req)
    }
}

// Run with: go test -bench=. -benchmem
```

### Python Load Test
```python
import requests
import time
from concurrent.futures import ThreadPoolExecutor

def load_test(url, num_requests=1000, num_threads=100):
    start = time.time()

    def make_request():
        return requests.get(url)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(make_request, [url] * num_requests))

    elapsed = time.time() - start
    success = len([r for r in results if r.status_code == 200])

    print(f"Completed {success}/{num_requests} requests in {elapsed:.2f}s")
    print(f"Throughput: {num_requests/elapsed:.0f} req/s")

load_test("http://localhost:5000/api/exercises")
```

## Expected Performance Gains

### Startup Time
- **Reason**: Go compiles to native binary vs Python interpreter startup
- **Improvement**: 20x (2000ms → <100ms)

### Memory Usage
- **Reason**: Go's efficient memory management, no GC pauses like CPython
- **Improvement**: 3-5x (50MB → 10-15MB)

### Request Latency
- **Reason**:
  - Compiled language (no interpretation overhead)
  - Better concurrency (goroutines vs threads)
  - Efficient string/JSON handling
- **Improvement**: 10-25x (<10ms vs 100ms)

### Throughput
- **Reason**:
  - Can handle thousands of concurrent connections efficiently
  - No GIL (Python's Global Interpreter Lock)
  - Lightweight goroutines (millions possible)
- **Improvement**: 25x (25,000 vs 1,000 req/s)

### CPU Usage
- **Reason**:
  - No interpreter overhead
  - Efficient goroutine scheduler
  - Single binary vs multi-process Flask
- **Reduction**: 60-80% reduction in CPU usage

## Considerations

### When Go May Be Slower
1. **First request**: JIT compilation overhead (negligible for server apps)
2. **Very simple operations**: Python can be faster due to optimized C libraries
3. **GC pauses**: Large Go heaps may have noticeable GC pauses (mitigated with tuning)

### When Go Is Faster
1. ✅ I/O-heavy workloads (database queries, file I/O)
2. ✅ High concurrency scenarios
3. ✅ Long-running processes (startup cost amortized)
4. ✅ Memory efficiency (lower memory per concurrent request)

## Verification Checklist

- [ ] Baseline measurements taken (Python)
- [ ] Same hardware used for both
- [ ] Same database schema and data
- [ ] Same test load profiles
- [ ] Measurements repeated 3+ times
- [ ] Results averaged
- [ ] Cache warmed up before measurements
- [ ] Network latency accounted for

## References

- [Go Performance Tips](https://golang.org/doc/diagnostics)
- [Benchmarking Go Code](https://golang.org/pkg/testing/#B)
- [Apache JMeter User Manual](https://jmeter.apache.org/usermanual/)
- [Python Performance Profiling](https://docs.python.org/3/library/profile.html)
