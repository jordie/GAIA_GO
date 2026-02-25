"""System-wide resource monitoring and auto-throttling service."""
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitor system resources and determine auto-throttling status."""

    # Load thresholds
    HIGH_LOAD_THRESHOLD = 80  # CPU/memory %
    CRITICAL_LOAD_THRESHOLD = 95

    def __init__(self, db_connection_factory):
        """Initialize resource monitor.

        Args:
            db_connection_factory: Callable that returns DB connection
        """
        self.get_db = db_connection_factory
        self.high_load_threshold = self.HIGH_LOAD_THRESHOLD
        self.critical_load_threshold = self.CRITICAL_LOAD_THRESHOLD
        self.throttle_active = False
        self._last_disk_io = None
        self._last_net_io = None

    def record_snapshot(self) -> Dict:
        """Record current resource usage to database.

        Returns:
            Dictionary with current resource metrics
        """
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()

            # Get disk and network I/O
            try:
                disk = psutil.disk_io_counters()
                disk_read_mb = (disk.read_bytes / (1024 * 1024)) if self._last_disk_io is None else \
                    ((disk.read_bytes - self._last_disk_io.read_bytes) / (1024 * 1024))
                disk_write_mb = (disk.write_bytes / (1024 * 1024)) if self._last_disk_io is None else \
                    ((disk.write_bytes - self._last_disk_io.write_bytes) / (1024 * 1024))
                self._last_disk_io = disk
            except Exception:
                disk_read_mb = 0
                disk_write_mb = 0

            try:
                network = psutil.net_io_counters()
                net_sent_mb = (network.bytes_sent / (1024 * 1024)) if self._last_net_io is None else \
                    ((network.bytes_sent - self._last_net_io.bytes_sent) / (1024 * 1024))
                net_recv_mb = (network.bytes_recv / (1024 * 1024)) if self._last_net_io is None else \
                    ((network.bytes_recv - self._last_net_io.bytes_recv) / (1024 * 1024))
                self._last_net_io = network
            except Exception:
                net_sent_mb = 0
                net_recv_mb = 0

            snapshot = {
                "cpu_percent": cpu,
                "memory_percent": memory.percent,
                "memory_mb": memory.used / (1024 * 1024),
                "disk_io_read_mb": disk_read_mb,
                "disk_io_write_mb": disk_write_mb,
                "network_sent_mb": net_sent_mb,
                "network_recv_mb": net_recv_mb,
            }

            # Store in database
            try:
                conn = self.get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO resource_consumption
                    (cpu_percent, memory_percent, memory_mb, disk_io_read_mb,
                     disk_io_write_mb, network_sent_mb, network_recv_mb)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, tuple(snapshot.values()))
                conn.commit()
            except Exception as e:
                logger.error(f"Error storing resource snapshot: {e}")

            return snapshot
        except Exception as e:
            logger.error(f"Error recording snapshot: {e}")
            return {}

    def should_throttle(self) -> Tuple[bool, Optional[str]]:
        """Check if system should throttle requests.

        Returns:
            Tuple of (should_throttle, reason_string)
        """
        try:
            snapshot = self.get_current_load()

            if snapshot["cpu_percent"] > self.critical_load_threshold:
                return True, "critical_cpu"
            if snapshot["memory_percent"] > self.critical_load_threshold:
                return True, "critical_memory"
            if snapshot["cpu_percent"] > self.high_load_threshold:
                return True, "high_cpu"
            if snapshot["memory_percent"] > self.high_load_threshold:
                return True, "high_memory"

            return False, None
        except Exception as e:
            logger.error(f"Error checking throttle status: {e}")
            return False, None

    def get_current_load(self) -> Dict:
        """Get current system load metrics.

        Returns:
            Dictionary with current CPU, memory, and disk usage
        """
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting current load: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0
            }

    def get_load_trend(self, minutes: int = 5) -> Dict:
        """Get load trend over specified time period.

        Args:
            minutes: Number of minutes to analyze

        Returns:
            Dictionary with load trend statistics
        """
        try:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    AVG(cpu_percent) as avg_cpu,
                    MAX(cpu_percent) as max_cpu,
                    MIN(cpu_percent) as min_cpu,
                    AVG(memory_percent) as avg_memory,
                    MAX(memory_percent) as max_memory,
                    MIN(memory_percent) as min_memory,
                    COUNT(*) as samples
                FROM resource_consumption
                WHERE timestamp > ?
            """, (cutoff,))

            row = cursor.fetchone()
            if row:
                return {
                    "minutes": minutes,
                    "cpu": {
                        "avg": round(row[0], 2) if row[0] else 0,
                        "max": round(row[1], 2) if row[1] else 0,
                        "min": round(row[2], 2) if row[2] else 0
                    },
                    "memory": {
                        "avg": round(row[3], 2) if row[3] else 0,
                        "max": round(row[4], 2) if row[4] else 0,
                        "min": round(row[5], 2) if row[5] else 0
                    },
                    "samples": row[6]
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting load trend: {e}")
            return {}

    def get_hourly_summary(self, hours: int = 24) -> Dict:
        """Get hourly resource usage summary.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with hourly breakdown
        """
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    DATE(timestamp) as date,
                    CAST(STRFTIME('%H', timestamp) as INTEGER) as hour,
                    AVG(cpu_percent) as avg_cpu,
                    MAX(cpu_percent) as max_cpu,
                    AVG(memory_percent) as avg_memory,
                    MAX(memory_percent) as max_memory
                FROM resource_consumption
                WHERE timestamp > ?
                GROUP BY DATE(timestamp), hour
                ORDER BY date DESC, hour DESC
            """, (cutoff,))

            hourly = []
            for row in cursor.fetchall():
                hourly.append({
                    "date": row[0],
                    "hour": row[1],
                    "cpu_avg": round(row[2], 2) if row[2] else 0,
                    "cpu_max": round(row[3], 2) if row[3] else 0,
                    "memory_avg": round(row[4], 2) if row[4] else 0,
                    "memory_max": round(row[5], 2) if row[5] else 0
                })

            return {
                "hours": hours,
                "hourly_data": hourly
            }
        except Exception as e:
            logger.error(f"Error getting hourly summary: {e}")
            return {}

    def record_throttle_event(self, reason: str) -> bool:
        """Record when throttling was activated.

        Args:
            reason: Reason for throttling

        Returns:
            True if successful
        """
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO system_load_history
                (cpu_percent, memory_percent, disk_percent, throttle_active, throttle_reason)
                SELECT
                    (SELECT AVG(cpu_percent) FROM resource_consumption WHERE timestamp > datetime('now', '-1 minute')),
                    (SELECT AVG(memory_percent) FROM resource_consumption WHERE timestamp > datetime('now', '-1 minute')),
                    NULL,
                    1,
                    ?
            """, (reason,))

            conn.commit()
            self.throttle_active = True
            logger.warning(f"Throttling activated: {reason}")
            return True
        except Exception as e:
            logger.error(f"Error recording throttle event: {e}")
            return False

    def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old resource consumption data.

        Args:
            days: Number of days to retain

        Returns:
            Number of records deleted
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM resource_consumption WHERE timestamp < ?",
                (cutoff,)
            )
            consumption_deleted = cursor.rowcount

            cursor.execute(
                "DELETE FROM system_load_history WHERE timestamp < ?",
                (cutoff,)
            )
            history_deleted = cursor.rowcount

            conn.commit()
            total = consumption_deleted + history_deleted
            logger.info(f"Cleanup: deleted {consumption_deleted} consumption records, {history_deleted} history records")
            return total
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def get_health_status(self) -> Dict:
        """Get overall system health status.

        Returns:
            Dictionary with health metrics
        """
        try:
            current = self.get_current_load()
            trend = self.get_load_trend(minutes=5)
            should_throttle, throttle_reason = self.should_throttle()

            return {
                "healthy": not should_throttle,
                "current": current,
                "trend_5min": trend,
                "throttling": should_throttle,
                "throttle_reason": throttle_reason,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"healthy": True}  # Assume healthy if error

    def set_thresholds(self, high: int = 80, critical: int = 95) -> None:
        """Configure load thresholds.

        Args:
            high: High load threshold percentage
            critical: Critical load threshold percentage
        """
        if 0 < high < 100 and 0 < critical < 100 and high < critical:
            self.high_load_threshold = high
            self.critical_load_threshold = critical
            logger.info(f"Updated thresholds: high={high}%, critical={critical}%")
        else:
            logger.warning(f"Invalid threshold values: high={high}, critical={critical}")
