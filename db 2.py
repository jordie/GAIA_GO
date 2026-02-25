"""
Centralized Database Access Module

This module provides a unified interface for database operations with connection pooling.
Currently supports SQLite, but designed to easily switch to PostgreSQL/MySQL.

Features:
    - Connection pooling for improved performance
    - Thread-safe connection management
    - Automatic connection health checks
    - Configurable pool sizes and timeouts
    - Connection statistics and monitoring

Usage:
    from db import get_connection, Database, get_pool_stats

    # Simple usage with pooled connection
    with get_connection() as conn:
        conn.execute("SELECT * FROM projects")

    # With specific database
    with get_connection(db_type='delegator') as conn:
        conn.execute("SELECT * FROM tasks")

    # Using Database class for more control
    db = Database()
    result = db.query("SELECT * FROM projects WHERE id = ?", (1,))
    db.execute("UPDATE projects SET name = ? WHERE id = ?", ("New Name", 1))

    # Get pool statistics
    stats = get_pool_stats()
    print(f"Active connections: {stats['active']}, Available: {stats['available']}")
"""

import atexit
import logging
import os
import queue
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "type": "sqlite",  # Future: 'postgresql', 'mysql'
    "timeout": 30.0,
    "retry_count": 3,
    "retry_delay": 0.5,
    "pragmas": {
        "journal_mode": "WAL",
        "busy_timeout": 30000,
        "cache_size": -64000,  # 64MB cache
        "synchronous": "NORMAL",
    },
}

# Connection pool configuration
POOL_CONFIG = {
    "min_connections": 2,  # Minimum connections to maintain
    "max_connections": 10,  # Maximum connections allowed
    "max_overflow": 5,  # Extra connections when pool exhausted
    "pool_timeout": 30.0,  # Seconds to wait for available connection
    "recycle_time": 3600,  # Recycle connections after 1 hour
    "health_check_interval": 60,  # Seconds between health checks
    "enabled": True,  # Enable/disable pooling
}

# Base paths
BASE_DIR = Path(__file__).parent
APP_ENV = os.environ.get("APP_ENV", "prod")
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data" / APP_ENV)))

# Database paths - centralized location for all database files
DB_PATHS = {
    "main": DATA_DIR / "architect.db",
    "delegator": BASE_DIR / "data" / "task_delegator.db",
    "command_log": BASE_DIR / "data" / "command_log.db",
    "response_log": BASE_DIR / "data" / "response_log.db",
    "assigner": BASE_DIR / "data" / "assigner" / "assigner.db",
}

# Thread-local storage for connections
_local = threading.local()

# Global pool registry
_pools: Dict[str, "ConnectionPool"] = {}
_pools_lock = threading.Lock()


@dataclass
class PooledConnection:
    """Wrapper for a pooled database connection."""

    connection: sqlite3.Connection
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    is_valid: bool = True

    def touch(self):
        """Update last used timestamp and increment use count."""
        self.last_used = time.time()
        self.use_count += 1

    def is_expired(self, recycle_time: float) -> bool:
        """Check if connection should be recycled."""
        return (time.time() - self.created_at) > recycle_time

    def is_healthy(self) -> bool:
        """Check if connection is still usable."""
        if not self.is_valid:
            return False
        try:
            self.connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            self.is_valid = False
            return False


class ConnectionPool:
    """
    Thread-safe connection pool for SQLite databases.

    Features:
        - Maintains a pool of reusable connections
        - Automatic connection recycling
        - Health checking
        - Overflow handling for burst traffic
        - Statistics tracking

    Example:
        pool = ConnectionPool('/path/to/db.sqlite')

        with pool.get_connection() as conn:
            conn.execute("SELECT * FROM table")

        # Check pool stats
        stats = pool.get_stats()
    """

    def __init__(
        self,
        db_path: Path,
        min_connections: int = None,
        max_connections: int = None,
        max_overflow: int = None,
        pool_timeout: float = None,
        recycle_time: float = None,
        timeout: float = None,
    ):
        self.db_path = Path(db_path)
        self.min_connections = min_connections or POOL_CONFIG["min_connections"]
        self.max_connections = max_connections or POOL_CONFIG["max_connections"]
        self.max_overflow = max_overflow or POOL_CONFIG["max_overflow"]
        self.pool_timeout = pool_timeout or POOL_CONFIG["pool_timeout"]
        self.recycle_time = recycle_time or POOL_CONFIG["recycle_time"]
        self.timeout = timeout or DB_CONFIG["timeout"]

        # Pool state
        self._pool: queue.Queue[PooledConnection] = queue.Queue(maxsize=self.max_connections)
        self._lock = threading.Lock()
        self._active_count = 0
        self._overflow_count = 0
        self._closed = False

        # Statistics
        self._stats = {
            "created": 0,
            "reused": 0,
            "recycled": 0,
            "failed": 0,
            "overflow_used": 0,
            "timeout_errors": 0,
            "health_checks": 0,
            "health_failures": 0,
        }

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-populate pool with minimum connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Create initial pool connections."""
        for _ in range(self.min_connections):
            try:
                pooled = self._create_pooled_connection()
                self._pool.put_nowait(pooled)
            except sqlite3.Error as e:
                logger.warning(f"Failed to create initial connection: {e}")

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new raw database connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        _apply_pragmas(conn)
        return conn

    def _create_pooled_connection(self) -> PooledConnection:
        """Create a new pooled connection wrapper."""
        conn = self._create_connection()
        self._stats["created"] += 1
        return PooledConnection(connection=conn)

    def _get_from_pool(self) -> Optional[PooledConnection]:
        """Try to get a connection from the pool."""
        try:
            pooled = self._pool.get_nowait()
            # Check if connection needs recycling
            if pooled.is_expired(self.recycle_time):
                self._close_pooled(pooled)
                self._stats["recycled"] += 1
                return None
            # Health check
            if not pooled.is_healthy():
                self._close_pooled(pooled)
                self._stats["health_failures"] += 1
                return None
            return pooled
        except queue.Empty:
            return None

    def _close_pooled(self, pooled: PooledConnection):
        """Close a pooled connection."""
        try:
            pooled.is_valid = False
            pooled.connection.close()
        except Exception:
            pass

    def acquire(self) -> PooledConnection:
        """
        Acquire a connection from the pool.

        Returns:
            PooledConnection ready for use

        Raises:
            TimeoutError: If no connection available within timeout
            sqlite3.Error: If connection creation fails
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        deadline = time.time() + self.pool_timeout

        while True:
            # Try to get from pool
            pooled = self._get_from_pool()
            if pooled:
                with self._lock:
                    self._active_count += 1
                pooled.touch()
                self._stats["reused"] += 1
                return pooled

            # Try to create new connection
            with self._lock:
                total = self._active_count + self._pool.qsize()
                can_create = total < self.max_connections
                can_overflow = not can_create and self._overflow_count < self.max_overflow

                if can_create:
                    try:
                        pooled = self._create_pooled_connection()
                        self._active_count += 1
                        pooled.touch()
                        return pooled
                    except sqlite3.Error as e:
                        self._stats["failed"] += 1
                        raise

                if can_overflow:
                    try:
                        pooled = self._create_pooled_connection()
                        self._overflow_count += 1
                        self._stats["overflow_used"] += 1
                        pooled.touch()
                        return pooled
                    except sqlite3.Error as e:
                        self._stats["failed"] += 1
                        raise

            # Wait for available connection
            remaining = deadline - time.time()
            if remaining <= 0:
                self._stats["timeout_errors"] += 1
                raise TimeoutError(
                    f"Could not acquire connection within {self.pool_timeout}s. "
                    f"Pool stats: active={self._active_count}, "
                    f"available={self._pool.qsize()}, overflow={self._overflow_count}"
                )

            # Brief sleep before retry
            time.sleep(min(0.1, remaining))

    def release(self, pooled: PooledConnection, discard: bool = False):
        """
        Return a connection to the pool.

        Args:
            pooled: The pooled connection to release
            discard: If True, close connection instead of returning to pool
        """
        with self._lock:
            self._active_count = max(0, self._active_count - 1)

            # Check if this was an overflow connection
            total_in_pool = self._pool.qsize()
            if total_in_pool >= self.max_connections or self._overflow_count > 0:
                self._overflow_count = max(0, self._overflow_count - 1)
                discard = True

        if discard or not pooled.is_valid:
            self._close_pooled(pooled)
            return

        # Return to pool if not expired
        if pooled.is_expired(self.recycle_time):
            self._close_pooled(pooled)
            self._stats["recycled"] += 1
            return

        try:
            self._pool.put_nowait(pooled)
        except queue.Full:
            self._close_pooled(pooled)

    @contextmanager
    def get_connection(self):
        """
        Context manager for acquiring a pooled connection.

        Yields:
            sqlite3.Connection ready for use

        Example:
            with pool.get_connection() as conn:
                conn.execute("SELECT * FROM table")
        """
        pooled = self.acquire()
        try:
            yield pooled.connection
            pooled.connection.commit()
        except Exception:
            try:
                pooled.connection.rollback()
            except Exception:
                pooled.is_valid = False
            raise
        finally:
            self.release(pooled)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "db_path": str(self.db_path),
            "active": self._active_count,
            "available": self._pool.qsize(),
            "overflow": self._overflow_count,
            "max_connections": self.max_connections,
            "max_overflow": self.max_overflow,
            **self._stats,
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all pooled connections.

        Returns:
            Dict with health check results
        """
        self._stats["health_checks"] += 1
        healthy = 0
        unhealthy = 0
        recycled = 0

        # Check connections in pool
        checked = []
        while True:
            try:
                pooled = self._pool.get_nowait()
            except queue.Empty:
                break

            if pooled.is_expired(self.recycle_time):
                self._close_pooled(pooled)
                recycled += 1
            elif pooled.is_healthy():
                checked.append(pooled)
                healthy += 1
            else:
                self._close_pooled(pooled)
                unhealthy += 1

        # Return healthy connections to pool
        for pooled in checked:
            try:
                self._pool.put_nowait(pooled)
            except queue.Full:
                self._close_pooled(pooled)

        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "recycled": recycled,
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        """Close all connections and shutdown the pool."""
        self._closed = True

        # Close all pooled connections
        while True:
            try:
                pooled = self._pool.get_nowait()
                self._close_pooled(pooled)
            except queue.Empty:
                break

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass


def get_pool(db_type: str = "main") -> ConnectionPool:
    """
    Get or create a connection pool for the specified database.

    Args:
        db_type: Type of database ('main', 'delegator', etc.)

    Returns:
        ConnectionPool instance
    """
    if not POOL_CONFIG["enabled"]:
        return None

    with _pools_lock:
        if db_type not in _pools:
            db_path = get_db_path(db_type)
            _pools[db_type] = ConnectionPool(db_path)
        return _pools[db_type]


def close_all_pools():
    """Close all connection pools. Call at application shutdown."""
    with _pools_lock:
        for pool in _pools.values():
            try:
                pool.close()
            except Exception as e:
                logger.warning(f"Error closing pool: {e}")
        _pools.clear()


# Register cleanup on exit
atexit.register(close_all_pools)


def get_db_path(db_type: str = "main") -> Path:
    """Get the path for a specific database type."""
    if db_type in DB_PATHS:
        return DB_PATHS[db_type]
    # Allow custom paths
    return Path(db_type)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply SQLite pragmas for better performance."""
    for pragma, value in DB_CONFIG["pragmas"].items():
        try:
            conn.execute(f"PRAGMA {pragma}={value}")
        except sqlite3.Error:
            pass  # Some pragmas may not be supported


def _create_connection(db_path: Path, timeout: float = None) -> sqlite3.Connection:
    """Create a new database connection with proper settings."""
    if timeout is None:
        timeout = DB_CONFIG["timeout"]

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)

    return conn


@contextmanager
def get_connection(db_type: str = "main", timeout: float = None, use_pool: bool = True):
    """
    Get a database connection as a context manager.

    Uses connection pooling by default for improved performance.

    Args:
        db_type: Type of database ('main', 'delegator', 'command_log', etc.)
                 or a path string for custom databases
        timeout: Connection timeout in seconds
        use_pool: Whether to use connection pooling (default: True)

    Yields:
        sqlite3.Connection with row_factory set to sqlite3.Row

    Example:
        with get_connection() as conn:
            result = conn.execute("SELECT * FROM projects").fetchall()

        # Without pooling (for long-running operations)
        with get_connection(use_pool=False) as conn:
            # ... long operation
    """
    # Use pool for known database types when enabled
    if use_pool and POOL_CONFIG["enabled"] and db_type in DB_PATHS:
        pool = get_pool(db_type)
        if pool:
            with pool.get_connection() as conn:
                yield conn
            return

    # Fall back to direct connection
    db_path = get_db_path(db_type)
    conn = _create_connection(db_path, timeout)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_with_retry(func, max_retries: int = None, delay: float = None):
    """
    Execute a database function with retry logic for locked database.

    Args:
        func: Function that takes a connection and performs database operations
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        Result of the function call
    """
    if max_retries is None:
        max_retries = DB_CONFIG["retry_count"]
    if delay is None:
        delay = DB_CONFIG["retry_delay"]

    last_error = None
    for attempt in range(max_retries):
        try:
            with get_connection() as conn:
                return func(conn)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                continue
            raise

    if last_error:
        raise last_error


class Database:
    """
    High-level database interface with query and execute methods.

    Example:
        db = Database()

        # Query with automatic connection handling
        projects = db.query("SELECT * FROM projects WHERE status = ?", ('active',))

        # Execute with automatic commit
        db.execute("INSERT INTO projects (name) VALUES (?)", ('New Project',))

        # Get single row
        project = db.query_one("SELECT * FROM projects WHERE id = ?", (1,))
    """

    def __init__(self, db_type: str = "main", timeout: float = None):
        self.db_type = db_type
        self.timeout = timeout

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new connection."""
        db_path = get_db_path(self.db_type)
        return _create_connection(db_path, self.timeout)

    def query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a query and return all results."""
        with get_connection(self.db_type, self.timeout) as conn:
            return conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a query and return first result or None."""
        with get_connection(self.db_type, self.timeout) as conn:
            return conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute a statement and return lastrowid."""
        with get_connection(self.db_type, self.timeout) as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid

    def executemany(self, sql: str, params_list: List[tuple]) -> int:
        """Execute a statement with multiple parameter sets."""
        with get_connection(self.db_type, self.timeout) as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount

    def executescript(self, script: str) -> None:
        """Execute a SQL script."""
        with get_connection(self.db_type, self.timeout) as conn:
            conn.executescript(script)


# Convenience functions for common operations
def query(sql: str, params: tuple = (), db_type: str = "main") -> List[sqlite3.Row]:
    """Execute a query and return results."""
    return Database(db_type).query(sql, params)


def query_one(sql: str, params: tuple = (), db_type: str = "main") -> Optional[sqlite3.Row]:
    """Execute a query and return first result."""
    return Database(db_type).query_one(sql, params)


def execute(sql: str, params: tuple = (), db_type: str = "main") -> int:
    """Execute a statement and return lastrowid."""
    return Database(db_type).execute(sql, params)


# Legacy compatibility - matches existing get_db_connection signature
def get_db_connection(timeout: float = None, use_pool: bool = False):
    """
    Legacy function for backward compatibility.
    Returns a connection to the main database.

    Note: Prefer using get_connection() context manager instead,
    which properly handles connection pooling and cleanup.

    Args:
        timeout: Connection timeout in seconds
        use_pool: If True, get from pool (caller must return via release_connection)

    Warning: When use_pool=True, caller MUST call release_connection() when done.
    """
    if use_pool and POOL_CONFIG["enabled"]:
        pool = get_pool("main")
        if pool:
            pooled = pool.acquire()
            # Store pooled connection for release
            if not hasattr(_local, "pooled_connections"):
                _local.pooled_connections = {}
            _local.pooled_connections[id(pooled.connection)] = pooled
            return pooled.connection

    db_path = get_db_path("main")
    return _create_connection(db_path, timeout)


def release_connection(conn: sqlite3.Connection):
    """
    Release a connection obtained via get_db_connection(use_pool=True).

    Args:
        conn: The connection to release back to the pool
    """
    if hasattr(_local, "pooled_connections"):
        conn_id = id(conn)
        if conn_id in _local.pooled_connections:
            pooled = _local.pooled_connections.pop(conn_id)
            pool = get_pool("main")
            if pool:
                pool.release(pooled)
                return

    # Not a pooled connection, just close it
    try:
        conn.close()
    except Exception:
        pass


# Database type detection for future migration
def get_database_type() -> str:
    """Get the configured database type."""
    return DB_CONFIG["type"]


def set_database_config(config: Dict[str, Any]) -> None:
    """
    Update database configuration.

    Args:
        config: Dictionary with configuration updates

    Example:
        set_database_config({
            'type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'database': 'architect'
        })
    """
    DB_CONFIG.update(config)


# Initialize databases if needed
def init_databases():
    """Ensure all database directories exist."""
    for db_type, db_path in DB_PATHS.items():
        db_path.parent.mkdir(parents=True, exist_ok=True)


# Pool management functions


def get_pool_stats(db_type: str = None) -> Dict[str, Any]:
    """
    Get connection pool statistics.

    Args:
        db_type: Specific database type, or None for all pools

    Returns:
        Dict with pool statistics

    Example:
        stats = get_pool_stats()
        print(f"Main DB - Active: {stats['main']['active']}")

        stats = get_pool_stats('main')
        print(f"Created: {stats['created']}, Reused: {stats['reused']}")
    """
    if not POOL_CONFIG["enabled"]:
        return {"enabled": False}

    if db_type:
        pool = _pools.get(db_type)
        if pool:
            return pool.get_stats()
        return {"error": f"No pool for {db_type}"}

    return {"enabled": True, "pools": {name: pool.get_stats() for name, pool in _pools.items()}}


def set_pool_config(config: Dict[str, Any]) -> None:
    """
    Update pool configuration.

    Args:
        config: Dictionary with configuration updates

    Example:
        set_pool_config({
            'max_connections': 20,
            'pool_timeout': 60
        })

    Note: Changes only affect new pools. Use reset_pools() to apply to existing.
    """
    POOL_CONFIG.update(config)


def reset_pools():
    """
    Close and recreate all connection pools.

    Use after changing pool configuration to apply new settings.
    """
    close_all_pools()
    # Pools will be recreated on next get_pool() call


def pool_health_check(db_type: str = None) -> Dict[str, Any]:
    """
    Perform health check on connection pools.

    Args:
        db_type: Specific database type, or None for all pools

    Returns:
        Dict with health check results
    """
    if not POOL_CONFIG["enabled"]:
        return {"enabled": False}

    if db_type:
        pool = _pools.get(db_type)
        if pool:
            return pool.health_check()
        return {"error": f"No pool for {db_type}"}

    return {name: pool.health_check() for name, pool in _pools.items()}


def warmup_pools(db_types: List[str] = None):
    """
    Pre-create connection pools for specified database types.

    Args:
        db_types: List of database types to warm up, or None for all

    Example:
        warmup_pools(['main', 'delegator'])  # Pre-create pools
    """
    if not POOL_CONFIG["enabled"]:
        return

    types_to_warm = db_types or list(DB_PATHS.keys())
    for db_type in types_to_warm:
        if db_type in DB_PATHS:
            get_pool(db_type)


def disable_pooling():
    """Disable connection pooling globally."""
    POOL_CONFIG["enabled"] = False
    close_all_pools()


def enable_pooling():
    """Enable connection pooling globally."""
    POOL_CONFIG["enabled"] = True


# =============================================================================
# Background Health Checker
# =============================================================================


class PoolHealthChecker:
    """
    Background thread for periodic health checks of connection pools.

    Features:
        - Periodic health checks on all pools
        - Automatic connection recycling
        - Metrics collection
        - Configurable check interval
    """

    def __init__(self, check_interval: int = None):
        self.check_interval = check_interval or POOL_CONFIG["health_check_interval"]
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_check: Optional[datetime] = None
        self._check_results: Dict[str, Any] = {}

    def start(self):
        """Start the background health checker."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop, name="PoolHealthChecker", daemon=True
            )
            self._thread.start()
            logger.info(f"Pool health checker started (interval: {self.check_interval}s)")

    def stop(self):
        """Stop the background health checker."""
        with self._lock:
            self._running = False
            if self._thread:
                self._thread.join(timeout=5)
                self._thread = None
            logger.info("Pool health checker stopped")

    def _run_loop(self):
        """Main health check loop."""
        while self._running:
            try:
                self._perform_checks()
            except Exception as e:
                logger.error(f"Error in pool health check: {e}")

            # Sleep in small increments for responsive shutdown
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _perform_checks(self):
        """Perform health checks on all pools."""
        self._last_check = datetime.now()
        results = {}

        with _pools_lock:
            pool_names = list(_pools.keys())

        for name in pool_names:
            try:
                pool = _pools.get(name)
                if pool:
                    results[name] = pool.health_check()
            except Exception as e:
                results[name] = {"error": str(e)}

        self._check_results = {"timestamp": self._last_check.isoformat(), "pools": results}

    def get_last_results(self) -> Dict[str, Any]:
        """Get results from the last health check."""
        return self._check_results

    def is_running(self) -> bool:
        """Check if the health checker is running."""
        return self._running


# Global health checker instance
_health_checker: Optional[PoolHealthChecker] = None


def start_health_checker(check_interval: int = None):
    """Start the background pool health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = PoolHealthChecker(check_interval)
    _health_checker.start()


def stop_health_checker():
    """Stop the background pool health checker."""
    global _health_checker
    if _health_checker:
        _health_checker.stop()


def get_health_check_results() -> Dict[str, Any]:
    """Get the latest health check results."""
    if _health_checker:
        return _health_checker.get_last_results()
    return {"error": "Health checker not running"}


# =============================================================================
# Service Connection Pool Helper
# =============================================================================


class ServiceConnectionPool:
    """
    Helper class for services to use pooled connections with custom database paths.

    This allows services that were using direct sqlite3.connect to easily migrate
    to pooled connections while maintaining their own database files.

    Usage:
        # In your service
        from db import ServiceConnectionPool

        class MyService:
            def __init__(self, db_path: str):
                self._pool = ServiceConnectionPool(db_path)

            def do_something(self):
                with self._pool.connection() as conn:
                    conn.execute("SELECT * FROM table")

            def close(self):
                self._pool.close()
    """

    _instances: Dict[str, "ServiceConnectionPool"] = {}
    _instances_lock = threading.Lock()

    def __init__(
        self,
        db_path: Union[str, Path],
        pool_name: Optional[str] = None,
        min_connections: int = 1,
        max_connections: int = 5,
        **kwargs,
    ):
        """
        Create a service connection pool.

        Args:
            db_path: Path to the database file
            pool_name: Optional name for the pool (defaults to db filename)
            min_connections: Minimum connections to maintain
            max_connections: Maximum connections allowed
            **kwargs: Additional ConnectionPool arguments
        """
        self.db_path = Path(db_path)
        self.pool_name = pool_name or self.db_path.stem

        if POOL_CONFIG["enabled"]:
            self._pool = ConnectionPool(
                self.db_path,
                min_connections=min_connections,
                max_connections=max_connections,
                **kwargs,
            )
        else:
            self._pool = None

    @classmethod
    def get_or_create(cls, db_path: Union[str, Path], **kwargs) -> "ServiceConnectionPool":
        """
        Get an existing pool or create a new one for the given path.

        This ensures only one pool exists per database path.
        """
        path_key = str(Path(db_path).resolve())

        with cls._instances_lock:
            if path_key not in cls._instances:
                cls._instances[path_key] = cls(db_path, **kwargs)
            return cls._instances[path_key]

    @contextmanager
    def connection(self, timeout: float = None):
        """
        Get a connection from the pool.

        Yields:
            sqlite3.Connection ready for use
        """
        if self._pool and POOL_CONFIG["enabled"]:
            with self._pool.get_connection() as conn:
                yield conn
        else:
            # Fallback to direct connection
            conn = sqlite3.connect(str(self.db_path), timeout=timeout or DB_CONFIG["timeout"])
            conn.row_factory = sqlite3.Row
            _apply_pragmas(conn)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        if self._pool:
            return self._pool.get_stats()
        return {"pooling": False, "db_path": str(self.db_path)}

    def close(self):
        """Close the pool."""
        if self._pool:
            self._pool.close()

    @classmethod
    def close_all(cls):
        """Close all service connection pools."""
        with cls._instances_lock:
            for pool in cls._instances.values():
                try:
                    pool.close()
                except Exception:
                    pass
            cls._instances.clear()


# Register cleanup
atexit.register(ServiceConnectionPool.close_all)


# =============================================================================
# Pool Metrics and Monitoring
# =============================================================================


class PoolMetrics:
    """
    Collects and provides metrics for all connection pools.

    Useful for monitoring and alerting.
    """

    @staticmethod
    def get_all_metrics() -> Dict[str, Any]:
        """Get comprehensive metrics for all pools."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "pooling_enabled": POOL_CONFIG["enabled"],
                "min_connections": POOL_CONFIG["min_connections"],
                "max_connections": POOL_CONFIG["max_connections"],
                "max_overflow": POOL_CONFIG["max_overflow"],
                "pool_timeout": POOL_CONFIG["pool_timeout"],
                "recycle_time": POOL_CONFIG["recycle_time"],
            },
            "pools": {},
            "service_pools": {},
            "summary": {
                "total_pools": 0,
                "total_active": 0,
                "total_available": 0,
                "total_created": 0,
                "total_reused": 0,
                "total_failed": 0,
            },
        }

        # Global pools
        with _pools_lock:
            for name, pool in _pools.items():
                stats = pool.get_stats()
                metrics["pools"][name] = stats
                metrics["summary"]["total_pools"] += 1
                metrics["summary"]["total_active"] += stats.get("active", 0)
                metrics["summary"]["total_available"] += stats.get("available", 0)
                metrics["summary"]["total_created"] += stats.get("created", 0)
                metrics["summary"]["total_reused"] += stats.get("reused", 0)
                metrics["summary"]["total_failed"] += stats.get("failed", 0)

        # Service pools
        with ServiceConnectionPool._instances_lock:
            for path, svc_pool in ServiceConnectionPool._instances.items():
                stats = svc_pool.get_stats()
                metrics["service_pools"][svc_pool.pool_name] = stats
                if "active" in stats:
                    metrics["summary"]["total_pools"] += 1
                    metrics["summary"]["total_active"] += stats.get("active", 0)
                    metrics["summary"]["total_available"] += stats.get("available", 0)

        # Health check results
        if _health_checker:
            metrics["health_check"] = _health_checker.get_last_results()

        return metrics

    @staticmethod
    def get_pool_summary() -> Dict[str, Any]:
        """Get a simple summary of pool status."""
        total_active = 0
        total_available = 0
        pool_count = 0

        with _pools_lock:
            for pool in _pools.values():
                stats = pool.get_stats()
                total_active += stats.get("active", 0)
                total_available += stats.get("available", 0)
                pool_count += 1

        return {
            "pools": pool_count,
            "active_connections": total_active,
            "available_connections": total_available,
            "pooling_enabled": POOL_CONFIG["enabled"],
        }


def get_pool_metrics() -> Dict[str, Any]:
    """Get comprehensive pool metrics."""
    return PoolMetrics.get_all_metrics()


def get_pool_summary() -> Dict[str, Any]:
    """Get a simple pool status summary."""
    return PoolMetrics.get_pool_summary()


# =============================================================================
# Connection Factory for Migration
# =============================================================================


def create_pooled_connection(
    db_path: Union[str, Path], timeout: float = None
) -> sqlite3.Connection:
    """
    Create a connection that may be from a pool.

    This is a drop-in replacement for sqlite3.connect that uses pooling
    when available. Use this when migrating services from direct connections.

    WARNING: When using this function, you MUST call close_pooled_connection()
    instead of conn.close() to properly return the connection to the pool.

    For new code, prefer using ServiceConnectionPool or get_connection() context manager.

    Args:
        db_path: Path to the database
        timeout: Connection timeout

    Returns:
        sqlite3.Connection (may be pooled)
    """
    path = Path(db_path)

    # Check if we have a pool for this path
    pool = ServiceConnectionPool.get_or_create(path)

    if pool._pool and POOL_CONFIG["enabled"]:
        pooled = pool._pool.acquire()
        # Store for later release
        if not hasattr(_local, "service_pooled"):
            _local.service_pooled = {}
        _local.service_pooled[id(pooled.connection)] = (pool._pool, pooled)
        return pooled.connection

    # Fallback to direct connection
    conn = sqlite3.connect(str(path), timeout=timeout or DB_CONFIG["timeout"])
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def close_pooled_connection(conn: sqlite3.Connection):
    """
    Close or return a connection that may be pooled.

    Use this instead of conn.close() when using create_pooled_connection().

    Args:
        conn: Connection to close/return
    """
    if hasattr(_local, "service_pooled"):
        conn_id = id(conn)
        if conn_id in _local.service_pooled:
            pool, pooled = _local.service_pooled.pop(conn_id)
            pool.release(pooled)
            return

    # Not pooled, just close
    try:
        conn.close()
    except Exception:
        pass


# =============================================================================
# Initialization
# =============================================================================


def initialize_pools(warmup: bool = True, health_checker: bool = True, db_types: List[str] = None):
    """
    Initialize connection pools for the application.

    Call this at application startup for best performance.

    Args:
        warmup: Pre-create pool connections
        health_checker: Start background health checker
        db_types: Specific database types to initialize
    """
    if not POOL_CONFIG["enabled"]:
        logger.info("Connection pooling is disabled")
        return

    # Warm up pools
    if warmup:
        types = db_types or list(DB_PATHS.keys())
        warmup_pools(types)
        logger.info(f"Warmed up connection pools for: {types}")

    # Start health checker
    if health_checker:
        start_health_checker()

    logger.info("Connection pooling initialized")
