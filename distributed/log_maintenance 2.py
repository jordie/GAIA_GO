#!/usr/bin/env python3
"""
Log Maintenance Worker for Distributed System.

This module provides automated log file maintenance including:
- Size-based log trimming
- Age-based log rotation
- Archive creation for historical logs
- Configurable retention policies

Usage:
    # Trim logs in a directory
    python3 -m distributed.log_maintenance trim /path/to/logs

    # Set max size in MB
    python3 -m distributed.log_maintenance trim /path/to/logs --max-size 10

    # Archive old logs
    python3 -m distributed.log_maintenance archive /path/to/logs --older-than 7

    # Clean all logs in project
    python3 -m distributed.log_maintenance clean-project
"""

import gzip
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LogAction(Enum):
    """Actions that can be performed on log files."""

    TRIM = "trim"
    ARCHIVE = "archive"
    DELETE = "delete"
    SKIP = "skip"


@dataclass
class LogFileInfo:
    """Information about a log file."""

    path: Path
    name: str
    size_bytes: int
    size_mb: float
    modified_time: datetime
    age_days: float
    line_count: Optional[int] = None

    @classmethod
    def from_path(cls, path: Path) -> "LogFileInfo":
        """Create LogFileInfo from a file path."""
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        age = (datetime.now() - modified).total_seconds() / 86400
        return cls(
            path=path,
            name=path.name,
            size_bytes=stat.st_size,
            size_mb=round(stat.st_size / (1024 * 1024), 2),
            modified_time=modified,
            age_days=round(age, 1),
        )


@dataclass
class MaintenancePolicy:
    """Configuration for log maintenance."""

    max_size_mb: float = 10.0  # Max size before trimming
    max_age_days: int = 30  # Max age before archiving
    keep_lines: int = 5000  # Lines to keep when trimming
    archive_after_days: int = 7  # Archive files older than this
    delete_archives_after_days: int = 90  # Delete old archives
    exclude_patterns: List[str] = None  # Patterns to exclude

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = [".git", "__pycache__", "node_modules", ".gz"]


class LogMaintenance:
    """Worker for log file maintenance operations."""

    LOG_EXTENSIONS = {".log", ".txt", ".out", ".err"}

    def __init__(self, base_path: Path, policy: Optional[MaintenancePolicy] = None):
        """Initialize log maintenance worker.

        Args:
            base_path: Base directory to scan for logs
            policy: Maintenance policy configuration
        """
        self.base_path = Path(base_path)
        self.policy = policy or MaintenancePolicy()
        self.stats = {
            "scanned": 0,
            "trimmed": 0,
            "archived": 0,
            "deleted": 0,
            "bytes_freed": 0,
            "errors": [],
        }

    def scan_logs(self) -> List[LogFileInfo]:
        """Scan directory for log files.

        Returns:
            List of LogFileInfo objects for found log files
        """
        logs = []

        for ext in self.LOG_EXTENSIONS:
            for log_path in self.base_path.rglob(f"*{ext}"):
                # Skip excluded patterns
                path_str = str(log_path)
                if any(p in path_str for p in self.policy.exclude_patterns):
                    continue

                try:
                    info = LogFileInfo.from_path(log_path)
                    logs.append(info)
                    self.stats["scanned"] += 1
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not access {log_path}: {e}")

        return sorted(logs, key=lambda x: x.size_bytes, reverse=True)

    def analyze_logs(self) -> Dict[str, List[LogFileInfo]]:
        """Analyze logs and categorize by recommended action.

        Returns:
            Dictionary mapping actions to lists of log files
        """
        logs = self.scan_logs()
        categorized = {
            LogAction.TRIM: [],
            LogAction.ARCHIVE: [],
            LogAction.DELETE: [],
            LogAction.SKIP: [],
        }

        for log in logs:
            if log.size_mb > self.policy.max_size_mb:
                categorized[LogAction.TRIM].append(log)
            elif log.age_days > self.policy.archive_after_days:
                categorized[LogAction.ARCHIVE].append(log)
            elif log.name.endswith(".gz") and log.age_days > self.policy.delete_archives_after_days:
                categorized[LogAction.DELETE].append(log)
            else:
                categorized[LogAction.SKIP].append(log)

        return categorized

    def trim_log(self, log_path: Path, keep_lines: Optional[int] = None) -> Tuple[bool, int]:
        """Trim a log file, keeping only the most recent lines.

        Args:
            log_path: Path to the log file
            keep_lines: Number of lines to keep (uses policy default if None)

        Returns:
            Tuple of (success, bytes_freed)
        """
        keep = keep_lines or self.policy.keep_lines
        original_size = log_path.stat().st_size

        try:
            # Read all lines
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # Keep only the last N lines
            if len(lines) > keep:
                kept_lines = lines[-keep:]

                # Add header indicating trimming
                header = f"# Log trimmed on {datetime.now().isoformat()}\n"
                header += f"# Removed {len(lines) - keep} lines, kept last {keep}\n"
                header += "# ---\n"

                # Write back
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(header)
                    f.writelines(kept_lines)

                new_size = log_path.stat().st_size
                bytes_freed = original_size - new_size

                logger.info(
                    f"Trimmed {log_path.name}: {original_size/1024:.1f}KB -> {new_size/1024:.1f}KB"
                )
                self.stats["trimmed"] += 1
                self.stats["bytes_freed"] += bytes_freed

                return True, bytes_freed
            else:
                logger.debug(f"Log {log_path.name} has {len(lines)} lines, no trimming needed")
                return True, 0

        except Exception as e:
            logger.error(f"Error trimming {log_path}: {e}")
            self.stats["errors"].append(str(e))
            return False, 0

    def archive_log(self, log_path: Path) -> Tuple[bool, int]:
        """Archive a log file by compressing it.

        Args:
            log_path: Path to the log file

        Returns:
            Tuple of (success, bytes_freed)
        """
        original_size = log_path.stat().st_size
        archive_path = log_path.with_suffix(log_path.suffix + ".gz")

        try:
            # Compress the file
            with open(log_path, "rb") as f_in:
                with gzip.open(archive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original
            log_path.unlink()

            new_size = archive_path.stat().st_size
            bytes_freed = original_size - new_size

            logger.info(
                f"Archived {log_path.name} -> {archive_path.name} ({bytes_freed/1024:.1f}KB freed)"
            )
            self.stats["archived"] += 1
            self.stats["bytes_freed"] += bytes_freed

            return True, bytes_freed

        except Exception as e:
            logger.error(f"Error archiving {log_path}: {e}")
            self.stats["errors"].append(str(e))
            return False, 0

    def delete_old_archives(self) -> int:
        """Delete archives older than retention period.

        Returns:
            Number of archives deleted
        """
        deleted = 0
        cutoff = datetime.now() - timedelta(days=self.policy.delete_archives_after_days)

        for archive in self.base_path.rglob("*.gz"):
            try:
                mtime = datetime.fromtimestamp(archive.stat().st_mtime)
                if mtime < cutoff:
                    size = archive.stat().st_size
                    archive.unlink()
                    deleted += 1
                    self.stats["deleted"] += 1
                    self.stats["bytes_freed"] += size
                    logger.info(f"Deleted old archive: {archive.name}")
            except Exception as e:
                logger.error(f"Error deleting {archive}: {e}")
                self.stats["errors"].append(str(e))

        return deleted

    def run_maintenance(self, dry_run: bool = False) -> Dict:
        """Run full maintenance cycle.

        Args:
            dry_run: If True, only analyze without making changes

        Returns:
            Dictionary with maintenance results
        """
        logger.info(f"Starting log maintenance for {self.base_path}")

        categorized = self.analyze_logs()

        results = {
            "dry_run": dry_run,
            "base_path": str(self.base_path),
            "policy": {
                "max_size_mb": self.policy.max_size_mb,
                "keep_lines": self.policy.keep_lines,
                "archive_after_days": self.policy.archive_after_days,
            },
            "to_trim": [
                {"name": l.name, "size_mb": l.size_mb} for l in categorized[LogAction.TRIM]
            ],
            "to_archive": [
                {"name": l.name, "age_days": l.age_days} for l in categorized[LogAction.ARCHIVE]
            ],
            "to_delete": [
                {"name": l.name, "age_days": l.age_days} for l in categorized[LogAction.DELETE]
            ],
        }

        if not dry_run:
            # Trim oversized logs
            for log in categorized[LogAction.TRIM]:
                self.trim_log(log.path)

            # Archive old logs
            for log in categorized[LogAction.ARCHIVE]:
                self.archive_log(log.path)

            # Delete old archives
            self.delete_old_archives()

        results["stats"] = self.stats
        results["bytes_freed_mb"] = round(self.stats["bytes_freed"] / (1024 * 1024), 2)

        return results


def get_project_logs(project_path: Optional[Path] = None) -> List[LogFileInfo]:
    """Get all log files in the project.

    Args:
        project_path: Path to project (defaults to current working directory)

    Returns:
        List of log file info sorted by size
    """
    path = project_path or Path.cwd()
    maintenance = LogMaintenance(path)
    return maintenance.scan_logs()


def trim_large_logs(
    project_path: Optional[Path] = None,
    max_size_mb: float = 10.0,
    keep_lines: int = 5000,
    dry_run: bool = False,
) -> Dict:
    """Trim all large log files in a project.

    Args:
        project_path: Path to project
        max_size_mb: Maximum size before trimming
        keep_lines: Number of lines to keep
        dry_run: If True, only report what would be done

    Returns:
        Dictionary with results
    """
    path = project_path or Path.cwd()
    policy = MaintenancePolicy(max_size_mb=max_size_mb, keep_lines=keep_lines)
    maintenance = LogMaintenance(path, policy)
    return maintenance.run_maintenance(dry_run=dry_run)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Log file maintenance utility")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for log files")
    scan_parser.add_argument("path", nargs="?", default=".", help="Directory to scan")

    # Trim command
    trim_parser = subparsers.add_parser("trim", help="Trim oversized log files")
    trim_parser.add_argument("path", nargs="?", default=".", help="Directory to process")
    trim_parser.add_argument("--max-size", type=float, default=10.0, help="Max size in MB")
    trim_parser.add_argument("--keep-lines", type=int, default=5000, help="Lines to keep")
    trim_parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")

    # Archive command
    archive_parser = subparsers.add_parser("archive", help="Archive old log files")
    archive_parser.add_argument("path", nargs="?", default=".", help="Directory to process")
    archive_parser.add_argument("--older-than", type=int, default=7, help="Days before archiving")
    archive_parser.add_argument(
        "--dry-run", action="store_true", help="Only show what would be done"
    )

    # Clean command
    clean_parser = subparsers.add_parser("clean-project", help="Full maintenance cycle")
    clean_parser.add_argument("--path", default=".", help="Project path")
    clean_parser.add_argument("--max-size", type=float, default=10.0, help="Max size in MB")
    clean_parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.command == "scan":
        path = Path(args.path).resolve()
        maintenance = LogMaintenance(path)
        logs = maintenance.scan_logs()

        print(f"\nLog files in {path}:")
        print("-" * 60)
        total_size = 0
        for log in logs[:20]:  # Show top 20
            print(f"  {log.size_mb:>8.2f} MB  {log.age_days:>5.1f}d  {log.path.relative_to(path)}")
            total_size += log.size_bytes

        if len(logs) > 20:
            print(f"  ... and {len(logs) - 20} more files")

        print("-" * 60)
        print(f"Total: {len(logs)} files, {total_size / (1024*1024):.2f} MB")

    elif args.command == "trim":
        path = Path(args.path).resolve()
        policy = MaintenancePolicy(max_size_mb=args.max_size, keep_lines=args.keep_lines)
        maintenance = LogMaintenance(path, policy)

        logs = maintenance.scan_logs()
        to_trim = [l for l in logs if l.size_mb > args.max_size]

        if not to_trim:
            print(f"No log files larger than {args.max_size}MB found")
            return

        print(f"\nFiles to trim (>{args.max_size}MB):")
        for log in to_trim:
            print(f"  {log.size_mb:>8.2f} MB  {log.path.relative_to(path)}")

        if args.dry_run:
            print("\n[DRY RUN] No changes made")
        else:
            print(f"\nTrimming to keep last {args.keep_lines} lines...")
            for log in to_trim:
                maintenance.trim_log(log.path)

            print(f"\nTrimmed {maintenance.stats['trimmed']} files")
            print(f"Freed {maintenance.stats['bytes_freed'] / (1024*1024):.2f} MB")

    elif args.command == "archive":
        path = Path(args.path).resolve()
        policy = MaintenancePolicy(archive_after_days=args.older_than)
        maintenance = LogMaintenance(path, policy)

        logs = maintenance.scan_logs()
        to_archive = [l for l in logs if l.age_days > args.older_than]

        if not to_archive:
            print(f"No log files older than {args.older_than} days found")
            return

        print(f"\nFiles to archive (>{args.older_than} days old):")
        for log in to_archive:
            print(f"  {log.age_days:>5.1f}d  {log.size_mb:>8.2f} MB  {log.path.relative_to(path)}")

        if args.dry_run:
            print("\n[DRY RUN] No changes made")
        else:
            print("\nArchiving...")
            for log in to_archive:
                maintenance.archive_log(log.path)

            print(f"\nArchived {maintenance.stats['archived']} files")
            print(f"Freed {maintenance.stats['bytes_freed'] / (1024*1024):.2f} MB")

    elif args.command == "clean-project":
        path = Path(args.path).resolve()
        policy = MaintenancePolicy(max_size_mb=args.max_size)
        maintenance = LogMaintenance(path, policy)

        results = maintenance.run_maintenance(dry_run=args.dry_run)

        print(f"\nLog Maintenance Report for {path}")
        print("=" * 60)

        if results["to_trim"]:
            print("\nFiles trimmed (oversized):")
            for f in results["to_trim"]:
                print(f"  {f['size_mb']:>8.2f} MB  {f['name']}")

        if results["to_archive"]:
            print("\nFiles archived (old):")
            for f in results["to_archive"]:
                print(f"  {f['age_days']:>5.1f}d  {f['name']}")

        if results["to_delete"]:
            print("\nArchives deleted (expired):")
            for f in results["to_delete"]:
                print(f"  {f['age_days']:>5.1f}d  {f['name']}")

        print("\n" + "-" * 60)
        stats = results["stats"]
        print(f"Scanned: {stats['scanned']} files")
        print(f"Trimmed: {stats['trimmed']} files")
        print(f"Archived: {stats['archived']} files")
        print(f"Deleted: {stats['deleted']} files")
        print(f"Space freed: {results['bytes_freed_mb']:.2f} MB")

        if args.dry_run:
            print("\n[DRY RUN] No changes were made")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
