#!/usr/bin/env python3
"""
Cluster Coordinator for Failover Architecture.

Manages primary/failover roles, health monitoring, and automatic failover
for the educational apps distributed system.

Architecture:
- One PRIMARY node runs the master dashboard
- One FAILOVER node is ready to take over if primary fails
- WORKER nodes run apps only, report metrics to primary

Usage:
    from distributed.cluster_coordinator import ClusterCoordinator, NodeRole

    coordinator = ClusterCoordinator(
        node_id='primary',
        role=NodeRole.PRIMARY,
        bind_port=5051
    )
    coordinator.start()
"""

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """Role of a node in the cluster."""

    PRIMARY = "primary"  # Master dashboard, controls cluster
    FAILOVER = "failover"  # Ready to take over if primary fails
    WORKER = "worker"  # Apps only, reports to primary


class ClusterState(Enum):
    """State of the cluster."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Some nodes down
    FAILOVER = "failover"  # Primary down, failover active
    SPLIT = "split"  # Network partition detected


@dataclass
class NodeInfo:
    """Information about a cluster node."""

    node_id: str
    role: NodeRole
    host: str
    port: int
    dashboard_url: str
    api_url: str
    last_heartbeat: float = 0
    cpu_usage: float = 0
    memory_usage: float = 0
    disk_usage: float = 0
    is_healthy: bool = False
    is_reachable: bool = False
    services: List[str] = None

    def __post_init__(self):
        if self.services is None:
            self.services = []

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["role"] = self.role.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "NodeInfo":
        data["role"] = NodeRole(data["role"])
        return cls(**data)


@dataclass
class ClusterConfig:
    """Configuration for the cluster."""

    heartbeat_interval: int = 10  # Seconds between heartbeats
    health_check_interval: int = 15  # Seconds between health checks
    failover_threshold: int = 30  # Seconds before failover
    recovery_threshold: int = 60  # Seconds before primary can reclaim
    max_missed_heartbeats: int = 3  # Missed heartbeats before unhealthy


class ClusterCoordinator:
    """Coordinates cluster nodes and manages failover."""

    def __init__(
        self,
        node_id: str,
        role: NodeRole,
        host: str = "0.0.0.0",
        port: int = 5051,
        config: Optional[ClusterConfig] = None,
        db_path: Optional[Path] = None,
    ):
        self.node_id = node_id
        self.role = role
        self.original_role = role
        self.host = host
        self.port = port
        self.config = config or ClusterConfig()

        # Database for cluster state
        self.db_path = db_path or Path(__file__).parent.parent / "cluster_state.db"
        self._init_database()

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.cluster_state = ClusterState.HEALTHY
        self.is_active_primary = role == NodeRole.PRIMARY
        self.primary_node_id: Optional[str] = None
        self.failover_node_id: Optional[str] = None

        # Threading
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._health_check_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Callbacks
        self._on_role_change: Optional[Callable] = None
        self._on_failover: Optional[Callable] = None
        self._on_node_down: Optional[Callable] = None

        # Register self
        self._register_self()

    def _get_db_connection(self):
        """Get database connection with WAL mode and proper timeout."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_database(self):
        """Initialize the cluster state database."""
        with self._get_db_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cluster_nodes (
                    node_id TEXT PRIMARY KEY,
                    role TEXT,
                    host TEXT,
                    port INTEGER,
                    dashboard_url TEXT,
                    api_url TEXT,
                    last_heartbeat REAL,
                    cpu_usage REAL DEFAULT 0,
                    memory_usage REAL DEFAULT 0,
                    disk_usage REAL DEFAULT 0,
                    is_healthy INTEGER DEFAULT 0,
                    services TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cluster_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS failover_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    from_node TEXT,
                    to_node TEXT,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.commit()

    def _register_self(self):
        """Register this node in the cluster."""
        dashboard_url = f"https://{self.host}:{self.port}/architecture/"
        api_url = f"https://{self.host}:{self.port}/architecture/api"

        self_info = NodeInfo(
            node_id=self.node_id,
            role=self.role,
            host=self.host,
            port=self.port,
            dashboard_url=dashboard_url,
            api_url=api_url,
            last_heartbeat=time.time(),
            is_healthy=True,
            is_reachable=True,
            services=["typing", "math", "reading", "piano"],
        )

        self.nodes[self.node_id] = self_info
        self._save_node(self_info)

        if self.role == NodeRole.PRIMARY:
            self.primary_node_id = self.node_id
        elif self.role == NodeRole.FAILOVER:
            self.failover_node_id = self.node_id

    def _save_node(self, node: NodeInfo):
        """Save node info to database."""
        with self._get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cluster_nodes
                (node_id, role, host, port, dashboard_url, api_url,
                 last_heartbeat, cpu_usage, memory_usage, disk_usage,
                 is_healthy, services, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    node.node_id,
                    node.role.value,
                    node.host,
                    node.port,
                    node.dashboard_url,
                    node.api_url,
                    node.last_heartbeat,
                    node.cpu_usage,
                    node.memory_usage,
                    node.disk_usage,
                    1 if node.is_healthy else 0,
                    json.dumps(node.services),
                ),
            )
            conn.commit()

    def _load_nodes(self):
        """Load all nodes from database."""
        with self._get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM cluster_nodes").fetchall()

            for row in rows:
                node = NodeInfo(
                    node_id=row["node_id"],
                    role=NodeRole(row["role"]),
                    host=row["host"],
                    port=row["port"],
                    dashboard_url=row["dashboard_url"],
                    api_url=row["api_url"],
                    last_heartbeat=row["last_heartbeat"] or 0,
                    cpu_usage=row["cpu_usage"] or 0,
                    memory_usage=row["memory_usage"] or 0,
                    disk_usage=row["disk_usage"] or 0,
                    is_healthy=bool(row["is_healthy"]),
                    services=json.loads(row["services"] or "[]"),
                )
                self.nodes[node.node_id] = node

    def add_node(
        self,
        node_id: str,
        role: NodeRole,
        host: str,
        port: int,
        services: Optional[List[str]] = None,
    ) -> NodeInfo:
        """Add a node to the cluster."""
        dashboard_url = f"https://{host}:{port}/architecture/"
        api_url = f"https://{host}:{port}/architecture/api"

        node = NodeInfo(
            node_id=node_id,
            role=role,
            host=host,
            port=port,
            dashboard_url=dashboard_url,
            api_url=api_url,
            services=services or ["typing", "math", "reading", "piano"],
        )

        with self._lock:
            self.nodes[node_id] = node
            self._save_node(node)

            if role == NodeRole.FAILOVER:
                self.failover_node_id = node_id

        logger.info(f"Added node {node_id} as {role.value}")
        return node

    def remove_node(self, node_id: str):
        """Remove a node from the cluster."""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]

            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM cluster_nodes WHERE node_id = ?", (node_id,))
                conn.commit()

        logger.info(f"Removed node {node_id}")

    def start(self):
        """Start the coordinator."""
        self._running = True
        self._load_nodes()

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name=f"heartbeat-{self.node_id}"
        )
        self._heartbeat_thread.start()

        # Start health check thread (primary and failover only)
        if self.role in (NodeRole.PRIMARY, NodeRole.FAILOVER):
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop, daemon=True, name=f"health-{self.node_id}"
            )
            self._health_check_thread.start()

        logger.info(f"Cluster coordinator started: {self.node_id} as {self.role.value}")

    def stop(self):
        """Stop the coordinator."""
        self._running = False

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

        logger.info(f"Cluster coordinator stopped: {self.node_id}")

    def _heartbeat_loop(self):
        """Send heartbeats to primary (workers) or update local state (primary)."""
        while self._running:
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            time.sleep(self.config.heartbeat_interval)

    def _send_heartbeat(self):
        """Send heartbeat with current metrics."""
        import psutil

        metrics = {
            "node_id": self.node_id,
            "role": self.role.value,
            "timestamp": time.time(),
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
        }

        # Update self
        with self._lock:
            if self.node_id in self.nodes:
                node = self.nodes[self.node_id]
                node.last_heartbeat = metrics["timestamp"]
                node.cpu_usage = metrics["cpu_usage"]
                node.memory_usage = metrics["memory_usage"]
                node.disk_usage = metrics["disk_usage"]
                node.is_healthy = True
                self._save_node(node)

        # If worker, send to primary
        if self.role == NodeRole.WORKER and self.primary_node_id:
            primary = self.nodes.get(self.primary_node_id)
            if primary:
                try:
                    url = f"{primary.api_url}/cluster/heartbeat"
                    requests.post(url, json=metrics, timeout=5, verify=False)
                except Exception as e:
                    logger.warning(f"Failed to send heartbeat to primary: {e}")

    def _health_check_loop(self):
        """Check health of all nodes (primary and failover only)."""
        while self._running:
            try:
                self._check_all_nodes()
                self._evaluate_cluster_state()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            time.sleep(self.config.health_check_interval)

    def _check_all_nodes(self):
        """Check health of all registered nodes."""
        now = time.time()

        with self._lock:
            for node_id, node in self.nodes.items():
                if node_id == self.node_id:
                    continue

                # Check if node is reachable
                try:
                    url = f"{node.api_url}/health"
                    resp = requests.get(url, timeout=5, verify=False)
                    node.is_reachable = resp.status_code == 200

                    if node.is_reachable:
                        data = resp.json()
                        node.last_heartbeat = now
                        node.cpu_usage = data.get("cpu_usage", 0)
                        node.memory_usage = data.get("memory_usage", 0)
                        node.is_healthy = True
                except Exception:
                    node.is_reachable = False

                # Check heartbeat age
                heartbeat_age = now - node.last_heartbeat
                if (
                    heartbeat_age
                    > self.config.heartbeat_interval * self.config.max_missed_heartbeats
                ):
                    node.is_healthy = False

                self._save_node(node)

    def _evaluate_cluster_state(self):
        """Evaluate cluster state and trigger failover if needed."""
        with self._lock:
            healthy_count = sum(1 for n in self.nodes.values() if n.is_healthy)
            total_count = len(self.nodes)

            # Check if primary is down
            primary = self.nodes.get(self.primary_node_id)
            primary_down = primary and not primary.is_healthy

            if primary_down and self.role == NodeRole.FAILOVER:
                # Check failover threshold
                if primary:
                    down_time = time.time() - primary.last_heartbeat
                    if down_time >= self.config.failover_threshold:
                        self._trigger_failover()
                        return

            # Update cluster state
            if healthy_count == total_count:
                self.cluster_state = ClusterState.HEALTHY
            elif healthy_count > 0:
                self.cluster_state = ClusterState.DEGRADED
            else:
                self.cluster_state = ClusterState.SPLIT

    def _trigger_failover(self):
        """Trigger failover - this node becomes primary."""
        logger.warning(f"FAILOVER: {self.node_id} taking over as primary")

        old_primary = self.primary_node_id

        with self._lock:
            self.role = NodeRole.PRIMARY
            self.is_active_primary = True
            self.primary_node_id = self.node_id
            self.cluster_state = ClusterState.FAILOVER

            # Update self in nodes
            if self.node_id in self.nodes:
                self.nodes[self.node_id].role = NodeRole.PRIMARY
                self._save_node(self.nodes[self.node_id])

            # Log the failover
            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO failover_log (event_type, from_node, to_node, reason)
                    VALUES (?, ?, ?, ?)
                """,
                    ("failover", old_primary, self.node_id, "Primary unreachable"),
                )
                conn.commit()

        # Notify callback
        if self._on_failover:
            self._on_failover(old_primary, self.node_id)

        if self._on_role_change:
            self._on_role_change(self.role)

    def receive_heartbeat(self, data: Dict):
        """Receive heartbeat from a worker node."""
        node_id = data.get("node_id")
        if not node_id:
            return

        with self._lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.last_heartbeat = data.get("timestamp", time.time())
                node.cpu_usage = data.get("cpu_usage", 0)
                node.memory_usage = data.get("memory_usage", 0)
                node.disk_usage = data.get("disk_usage", 0)
                node.is_healthy = True
                node.is_reachable = True
                self._save_node(node)

    def get_cluster_status(self) -> Dict:
        """Get current cluster status."""
        with self._lock:
            nodes_list = []
            for node in self.nodes.values():
                nodes_list.append(node.to_dict())

            return {
                "cluster_state": self.cluster_state.value,
                "primary_node": self.primary_node_id,
                "failover_node": self.failover_node_id,
                "this_node": self.node_id,
                "this_role": self.role.value,
                "is_active_primary": self.is_active_primary,
                "total_nodes": len(self.nodes),
                "healthy_nodes": sum(1 for n in self.nodes.values() if n.is_healthy),
                "nodes": nodes_list,
            }

    def get_dashboard_url(self) -> str:
        """Get URL of the active dashboard."""
        if self.is_active_primary:
            return self.nodes[self.node_id].dashboard_url

        if self.primary_node_id and self.primary_node_id in self.nodes:
            primary = self.nodes[self.primary_node_id]
            if primary.is_healthy:
                return primary.dashboard_url

        # Failover to failover node
        if self.failover_node_id and self.failover_node_id in self.nodes:
            return self.nodes[self.failover_node_id].dashboard_url

        return None

    def on_role_change(self, callback: Callable):
        """Set callback for role changes."""
        self._on_role_change = callback

    def on_failover(self, callback: Callable):
        """Set callback for failover events."""
        self._on_failover = callback

    def on_node_down(self, callback: Callable):
        """Set callback for node down events."""
        self._on_node_down = callback


# Singleton instance
_coordinator: Optional[ClusterCoordinator] = None


def get_coordinator() -> Optional[ClusterCoordinator]:
    """Get the global coordinator instance."""
    return _coordinator


def init_coordinator(
    node_id: str, role: NodeRole, host: str = "0.0.0.0", port: int = 5051, **kwargs
) -> ClusterCoordinator:
    """Initialize the global coordinator."""
    global _coordinator
    _coordinator = ClusterCoordinator(node_id=node_id, role=role, host=host, port=port, **kwargs)
    return _coordinator
