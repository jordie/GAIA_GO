"""
Worker Load Balancer Service

Distributes tasks across workers based on current load, capacity, and capabilities.

Features:
- Multiple load balancing strategies (least-loaded, round-robin, weighted, skill-based)
- Real-time worker load tracking
- Configurable worker capacity limits
- Health-aware routing (avoids unhealthy workers)
- Task affinity support (prefer workers with relevant experience)
- Load metrics and analytics

Usage:
    from services.load_balancer import LoadBalancer, LoadBalancingStrategy

    # Create load balancer
    lb = LoadBalancer(db_path)

    # Find best worker for a task
    worker = lb.select_worker(task_type='shell', strategy=LoadBalancingStrategy.LEAST_LOADED)

    # Get load distribution
    distribution = lb.get_load_distribution()
"""

import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Available load balancing strategies."""

    ROUND_ROBIN = "round_robin"  # Simple rotation through workers
    LEAST_LOADED = "least_loaded"  # Prefer worker with fewest tasks
    WEIGHTED = "weighted"  # Consider worker capacity weights
    SKILL_BASED = "skill_based"  # Match worker skills to task
    LEAST_CONNECTIONS = "least_connections"  # Prefer worker with fewest active connections
    ADAPTIVE = "adaptive"  # Combine multiple factors dynamically


@dataclass
class WorkerLoad:
    """Current load information for a worker."""

    worker_id: str
    worker_type: str
    node_id: str
    status: str
    current_tasks: int = 0
    pending_tasks: int = 0
    completed_today: int = 0
    failed_today: int = 0
    capacity: int = 10  # Max concurrent tasks
    weight: float = 1.0  # Load balancing weight (higher = more tasks)
    last_task_assigned: Optional[str] = None
    last_heartbeat: Optional[str] = None
    avg_task_duration_ms: float = 0.0
    success_rate: float = 100.0
    is_healthy: bool = True
    is_draining: bool = False  # True if worker is shutting down

    @property
    def load_percentage(self) -> float:
        """Calculate current load as percentage of capacity."""
        if self.capacity <= 0:
            return 100.0
        return min(100.0, (self.current_tasks / self.capacity) * 100)

    @property
    def available_capacity(self) -> int:
        """Calculate remaining capacity."""
        return max(0, self.capacity - self.current_tasks)

    @property
    def effective_weight(self) -> float:
        """Calculate effective weight considering health and drain status."""
        if not self.is_healthy or self.is_draining:
            return 0.0
        # Reduce weight based on load
        load_factor = 1.0 - (self.load_percentage / 100.0)
        return self.weight * load_factor * (self.success_rate / 100.0)


@dataclass
class LoadDistribution:
    """Load distribution across all workers."""

    total_workers: int = 0
    healthy_workers: int = 0
    total_capacity: int = 0
    total_current_tasks: int = 0
    avg_load_percentage: float = 0.0
    max_load_percentage: float = 0.0
    min_load_percentage: float = 0.0
    workers: List[Dict] = field(default_factory=list)
    by_node: Dict[str, Dict] = field(default_factory=dict)
    by_type: Dict[str, Dict] = field(default_factory=dict)
    imbalance_score: float = 0.0  # 0 = perfect balance, 100 = completely imbalanced
    recommendations: List[str] = field(default_factory=list)


@dataclass
class WorkerSelection:
    """Result of worker selection."""

    worker_id: Optional[str] = None
    worker_type: Optional[str] = None
    node_id: Optional[str] = None
    strategy_used: str = ""
    score: float = 0.0
    reason: str = ""
    alternatives: List[Dict] = field(default_factory=list)
    load_before: float = 0.0
    estimated_load_after: float = 0.0


class LoadBalancer:
    """
    Worker load balancer for distributing tasks based on current load.
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "default_strategy": LoadBalancingStrategy.ADAPTIVE.value,
        "default_capacity": 10,
        "health_check_interval": 60,  # seconds
        "heartbeat_timeout": 120,  # seconds before marking unhealthy
        "min_success_rate": 50.0,  # minimum success rate to be considered healthy
        "load_threshold_warning": 70.0,  # warn when load exceeds this
        "load_threshold_critical": 90.0,  # critical when load exceeds this
        "skill_weight": 0.3,  # weight of skill match in adaptive strategy
        "load_weight": 0.5,  # weight of current load in adaptive strategy
        "success_weight": 0.2,  # weight of success rate in adaptive strategy
        "round_robin_index": 0,
    }

    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._round_robin_index = self.config["round_robin_index"]
        self._lock = threading.Lock()
        self._worker_cache: Dict[str, WorkerLoad] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 5.0  # Cache TTL in seconds

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Worker Load Tracking
    # =========================================================================

    def get_worker_load(self, worker_id: str, conn=None) -> Optional[WorkerLoad]:
        """Get current load information for a specific worker."""
        close_conn = conn is None
        if conn is None:
            conn = self._get_connection()

        try:
            # Get worker info
            worker = conn.execute(
                """
                SELECT id, worker_type, node_id, status, last_heartbeat
                FROM workers
                WHERE id = ?
            """,
                (worker_id,),
            ).fetchone()

            if not worker:
                return None

            # Get current task counts
            task_counts = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
                    COUNT(CASE WHEN status = 'pending' AND assigned_worker = ? THEN 1 END) as pending
                FROM task_queue
                WHERE assigned_worker = ?
            """,
                (worker_id, worker_id),
            ).fetchone()

            # Get today's stats
            today_stats = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
                FROM task_queue
                WHERE assigned_worker = ?
                  AND completed_at >= date('now')
            """,
                (worker_id,),
            ).fetchone()

            # Get average task duration and success rate
            perf_stats = conn.execute(
                """
                SELECT
                    AVG(CAST((julianday(completed_at) - julianday(started_at)) * 86400000 AS INTEGER)) as avg_duration_ms,
                    CAST(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS FLOAT) /
                        NULLIF(COUNT(*), 0) * 100 as success_rate
                FROM task_queue
                WHERE assigned_worker = ?
                  AND status IN ('completed', 'failed')
                  AND completed_at >= datetime('now', '-7 days')
            """,
                (worker_id,),
            ).fetchone()

            # Get worker capacity from config (or use default)
            capacity = conn.execute(
                """
                SELECT value FROM worker_config
                WHERE worker_id = ? AND key = 'capacity'
            """,
                (worker_id,),
            ).fetchone()

            # Get worker weight
            weight = conn.execute(
                """
                SELECT value FROM worker_config
                WHERE worker_id = ? AND key = 'weight'
            """,
                (worker_id,),
            ).fetchone()

            # Determine health status
            last_heartbeat = worker["last_heartbeat"]
            is_healthy = True
            is_draining = worker["status"] in ("draining", "shutting_down")

            if last_heartbeat:
                try:
                    hb_time = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                    age = (datetime.now() - hb_time.replace(tzinfo=None)).total_seconds()
                    if age > self.config["heartbeat_timeout"]:
                        is_healthy = False
                except:
                    pass

            success_rate = perf_stats["success_rate"] if perf_stats["success_rate"] else 100.0
            if success_rate < self.config["min_success_rate"]:
                is_healthy = False

            return WorkerLoad(
                worker_id=worker["id"],
                worker_type=worker["worker_type"],
                node_id=worker["node_id"],
                status=worker["status"],
                current_tasks=task_counts["running"] or 0,
                pending_tasks=task_counts["pending"] or 0,
                completed_today=today_stats["completed"] or 0,
                failed_today=today_stats["failed"] or 0,
                capacity=int(capacity["value"]) if capacity else self.config["default_capacity"],
                weight=float(weight["value"]) if weight else 1.0,
                last_heartbeat=last_heartbeat,
                avg_task_duration_ms=perf_stats["avg_duration_ms"] or 0.0,
                success_rate=success_rate,
                is_healthy=is_healthy,
                is_draining=is_draining,
            )

        finally:
            if close_conn:
                conn.close()

    def get_all_worker_loads(
        self, include_unhealthy: bool = False, worker_type: str = None
    ) -> List[WorkerLoad]:
        """Get load information for all workers."""
        conn = self._get_connection()
        try:
            query = "SELECT id FROM workers WHERE 1=1"
            params = []

            if not include_unhealthy:
                query += " AND status IN ('idle', 'busy', 'active')"

            if worker_type:
                query += " AND worker_type = ?"
                params.append(worker_type)

            workers = conn.execute(query, params).fetchall()

            loads = []
            for w in workers:
                load = self.get_worker_load(w["id"], conn)
                if load:
                    if include_unhealthy or load.is_healthy:
                        loads.append(load)

            return loads
        finally:
            conn.close()

    # =========================================================================
    # Load Balancing Strategies
    # =========================================================================

    def _select_round_robin(self, workers: List[WorkerLoad]) -> Optional[WorkerLoad]:
        """Simple round-robin selection."""
        available = [w for w in workers if w.available_capacity > 0 and w.is_healthy]
        if not available:
            return None

        with self._lock:
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            return available[self._round_robin_index]

    def _select_least_loaded(self, workers: List[WorkerLoad]) -> Optional[WorkerLoad]:
        """Select worker with lowest current load."""
        available = [w for w in workers if w.available_capacity > 0 and w.is_healthy]
        if not available:
            return None

        # Sort by load percentage, then by current tasks
        return min(available, key=lambda w: (w.load_percentage, w.current_tasks))

    def _select_weighted(self, workers: List[WorkerLoad]) -> Optional[WorkerLoad]:
        """Select worker based on weighted capacity."""
        available = [w for w in workers if w.available_capacity > 0 and w.is_healthy]
        if not available:
            return None

        # Calculate weighted scores
        total_weight = sum(w.effective_weight for w in available)
        if total_weight == 0:
            return self._select_least_loaded(workers)

        # Select worker with highest effective weight
        return max(available, key=lambda w: w.effective_weight)

    def _select_skill_based(
        self, workers: List[WorkerLoad], task_type: str, conn
    ) -> Optional[WorkerLoad]:
        """Select worker based on skill matching."""
        from services.skill_matching import calculate_skill_match_score

        available = [w for w in workers if w.available_capacity > 0 and w.is_healthy]
        if not available:
            return None

        # Calculate skill scores
        scored_workers = []
        for worker in available:
            try:
                match = calculate_skill_match_score(worker.worker_id, task_type, conn)
                scored_workers.append((worker, match["score"]))
            except:
                scored_workers.append((worker, 50))  # Default score if matching fails

        # Select highest scoring worker
        if scored_workers:
            return max(scored_workers, key=lambda x: x[1])[0]

        return None

    def _select_adaptive(
        self, workers: List[WorkerLoad], task_type: str = None, conn=None
    ) -> Optional[WorkerLoad]:
        """Adaptive selection combining multiple factors."""
        available = [w for w in workers if w.available_capacity > 0 and w.is_healthy]
        if not available:
            return None

        scores = []
        for worker in available:
            # Load score (lower load = higher score)
            load_score = 100 - worker.load_percentage

            # Success rate score
            success_score = worker.success_rate

            # Skill score (if task_type provided)
            skill_score = 50  # default
            if task_type and conn:
                try:
                    from services.skill_matching import calculate_skill_match_score

                    match = calculate_skill_match_score(worker.worker_id, task_type, conn)
                    skill_score = match["score"]
                except:
                    pass

            # Calculate weighted total
            total_score = (
                load_score * self.config["load_weight"]
                + success_score * self.config["success_weight"]
                + skill_score * self.config["skill_weight"]
            )

            scores.append((worker, total_score))

        # Select highest scoring worker
        if scores:
            return max(scores, key=lambda x: x[1])[0]

        return None

    # =========================================================================
    # Main Selection Interface
    # =========================================================================

    def select_worker(
        self,
        task_type: str = None,
        strategy: LoadBalancingStrategy = None,
        worker_type: str = None,
        exclude_workers: List[str] = None,
        min_capacity: int = 1,
    ) -> WorkerSelection:
        """
        Select the best worker for a task based on the specified strategy.

        Args:
            task_type: Type of task to assign (for skill-based matching)
            strategy: Load balancing strategy to use
            worker_type: Filter by worker type
            exclude_workers: List of worker IDs to exclude
            min_capacity: Minimum available capacity required

        Returns:
            WorkerSelection with selected worker and metadata
        """
        strategy = strategy or LoadBalancingStrategy(self.config["default_strategy"])
        exclude_workers = exclude_workers or []

        conn = self._get_connection()
        try:
            # Get all available workers
            all_workers = self.get_all_worker_loads(
                include_unhealthy=False, worker_type=worker_type
            )

            # Filter workers
            workers = [
                w
                for w in all_workers
                if w.worker_id not in exclude_workers
                and w.available_capacity >= min_capacity
                and not w.is_draining
            ]

            if not workers:
                return WorkerSelection(
                    strategy_used=strategy.value,
                    reason="No workers available with sufficient capacity",
                )

            # Select based on strategy
            selected = None
            if strategy == LoadBalancingStrategy.ROUND_ROBIN:
                selected = self._select_round_robin(workers)
            elif strategy == LoadBalancingStrategy.LEAST_LOADED:
                selected = self._select_least_loaded(workers)
            elif strategy == LoadBalancingStrategy.WEIGHTED:
                selected = self._select_weighted(workers)
            elif strategy == LoadBalancingStrategy.SKILL_BASED:
                selected = self._select_skill_based(workers, task_type, conn)
            elif strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                selected = self._select_least_loaded(workers)  # Same as least_loaded
            elif strategy == LoadBalancingStrategy.ADAPTIVE:
                selected = self._select_adaptive(workers, task_type, conn)
            else:
                selected = self._select_least_loaded(workers)

            if not selected:
                return WorkerSelection(
                    strategy_used=strategy.value, reason="No suitable worker found"
                )

            # Build alternatives list
            alternatives = []
            for w in workers:
                if w.worker_id != selected.worker_id:
                    alternatives.append(
                        {
                            "worker_id": w.worker_id,
                            "load_percentage": w.load_percentage,
                            "available_capacity": w.available_capacity,
                        }
                    )
            alternatives.sort(key=lambda x: x["load_percentage"])

            return WorkerSelection(
                worker_id=selected.worker_id,
                worker_type=selected.worker_type,
                node_id=selected.node_id,
                strategy_used=strategy.value,
                score=selected.effective_weight,
                reason=f"Selected via {strategy.value}",
                alternatives=alternatives[:5],
                load_before=selected.load_percentage,
                estimated_load_after=((selected.current_tasks + 1) / selected.capacity) * 100,
            )

        finally:
            conn.close()

    # =========================================================================
    # Load Distribution Analysis
    # =========================================================================

    def get_load_distribution(self) -> LoadDistribution:
        """Get current load distribution across all workers."""
        workers = self.get_all_worker_loads(include_unhealthy=True)

        if not workers:
            return LoadDistribution()

        healthy_workers = [w for w in workers if w.is_healthy]

        total_capacity = sum(w.capacity for w in workers)
        total_current = sum(w.current_tasks for w in workers)

        load_percentages = [w.load_percentage for w in workers]
        avg_load = sum(load_percentages) / len(load_percentages) if load_percentages else 0

        # Calculate load by node
        by_node: Dict[str, Dict] = {}
        for w in workers:
            if w.node_id not in by_node:
                by_node[w.node_id] = {
                    "workers": 0,
                    "capacity": 0,
                    "current_tasks": 0,
                    "healthy": 0,
                    "avg_load": 0,
                }
            by_node[w.node_id]["workers"] += 1
            by_node[w.node_id]["capacity"] += w.capacity
            by_node[w.node_id]["current_tasks"] += w.current_tasks
            if w.is_healthy:
                by_node[w.node_id]["healthy"] += 1

        for node in by_node.values():
            if node["capacity"] > 0:
                node["avg_load"] = (node["current_tasks"] / node["capacity"]) * 100

        # Calculate load by type
        by_type: Dict[str, Dict] = {}
        for w in workers:
            if w.worker_type not in by_type:
                by_type[w.worker_type] = {
                    "workers": 0,
                    "capacity": 0,
                    "current_tasks": 0,
                    "healthy": 0,
                    "avg_load": 0,
                }
            by_type[w.worker_type]["workers"] += 1
            by_type[w.worker_type]["capacity"] += w.capacity
            by_type[w.worker_type]["current_tasks"] += w.current_tasks
            if w.is_healthy:
                by_type[w.worker_type]["healthy"] += 1

        for wtype in by_type.values():
            if wtype["capacity"] > 0:
                wtype["avg_load"] = (wtype["current_tasks"] / wtype["capacity"]) * 100

        # Calculate imbalance score (standard deviation of load percentages)
        if len(load_percentages) > 1:
            mean = avg_load
            variance = sum((x - mean) ** 2 for x in load_percentages) / len(load_percentages)
            imbalance = min(100, variance**0.5)  # Standard deviation, capped at 100
        else:
            imbalance = 0

        # Generate recommendations
        recommendations = []
        if imbalance > 30:
            recommendations.append(
                f"High load imbalance detected ({imbalance:.1f}). Consider rebalancing tasks."
            )

        overloaded = [
            w for w in workers if w.load_percentage > self.config["load_threshold_critical"]
        ]
        if overloaded:
            recommendations.append(
                f"{len(overloaded)} worker(s) are critically overloaded (>{self.config['load_threshold_critical']}%)"
            )

        underutilized = [w for w in healthy_workers if w.load_percentage < 10 and w.capacity > 0]
        if underutilized and overloaded:
            recommendations.append(
                f"{len(underutilized)} worker(s) are underutilized while others are overloaded"
            )

        unhealthy = len(workers) - len(healthy_workers)
        if unhealthy > 0:
            recommendations.append(f"{unhealthy} worker(s) are unhealthy")

        # Convert workers to dict and add computed properties
        workers_data = []
        for w in workers:
            w_dict = asdict(w)
            # Add computed properties that aren't included by asdict
            w_dict["load_percentage"] = w.load_percentage
            w_dict["available_capacity"] = w.available_capacity
            w_dict["effective_weight"] = w.effective_weight
            workers_data.append(w_dict)

        return LoadDistribution(
            total_workers=len(workers),
            healthy_workers=len(healthy_workers),
            total_capacity=total_capacity,
            total_current_tasks=total_current,
            avg_load_percentage=avg_load,
            max_load_percentage=max(load_percentages) if load_percentages else 0,
            min_load_percentage=min(load_percentages) if load_percentages else 0,
            workers=workers_data,
            by_node=by_node,
            by_type=by_type,
            imbalance_score=imbalance,
            recommendations=recommendations,
        )

    # =========================================================================
    # Worker Configuration
    # =========================================================================

    def set_worker_capacity(self, worker_id: str, capacity: int) -> bool:
        """Set the maximum capacity for a worker."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO worker_config (worker_id, key, value, updated_at)
                VALUES (?, 'capacity', ?, CURRENT_TIMESTAMP)
            """,
                (worker_id, str(capacity)),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set worker capacity: {e}")
            return False
        finally:
            conn.close()

    def set_worker_weight(self, worker_id: str, weight: float) -> bool:
        """Set the load balancing weight for a worker."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO worker_config (worker_id, key, value, updated_at)
                VALUES (?, 'weight', ?, CURRENT_TIMESTAMP)
            """,
                (worker_id, str(weight)),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set worker weight: {e}")
            return False
        finally:
            conn.close()

    def drain_worker(self, worker_id: str) -> bool:
        """Mark a worker as draining (no new tasks, finish current)."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE workers SET status = 'draining'
                WHERE id = ?
            """,
                (worker_id,),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to drain worker: {e}")
            return False
        finally:
            conn.close()

    def undrain_worker(self, worker_id: str) -> bool:
        """Remove draining status from a worker."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE workers SET status = 'idle'
                WHERE id = ? AND status = 'draining'
            """,
                (worker_id,),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to undrain worker: {e}")
            return False
        finally:
            conn.close()

    # =========================================================================
    # Task Rebalancing
    # =========================================================================

    def suggest_rebalance(self) -> List[Dict]:
        """
        Suggest task reassignments to better balance load.

        Returns list of suggested moves: {task_id, from_worker, to_worker, reason}
        """
        conn = self._get_connection()
        suggestions = []

        try:
            distribution = self.get_load_distribution()
            if distribution.imbalance_score < 20:
                return []  # Already well balanced

            # Find overloaded and underutilized workers
            overloaded = [
                w
                for w in distribution.workers
                if w["load_percentage"] > self.config["load_threshold_warning"] and w["is_healthy"]
            ]
            underutilized = [
                w
                for w in distribution.workers
                if w["load_percentage"] < 30 and w["is_healthy"] and w["available_capacity"] > 0
            ]

            if not overloaded or not underutilized:
                return []

            # For each overloaded worker, find tasks to move
            for worker in overloaded:
                # Get pending (not started) tasks for this worker
                tasks = conn.execute(
                    """
                    SELECT id, task_type, priority
                    FROM task_queue
                    WHERE assigned_worker = ?
                      AND status = 'pending'
                    ORDER BY priority ASC
                    LIMIT 5
                """,
                    (worker["worker_id"],),
                ).fetchall()

                for task in tasks:
                    # Find best target worker
                    for target in underutilized:
                        if target["worker_id"] != worker["worker_id"]:
                            suggestions.append(
                                {
                                    "task_id": task["id"],
                                    "task_type": task["task_type"],
                                    "from_worker": worker["worker_id"],
                                    "to_worker": target["worker_id"],
                                    "from_load": worker["load_percentage"],
                                    "to_load": target["load_percentage"],
                                    "reason": f"Rebalance from {worker['load_percentage']:.0f}% to {target['load_percentage']:.0f}%",
                                }
                            )
                            break

        finally:
            conn.close()

        return suggestions[:10]  # Limit suggestions

    def execute_rebalance(self, task_id: int, to_worker: str) -> bool:
        """Move a task from one worker to another."""
        conn = self._get_connection()
        try:
            # Only move pending tasks
            result = conn.execute(
                """
                UPDATE task_queue
                SET assigned_worker = ?
                WHERE id = ? AND status = 'pending'
            """,
                (to_worker, task_id),
            )

            if result.rowcount > 0:
                conn.commit()
                logger.info(f"Rebalanced task {task_id} to worker {to_worker}")
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to rebalance task: {e}")
            return False
        finally:
            conn.close()


# =============================================================================
# Database Schema
# =============================================================================

LOAD_BALANCER_SCHEMA = """
-- Worker configuration table
CREATE TABLE IF NOT EXISTS worker_config (
    id INTEGER PRIMARY KEY,
    worker_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, key)
);

CREATE INDEX IF NOT EXISTS idx_worker_config_worker ON worker_config(worker_id);
"""


def init_load_balancer_schema(db_path: str):
    """Initialize load balancer database schema."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(LOAD_BALANCER_SCHEMA)
        conn.commit()
        logger.info("Load balancer schema initialized")
    finally:
        conn.close()


# =============================================================================
# Convenience Functions
# =============================================================================


def get_load_balancer(db_path: str = None) -> LoadBalancer:
    """Get a load balancer instance."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent / "data" / "architect.db")
    return LoadBalancer(db_path)


def select_worker_for_task(
    task_type: str, db_path: str = None, strategy: str = "adaptive"
) -> Optional[str]:
    """Convenience function to select a worker for a task."""
    lb = get_load_balancer(db_path)
    result = lb.select_worker(task_type=task_type, strategy=LoadBalancingStrategy(strategy))
    return result.worker_id
