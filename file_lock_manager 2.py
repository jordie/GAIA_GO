#!/usr/bin/env python3
"""
File-based Semaphore System for Multi-Agent Coordination
Uses lock files to ensure only one agent modifies files in a directory at a time.
"""

import os
import time
import json
import fcntl
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import atexit
import signal
import sys


class FileLockManager:
    """
    Manages file-based locks for multi-agent coordination.
    Uses atomic file operations and fcntl for exclusive locking.
    """

    LOCK_DIR = Path("/tmp/agent_locks")
    LOCK_TIMEOUT = 300  # 5 minutes
    HEARTBEAT_INTERVAL = 30  # 30 seconds

    def __init__(self, agent_name: str, lock_dir: Optional[Path] = None):
        self.agent_name = agent_name
        self.lock_dir = lock_dir or self.LOCK_DIR
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.held_locks: Dict[str, dict] = {}

        # Register cleanup handlers
        atexit.register(self.cleanup_all_locks)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        print(f"\n[{self.agent_name}] Received signal {signum}, releasing locks...")
        self.cleanup_all_locks()
        sys.exit(0)

    def _get_lock_path(self, directory: Path) -> Path:
        """Get lock file path for a directory."""
        # Use hash of absolute path to avoid path separator issues
        dir_hash = hashlib.md5(str(directory.absolute()).encode()).hexdigest()
        return self.lock_dir / f"{dir_hash}.lock"

    def _get_lock_info_path(self, directory: Path) -> Path:
        """Get lock info file path."""
        dir_hash = hashlib.md5(str(directory.absolute()).encode()).hexdigest()
        return self.lock_dir / f"{dir_hash}.info"

    def acquire_lock(self, directory: Path, timeout: int = 60, wait: bool = True) -> bool:
        """
        Acquire exclusive lock on a directory.

        Args:
            directory: Directory to lock
            timeout: Maximum time to wait for lock (seconds)
            wait: If True, wait for lock. If False, return immediately if locked.

        Returns:
            True if lock acquired, False otherwise
        """
        directory = Path(directory).absolute()
        lock_path = self._get_lock_path(directory)
        info_path = self._get_lock_info_path(directory)

        start_time = time.time()

        while True:
            try:
                # Try to acquire lock file with exclusive lock
                lock_file = open(lock_path, 'w')

                if wait:
                    # Blocking lock with timeout
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    # Non-blocking lock
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except IOError:
                        lock_file.close()
                        return False

                # Successfully acquired lock
                lock_info = {
                    "agent": self.agent_name,
                    "directory": str(directory),
                    "acquired_at": datetime.now().isoformat(),
                    "pid": os.getpid(),
                    "hostname": os.uname().nodename
                }

                # Write lock info
                with open(info_path, 'w') as f:
                    json.dump(lock_info, f, indent=2)

                # Store lock reference
                self.held_locks[str(directory)] = {
                    "lock_file": lock_file,
                    "lock_path": lock_path,
                    "info_path": info_path,
                    "acquired_at": time.time()
                }

                print(f"[{self.agent_name}] 🔒 Acquired lock on {directory}")
                return True

            except IOError as e:
                # Lock is held by another process
                if not wait:
                    return False

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    print(f"[{self.agent_name}] ⏱️  Lock timeout on {directory}")
                    return False

                # Check who holds the lock
                lock_holder = self.get_lock_holder(directory)
                if lock_holder:
                    print(f"[{self.agent_name}] ⏳ Waiting for lock on {directory} (held by {lock_holder['agent']})...")

                # Wait before retrying
                time.sleep(2)

    def release_lock(self, directory: Path) -> bool:
        """
        Release lock on a directory.

        Args:
            directory: Directory to unlock

        Returns:
            True if lock released, False if not held
        """
        directory = Path(directory).absolute()
        dir_key = str(directory)

        if dir_key not in self.held_locks:
            print(f"[{self.agent_name}] ⚠️  No lock held on {directory}")
            return False

        lock_data = self.held_locks[dir_key]

        try:
            # Release fcntl lock
            fcntl.flock(lock_data["lock_file"].fileno(), fcntl.LOCK_UN)
            lock_data["lock_file"].close()

            # Remove lock files
            if lock_data["lock_path"].exists():
                lock_data["lock_path"].unlink()
            if lock_data["info_path"].exists():
                lock_data["info_path"].unlink()

            # Remove from held locks
            del self.held_locks[dir_key]

            print(f"[{self.agent_name}] 🔓 Released lock on {directory}")
            return True

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error releasing lock on {directory}: {e}")
            return False

    def get_lock_holder(self, directory: Path) -> Optional[Dict]:
        """
        Get information about who holds the lock.

        Args:
            directory: Directory to check

        Returns:
            Lock holder info dict or None
        """
        info_path = self._get_lock_info_path(Path(directory).absolute())

        if not info_path.exists():
            return None

        try:
            with open(info_path, 'r') as f:
                return json.load(f)
        except:
            return None

    def is_locked(self, directory: Path) -> bool:
        """
        Check if directory is currently locked.

        Args:
            directory: Directory to check

        Returns:
            True if locked, False otherwise
        """
        return self.get_lock_holder(directory) is not None

    def cleanup_stale_locks(self, max_age: int = 600):
        """
        Clean up stale locks (older than max_age seconds).

        Args:
            max_age: Maximum lock age in seconds
        """
        now = time.time()
        cleaned = 0

        for info_file in self.lock_dir.glob("*.info"):
            try:
                with open(info_file, 'r') as f:
                    lock_info = json.load(f)

                acquired_at = datetime.fromisoformat(lock_info["acquired_at"])
                age = now - acquired_at.timestamp()

                if age > max_age:
                    # Check if process still exists
                    pid = lock_info.get("pid")
                    if pid and not self._is_process_alive(pid):
                        # Stale lock - remove it
                        lock_hash = info_file.stem
                        lock_path = self.lock_dir / f"{lock_hash}.lock"

                        if lock_path.exists():
                            lock_path.unlink()
                        info_file.unlink()

                        cleaned += 1
                        print(f"[LockManager] 🧹 Cleaned stale lock: {lock_info['directory']} (held by {lock_info['agent']})")
            except:
                continue

        if cleaned > 0:
            print(f"[LockManager] Cleaned {cleaned} stale locks")

    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still running."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def cleanup_all_locks(self):
        """Release all locks held by this agent."""
        for directory in list(self.held_locks.keys()):
            self.release_lock(Path(directory))

    def list_all_locks(self) -> List[Dict]:
        """List all active locks."""
        locks = []

        for info_file in self.lock_dir.glob("*.info"):
            try:
                with open(info_file, 'r') as f:
                    lock_info = json.load(f)
                locks.append(lock_info)
            except:
                continue

        return locks

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup locks."""
        self.cleanup_all_locks()


class DirectoryLock:
    """Context manager for directory locks."""

    def __init__(self, agent_name: str, directory: Path, timeout: int = 60):
        self.manager = FileLockManager(agent_name)
        self.directory = directory
        self.timeout = timeout
        self.acquired = False

    def __enter__(self):
        """Acquire lock on entry."""
        self.acquired = self.manager.acquire_lock(self.directory, self.timeout)
        if not self.acquired:
            raise TimeoutError(f"Could not acquire lock on {self.directory}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock on exit."""
        if self.acquired:
            self.manager.release_lock(self.directory)


def list_locks():
    """CLI function to list all locks."""
    manager = FileLockManager("cli")
    locks = manager.list_all_locks()

    if not locks:
        print("No active locks")
        return

    print(f"\n📋 Active Locks ({len(locks)}):")
    print("=" * 80)

    for lock in locks:
        print(f"\n🔒 {lock['directory']}")
        print(f"   Agent: {lock['agent']}")
        print(f"   Acquired: {lock['acquired_at']}")
        print(f"   PID: {lock['pid']}")
        print(f"   Host: {lock['hostname']}")


def cleanup_locks():
    """CLI function to cleanup stale locks."""
    manager = FileLockManager("cli")
    manager.cleanup_stale_locks()


def force_unlock(directory: str):
    """CLI function to force unlock a directory."""
    manager = FileLockManager("cli")
    directory = Path(directory).absolute()

    lock_holder = manager.get_lock_holder(directory)
    if not lock_holder:
        print(f"Directory {directory} is not locked")
        return

    print(f"Force unlocking {directory} (held by {lock_holder['agent']})...")

    # Remove lock files directly
    lock_path = manager._get_lock_path(directory)
    info_path = manager._get_lock_info_path(directory)

    if lock_path.exists():
        lock_path.unlink()
    if info_path.exists():
        info_path.unlink()

    print("✅ Lock removed")


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python file_lock_manager.py list              - List all locks")
        print("  python file_lock_manager.py cleanup           - Cleanup stale locks")
        print("  python file_lock_manager.py unlock <dir>      - Force unlock directory")
        print("  python file_lock_manager.py test              - Run test")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_locks()
    elif command == "cleanup":
        cleanup_locks()
    elif command == "unlock":
        if len(sys.argv) < 3:
            print("Error: Directory path required")
            sys.exit(1)
        force_unlock(sys.argv[2])
    elif command == "test":
        # Test locking
        manager = FileLockManager("test-agent")
        test_dir = Path("/tmp/test_lock_dir")
        test_dir.mkdir(exist_ok=True)

        print(f"Testing lock on {test_dir}...")

        if manager.acquire_lock(test_dir):
            print("Lock acquired!")
            time.sleep(5)
            manager.release_lock(test_dir)
            print("Lock released!")
        else:
            print("Failed to acquire lock")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
