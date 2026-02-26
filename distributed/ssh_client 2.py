"""
SSH Client for secure remote server management.

Provides connection pooling, command execution, and file transfers
to remote nodes in the cluster.
"""

import logging
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SSHConfig:
    """SSH connection configuration."""

    host: str
    port: int = 22
    user: str = None
    key_file: str = None
    password: str = None
    timeout: int = 30

    def __post_init__(self):
        if self.user is None:
            self.user = os.environ.get("USER", "root")
        if self.key_file is None:
            default_key = Path.home() / ".ssh" / "id_rsa"
            if default_key.exists():
                self.key_file = str(default_key)


class SSHClient:
    """
    SSH client for remote command execution and file transfers.

    Uses native SSH commands for better compatibility and security.
    """

    def __init__(self, config: SSHConfig):
        self.config = config
        self._connected = False

    @property
    def connection_string(self) -> str:
        """Get SSH connection string."""
        return f"{self.config.user}@{self.config.host}"

    def _build_ssh_command(self, extra_args: List[str] = None) -> List[str]:
        """Build base SSH command with common options."""
        cmd = ["ssh"]

        # Add key file if specified
        if self.config.key_file:
            cmd.extend(["-i", self.config.key_file])

        # Port
        cmd.extend(["-p", str(self.config.port)])

        # Common options
        cmd.extend(
            [
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                f"ConnectTimeout={self.config.timeout}",
                "-o",
                "BatchMode=yes",  # Non-interactive
            ]
        )

        if extra_args:
            cmd.extend(extra_args)

        cmd.append(self.connection_string)

        return cmd

    def test_connection(self) -> bool:
        """Test SSH connectivity to the remote host."""
        try:
            result = self.execute("echo ok", timeout=10)
            return result[0] == 0 and "ok" in result[1]
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def execute(
        self, command: str, timeout: int = None, env: Dict[str, str] = None
    ) -> Tuple[int, str, str]:
        """
        Execute a command on the remote server.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            env: Environment variables to set

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Build command with environment variables
        if env:
            env_str = " ".join(f"{k}={v}" for k, v in env.items())
            command = f"{env_str} {command}"

        ssh_cmd = self._build_ssh_command()
        ssh_cmd.append(command)

        try:
            result = subprocess.run(
                ssh_cmd, capture_output=True, text=True, timeout=timeout or self.config.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command[:50]}...")
            return -1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return -1, "", str(e)

    def execute_script(self, script: str, interpreter: str = "/bin/bash") -> Tuple[int, str, str]:
        """
        Execute a multi-line script on the remote server.

        Args:
            script: Script content to execute
            interpreter: Script interpreter to use

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Escape the script for SSH
        escaped_script = script.replace("'", "'\"'\"'")
        command = f"{interpreter} -c '{escaped_script}'"
        return self.execute(command)

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a file to the remote server using SCP.

        Args:
            local_path: Local file path
            remote_path: Remote destination path

        Returns:
            True if successful
        """
        cmd = ["scp"]

        if self.config.key_file:
            cmd.extend(["-i", self.config.key_file])

        cmd.extend(
            [
                "-P",
                str(self.config.port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                local_path,
                f"{self.connection_string}:{remote_path}",
            ]
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                logger.error(f"SCP failed: {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from the remote server using SCP.

        Args:
            remote_path: Remote file path
            local_path: Local destination path

        Returns:
            True if successful
        """
        cmd = ["scp"]

        if self.config.key_file:
            cmd.extend(["-i", self.config.key_file])

        cmd.extend(
            [
                "-P",
                str(self.config.port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"{self.connection_string}:{remote_path}",
                local_path,
            ]
        )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return False

    def get_system_info(self) -> Dict:
        """Get system information from the remote server."""
        info = {}

        # Detect OS type
        code, out, _ = self.execute("uname -s")
        os_type = out.strip().lower() if code == 0 else "linux"
        info["os_type"] = os_type

        if os_type == "darwin":
            # macOS commands
            # CPU cores
            code, out, _ = self.execute("sysctl -n hw.ncpu")
            if code == 0 and out.strip():
                try:
                    info["cpu_cores"] = int(out.strip())
                except:
                    info["cpu_cores"] = 0

            # Memory (bytes to MB)
            code, out, _ = self.execute("sysctl -n hw.memsize")
            if code == 0 and out.strip():
                try:
                    info["memory_mb"] = int(int(out.strip()) / (1024 * 1024))
                except:
                    info["memory_mb"] = 0

            # Disk free (GB to MB)
            code, out, _ = self.execute("df -g / | awk 'NR==2 {print $4}'")
            if code == 0 and out.strip():
                try:
                    info["disk_free_mb"] = int(float(out.strip()) * 1024)
                except:
                    info["disk_free_mb"] = 0

            # CPU usage (use ps)
            code, out, _ = self.execute("ps -A -o %cpu | awk '{s+=$1} END {print s}'")
            if code == 0 and out.strip():
                try:
                    info["cpu_usage"] = min(float(out.strip()), 100.0)
                except:
                    info["cpu_usage"] = 0

            # Memory usage via vm_stat
            code, out, _ = self.execute("vm_stat | awk '/Pages active/ {print $3}' | tr -d '.'")
            if code == 0 and out.strip():
                try:
                    active_pages = int(out.strip())
                    # Each page is 4096 bytes
                    used_mb = (active_pages * 4096) / (1024 * 1024)
                    if info.get("memory_mb", 0) > 0:
                        info["memory_usage"] = round((used_mb / info["memory_mb"]) * 100, 1)
                    else:
                        info["memory_usage"] = 0
                except:
                    info["memory_usage"] = 0
        else:
            # Linux commands
            # CPU info
            code, out, _ = self.execute("grep -c processor /proc/cpuinfo")
            if code == 0 and out.strip():
                try:
                    info["cpu_cores"] = int(out.strip())
                except:
                    info["cpu_cores"] = 0

            # Memory info
            code, out, _ = self.execute("free -m | awk '/Mem:/ {print $2}'")
            if code == 0 and out.strip():
                try:
                    info["memory_mb"] = int(out.strip())
                except:
                    info["memory_mb"] = 0

            # Disk info
            code, out, _ = self.execute("df -m / | awk 'NR==2 {print $4}'")
            if code == 0 and out.strip():
                try:
                    info["disk_free_mb"] = int(out.strip())
                except:
                    info["disk_free_mb"] = 0

            # CPU usage
            code, out, _ = self.execute("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
            if code == 0 and out.strip():
                try:
                    info["cpu_usage"] = float(out.strip().replace("%", ""))
                except:
                    info["cpu_usage"] = 0

            # Memory usage
            code, out, _ = self.execute("free | awk '/Mem:/ {printf(\"%.1f\", $3/$2 * 100)}'")
            if code == 0 and out.strip():
                try:
                    info["memory_usage"] = float(out.strip())
                except:
                    info["memory_usage"] = 0

        # Hostname (works on both)
        code, out, _ = self.execute("hostname")
        if code == 0:
            info["hostname"] = out.strip()

        # Check for GPU (NVIDIA)
        code, out, _ = self.execute(
            "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1"
        )
        info["has_gpu"] = code == 0 and len(out.strip()) > 0
        if info["has_gpu"]:
            info["gpu_name"] = out.strip()

        return info

    def check_service_running(self, process_name: str) -> bool:
        """Check if a service/process is running."""
        code, out, _ = self.execute(f"pgrep -f '{process_name}'")
        return code == 0 and len(out.strip()) > 0

    def start_service(
        self, command: str, background: bool = True, log_file: str = None
    ) -> Tuple[int, str, str]:
        """
        Start a service on the remote server.

        Args:
            command: Command to start the service
            background: Run in background
            log_file: Optional log file path

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if background:
            if log_file:
                command = f"nohup {command} > {log_file} 2>&1 &"
            else:
                command = f"nohup {command} > /dev/null 2>&1 &"

        return self.execute(command)

    def stop_service(self, process_name: str) -> bool:
        """Stop a service by process name."""
        code, _, _ = self.execute(f"pkill -f '{process_name}'")
        return code == 0


class SSHConnectionPool:
    """
    Pool of SSH connections for efficient reuse.
    """

    def __init__(self):
        self._clients: Dict[str, SSHClient] = {}

    def get_client(self, config: SSHConfig) -> SSHClient:
        """Get or create an SSH client for the given config."""
        key = f"{config.user}@{config.host}:{config.port}"

        if key not in self._clients:
            self._clients[key] = SSHClient(config)

        return self._clients[key]

    def close_all(self):
        """Close all pooled connections."""
        self._clients.clear()

    @contextmanager
    def connection(self, config: SSHConfig):
        """Context manager for getting a connection."""
        client = self.get_client(config)
        try:
            yield client
        finally:
            pass  # Keep connection in pool


# Global connection pool
_pool = SSHConnectionPool()


def get_client(host: str, user: str = None, port: int = 22, key_file: str = None) -> SSHClient:
    """
    Get an SSH client from the global pool.

    Args:
        host: Remote host address
        user: SSH username
        port: SSH port
        key_file: Path to SSH private key

    Returns:
        SSHClient instance
    """
    config = SSHConfig(host=host, user=user, port=port, key_file=key_file)
    return _pool.get_client(config)
