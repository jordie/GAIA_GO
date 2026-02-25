#!/usr/bin/env python3
"""
Health Check System

Provides health check utilities for supervised services:
- HTTP health checks with retry logic
- TCP port checks
- Process health checks
- Custom health check scripts
- Health check history and reporting
"""

import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import psutil
import requests


class HealthStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    message: str
    details: Optional[Dict] = None


class HealthChecker:
    """Health check executor."""

    def __init__(self):
        """Initialize health checker."""
        self.history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history = 100

    def check_http(
        self,
        endpoint: str,
        timeout: int = 10,
        expected_status: int = 200,
        expected_content: Optional[str] = None,
        headers: Optional[Dict] = None,
        verify_ssl: bool = True,
    ) -> HealthCheckResult:
        """Perform HTTP health check.

        Args:
            endpoint: HTTP endpoint URL
            timeout: Request timeout in seconds
            expected_status: Expected HTTP status code
            expected_content: Expected content in response body
            headers: Optional HTTP headers
            verify_ssl: Verify SSL certificates

        Returns:
            HealthCheckResult
        """
        start_time = time.time()

        try:
            response = requests.get(
                endpoint,
                timeout=timeout,
                headers=headers or {},
                verify=verify_ssl,
                allow_redirects=True,
            )

            response_time = (time.time() - start_time) * 1000

            # Check status code
            if response.status_code != expected_status:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    message=f"Unexpected status code: {response.status_code}",
                    details={"status_code": response.status_code, "expected": expected_status},
                )

            # Check content if specified
            if expected_content and expected_content not in response.text:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    message=f"Expected content not found: {expected_content}",
                    details={"content_length": len(response.text)},
                )

            # Determine status based on response time
            if response_time < 1000:
                status = HealthStatus.HEALTHY
            elif response_time < 5000:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheckResult(
                status=status,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                message="OK",
                details={"status_code": response.status_code, "content_length": len(response.text)},
            )

        except requests.Timeout:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Request timeout after {timeout}s",
            )

        except requests.ConnectionError as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Connection error: {str(e)}",
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Health check error: {str(e)}",
            )

    def check_tcp(self, host: str, port: int, timeout: int = 5) -> HealthCheckResult:
        """Perform TCP port health check.

        Args:
            host: Target host
            port: Target port
            timeout: Connection timeout in seconds

        Returns:
            HealthCheckResult
        """
        start_time = time.time()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            result = sock.connect_ex((host, port))
            sock.close()

            response_time = (time.time() - start_time) * 1000

            if result == 0:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    message=f"Port {port} is open",
                    details={"host": host, "port": port},
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    message=f"Port {port} is closed or unreachable",
                    details={"host": host, "port": port, "error_code": result},
                )

        except socket.timeout:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Connection timeout after {timeout}s",
                details={"host": host, "port": port},
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"TCP check error: {str(e)}",
                details={"host": host, "port": port},
            )

    def check_process(self, pid: int, check_responsive: bool = True) -> HealthCheckResult:
        """Perform process health check.

        Args:
            pid: Process ID
            check_responsive: Check if process is responsive (not zombie/stopped)

        Returns:
            HealthCheckResult
        """
        start_time = time.time()

        try:
            if not psutil.pid_exists(pid):
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(),
                    message=f"Process {pid} does not exist",
                )

            proc = psutil.Process(pid)

            if not proc.is_running():
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(),
                    message=f"Process {pid} is not running",
                )

            # Check if process is zombie or stopped
            if check_responsive:
                status = proc.status()
                if status == psutil.STATUS_ZOMBIE:
                    return HealthCheckResult(
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=(time.time() - start_time) * 1000,
                        timestamp=datetime.now(),
                        message=f"Process {pid} is a zombie",
                        details={"status": status},
                    )
                elif status == psutil.STATUS_STOPPED:
                    return HealthCheckResult(
                        status=HealthStatus.DEGRADED,
                        response_time_ms=(time.time() - start_time) * 1000,
                        timestamp=datetime.now(),
                        message=f"Process {pid} is stopped",
                        details={"status": status},
                    )

            # Get process info
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_mb = proc.memory_info().rss / (1024 * 1024)

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Process {pid} is healthy",
                details={
                    "pid": pid,
                    "status": proc.status(),
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "num_threads": proc.num_threads(),
                },
            )

        except psutil.NoSuchProcess:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Process {pid} not found",
            )

        except psutil.AccessDenied:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Access denied to process {pid}",
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Process check error: {str(e)}",
            )

    def check_script(
        self, script_path: str, timeout: int = 30, args: Optional[List[str]] = None
    ) -> HealthCheckResult:
        """Execute custom health check script.

        Args:
            script_path: Path to health check script
            timeout: Script timeout in seconds
            args: Optional script arguments

        Returns:
            HealthCheckResult

        Script should exit with:
        - 0: Healthy
        - 1: Degraded
        - 2+: Unhealthy
        """
        start_time = time.time()

        try:
            command = [script_path] + (args or [])

            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)

            response_time = (time.time() - start_time) * 1000

            # Determine status from exit code
            if result.returncode == 0:
                status = HealthStatus.HEALTHY
                message = "Script check passed"
            elif result.returncode == 1:
                status = HealthStatus.DEGRADED
                message = "Script check degraded"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Script check failed (exit code: {result.returncode})"

            return HealthCheckResult(
                status=status,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                message=message,
                details={
                    "exit_code": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                },
            )

        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Script timeout after {timeout}s",
            )

        except FileNotFoundError:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Script not found: {script_path}",
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(),
                message=f"Script check error: {str(e)}",
            )

    def record_result(self, service_id: str, result: HealthCheckResult):
        """Record health check result in history.

        Args:
            service_id: Service identifier
            result: Health check result
        """
        if service_id not in self.history:
            self.history[service_id] = []

        self.history[service_id].append(result)

        # Limit history size
        if len(self.history[service_id]) > self.max_history:
            self.history[service_id] = self.history[service_id][-self.max_history :]

    def get_health_summary(self, service_id: str, window_minutes: int = 60) -> Dict:
        """Get health summary for a service.

        Args:
            service_id: Service identifier
            window_minutes: Time window in minutes

        Returns:
            Health summary dictionary
        """
        if service_id not in self.history:
            return {
                "status": "unknown",
                "checks_count": 0,
                "success_rate": 0.0,
                "avg_response_time_ms": 0.0,
            }

        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_checks = [check for check in self.history[service_id] if check.timestamp >= cutoff]

        if not recent_checks:
            return {
                "status": "unknown",
                "checks_count": 0,
                "success_rate": 0.0,
                "avg_response_time_ms": 0.0,
            }

        # Calculate metrics
        healthy_count = sum(1 for check in recent_checks if check.status == HealthStatus.HEALTHY)

        success_rate = (healthy_count / len(recent_checks)) * 100

        avg_response_time = sum(check.response_time_ms for check in recent_checks) / len(
            recent_checks
        )

        # Determine overall status
        if success_rate >= 95:
            overall_status = "healthy"
        elif success_rate >= 80:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "checks_count": len(recent_checks),
            "success_rate": success_rate,
            "avg_response_time_ms": avg_response_time,
            "last_check": recent_checks[-1].timestamp.isoformat(),
            "last_status": recent_checks[-1].status.value,
        }


if __name__ == "__main__":
    # Quick test
    checker = HealthChecker()

    # Test HTTP check
    result = checker.check_http("http://localhost:8080/health")
    print(f"HTTP Check: {result.status.value} - {result.message}")

    # Test TCP check
    result = checker.check_tcp("localhost", 8080)
    print(f"TCP Check: {result.status.value} - {result.message}")
