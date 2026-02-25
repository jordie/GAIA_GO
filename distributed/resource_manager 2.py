"""
Resource Manager for distributed system.

Central coordinator for cluster resources, node management,
health monitoring, and resource allocation.
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """Node role in the cluster."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    WORKER = "worker"


class NodeStatus(Enum):
    """Node health status."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class NodeConfig:
    """Configuration for a cluster node."""

    id: str
    hostname: str
    ip_address: str
    ssh_port: int = 22
    ssh_user: str = None
    ssh_key_file: str = None
    role: NodeRole = NodeRole.WORKER
    services: List[str] = field(default_factory=list)
    cpu_limit: int = 80  # Max CPU usage %
    memory_limit: int = 80  # Max memory usage %
    has_gpu: bool = False

    def __post_init__(self):
        if self.ssh_user is None:
            self.ssh_user = os.environ.get("USER", "root")


@dataclass
class NodeState:
    """Runtime state of a node."""

    node_id: str
    status: NodeStatus = NodeStatus.OFFLINE
    last_heartbeat: float = 0
    cpu_usage: float = 0
    memory_usage: float = 0
    disk_usage: float = 0
    memory_mb: int = 0
    disk_free_mb: int = 0
    cpu_cores: int = 0
    load_average: List[float] = field(default_factory=list)
    active_services: List[str] = field(default_factory=list)
    error_message: str = ""

    def is_healthy(self) -> bool:
        """Check if node is healthy."""
        return self.status == NodeStatus.ONLINE

    def is_overloaded(self, cpu_limit: int = 80, memory_limit: int = 80) -> bool:
        """Check if node is overloaded."""
        return self.cpu_usage > cpu_limit or self.memory_usage > memory_limit


@dataclass
class ResourceAllocation:
    """Tracks a resource allocation."""

    id: str
    resource_type: str  # "ollama", "gpu", etc.
    requester: str  # Who requested it
    node_id: str  # Where it's allocated
    allocated_at: float
    released_at: Optional[float] = None
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceManager:
    """
    Central coordinator for distributed cluster resources.

    Manages nodes, monitors health, allocates resources,
    and handles failover.
    """

    def __init__(
        self,
        cluster_name: str = "edu-apps-cluster",
        heartbeat_interval: int = 10,
        failure_threshold: int = 3,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the resource manager.

        Args:
            cluster_name: Name of this cluster
            heartbeat_interval: Seconds between heartbeat checks
            failure_threshold: Missed heartbeats before marking offline
            db_path: Path to SQLite database for persistence
        """
        self.cluster_name = cluster_name
        self.heartbeat_interval = heartbeat_interval
        self.failure_threshold = failure_threshold

        self._nodes: Dict[str, NodeConfig] = {}
        self._node_states: Dict[str, NodeState] = {}
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._lock = threading.RLock()

        # Callbacks for events
        self._on_node_offline: List[Callable[[str], None]] = []
        self._on_node_online: List[Callable[[str], None]] = []
        self._on_failover: List[Callable[[str, str], None]] = []

        # Database setup
        if db_path:
            self._db_path = Path(db_path)
        else:
            self._db_path = Path(__file__).parent.parent / "cluster.db"

        self._init_database()

        # Background monitoring
        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def _get_db_connection(self):
        """Get database connection with WAL mode and proper timeout."""
        conn = sqlite3.connect(str(self._db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_database(self) -> None:
        """Initialize the SQLite database for persistence."""
        with self._get_db_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cluster_nodes (
                    id TEXT PRIMARY KEY,
                    hostname TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    ssh_port INTEGER DEFAULT 22,
                    ssh_user TEXT,
                    ssh_key_file TEXT,
                    role TEXT NOT NULL,
                    services TEXT,
                    cpu_limit INTEGER DEFAULT 80,
                    memory_limit INTEGER DEFAULT 80,
                    has_gpu INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'offline',
                    last_heartbeat TIMESTAMP,
                    cpu_usage REAL DEFAULT 0,
                    memory_usage REAL DEFAULT 0,
                    disk_usage REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS service_instances (
                    id TEXT PRIMARY KEY,
                    node_id TEXT REFERENCES cluster_nodes(id),
                    service_name TEXT NOT NULL,
                    port INTEGER,
                    status TEXT DEFAULT 'starting',
                    health_endpoint TEXT,
                    last_health_check TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS resource_allocations (
                    id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    requester TEXT,
                    node_id TEXT REFERENCES cluster_nodes(id),
                    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    released_at TIMESTAMP,
                    priority TEXT DEFAULT 'normal',
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS cluster_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    node_id TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

    def _log_event(self, event_type: str, node_id: str = None, description: str = "") -> None:
        """Log a cluster event to the database."""
        try:
            with self._get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO cluster_events (event_type, node_id, description) VALUES (?, ?, ?)",
                    (event_type, node_id, description),
                )
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def register_node(self, config: NodeConfig) -> str:
        """
        Register a node with the cluster.

        Args:
            config: Node configuration

        Returns:
            Node ID
        """
        with self._lock:
            self._nodes[config.id] = config
            self._node_states[config.id] = NodeState(node_id=config.id)

            # Persist to database
            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cluster_nodes
                    (id, hostname, ip_address, ssh_port, ssh_user, ssh_key_file,
                     role, services, cpu_limit, memory_limit, has_gpu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        config.id,
                        config.hostname,
                        config.ip_address,
                        config.ssh_port,
                        config.ssh_user,
                        config.ssh_key_file,
                        config.role.value,
                        json.dumps(config.services),
                        config.cpu_limit,
                        config.memory_limit,
                        1 if config.has_gpu else 0,
                    ),
                )

            self._log_event(
                "node_registered",
                config.id,
                f"Registered node {config.hostname} as {config.role.value}",
            )

            logger.info(f"Registered node: {config.id} ({config.hostname})")
            return config.id

    def deregister_node(self, node_id: str) -> bool:
        """Remove a node from the cluster."""
        with self._lock:
            if node_id not in self._nodes:
                return False

            config = self._nodes.pop(node_id)
            self._node_states.pop(node_id, None)

            # Remove from database
            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM cluster_nodes WHERE id = ?", (node_id,))

            self._log_event("node_deregistered", node_id, f"Deregistered node {config.hostname}")

            logger.info(f"Deregistered node: {node_id}")
            return True

    def get_node(self, node_id: str) -> Optional[NodeConfig]:
        """Get node configuration by ID."""
        return self._nodes.get(node_id)

    def get_node_state(self, node_id: str) -> Optional[NodeState]:
        """Get current state of a node."""
        return self._node_states.get(node_id)

    def get_all_nodes(self) -> List[NodeConfig]:
        """Get all registered nodes."""
        return list(self._nodes.values())

    def get_online_nodes(self) -> List[NodeConfig]:
        """Get all online nodes."""
        with self._lock:
            return [
                self._nodes[node_id]
                for node_id, state in self._node_states.items()
                if state.is_healthy() and node_id in self._nodes
            ]

    def get_nodes_by_role(self, role: NodeRole) -> List[NodeConfig]:
        """Get nodes with a specific role."""
        return [n for n in self._nodes.values() if n.role == role]

    def get_nodes_with_service(self, service_name: str) -> List[NodeConfig]:
        """Get nodes that can run a specific service."""
        return [n for n in self._nodes.values() if service_name in n.services]

    def update_node_state(self, node_id: str, **kwargs) -> None:
        """
        Update the runtime state of a node.

        Args:
            node_id: Node to update
            **kwargs: State fields to update
        """
        with self._lock:
            state = self._node_states.get(node_id)
            if not state:
                return

            old_status = state.status

            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)

            state.last_heartbeat = time.time()

            # Check for status change
            if "status" in kwargs and kwargs["status"] != old_status:
                new_status = kwargs["status"]
                if new_status == NodeStatus.ONLINE:
                    for callback in self._on_node_online:
                        try:
                            callback(node_id)
                        except Exception as e:
                            logger.error(f"Online callback error: {e}")
                elif new_status == NodeStatus.OFFLINE:
                    for callback in self._on_node_offline:
                        try:
                            callback(node_id)
                        except Exception as e:
                            logger.error(f"Offline callback error: {e}")

            # Update database
            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    UPDATE cluster_nodes
                    SET status = ?, last_heartbeat = ?, cpu_usage = ?,
                        memory_usage = ?, disk_usage = ?
                    WHERE id = ?
                """,
                    (
                        state.status.value,
                        datetime.now().isoformat(),
                        state.cpu_usage,
                        state.memory_usage,
                        state.disk_usage,
                        node_id,
                    ),
                )

    def heartbeat(self, node_id: str, metrics: Dict[str, Any] = None) -> bool:
        """
        Process a heartbeat from a node.

        Args:
            node_id: Node sending heartbeat
            metrics: Optional resource metrics

        Returns:
            True if heartbeat accepted
        """
        with self._lock:
            if node_id not in self._nodes:
                return False

            state = self._node_states.get(node_id)
            if not state:
                return False

            # Update state from metrics
            if metrics:
                state.cpu_usage = metrics.get("cpu_usage", state.cpu_usage)
                state.memory_usage = metrics.get("memory_usage", state.memory_usage)
                state.disk_usage = metrics.get("disk_usage", state.disk_usage)
                state.memory_mb = metrics.get("memory_mb", state.memory_mb)
                state.disk_free_mb = metrics.get("disk_free_mb", state.disk_free_mb)
                state.cpu_cores = metrics.get("cpu_cores", state.cpu_cores)
                state.load_average = metrics.get("load_average", state.load_average)
                state.active_services = metrics.get("active_services", state.active_services)

            state.last_heartbeat = time.time()

            # Mark online if was offline
            if state.status != NodeStatus.ONLINE:
                state.status = NodeStatus.ONLINE
                self._log_event("node_online", node_id, "Node came online")
                for callback in self._on_node_online:
                    try:
                        callback(node_id)
                    except Exception as e:
                        logger.error(f"Online callback error: {e}")

            return True

    def allocate_resource(
        self,
        resource_type: str,
        requester: str,
        preferred_node: str = None,
        priority: str = "normal",
    ) -> Optional[ResourceAllocation]:
        """
        Allocate a shared resource.

        Args:
            resource_type: Type of resource (e.g., "ollama", "gpu")
            requester: Who is requesting the resource
            preferred_node: Preferred node for allocation
            priority: Request priority

        Returns:
            ResourceAllocation if successful, None otherwise
        """
        with self._lock:
            # Find suitable node
            target_node = None

            if preferred_node and preferred_node in self._nodes:
                state = self._node_states.get(preferred_node)
                if state and state.is_healthy():
                    target_node = preferred_node

            if not target_node:
                # Find least loaded node with the resource
                candidates = []
                for node_id, config in self._nodes.items():
                    state = self._node_states.get(node_id)
                    if state and state.is_healthy():
                        # Check if node has the resource
                        if resource_type in config.services or config.has_gpu:
                            candidates.append((node_id, state.cpu_usage + state.memory_usage))

                if candidates:
                    # Sort by load (lowest first)
                    candidates.sort(key=lambda x: x[1])
                    target_node = candidates[0][0]

            if not target_node:
                logger.warning(f"No suitable node for resource {resource_type}")
                return None

            # Create allocation
            allocation = ResourceAllocation(
                id=str(uuid.uuid4()),
                resource_type=resource_type,
                requester=requester,
                node_id=target_node,
                allocated_at=time.time(),
                priority=priority,
            )

            self._allocations[allocation.id] = allocation

            # Persist
            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO resource_allocations
                    (id, resource_type, requester, node_id, priority)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (allocation.id, resource_type, requester, target_node, priority),
                )

            self._log_event(
                "resource_allocated", target_node, f"Allocated {resource_type} to {requester}"
            )

            logger.info(f"Allocated {resource_type} on {target_node} for {requester}")
            return allocation

    def release_resource(self, allocation_id: str) -> bool:
        """Release a resource allocation."""
        with self._lock:
            allocation = self._allocations.get(allocation_id)
            if not allocation:
                return False

            allocation.released_at = time.time()

            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    UPDATE resource_allocations
                    SET released_at = ?
                    WHERE id = ?
                """,
                    (datetime.now().isoformat(), allocation_id),
                )

            self._log_event(
                "resource_released",
                allocation.node_id,
                f"Released {allocation.resource_type} from {allocation.requester}",
            )

            logger.info(f"Released allocation {allocation_id}")
            return True

    def get_active_allocations(
        self, resource_type: str = None, node_id: str = None
    ) -> List[ResourceAllocation]:
        """Get active resource allocations."""
        with self._lock:
            allocations = [a for a in self._allocations.values() if a.released_at is None]

            if resource_type:
                allocations = [a for a in allocations if a.resource_type == resource_type]

            if node_id:
                allocations = [a for a in allocations if a.node_id == node_id]

            return allocations

    def _check_heartbeats(self) -> None:
        """Check for missed heartbeats and mark nodes offline."""
        cutoff = time.time() - (self.heartbeat_interval * self.failure_threshold)

        with self._lock:
            for node_id, state in self._node_states.items():
                if state.status == NodeStatus.ONLINE and state.last_heartbeat < cutoff:
                    state.status = NodeStatus.OFFLINE
                    state.error_message = "Missed heartbeats"

                    self._log_event("node_offline", node_id, "Node missed heartbeat threshold")

                    logger.warning(f"Node {node_id} marked offline (missed heartbeats)")

                    for callback in self._on_node_offline:
                        try:
                            callback(node_id)
                        except Exception as e:
                            logger.error(f"Offline callback error: {e}")

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitor_running:
            try:
                self._check_heartbeats()
            except Exception as e:
                logger.error(f"Monitor error: {e}")

            # Sleep in small increments for responsive shutdown
            for _ in range(self.heartbeat_interval):
                if not self._monitor_running:
                    break
                time.sleep(1)

    def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self._monitor_running:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="ResourceManager-Monitor"
        )
        self._monitor_thread.start()
        logger.info("Started resource monitoring")

    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
            logger.info("Stopped resource monitoring")

    def on_node_offline(self, callback: Callable[[str], None]) -> None:
        """Register callback for node offline events."""
        self._on_node_offline.append(callback)

    def on_node_online(self, callback: Callable[[str], None]) -> None:
        """Register callback for node online events."""
        self._on_node_online.append(callback)

    def on_failover(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for failover events (from_node, to_node)."""
        self._on_failover.append(callback)

    def trigger_failover(self, from_node: str, to_node: str = None) -> Optional[str]:
        """
        Trigger failover from one node to another.

        Args:
            from_node: Node to failover from
            to_node: Target node (auto-select if None)

        Returns:
            Target node ID if successful
        """
        with self._lock:
            if from_node not in self._nodes:
                return None

            from_config = self._nodes[from_node]

            # Find target node
            if not to_node:
                # Find a healthy node with same role or worker
                candidates = []
                for node_id, config in self._nodes.items():
                    if node_id == from_node:
                        continue
                    state = self._node_states.get(node_id)
                    if state and state.is_healthy():
                        # Prefer same role, then workers
                        priority = 0 if config.role == from_config.role else 1
                        candidates.append((node_id, priority, state.cpu_usage))

                if candidates:
                    candidates.sort(key=lambda x: (x[1], x[2]))
                    to_node = candidates[0][0]

            if not to_node:
                logger.error(f"No failover target available for {from_node}")
                return None

            self._log_event("failover", from_node, f"Failover from {from_node} to {to_node}")

            logger.info(f"Triggering failover from {from_node} to {to_node}")

            for callback in self._on_failover:
                try:
                    callback(from_node, to_node)
                except Exception as e:
                    logger.error(f"Failover callback error: {e}")

            return to_node

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get full cluster status."""
        with self._lock:
            nodes = []
            for node_id, config in self._nodes.items():
                state = self._node_states.get(node_id, NodeState(node_id=node_id))
                nodes.append(
                    {
                        "id": node_id,
                        "hostname": config.hostname,
                        "ip_address": config.ip_address,
                        "role": config.role.value,
                        "status": state.status.value,
                        "cpu_usage": state.cpu_usage,
                        "memory_usage": state.memory_usage,
                        "disk_usage": state.disk_usage,
                        "services": config.services,
                        "active_services": state.active_services,
                        "last_heartbeat": state.last_heartbeat,
                        "is_healthy": state.is_healthy(),
                        "is_overloaded": state.is_overloaded(config.cpu_limit, config.memory_limit),
                    }
                )

            online_count = sum(1 for n in nodes if n["is_healthy"])
            overloaded_count = sum(1 for n in nodes if n["is_overloaded"])

            return {
                "cluster_name": self.cluster_name,
                "total_nodes": len(nodes),
                "online_nodes": online_count,
                "offline_nodes": len(nodes) - online_count,
                "overloaded_nodes": overloaded_count,
                "nodes": nodes,
                "active_allocations": len(
                    [a for a in self._allocations.values() if a.released_at is None]
                ),
                "timestamp": time.time(),
            }

    def load_from_database(self) -> None:
        """Load nodes from database."""
        try:
            with self._get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM cluster_nodes").fetchall()

                for row in rows:
                    config = NodeConfig(
                        id=row["id"],
                        hostname=row["hostname"],
                        ip_address=row["ip_address"],
                        ssh_port=row["ssh_port"],
                        ssh_user=row["ssh_user"],
                        ssh_key_file=row["ssh_key_file"],
                        role=NodeRole(row["role"]),
                        services=json.loads(row["services"] or "[]"),
                        cpu_limit=row["cpu_limit"],
                        memory_limit=row["memory_limit"],
                        has_gpu=bool(row["has_gpu"]),
                    )
                    self._nodes[config.id] = config
                    self._node_states[config.id] = NodeState(
                        node_id=config.id,
                        status=NodeStatus(row["status"]) if row["status"] else NodeStatus.OFFLINE,
                        cpu_usage=row["cpu_usage"] or 0,
                        memory_usage=row["memory_usage"] or 0,
                        disk_usage=row["disk_usage"] or 0,
                    )

                logger.info(f"Loaded {len(rows)} nodes from database")
        except Exception as e:
            logger.error(f"Failed to load from database: {e}")


# Global manager instance
_manager: Optional[ResourceManager] = None


def get_manager() -> ResourceManager:
    """Get or create the global resource manager."""
    global _manager
    if _manager is None:
        _manager = ResourceManager()
    return _manager
