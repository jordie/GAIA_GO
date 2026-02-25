#!/usr/bin/env python3
"""
Session Status Monitor

Monitors session status update files and aggregates current state.
Runs as daemon to provide real-time session monitoring.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SessionMonitor:
    """Monitor session status updates from files."""

    def __init__(self, status_dir: Path, check_interval: int = 10):
        """
        Initialize monitor.

        Args:
            status_dir: Directory containing status files
            check_interval: Seconds between checks
        """
        self.status_dir = Path(status_dir)
        self.check_interval = check_interval
        self.status_dir.mkdir(parents=True, exist_ok=True)

        # Track file modification times
        self.file_mtimes: Dict[Path, float] = {}

        # Current status for each session
        self.current_status: Dict[str, Dict] = {}

    def get_latest_status(self, session_file: Path) -> Optional[Dict]:
        """Get latest status from a session file."""
        if not session_file.exists():
            return None

        try:
            # Read last line (most recent update)
            with open(session_file, "r") as f:
                lines = f.readlines()
                if not lines:
                    return None

                last_line = lines[-1].strip()
                if not last_line:
                    return None

                return json.loads(last_line)
        except Exception as e:
            logger.error(f"Error reading {session_file}: {e}")
            return None

    def get_all_updates(self, session_file: Path, since: Optional[datetime] = None) -> List[Dict]:
        """Get all updates from a session file, optionally filtered by time."""
        if not session_file.exists():
            return []

        updates = []
        try:
            with open(session_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    update = json.loads(line)

                    # Filter by timestamp if requested
                    if since:
                        update_time = datetime.fromisoformat(update["timestamp"].replace("Z", "+00:00"))
                        if update_time < since:
                            continue

                    updates.append(update)
        except Exception as e:
            logger.error(f"Error reading all updates from {session_file}: {e}")

        return updates

    def scan_sessions(self) -> Dict[str, Dict]:
        """Scan all session status files and return current state."""
        current = {}

        for status_file in self.status_dir.glob("*_status.json"):
            session_name = status_file.stem.replace("_status", "")

            # Check if file was modified
            mtime = status_file.stat().st_mtime
            if status_file in self.file_mtimes and self.file_mtimes[status_file] == mtime:
                # File unchanged, use cached status
                if session_name in self.current_status:
                    current[session_name] = self.current_status[session_name]
                    continue

            # File changed, read latest status
            self.file_mtimes[status_file] = mtime
            latest = self.get_latest_status(status_file)

            if latest:
                # Add staleness check
                update_time = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
                age = datetime.utcnow() - update_time.replace(tzinfo=None)

                latest["age_seconds"] = age.total_seconds()
                latest["is_stale"] = age > timedelta(minutes=5)
                latest["is_very_stale"] = age > timedelta(minutes=15)

                current[session_name] = latest

        self.current_status = current
        return current

    def get_summary(self) -> Dict:
        """Get summary of all session statuses."""
        statuses = self.scan_sessions()

        summary = {
            "total_sessions": len(statuses),
            "by_status": {},
            "stale_sessions": [],
            "error_sessions": [],
            "working_sessions": [],
            "idle_sessions": [],
        }

        for session_name, status in statuses.items():
            # Count by status
            status_val = status.get("status", "unknown")
            summary["by_status"][status_val] = summary["by_status"].get(status_val, 0) + 1

            # Categorize
            if status.get("is_very_stale"):
                summary["stale_sessions"].append(session_name)
            elif status_val == "error":
                summary["error_sessions"].append(session_name)
            elif status_val == "working":
                summary["working_sessions"].append(session_name)
            elif status_val == "idle":
                summary["idle_sessions"].append(session_name)

        return summary

    def print_status(self):
        """Print current status in human-readable format."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("SESSION STATUS SUMMARY")
        print("=" * 60)
        print(f"Total Sessions: {summary['total_sessions']}")
        print(f"\nBy Status:")
        for status, count in sorted(summary['by_status'].items()):
            print(f"  {status}: {count}")

        if summary['working_sessions']:
            print(f"\nWorking ({len(summary['working_sessions'])}):")
            for session in summary['working_sessions']:
                status = self.current_status[session]
                progress = status.get('progress', 0) * 100
                print(f"  • {session}: {status['message']} ({progress:.0f}%)")

        if summary['error_sessions']:
            print(f"\n❌ Errors ({len(summary['error_sessions'])}):")
            for session in summary['error_sessions']:
                status = self.current_status[session]
                print(f"  • {session}: {status['message']}")

        if summary['stale_sessions']:
            print(f"\n⚠️  Stale ({len(summary['stale_sessions'])}):")
            for session in summary['stale_sessions']:
                status = self.current_status[session]
                age_min = status['age_seconds'] / 60
                print(f"  • {session}: No update for {age_min:.1f} minutes")

        print("=" * 60 + "\n")

    def run(self):
        """Run monitor loop."""
        logger.info(f"Starting session monitor (checking every {self.check_interval}s)")
        logger.info(f"Monitoring directory: {self.status_dir}")

        try:
            while True:
                self.print_status()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor session status updates")
    parser.add_argument(
        "--status-dir",
        default="data/session_status",
        help="Directory containing status files"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Check interval in seconds"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit (don't run as daemon)"
    )

    args = parser.parse_args()

    # Find project root
    current = Path.cwd()
    while current.parent != current:
        if (current / "data").exists():
            break
        current = current.parent

    status_dir = current / args.status_dir

    monitor = SessionMonitor(status_dir, args.interval)

    if args.once:
        monitor.print_status()
    else:
        monitor.run()


if __name__ == "__main__":
    main()
