# Web Dashboard - Quick Reference

## 🚀 Quick Start

### Start the Dashboard
```bash
python3 web_dashboard.py
```

### Access URLs
- **Dashboard UI**: http://localhost:8080
- **API Endpoint**: http://localhost:8080/api/status
- **Health Check**: http://localhost:8080/api/health

### Access from Other Devices
The dashboard binds to 0.0.0.0, so you can access it from other devices on your network:
```
http://YOUR_IP:8080
```

Find your IP:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

## 📊 Dashboard Features

### Real-Time Monitoring
- **Auto-Confirm Status** - Shows if auto-confirm worker is running
  - Process ID (PID)
  - CPU usage percentage
  - Memory usage in MB

- **Tmux Sessions** - Lists all active tmux sessions
  - Total count
  - First 5 sessions shown
  - Indicates if more exist

- **Research Projects** - Shows project status
  - Project name
  - Topic count
  - Status (complete/in progress)

- **Messaging Stats** - Message delivery statistics
  - Total messages sent
  - Breakdown by backend (WhatsApp, Email, File, Console)

- **Verification Metrics** - Automation verification stats
  - Success rate percentage
  - Total operations
  - Verified count
  - Failed count

- **System Resources** - Real-time system metrics
  - CPU usage (color-coded progress bar)
  - Memory usage (color-coded progress bar)
  - Disk usage (color-coded progress bar)
  - Green < 50%, Yellow < 80%, Red ≥ 80%

### Auto-Refresh
Dashboard automatically refreshes every **5 seconds** to show latest data.

## 🔧 Management Commands

### Check if Running
```bash
ps aux | grep web_dashboard
```

### View Logs
```bash
tail -f data/web_dashboard.log
```

### Stop the Dashboard
```bash
# Find PID
ps aux | grep web_dashboard | grep -v grep | awk '{print $2}'

# Kill process
kill <PID>

# Or force kill
pkill -f web_dashboard.py
```

### Restart
```bash
pkill -f web_dashboard.py
python3 web_dashboard.py > data/web_dashboard.log 2>&1 &
```

## 📡 API Usage

### Get Status (JSON)
```bash
curl http://localhost:8080/api/status | jq '.'
```

### Health Check
```bash
curl http://localhost:8080/api/health
```

### Example API Response
```json
{
  "timestamp": "2026-02-14T18:52:18.195916",
  "auto_confirm": {
    "running": true,
    "pid": 13782,
    "cpu_percent": 16.0,
    "memory_mb": 17.64
  },
  "tmux": {
    "count": 28,
    "sessions": ["architect", "foundation", "claude-1", ...],
    "total": 28
  },
  "research_projects": [
    {
      "name": "Ethiopia Trip",
      "topics": 7,
      "status": "complete",
      "path": "data/ethiopia/research_results"
    }
  ],
  "messaging": {
    "total_messages": 1,
    "by_backend": {
      "Email": 1
    }
  },
  "verification": {
    "total": 3,
    "verified": 2,
    "failed": 1,
    "success_rate": "66.7%"
  },
  "system": {
    "cpu_percent": 40.9,
    "memory_percent": 74.8,
    "disk_percent": 13.5
  }
}
```

## 🎨 UI Features

### Color Coding
- **Green** - Healthy (< 50%)
- **Yellow** - Warning (50-80%)
- **Red** - Critical (> 80%)

### Status Badges
- **Running** (Green) - Service is active
- **Stopped** (Red) - Service is inactive
- **Complete** (Blue) - Task finished

### Responsive Design
- Works on desktop, tablet, and mobile
- Touch-friendly interface
- Adaptive layout

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Find process using port 8080
lsof -i :8080

# Kill it
kill -9 <PID>

# Or use different port
# Edit web_dashboard.py, change: app.run(port=8081)
```

### Dashboard Not Updating
- Check if auto-confirm is running: `ps aux | grep auto_confirm_worker`
- Check if tmux sessions exist: `tmux list-sessions`
- Verify data files exist:
  - `data/messaging_stats.json`
  - `data/verification_log.json`

### API Returns Empty Data
- Ensure `status_dashboard.py` is in the same directory
- Check file permissions: `ls -la status_dashboard.py`
- Verify Python dependencies: `pip3 list | grep -E "flask|psutil"`

## 🚦 Integration Examples

### Monitor from Command Line
```bash
# Watch status updates
watch -n 5 'curl -s http://localhost:8080/api/status | jq .'

# Get just auto-confirm status
curl -s http://localhost:8080/api/status | jq '.auto_confirm'

# Get just system resources
curl -s http://localhost:8080/api/status | jq '.system'
```

### Use in Scripts
```python
import requests

response = requests.get('http://localhost:8080/api/status')
status = response.json()

if status['auto_confirm']['running']:
    print(f"Auto-confirm running on PID {status['auto_confirm']['pid']}")

if status['system']['cpu_percent'] > 80:
    print("WARNING: High CPU usage!")
```

### Monitor with cron
```bash
# Add to crontab: Check every hour
0 * * * * curl -s http://localhost:8080/api/health || echo "Dashboard down!" | mail -s "Alert" you@email.com
```

## 📦 Dependencies

- Flask (web framework)
- flask-cors (CORS support)
- psutil (system metrics)

Install:
```bash
pip3 install flask flask-cors psutil
```

## 🎯 Next Steps

1. **Auto-Confirm Dashboard** - Add real-time view of what auto-confirm is approving
2. **Alert System** - Email/SMS when metrics exceed thresholds
3. **Historical Charts** - Graph resource usage over time
4. **Mobile App** - Native mobile dashboard

## 💡 Tips

1. **Bookmark the URL** - Add http://localhost:8080 to your browser bookmarks
2. **Use Multiple Browsers** - Different tabs can show different sections
3. **Check Regularly** - Monitor during long-running automation
4. **API Integration** - Use the API in your own monitoring tools
5. **Network Access** - Access from phone/tablet while working

## 📝 Notes

- Dashboard runs as a background process
- Logs to `data/web_dashboard.log`
- Uses minimal resources (< 20MB RAM)
- Auto-refresh keeps data current without manual intervention
- CORS enabled for API access from any origin
