#!/usr/bin/env python3
"""
Node Agent

A lightweight agent that runs on each cluster node to:
- Send heartbeats to the central dashboard
- Report system metrics (CPU, memory, disk)
- Manage local tmux sessions
- Execute commands from the dashboard
- Report errors back to the dashboard

Usage:
    python3 node_agent.py                           # Run agent
    python3 node_agent.py --dashboard http://host:8080   # Custom dashboard URL
    python3 node_agent.py --daemon                  # Run as daemon
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths for imports
AGENT_DIR = Path(__file__).parent
BASE_DIR = AGENT_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from graceful_shutdown import GracefulShutdown, ShutdownReason

# Configuration
DEFAULT_DASHBOARD_URL = "http://100.112.58.92:8080"
HEARTBEAT_INTERVAL = 30  # seconds
METRICS_INTERVAL = 60  # seconds
PID_FILE = Path("/tmp/architect_node_agent.pid")
STATE_FILE = Path("/tmp/architect_node_agent_state.json")
LOG_FILE = Path("/tmp/architect_node_agent.log")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("NodeAgent")


class NodeAgent:
    """
    Agent that runs on each cluster node.

    Responsibilities:
    - Report system metrics to the dashboard
    - Manage local tmux sessions
    - Execute commands from the dashboard
    - Report errors

    Features graceful shutdown with proper cleanup.
    """

    def __init__(
        self,
        dashboard_url: str = DEFAULT_DASHBOARD_URL,
        node_id: Optional[str] = None,
        hostname: Optional[str] = None,
        heartbeat_interval: int = HEARTBEAT_INTERVAL,
        metrics_interval: int = METRICS_INTERVAL,
        shutdown_timeout: int = 30,
    ):
        self.dashboard_url = dashboard_url.rstrip("/")
        self.node_id = node_id or self._generate_node_id()
        self.hostname = hostname or socket.gethostname()
        self.ip_address = self._get_ip_address()
        self.heartbeat_interval = heartbeat_interval
        self.metrics_interval = metrics_interval

        self._running = False
        self._start_time = None
        self._last_heartbeat = None
        self._last_metrics = None
        self._registered = False

        self._lock = threading.Lock()

        # Graceful shutdown handler
        self._shutdown = GracefulShutdown(
            worker_id=self.node_id,
            worker_type="node-agent",
            shutdown_timeout=shutdown_timeout,
            on_shutdown=self._on_shutdown,
            on_cleanup=self._on_cleanup,
            notify_dashboard=True,
            dashboard_url=dashboard_url,
            pid_file=PID_FILE,
            state_file=STATE_FILE,
        )

    def _on_shutdown(self):
        """Called when shutdown signal is received."""
        logger.info(f"Node agent {self.node_id} received shutdown signal")
        self._running = False

        # Notify dashboard we're shutting down
        try:
            self._send_request(f"/nodes/{self.node_id}/status", "POST", {"status": "shutting_down"})
        except Exception:
            pass

    def _on_cleanup(self):
        """Called during final cleanup phase."""
        logger.info(f"Cleaning up node agent {self.node_id}")

        # Mark node as offline
        try:
            self._send_request(
                f"/nodes/{self.node_id}/status",
                "POST",
                {"status": "offline", "shutdown_time": datetime.now().isoformat()},
            )
        except Exception:
            pass

        self._save_state()

    def _generate_node_id(self) -> str:
        """Generate a unique node ID based on hostname and MAC."""
        hostname = socket.gethostname()
        # Create deterministic ID from hostname
        return f"{hostname}-{uuid.uuid5(uuid.NAMESPACE_DNS, hostname).hex[:8]}"

    def _get_ip_address(self) -> str:
        """Get the primary IP address of this node."""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Collect system metrics."""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            load_avg = os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0]

            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "memory_total_mb": memory.total // (1024 * 1024),
                "memory_available_mb": memory.available // (1024 * 1024),
                "disk_usage": disk.percent,
                "disk_total_gb": disk.total // (1024 * 1024 * 1024),
                "disk_free_gb": disk.free // (1024 * 1024 * 1024),
                "load_average": list(load_avg),
                "cpu_cores": psutil.cpu_count(),
            }

        except ImportError:
            # Fallback without psutil
            return self._get_metrics_without_psutil()

    def _get_metrics_without_psutil(self) -> Dict[str, Any]:
        """Get metrics without psutil using shell commands."""
        metrics = {"cpu_usage": 0, "memory_usage": 0, "disk_usage": 0, "load_average": [0, 0, 0]}

        try:
            # CPU usage via top
            result = subprocess.run(
                ["top", "-l", "1", "-n", "0"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "CPU usage" in line:
                        # Parse: "CPU usage: 5.0% user, 10.0% sys, 85.0% idle"
                        parts = line.split(",")
                        user = float(parts[0].split(":")[1].replace("%", "").strip().split()[0])
                        sys_cpu = float(parts[1].replace("%", "").strip().split()[0])
                        metrics["cpu_usage"] = user + sys_cpu
                        break
        except Exception:
            pass

        try:
            # Memory via vm_stat (macOS) or free (Linux)
            if sys.platform == "darwin":
                result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
                # Parse vm_stat output
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    stats = {}
                    for line in lines[1:]:
                        if ":" in line:
                            key, value = line.split(":")
                            stats[key.strip()] = int(value.strip().rstrip("."))

                    page_size = 4096  # bytes
                    total_pages = (
                        stats.get("Pages free", 0)
                        + stats.get("Pages active", 0)
                        + stats.get("Pages inactive", 0)
                        + stats.get("Pages speculative", 0)
                        + stats.get("Pages wired down", 0)
                    )
                    used_pages = total_pages - stats.get("Pages free", 0)
                    if total_pages > 0:
                        metrics["memory_usage"] = (used_pages / total_pages) * 100
            else:
                result = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        total = int(parts[1])
                        used = int(parts[2])
                        if total > 0:
                            metrics["memory_usage"] = (used / total) * 100
        except Exception:
            pass

        try:
            # Disk usage via df
            result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    # Find percentage column
                    for part in parts:
                        if "%" in part:
                            metrics["disk_usage"] = float(part.replace("%", ""))
                            break
        except Exception:
            pass

        try:
            # Load average
            result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                if "load average:" in output:
                    load_str = output.split("load average:")[1].strip()
                    loads = [float(x.strip().rstrip(",")) for x in load_str.split()[:3]]
                    metrics["load_average"] = loads
        except Exception:
            pass

        return metrics

    def _get_tmux_sessions(self) -> List[Dict]:
        """Get list of local tmux sessions."""
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "list-sessions",
                    "-F",
                    "#{session_name}:#{session_windows}:#{session_attached}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            sessions = []
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":")
                        if len(parts) >= 3:
                            sessions.append(
                                {
                                    "name": parts[0],
                                    "windows": int(parts[1]),
                                    "attached": parts[2] == "1",
                                }
                            )
            return sessions

        except Exception as e:
            logger.debug(f"Could not get tmux sessions: {e}")
            return []

    def _send_request(
        self, endpoint: str, method: str = "POST", data: Dict = None
    ) -> Optional[Dict]:
        """Send HTTP request to the dashboard."""
        try:
            import requests

            url = f"{self.dashboard_url}/api{endpoint}"

            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Request failed: {response.status_code}")
                return None

        except ImportError:
            # Use urllib as fallback
            return self._send_request_urllib(endpoint, method, data)

        except Exception as e:
            logger.debug(f"Request error: {e}")
            return None

    def _send_request_urllib(
        self, endpoint: str, method: str = "POST", data: Dict = None
    ) -> Optional[Dict]:
        """Send request using urllib (no external dependencies)."""
        try:
            import urllib.error
            import urllib.request

            url = f"{self.dashboard_url}/api{endpoint}"
            headers = {"Content-Type": "application/json"}

            if data:
                data_bytes = json.dumps(data).encode("utf-8")
            else:
                data_bytes = None

            req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        except Exception as e:
            logger.debug(f"urllib error: {e}")
            return None

    def register(self) -> bool:
        """Register this node with the dashboard."""
        result = self._send_request(
            "/nodes",
            "POST",
            {
                "id": self.node_id,
                "hostname": self.hostname,
                "ip_address": self.ip_address,
                "ssh_port": 22,
                "ssh_user": os.environ.get("USER", "root"),
                "role": "worker",
                "services": ["tmux", "worker"],
            },
        )

        if result and result.get("success"):
            self._registered = True
            logger.info(f"Registered node {self.node_id} ({self.hostname})")
            return True
        else:
            logger.warning("Failed to register with dashboard")
            return False

    def send_heartbeat(self) -> bool:
        """Send heartbeat with metrics to the dashboard."""
        metrics = self._get_system_metrics()
        metrics["tmux_sessions"] = self._get_tmux_sessions()

        result = self._send_request(f"/nodes/{self.node_id}/heartbeat", "POST", metrics)

        if result and result.get("success"):
            self._last_heartbeat = datetime.now()
            return True
        else:
            return False

    def report_error(self, error_type: str, message: str, **kwargs) -> bool:
        """Report an error to the dashboard."""
        result = self._send_request(
            "/errors",
            "POST",
            {"node_id": self.node_id, "error_type": error_type, "message": message, **kwargs},
        )

        return result is not None

    def _save_state(self):
        """Save agent state to file."""
        state = {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "dashboard_url": self.dashboard_url,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "registered": self._registered,
            "running": self._running,
            "timestamp": datetime.now().isoformat(),
        }

        STATE_FILE.write_text(json.dumps(state, indent=2))

    def run(self):
        """Main agent loop with graceful shutdown support."""
        self._running = True
        self._start_time = datetime.now()

        logger.info(f"Starting node agent on {self.hostname} ({self.node_id})")
        logger.info(f"Dashboard URL: {self.dashboard_url}")
        logger.info("Graceful shutdown enabled")

        # Register graceful shutdown handler
        self._shutdown.register()

        # Register with dashboard
        self.register()

        last_heartbeat = 0
        last_metrics = 0

        try:
            while self._running and self._shutdown.should_run:
                current_time = time.time()

                # Send heartbeat
                if current_time - last_heartbeat >= self.heartbeat_interval:
                    if self.send_heartbeat():
                        logger.debug("Heartbeat sent")
                    else:
                        logger.warning("Heartbeat failed")

                        # Try to re-register
                        if not self._registered:
                            self.register()

                    last_heartbeat = current_time

                self._save_state()
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Agent interrupted")
            self._shutdown.request_shutdown(ShutdownReason.SIGINT)
        finally:
            self._running = False
            self._save_state()
            logger.info("Agent stopped")

    def stop(self):
        """Stop the agent gracefully."""
        logger.info(f"Stop requested for node agent {self.node_id}")
        self._shutdown.request_shutdown(ShutdownReason.MANUAL)


def run_daemon(dashboard_url: str):
    """Run agent as a daemon with graceful shutdown support."""
    # Check if already running
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Agent already running (PID {pid})")
            return
        except ProcessLookupError:
            PID_FILE.unlink()

    # Fork
    pid = os.fork()
    if pid > 0:
        print(f"Agent started (PID {pid})")
        return

    # Daemon setup
    os.setsid()
    os.chdir("/")

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    # Start agent - GracefulShutdown handles signals internally
    agent = NodeAgent(dashboard_url=dashboard_url)
    agent.run()
    # Note: Agent's graceful shutdown will clean up PID file


def stop_daemon():
    """Stop the daemon."""
    if not PID_FILE.exists():
        print("Agent not running")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent stop signal to agent (PID {pid})")

        # Wait for process to stop
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("Agent stopped")
                PID_FILE.unlink()
                return

        print("Agent did not stop, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink()

    except ProcessLookupError:
        print("Agent not running")
        PID_FILE.unlink()


def show_status():
    """Show agent status."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

        print(
            f"""
Node Agent Status
=================
Node ID:     {state.get('node_id', 'N/A')}
Hostname:    {state.get('hostname', 'N/A')}
IP Address:  {state.get('ip_address', 'N/A')}
Dashboard:   {state.get('dashboard_url', 'N/A')}
Registered:  {state.get('registered', False)}
Running:     {state.get('running', False)}
Started:     {state.get('start_time', 'N/A')}
Last HB:     {state.get('last_heartbeat', 'N/A')}
Last Update: {state.get('timestamp', 'N/A')}
"""
        )
    else:
        print("No agent state found")

    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Process: Running (PID {pid})")
        except ProcessLookupError:
            print("Process: Not running (stale PID file)")
    else:
        print("Process: Not running")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Node Agent")
    parser.add_argument("--dashboard", default=DEFAULT_DASHBOARD_URL, help="Dashboard URL")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--node-id", help="Node ID (auto-generated if not provided)")
    parser.add_argument("--hostname", help="Override hostname")
    parser.add_argument(
        "--heartbeat-interval", type=int, default=HEARTBEAT_INTERVAL, help="Heartbeat interval"
    )

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        show_status()
    elif args.daemon:
        run_daemon(args.dashboard)
    else:
        # Run in foreground
        agent = NodeAgent(
            dashboard_url=args.dashboard,
            node_id=args.node_id,
            hostname=args.hostname,
            heartbeat_interval=args.heartbeat_interval,
        )
        agent.run()


if __name__ == "__main__":
    main()
