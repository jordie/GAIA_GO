#!/usr/bin/env python3
"""
Auto-Confirm HA Monitor - Health Check & Restart
Ensures one auto-confirm worker always runs with proper failover.

Runs two workers:
- Primary: auto_confirm_worker_1
- Secondary: auto_confirm_worker_2

Both use shared lock file to prevent simultaneous confirms (no race conditions).
This monitor checks if both are alive and restarts if needed.

Run as:
    nohup python3 workers/auto_confirm_ha_monitor.py > /tmp/auto_confirm_ha.log 2>&1 &
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Config
WORKER_SCRIPT = Path(__file__).parent / "auto_confirm_worker.py"  # Absolute path to worker
LOCK_FILE = Path("/tmp/auto_confirm_shared.lock")
STATE_FILE = Path("/tmp/auto_confirm_ha_state.json")
CHECK_INTERVAL = 10  # Check every 10 seconds
RESTART_DELAY = 2  # Wait 2s before restarting

# Worker instances
WORKERS = {
    'primary': {'pid': None, 'name': 'auto_confirm_worker_1'},
    'secondary': {'pid': None, 'name': 'auto_confirm_worker_2'},
}

def log(msg):
    """Log with timestamp"""
    ts = datetime.now().isoformat()
    print(f"[{ts}] {msg}")
    sys.stdout.flush()

def find_worker_pid(worker_name):
    """Find PID of running worker"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'auto_confirm_worker.py'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            # Get all PIDs and filter out the monitor itself
            valid_pids = []
            for pid_str in pids:
                if pid_str and pid_str != str(os.getpid()):
                    try:
                        valid_pids.append(int(pid_str))
                    except ValueError:
                        pass
            # Return first valid PID
            return valid_pids[0] if valid_pids else None
    except Exception as e:
        log(f"❌ Error finding PID: {e}")
    return None

def is_worker_alive(pid):
    """Check if process is still running"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except OSError:
        return False

def start_worker(worker_name):
    """Start a worker instance"""
    try:
        log(f"🚀 Starting {worker_name}...")
        subprocess.Popen(
            ['python3', str(WORKER_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        time.sleep(RESTART_DELAY)
        pid = find_worker_pid(worker_name)
        if pid:
            log(f"✅ {worker_name} started (PID: {pid})")
            return pid
        else:
            log(f"⚠️  {worker_name} started but PID not found")
            return None
    except Exception as e:
        log(f"❌ Failed to start {worker_name}: {e}")
        return None

def ensure_lock_file():
    """Ensure shared lock file exists"""
    try:
        LOCK_FILE.touch(exist_ok=True)
    except Exception as e:
        log(f"❌ Error creating lock file: {e}")

def monitor_health():
    """Continuous health monitoring"""
    log("🔄 Auto-Confirm HA Monitor started")
    log("   Primary: auto_confirm_worker_1")
    log("   Secondary: auto_confirm_worker_2")
    log("   Lock file: /tmp/auto_confirm_shared.lock")
    log("   Shared state prevents race conditions")

    ensure_lock_file()

    # Start both workers
    WORKERS['primary']['pid'] = start_worker('primary')
    time.sleep(1)
    WORKERS['secondary']['pid'] = start_worker('secondary')

    failure_count = 0

    while True:
        try:
            time.sleep(CHECK_INTERVAL)

            # Check both workers
            primary_alive = is_worker_alive(WORKERS['primary']['pid'])
            secondary_alive = is_worker_alive(WORKERS['secondary']['pid'])

            status = f"Primary: {'✅ alive' if primary_alive else '❌ dead'} | Secondary: {'✅ alive' if secondary_alive else '❌ dead'}"
            log(status)

            # Restart if dead
            if not primary_alive:
                log("⚠️  PRIMARY DEAD - Restarting...")
                WORKERS['primary']['pid'] = start_worker('primary')
                failure_count += 1

            if not secondary_alive:
                log("⚠️  SECONDARY DEAD - Restarting...")
                WORKERS['secondary']['pid'] = start_worker('secondary')
                failure_count += 1

            # Alert if too many restarts (indicates systemic problem)
            if failure_count > 5:
                log("⚠️  WARNING: Excessive restarts - possible systemic issue")
                failure_count = 0

            # Both alive = success
            if primary_alive and secondary_alive:
                failure_count = 0

        except KeyboardInterrupt:
            log("\n🛑 Monitor stopped by user")
            break
        except Exception as e:
            log(f"❌ Monitor error: {e}")
            failure_count += 1

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    log("\n🛑 Shutting down...")
    # Kill both workers
    for worker_name, worker_info in WORKERS.items():
        if worker_info['pid']:
            try:
                os.kill(worker_info['pid'], signal.SIGTERM)
                log(f"   Stopped {worker_name} (PID: {worker_info['pid']})")
            except:
                pass
    sys.exit(0)

if __name__ == '__main__':
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start monitoring
    try:
        monitor_health()
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        sys.exit(1)
