# Quickstart Guide

## 1. Build the Wrapper

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper
go build -o wrapper main.go
```

## 2. Test with a Simple Command

```bash
# Quick test
./wrapper test-1 echo "Hello"

# Check the log
cat logs/agents/test-1/*-stdout.log
```

## 3. Run Codex Agent

```bash
# Start codex with logging
./wrapper codex-1 codex

# Or in background
./wrapper codex-1 codex &

# Check logs in real-time
tail -f logs/agents/codex-1/*-stdout.log
```

## 4. Run Multiple Agents Concurrently

```bash
# Start multiple codex sessions
./wrapper codex-1 codex &
./wrapper codex-2 codex &
./wrapper codex-3 codex &

# Or use a loop
for i in {1..5}; do
    ./wrapper codex-$i codex &
done

# Monitor all logs
tail -f logs/agents/*/2026-*-stdout.log
```

## 5. Check Log Files

```bash
# List all agent logs
ls -lh logs/agents/*/

# Find today's logs
find logs/agents/ -name "2026-02-09*.log"

# Check log sizes
du -sh logs/agents/*

# View specific agent
cat logs/agents/codex-1/*-stdout.log
```

## 6. Integration with Tmux

```bash
# Create tmux session with wrapped codex
tmux new-session -d -s codex-1 './wrapper codex-1 codex'

# Attach to view
tmux attach -t codex-1

# Create multiple sessions
for i in {1..5}; do
    tmux new-session -d -s codex-$i "./wrapper codex-$i codex"
done

# List sessions
tmux list-sessions
```

## 7. Stop Agents Gracefully

```bash
# Send SIGTERM to wrapper (it will forward to codex)
pkill -TERM -f "wrapper codex-1"

# Or use job control if running in foreground
# Ctrl+C (wrapper catches and stops codex cleanly)
```

## 8. Analyze Logs

```bash
# Count lines per agent
wc -l logs/agents/*/2026-*-stdout.log

# Search across all logs
grep -r "error" logs/agents/

# Check for ANSI codes (should be none)
grep -r $'\x1b' logs/agents/

# Get last 100 lines from all agents
for log in logs/agents/*/2026-*-stdout.log; do
    echo "=== $log ==="
    tail -100 "$log"
    echo ""
done
```

## 9. Custom Commands

```bash
# Run any command through wrapper
./wrapper my-agent bash -c "complex command here"

# With npm
./wrapper npm-agent npm run dev

# With python
./wrapper py-agent python3 script.py

# With custom environment
WRAPPER_LOGS_DIR=/custom/logs ./wrapper my-agent codex
```

## 10. Cleanup Old Logs

```bash
# Remove logs older than 7 days
find logs/agents/ -name "*.log" -mtime +7 -delete

# Archive old logs
tar -czf logs-archive-$(date +%Y%m%d).tar.gz logs/agents/
rm -rf logs/agents/*

# Or keep only recent
ls -t logs/agents/codex-1/*.log | tail -n +10 | xargs rm
```

## Performance Tips

### For 20+ Concurrent Agents

1. **Use SSD for logs** - Critical for I/O
   ```bash
   ln -s /path/to/ssd/logs logs/agents
   ```

2. **Monitor disk space**
   ```bash
   watch -n 60 'df -h | grep logs'
   ```

3. **Rotate logs automatically** (already built-in at 100MB)

4. **Check memory usage**
   ```bash
   ps aux | grep wrapper | awk '{sum+=$6} END {print "Total: " sum/1024 "MB"}'
   ```

5. **Limit concurrent agents if needed**
   ```bash
   # Use sem for concurrency control
   for i in {1..20}; do
       sem -j 10 "./wrapper codex-$i codex &"
   done
   ```

## Troubleshooting

### Wrapper won't start
```bash
# Check binary exists
ls -lh wrapper

# Rebuild
go build -o wrapper main.go

# Make executable
chmod +x wrapper
```

### Logs directory permission denied
```bash
mkdir -p logs/agents
chmod 755 logs/agents
```

### Process hangs
```bash
# Find wrapper processes
ps aux | grep wrapper

# Kill gracefully
pkill -TERM -f wrapper

# Force kill if needed
pkill -KILL -f wrapper
```

### High CPU usage
Check for ANSI regex inefficiency:
```bash
# Profile the wrapper
go test -cpuprofile=cpu.prof ./stream
go tool pprof cpu.prof
```

## Next Steps

- **Phase 2**: Add regex extraction for structured data
- **Dashboard Integration**: Real-time log viewer
- **Metrics**: Export Prometheus metrics
- **Compression**: Auto-compress old logs with gzip
