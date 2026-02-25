#!/usr/bin/env python3
"""
Process Supervisor - Advanced service supervision system

Monitors and manages critical services with:
- Auto-restart on failure with exponential backoff
- Health checks (HTTP, TCP, process)
- Resource monitoring and limits
- Graceful shutdown handling
- Dependency management
- Integration with architect dashboard
- Detailed logging and metrics

This replaces traditional supervisord with a Python-native solution
optimized for the architect dashboard ecosystem.
"""

import json
import logging
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/process_supervisor.log"), logging.StreamHandler()],
)
logger = logging.getLogger("process_supervisor")


class ServiceState(Enum):
    """Service state enumeration."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    BACKOFF = "backoff"
    FATAL = "fatal"


class HealthCheckType(Enum):
    """Health check type enumeration."""

    HTTP = "http"
    TCP = "tcp"
    PROCESS = "process"


@dataclass
class ServiceMetrics:
    """Service performance metrics."""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: int = 0
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    health_check_failures: int = 0
    last_health_check: Optional[datetime] = None
    total_failures: int = 0


@dataclass
class ManagedService:
    """Managed service configuration and state."""

    id: str
    config: Dict[str, Any]
    state: ServiceState = ServiceState.STOPPED
    process: Optional[psutil.Process] = None
    pid: Optional[int] = None
    start_time: Optional[datetime] = None
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)
    restart_attempts: int = 0
    next_restart_time: Optional[datetime] = None
    last_error: Optional[str] = None


class ProcessSupervisor:
    """Advanced process supervision system."""

    def __init__(self, config_path: str = None):
        """Initialize process supervisor.

        Args:
            config_path: Path to configuration file
        """
        if config_path is None:
            config_path = Path(__file__).parent / "supervisor_config.json"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.services: Dict[str, ManagedService] = {}
        self.running = False
        self.pid_file = Path("/tmp/process_supervisor.pid")

        # Global settings
        global_config = self.config.get("global", {})
        self.check_interval = global_config.get("check_interval", 30)
        self.restart_delay = global_config.get("restart_delay", 5)
        self.log_directory = Path(global_config.get("log_directory", "/tmp/supervisor_logs"))
        self.pid_directory = Path(global_config.get("pid_directory", "/tmp/supervisor_pids"))

        # Create directories
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.pid_directory.mkdir(parents=True, exist_ok=True)

        # Event queue for async operations
        self.event_queue = queue.Queue()

        # Initialize services
        self._initialize_services()

    def _load_config(self) -> Dict:
        """Load supervisor configuration."""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def _initialize_services(self):
        """Initialize all configured services."""
        services_config = self.config.get("services", {})

        for service_id, service_config in services_config.items():
            if not service_config.get("enabled", True):
                logger.info(f"Service '{service_id}' is disabled, skipping")
                continue

            service = ManagedService(
                id=service_id, config=service_config, state=ServiceState.STOPPED
            )

            self.services[service_id] = service
            logger.info(
                f"Initialized service: {service_id} - {service_config.get('name', service_id)}"
            )

    def start(self):
        """Start the supervisor daemon."""
        if self.is_running():
            logger.warning("Process supervisor already running")
            return False

        # Write PID file
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("🚀 Process Supervisor started")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Managing {len(self.services)} services")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        self.running = True

        # Start all enabled services
        self._start_all_services()

        # Start monitoring thread
        monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        monitor_thread.start()

        # Main supervision loop
        try:
            while self.running:
                self._supervision_cycle()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Supervisor stopped by user")
        except Exception as e:
            logger.error(f"Supervisor crashed: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop the supervisor and all services."""
        logger.info("Stopping process supervisor...")
        self.running = False

        # Stop all services
        for service_id, service in self.services.items():
            if service.state in [ServiceState.RUNNING, ServiceState.STARTING]:
                logger.info(f"Stopping service: {service_id}")
                self._stop_service(service)

        # Remove PID file
        if self.pid_file.exists():
            self.pid_file.unlink()

        logger.info("Process supervisor stopped")

    def is_running(self) -> bool:
        """Check if supervisor is already running."""
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            return psutil.pid_exists(pid)
        except (ValueError, ProcessLookupError):
            return False

    def _start_all_services(self):
        """Start all enabled services in priority order."""
        # Sort services by priority
        services_sorted = sorted(
            self.services.items(), key=lambda x: x[1].config.get("priority", 999)
        )

        for service_id, service in services_sorted:
            logger.info(f"Starting service: {service_id}")
            self._start_service(service)
            time.sleep(2)  # Brief delay between starts

    def _start_service(self, service: ManagedService) -> bool:
        """Start a service.

        Args:
            service: Service to start

        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Check if already running
            if service.state == ServiceState.RUNNING and service.process:
                if service.process.is_running():
                    logger.debug(f"Service '{service.id}' already running")
                    return True

            service.state = ServiceState.STARTING

            # Build command
            command = [service.config["command"]] + service.config.get("args", [])

            # Set up environment
            env = os.environ.copy()
            env.update(service.config.get("environment", {}))

            # Set up logging
            log_file = self.log_directory / f"{service.id}.log"
            log_handle = open(log_file, "a")

            # Start process
            working_dir = service.config.get("working_directory", os.getcwd())

            proc = subprocess.Popen(
                command,
                env=env,
                cwd=working_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            # Wait briefly and check if process started
            time.sleep(1)

            if proc.poll() is not None:
                logger.error(
                    f"Service '{service.id}' failed to start (exit code: {proc.returncode})"
                )
                service.state = ServiceState.FAILED
                service.last_error = f"Process exited immediately with code {proc.returncode}"
                return False

            # Store process info
            service.process = psutil.Process(proc.pid)
            service.pid = proc.pid
            service.start_time = datetime.now()
            service.state = ServiceState.RUNNING
            service.restart_attempts = 0

            # Write PID file
            pid_file = self.pid_directory / f"{service.id}.pid"
            with open(pid_file, "w") as f:
                f.write(str(proc.pid))

            logger.info(f"✅ Service '{service.id}' started (PID: {proc.pid})")

            # Send notification
            self._send_notification(
                "info", f"Service '{service.config.get('name', service.id)}' started", service.id
            )

            return True

        except Exception as e:
            logger.error(f"Failed to start service '{service.id}': {e}", exc_info=True)
            service.state = ServiceState.FAILED
            service.last_error = str(e)
            return False

    def _stop_service(self, service: ManagedService, force: bool = False):
        """Stop a service.

        Args:
            service: Service to stop
            force: Force kill if graceful shutdown fails
        """
        try:
            if not service.process or service.state == ServiceState.STOPPED:
                return

            service.state = ServiceState.STOPPING

            graceful_config = service.config.get("graceful_shutdown", {})

            if graceful_config.get("enabled", True) and not force:
                # Try graceful shutdown
                timeout = graceful_config.get("timeout", 30)
                signal_name = graceful_config.get("signal", "SIGTERM")
                sig = getattr(signal, signal_name, signal.SIGTERM)

                logger.info(f"Sending {signal_name} to '{service.id}' (PID: {service.pid})")
                service.process.send_signal(sig)

                # Wait for process to exit
                try:
                    service.process.wait(timeout=timeout)
                    logger.info(f"Service '{service.id}' stopped gracefully")
                except psutil.TimeoutExpired:
                    logger.warning(f"Service '{service.id}' did not stop gracefully, forcing")
                    service.process.kill()
                    service.process.wait(timeout=5)
            else:
                # Force kill
                logger.info(f"Force killing service '{service.id}' (PID: {service.pid})")
                service.process.kill()
                service.process.wait(timeout=5)

            service.state = ServiceState.STOPPED
            service.process = None
            service.pid = None

            # Remove PID file
            pid_file = self.pid_directory / f"{service.id}.pid"
            if pid_file.exists():
                pid_file.unlink()

            logger.info(f"Service '{service.id}' stopped")

        except Exception as e:
            logger.error(f"Error stopping service '{service.id}': {e}")
            service.state = ServiceState.STOPPED

    def _supervision_cycle(self):
        """Main supervision cycle - check and manage all services."""
        logger.debug(f"━━━ Supervision Cycle ━━━")

        for service_id, service in self.services.items():
            try:
                self._supervise_service(service)
            except Exception as e:
                logger.error(f"Error supervising '{service_id}': {e}", exc_info=True)

    def _supervise_service(self, service: ManagedService):
        """Supervise a single service.

        Args:
            service: Service to supervise
        """
        # Handle backoff state
        if service.state == ServiceState.BACKOFF:
            if datetime.now() >= service.next_restart_time:
                logger.info(f"Backoff period over for '{service.id}', attempting restart")
                self._start_service(service)
            return

        # Skip if not supposed to be running
        if service.state in [ServiceState.STOPPED, ServiceState.FATAL]:
            return

        # Check if process is still alive
        if service.process and not service.process.is_running():
            logger.warning(f"⚠️  Service '{service.id}' is not running")
            service.state = ServiceState.FAILED
            service.metrics.total_failures += 1

            # Auto-restart if enabled
            if service.config.get("restart_on_exit", True):
                self._handle_service_failure(service)
            return

        # Update metrics
        self._update_service_metrics(service)

        # Check resource limits
        self._check_resource_limits(service)

        # Run health checks
        if service.state == ServiceState.RUNNING:
            self._run_health_check(service)

    def _update_service_metrics(self, service: ManagedService):
        """Update service performance metrics."""
        if not service.process:
            return

        try:
            # CPU and memory
            service.metrics.cpu_percent = service.process.cpu_percent(interval=0.1)
            service.metrics.memory_mb = service.process.memory_info().rss / (1024 * 1024)

            # Uptime
            if service.start_time:
                service.metrics.uptime_seconds = int(
                    (datetime.now() - service.start_time).total_seconds()
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def _check_resource_limits(self, service: ManagedService):
        """Check if service exceeds resource limits."""
        limits = service.config.get("resource_limits", {})

        if not limits:
            return

        # Check memory
        max_memory = limits.get("max_memory_mb")
        if max_memory and service.metrics.memory_mb > max_memory:
            logger.warning(
                f"⚠️  Service '{service.id}' exceeds memory limit "
                f"({service.metrics.memory_mb:.1f}MB > {max_memory}MB)"
            )
            self._send_notification(
                "warning",
                f"Service '{service.id}' exceeds memory limit: {service.metrics.memory_mb:.1f}MB",
                service.id,
            )

        # Check CPU
        max_cpu = limits.get("max_cpu_percent")
        if max_cpu and service.metrics.cpu_percent > max_cpu:
            logger.warning(
                f"⚠️  Service '{service.id}' exceeds CPU limit "
                f"({service.metrics.cpu_percent:.1f}% > {max_cpu}%)"
            )

    def _run_health_check(self, service: ManagedService):
        """Run health check for a service."""
        health_config = service.config.get("health_check")

        if not health_config:
            return

        check_type = health_config.get("type", "process")
        healthy = False

        try:
            if check_type == "http":
                healthy = self._check_http_health(service, health_config)
            elif check_type == "tcp":
                healthy = self._check_tcp_health(service, health_config)
            else:
                # Process check - just verify it's running
                healthy = service.process and service.process.is_running()

            # Update metrics
            service.metrics.last_health_check = datetime.now()

            if healthy:
                service.metrics.health_check_failures = 0
            else:
                service.metrics.health_check_failures += 1
                logger.warning(
                    f"⚠️  Health check failed for '{service.id}' "
                    f"({service.metrics.health_check_failures} consecutive failures)"
                )

                # Auto-restart after multiple failures
                max_failures = health_config.get("max_failures", 3)
                if service.metrics.health_check_failures >= max_failures:
                    logger.error(
                        f"Service '{service.id}' failed {max_failures} health checks, restarting"
                    )
                    self._handle_service_failure(service)

        except Exception as e:
            logger.error(f"Health check error for '{service.id}': {e}")
            service.metrics.health_check_failures += 1

    def _check_http_health(self, service: ManagedService, config: Dict) -> bool:
        """Check HTTP health endpoint."""
        try:
            endpoint = config.get("endpoint")
            timeout = config.get("timeout", 10)
            expected_status = config.get("expected_status", 200)
            expected_content = config.get("expected_content")

            response = requests.get(endpoint, timeout=timeout)

            # Check status code
            if response.status_code != expected_status:
                logger.debug(
                    f"HTTP health check failed for '{service.id}': "
                    f"status {response.status_code} != {expected_status}"
                )

                # Try fallback check if configured
                fallback = config.get("fallback_check")
                if fallback and fallback.get("type") == "tcp":
                    return self._check_tcp_health(service, fallback)

                return False

            # Check content if specified
            if expected_content and expected_content not in response.text:
                logger.debug(
                    f"HTTP health check failed for '{service.id}': " f"expected content not found"
                )
                return False

            return True

        except Exception as e:
            logger.debug(f"HTTP health check error for '{service.id}': {e}")

            # Try fallback check if configured
            fallback = config.get("fallback_check")
            if fallback and fallback.get("type") == "tcp":
                return self._check_tcp_health(service, fallback)

            return False

    def _check_tcp_health(self, service: ManagedService, config: Dict) -> bool:
        """Check TCP port availability."""
        try:
            port = config.get("port")
            host = config.get("host", "localhost")
            timeout = config.get("timeout", 5)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            result = sock.connect_ex((host, port))
            sock.close()

            return result == 0

        except Exception as e:
            logger.debug(f"TCP health check error for '{service.id}': {e}")
            return False

    def _handle_service_failure(self, service: ManagedService):
        """Handle service failure and attempt restart."""
        # Check if we should restart
        restart_policy = service.config.get("restart_policy", {})
        max_retries = restart_policy.get("max_retries", 3)

        if service.restart_attempts >= max_retries:
            logger.error(
                f"❌ Service '{service.id}' exceeded max restart attempts ({max_retries}), "
                f"marking as FATAL"
            )
            service.state = ServiceState.FATAL

            self._send_notification(
                "critical",
                f"Service '{service.config.get('name', service.id)}' FATAL: "
                f"exceeded {max_retries} restart attempts",
                service.id,
            )
            return

        # Calculate backoff delay
        retry_delay = restart_policy.get("retry_delay", 5)
        backoff_multiplier = restart_policy.get("backoff_multiplier", 2)
        max_backoff = restart_policy.get("max_backoff", 300)

        delay = min(retry_delay * (backoff_multiplier**service.restart_attempts), max_backoff)

        service.state = ServiceState.BACKOFF
        service.next_restart_time = datetime.now() + timedelta(seconds=delay)
        service.restart_attempts += 1
        service.metrics.restart_count += 1
        service.metrics.last_restart = datetime.now()

        logger.warning(
            f"⏳ Service '{service.id}' will restart in {delay}s "
            f"(attempt {service.restart_attempts}/{max_retries})"
        )

        # Stop the failed process
        if service.process:
            try:
                service.process.kill()
            except:
                pass

        self._send_notification(
            "warning",
            f"Service '{service.config.get('name', service.id)}' failed, "
            f"restarting in {delay}s (attempt {service.restart_attempts})",
            service.id,
        )

    def _monitoring_loop(self):
        """Background monitoring and metrics collection."""
        while self.running:
            try:
                self._collect_metrics()
                time.sleep(60)  # Collect every minute
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def _collect_metrics(self):
        """Collect and report metrics to dashboard."""
        monitoring_config = self.config.get("monitoring", {})

        if not monitoring_config.get("enabled", True):
            return

        metrics = {"timestamp": datetime.now().isoformat(), "services": {}}

        for service_id, service in self.services.items():
            metrics["services"][service_id] = {
                "state": service.state.value,
                "pid": service.pid,
                "cpu_percent": service.metrics.cpu_percent,
                "memory_mb": service.metrics.memory_mb,
                "uptime_seconds": service.metrics.uptime_seconds,
                "restart_count": service.metrics.restart_count,
                "health_check_failures": service.metrics.health_check_failures,
                "total_failures": service.metrics.total_failures,
            }

        # Send to dashboard
        for dashboard_url in monitoring_config.get("dashboards", []):
            try:
                requests.post(f"{dashboard_url}/api/supervisor/metrics", json=metrics, timeout=5)
            except Exception as e:
                logger.debug(f"Failed to send metrics to {dashboard_url}: {e}")

    def _send_notification(self, level: str, message: str, service_id: str = None):
        """Send notification about service events."""
        notification_config = self.config.get("notifications", {})

        if not notification_config.get("enabled", True):
            return

        channels = notification_config.get("channels", {})

        # Log notification
        if channels.get("log", {}).get("enabled", True):
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, f"[NOTIFICATION] {message}")

        # Dashboard notification
        dashboard_config = channels.get("dashboard", {})
        if dashboard_config.get("enabled", True):
            try:
                url = dashboard_config.get("url", "http://localhost:8080/api/alerts")
                requests.post(
                    url,
                    json={
                        "level": level,
                        "message": message,
                        "source": "process_supervisor",
                        "service_id": service_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                    timeout=5,
                )
            except Exception as e:
                logger.debug(f"Failed to send dashboard notification: {e}")

    def status(self):
        """Print supervisor status."""
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📊 Process Supervisor Status")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if not self.is_running():
            print("❌ Supervisor not running\n")
            return

        print("✅ Supervisor running\n")

        print(
            f"{'Service':<20} {'State':<12} {'PID':<8} {'Uptime':<12} {'CPU%':<8} {'Mem(MB)':<10} {'Restarts':<10}"
        )
        print("-" * 90)

        for service_id, service in self.services.items():
            uptime = self._format_uptime(service.metrics.uptime_seconds)

            state_icon = {
                ServiceState.RUNNING: "✅",
                ServiceState.STOPPED: "⏸️ ",
                ServiceState.STARTING: "🔄",
                ServiceState.STOPPING: "⏹️ ",
                ServiceState.FAILED: "❌",
                ServiceState.BACKOFF: "⏳",
                ServiceState.FATAL: "💀",
            }.get(service.state, "❓")

            print(
                f"{service_id:<20} "
                f"{state_icon} {service.state.value:<10} "
                f"{service.pid or '-':<8} "
                f"{uptime:<12} "
                f"{service.metrics.cpu_percent:>6.1f}% "
                f"{service.metrics.memory_mb:>8.1f} "
                f"{service.metrics.restart_count:>10}"
            )

        print()

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

    def restart_service(self, service_id: str) -> bool:
        """Manually restart a service."""
        service = self.services.get(service_id)

        if not service:
            logger.error(f"Service '{service_id}' not found")
            return False

        logger.info(f"Manually restarting service '{service_id}'")

        # Stop if running
        if service.state != ServiceState.STOPPED:
            self._stop_service(service)

        # Reset restart attempts
        service.restart_attempts = 0
        service.state = ServiceState.STOPPED

        # Start
        return self._start_service(service)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Process Supervisor")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--restart", type=str, help="Restart specific service")

    args = parser.parse_args()

    supervisor = ProcessSupervisor(config_path=args.config)

    if args.status:
        supervisor.status()
    elif args.stop:
        if supervisor.is_running():
            try:
                with open(supervisor.pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print("✅ Process supervisor stopped")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Not running")
    elif args.restart:
        if not supervisor.is_running():
            print("❌ Supervisor not running")
            sys.exit(1)

        # This is a simplification - in production, use IPC
        print(f"To restart service '{args.restart}', use the dashboard or restart supervisor")
    elif args.daemon:
        # Daemonize
        pid = os.fork()
        if pid > 0:
            print(f"✅ Process supervisor started (PID: {pid})")
            sys.exit(0)

        os.setsid()
        os.chdir("/")

        sys.stdout.flush()
        sys.stderr.flush()

        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        supervisor.start()
    else:
        print("🚀 Starting process supervisor (Ctrl+C to stop)...")
        supervisor.start()


if __name__ == "__main__":
    main()
