#!/usr/bin/env python3
"""
Supervisor Integration Module

Integrates the process supervisor with:
- Existing health monitor worker
- Architect dashboard
- Alert system
- Metrics collection
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("supervisor_integration")


class SupervisorIntegration:
    """Integration layer between supervisor and architect systems."""

    def __init__(self, db_path: str = None):
        """Initialize integration.

        Args:
            db_path: Path to architect database
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "architect.db"

        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize supervisor tables in architect database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Supervisor services table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS supervisor_services (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        state TEXT NOT NULL,
                        pid INTEGER,
                        port INTEGER,
                        start_time TIMESTAMP,
                        uptime_seconds INTEGER DEFAULT 0,
                        restart_count INTEGER DEFAULT 0,
                        last_restart TIMESTAMP,
                        priority INTEGER DEFAULT 999,
                        critical INTEGER DEFAULT 0,
                        auto_restart INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Supervisor metrics table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS supervisor_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        cpu_percent REAL,
                        memory_mb REAL,
                        health_status TEXT,
                        response_time_ms REAL,
                        FOREIGN KEY (service_id) REFERENCES supervisor_services(id)
                    )
                """
                )

                # Supervisor events table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS supervisor_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message TEXT,
                        details TEXT,
                        FOREIGN KEY (service_id) REFERENCES supervisor_services(id)
                    )
                """
                )

                # Create indexes
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_supervisor_metrics_service
                    ON supervisor_metrics(service_id, timestamp)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_supervisor_events_service
                    ON supervisor_events(service_id, timestamp)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_supervisor_events_type
                    ON supervisor_events(event_type, timestamp)
                """
                )

                conn.commit()
                logger.info("Supervisor database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize supervisor database: {e}")

    def update_service_state(self, service_id: str, service_data: Dict):
        """Update service state in database.

        Args:
            service_id: Service identifier
            service_data: Service state data
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO supervisor_services
                    (id, name, description, state, pid, port, start_time,
                     uptime_seconds, restart_count, last_restart, priority,
                     critical, auto_restart, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        service_id,
                        service_data.get("name", service_id),
                        service_data.get("description"),
                        service_data.get("state"),
                        service_data.get("pid"),
                        service_data.get("port"),
                        service_data.get("start_time"),
                        service_data.get("uptime_seconds", 0),
                        service_data.get("restart_count", 0),
                        service_data.get("last_restart"),
                        service_data.get("priority", 999),
                        1 if service_data.get("critical") else 0,
                        1 if service_data.get("auto_restart", True) else 0,
                    ),
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update service state for '{service_id}': {e}")

    def record_metrics(self, service_id: str, metrics: Dict):
        """Record service metrics.

        Args:
            service_id: Service identifier
            metrics: Metrics data
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO supervisor_metrics
                    (service_id, cpu_percent, memory_mb, health_status, response_time_ms)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        service_id,
                        metrics.get("cpu_percent"),
                        metrics.get("memory_mb"),
                        metrics.get("health_status"),
                        metrics.get("response_time_ms"),
                    ),
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to record metrics for '{service_id}': {e}")

    def log_event(self, service_id: str, event_type: str, message: str, details: Dict = None):
        """Log supervisor event.

        Args:
            service_id: Service identifier
            event_type: Event type (started, stopped, failed, restarted, etc.)
            message: Event message
            details: Optional event details
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO supervisor_events
                    (service_id, event_type, message, details)
                    VALUES (?, ?, ?, ?)
                """,
                    (service_id, event_type, message, json.dumps(details) if details else None),
                )

                conn.commit()

                # Also log to activity_log if table exists
                try:
                    conn.execute(
                        """
                        INSERT INTO activity_log
                        (action, details, source)
                        VALUES (?, ?, ?)
                    """,
                        (
                            f"supervisor_{event_type}",
                            f"{service_id}: {message}",
                            "process_supervisor",
                        ),
                    )
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # activity_log table doesn't exist

        except Exception as e:
            logger.error(f"Failed to log event for '{service_id}': {e}")

    def create_alert(self, service_id: str, severity: str, message: str):
        """Create alert in dashboard.

        Args:
            service_id: Service identifier
            severity: Alert severity (info, warning, error, critical)
            message: Alert message
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Check if health_alerts table exists
                cursor = conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='health_alerts'
                """
                )

                if cursor.fetchone():
                    conn.execute(
                        """
                        INSERT INTO health_alerts
                        (severity, message, component, resolved)
                        VALUES (?, ?, ?, 0)
                    """,
                        (severity, message, f"supervisor:{service_id}"),
                    )
                    conn.commit()

        except Exception as e:
            logger.error(f"Failed to create alert: {e}")

    def get_service_status(self, service_id: str = None) -> List[Dict]:
        """Get service status from database.

        Args:
            service_id: Optional service ID to filter

        Returns:
            List of service status dictionaries
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if service_id:
                    cursor = conn.execute(
                        """
                        SELECT * FROM supervisor_services
                        WHERE id = ?
                    """,
                        (service_id,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM supervisor_services
                        ORDER BY priority ASC, name ASC
                    """
                    )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return []

    def get_service_metrics(self, service_id: str, limit: int = 100) -> List[Dict]:
        """Get recent metrics for a service.

        Args:
            service_id: Service identifier
            limit: Maximum number of metrics to return

        Returns:
            List of metrics dictionaries
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(
                    """
                    SELECT * FROM supervisor_metrics
                    WHERE service_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (service_id, limit),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get service metrics: {e}")
            return []

    def get_service_events(
        self, service_id: str = None, event_type: str = None, limit: int = 100
    ) -> List[Dict]:
        """Get recent events.

        Args:
            service_id: Optional service ID filter
            event_type: Optional event type filter
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                query = "SELECT * FROM supervisor_events WHERE 1=1"
                params = []

                if service_id:
                    query += " AND service_id = ?"
                    params.append(service_id)

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get service events: {e}")
            return []

    def cleanup_old_data(self, days: int = 30):
        """Cleanup old metrics and events.

        Args:
            days: Keep data newer than this many days
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Cleanup old metrics
                conn.execute(
                    """
                    DELETE FROM supervisor_metrics
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                    (days,),
                )

                # Cleanup old events
                conn.execute(
                    """
                    DELETE FROM supervisor_events
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                    (days,),
                )

                conn.commit()

                logger.info(f"Cleaned up supervisor data older than {days} days")

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")

    def get_dashboard_summary(self) -> Dict:
        """Get summary for dashboard display.

        Returns:
            Summary dictionary
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                # Get service counts by state
                cursor = conn.execute(
                    """
                    SELECT state, COUNT(*) as count
                    FROM supervisor_services
                    GROUP BY state
                """
                )

                state_counts = {row["state"]: row["count"] for row in cursor}

                # Get critical services
                cursor = conn.execute(
                    """
                    SELECT * FROM supervisor_services
                    WHERE critical = 1
                    ORDER BY state DESC, name ASC
                """
                )

                critical_services = [dict(row) for row in cursor]

                # Get recent failures
                cursor = conn.execute(
                    """
                    SELECT service_id, COUNT(*) as failure_count
                    FROM supervisor_events
                    WHERE event_type IN ('failed', 'restarted')
                    AND timestamp > datetime('now', '-1 hour')
                    GROUP BY service_id
                    ORDER BY failure_count DESC
                    LIMIT 5
                """
                )

                recent_failures = [dict(row) for row in cursor]

                return {
                    "state_counts": state_counts,
                    "critical_services": critical_services,
                    "recent_failures": recent_failures,
                    "total_services": sum(state_counts.values()),
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get dashboard summary: {e}")
            return {}


if __name__ == "__main__":
    # Test integration
    integration = SupervisorIntegration()

    # Test service update
    integration.update_service_state(
        "test-service",
        {
            "name": "Test Service",
            "description": "Test service for integration",
            "state": "running",
            "pid": 12345,
            "port": 8080,
            "start_time": datetime.now().isoformat(),
            "critical": True,
        },
    )

    # Test event logging
    integration.log_event("test-service", "started", "Service started successfully")

    # Test metrics recording
    integration.record_metrics(
        "test-service",
        {
            "cpu_percent": 5.2,
            "memory_mb": 128.5,
            "health_status": "healthy",
            "response_time_ms": 45.3,
        },
    )

    # Get summary
    summary = integration.get_dashboard_summary()
    print(json.dumps(summary, indent=2))
