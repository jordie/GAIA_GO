"""
Token Throttling System

Prevents cycles from using too many tokens and enforces budget limits.
Integrates with LLM provider to track and limit token usage.

Features:
    - Per-session token limits
    - Per-provider budget enforcement
    - Daily/hourly/monthly limits
    - Automatic throttling when limits approached
    - Queue requests when throttled
    - Alert system for budget warnings

Usage:
    from services.token_throttle import TokenThrottler, ThrottleConfig

    throttler = TokenThrottler()

    # Check if request is allowed
    if throttler.allow_request(session_id="worker1", estimated_tokens=1000):
        # Make LLM request
        response = llm.create_completion(...)
        # Record actual usage
        throttler.record_usage(session_id="worker1", tokens_used=response.usage.total_tokens)
    else:
        # Queue or delay request
        pass
"""

import logging
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ThrottleLevel(Enum):
    """Throttle severity levels."""

    NONE = "none"  # No throttling
    WARNING = "warning"  # Approaching limit, warn but allow
    SOFT = "soft"  # Delay requests, reduce priority
    HARD = "hard"  # Block non-critical requests
    CRITICAL = "critical"  # Block all requests


@dataclass
class ThrottleConfig:
    """Configuration for token throttling."""

    # Per-session limits
    tokens_per_hour: int = 100000  # 100K tokens per hour per session
    tokens_per_day: int = 1000000  # 1M tokens per day per session

    # Global limits
    global_tokens_per_hour: int = 500000  # 500K tokens per hour globally
    global_tokens_per_day: int = 5000000  # 5M tokens per day globally

    # Cost limits (USD)
    cost_per_hour: float = 5.0  # $5 per hour
    cost_per_day: float = 50.0  # $50 per day
    cost_per_month: float = 1000.0  # $1000 per month

    # Throttle thresholds (percentage of limit)
    warning_threshold: float = 0.70  # Warn at 70%
    soft_threshold: float = 0.80  # Soft throttle at 80%
    hard_threshold: float = 0.90  # Hard throttle at 90%
    critical_threshold: float = 0.95  # Critical throttle at 95%

    # Request limits
    max_tokens_per_request: int = 10000  # Max tokens in single request

    # Queue settings
    enable_queueing: bool = True
    max_queue_size: int = 100

    # Database
    db_path: str = "/tmp/token_throttle.db"


@dataclass
class UsageStats:
    """Token usage statistics."""

    session_id: str
    tokens_hour: int = 0
    tokens_day: int = 0
    tokens_month: int = 0
    cost_hour: float = 0.0
    cost_day: float = 0.0
    cost_month: float = 0.0
    requests_hour: int = 0
    requests_day: int = 0
    last_reset_hour: datetime = None
    last_reset_day: datetime = None
    last_reset_month: datetime = None


class TokenThrottler:
    """
    Token throttling system to prevent excessive token usage.

    Tracks token usage per session and globally, enforces limits,
    and throttles or queues requests when limits are approached.
    """

    def __init__(self, config: ThrottleConfig = None):
        self.config = config or ThrottleConfig()
        self.db_path = Path(self.config.db_path)

        # In-memory cache for fast lookups
        self.session_stats: Dict[str, UsageStats] = {}
        self.global_stats = UsageStats(session_id="__global__")

        # Request queue
        self.request_queue: List[Dict] = []

        # Thread safety
        self.lock = threading.RLock()

        # Initialize database
        self._init_db()

        # Load existing stats
        self._load_stats()

        logger.info(
            f"TokenThrottler initialized. Limits: {self.config.tokens_per_hour}/hr, {self.config.tokens_per_day}/day"
        )

    def _init_db(self):
        """Initialize SQLite database for persistence."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # Session usage tracking
        c.execute(
            """CREATE TABLE IF NOT EXISTS session_usage (
            session_id TEXT PRIMARY KEY,
            tokens_hour INTEGER DEFAULT 0,
            tokens_day INTEGER DEFAULT 0,
            tokens_month INTEGER DEFAULT 0,
            cost_hour REAL DEFAULT 0.0,
            cost_day REAL DEFAULT 0.0,
            cost_month REAL DEFAULT 0.0,
            requests_hour INTEGER DEFAULT 0,
            requests_day INTEGER DEFAULT 0,
            last_reset_hour TIMESTAMP,
            last_reset_day TIMESTAMP,
            last_reset_month TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Usage history
        c.execute(
            """CREATE TABLE IF NOT EXISTS usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            tokens_used INTEGER NOT NULL,
            cost REAL NOT NULL,
            model TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Throttle events
        c.execute(
            """CREATE TABLE IF NOT EXISTS throttle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            throttle_level TEXT NOT NULL,
            reason TEXT,
            tokens_used INTEGER,
            limit_value INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )

        # Create indexes
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_history_session ON usage_history(session_id)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_history_timestamp ON usage_history(timestamp)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_throttle_events_session ON throttle_events(session_id)"
        )

        conn.commit()
        conn.close()

    def _load_stats(self):
        """Load usage stats from database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("SELECT * FROM session_usage")
        rows = c.fetchall()

        for row in rows:
            session_id = row[0]
            stats = UsageStats(
                session_id=session_id,
                tokens_hour=row[1],
                tokens_day=row[2],
                tokens_month=row[3],
                cost_hour=row[4],
                cost_day=row[5],
                cost_month=row[6],
                requests_hour=row[7],
                requests_day=row[8],
                last_reset_hour=datetime.fromisoformat(row[9]) if row[9] else None,
                last_reset_day=datetime.fromisoformat(row[10]) if row[10] else None,
                last_reset_month=datetime.fromisoformat(row[11]) if row[11] else None,
            )

            # Check if counters need to be reset
            self._check_reset_counters(stats)

            if session_id == "__global__":
                self.global_stats = stats
            else:
                self.session_stats[session_id] = stats

        conn.close()

    def _check_reset_counters(self, stats: UsageStats):
        """Reset counters if time windows have elapsed."""
        now = datetime.now()

        # Reset hourly
        if stats.last_reset_hour is None or (now - stats.last_reset_hour) >= timedelta(hours=1):
            stats.tokens_hour = 0
            stats.cost_hour = 0.0
            stats.requests_hour = 0
            stats.last_reset_hour = now

        # Reset daily
        if stats.last_reset_day is None or (now - stats.last_reset_day) >= timedelta(days=1):
            stats.tokens_day = 0
            stats.cost_day = 0.0
            stats.requests_day = 0
            stats.last_reset_day = now

        # Reset monthly
        if stats.last_reset_month is None or (now - stats.last_reset_month) >= timedelta(days=30):
            stats.tokens_month = 0
            stats.cost_month = 0.0
            stats.last_reset_month = now

    def _get_session_stats(self, session_id: str) -> UsageStats:
        """Get or create session stats."""
        if session_id not in self.session_stats:
            self.session_stats[session_id] = UsageStats(
                session_id=session_id,
                last_reset_hour=datetime.now(),
                last_reset_day=datetime.now(),
                last_reset_month=datetime.now(),
            )

        stats = self.session_stats[session_id]
        self._check_reset_counters(stats)
        return stats

    def get_throttle_level(self, session_id: str, estimated_tokens: int = 0) -> ThrottleLevel:
        """
        Determine throttle level for a session.

        Args:
            session_id: Session identifier
            estimated_tokens: Estimated tokens for upcoming request

        Returns:
            ThrottleLevel indicating severity
        """
        with self.lock:
            stats = self._get_session_stats(session_id)
            self._check_reset_counters(self.global_stats)

            # Check global limits first
            global_hour_pct = (
                self.global_stats.tokens_hour + estimated_tokens
            ) / self.config.global_tokens_per_hour
            global_day_pct = (
                self.global_stats.tokens_day + estimated_tokens
            ) / self.config.global_tokens_per_day

            # Check session limits
            session_hour_pct = (stats.tokens_hour + estimated_tokens) / self.config.tokens_per_hour
            session_day_pct = (stats.tokens_day + estimated_tokens) / self.config.tokens_per_day

            # Check cost limits
            cost_hour_pct = stats.cost_hour / self.config.cost_per_hour
            cost_day_pct = stats.cost_day / self.config.cost_per_day

            # Take the maximum percentage across all limits
            max_pct = max(
                global_hour_pct,
                global_day_pct,
                session_hour_pct,
                session_day_pct,
                cost_hour_pct,
                cost_day_pct,
            )

            # Determine throttle level
            if max_pct >= self.config.critical_threshold:
                return ThrottleLevel.CRITICAL
            elif max_pct >= self.config.hard_threshold:
                return ThrottleLevel.HARD
            elif max_pct >= self.config.soft_threshold:
                return ThrottleLevel.SOFT
            elif max_pct >= self.config.warning_threshold:
                return ThrottleLevel.WARNING
            else:
                return ThrottleLevel.NONE

    def allow_request(
        self, session_id: str, estimated_tokens: int = 0, priority: str = "normal"
    ) -> bool:
        """
        Check if a request should be allowed.

        Args:
            session_id: Session identifier
            estimated_tokens: Estimated tokens for request
            priority: Request priority (critical, high, normal, low)

        Returns:
            True if request is allowed, False if throttled
        """
        with self.lock:
            # Check single request limit
            if estimated_tokens > self.config.max_tokens_per_request:
                logger.warning(
                    f"Request from {session_id} exceeds max tokens per request: {estimated_tokens}"
                )
                return False

            throttle_level = self.get_throttle_level(session_id, estimated_tokens)

            # Critical throttle - only allow critical priority
            if throttle_level == ThrottleLevel.CRITICAL:
                if priority != "critical":
                    self._log_throttle_event(
                        session_id, throttle_level, "Request blocked - critical throttle"
                    )
                    return False

            # Hard throttle - allow critical and high priority
            elif throttle_level == ThrottleLevel.HARD:
                if priority not in ["critical", "high"]:
                    self._log_throttle_event(
                        session_id, throttle_level, "Request blocked - hard throttle"
                    )
                    return False

            # Soft throttle - allow all but queue low priority
            elif throttle_level == ThrottleLevel.SOFT:
                if priority == "low" and self.config.enable_queueing:
                    self._queue_request(session_id, estimated_tokens, priority)
                    return False

            # Warning level - just log
            elif throttle_level == ThrottleLevel.WARNING:
                logger.warning(
                    f"Session {session_id} approaching token limit: {throttle_level.value}"
                )

            return True

    def record_usage(self, session_id: str, tokens_used: int, cost: float = 0.0, model: str = None):
        """
        Record token usage for a session.

        Args:
            session_id: Session identifier
            tokens_used: Actual tokens used
            cost: Cost in USD
            model: Model used
        """
        with self.lock:
            stats = self._get_session_stats(session_id)

            # Update session stats
            stats.tokens_hour += tokens_used
            stats.tokens_day += tokens_used
            stats.tokens_month += tokens_used
            stats.cost_hour += cost
            stats.cost_day += cost
            stats.cost_month += cost
            stats.requests_hour += 1
            stats.requests_day += 1

            # Update global stats
            self.global_stats.tokens_hour += tokens_used
            self.global_stats.tokens_day += tokens_used
            self.global_stats.tokens_month += tokens_used
            self.global_stats.cost_hour += cost
            self.global_stats.cost_day += cost
            self.global_stats.cost_month += cost

            # Persist to database
            self._save_usage(session_id, tokens_used, cost, model)
            self._save_stats(stats)
            if session_id != "__global__":
                self._save_stats(self.global_stats)

    def _save_usage(self, session_id: str, tokens_used: int, cost: float, model: str):
        """Save usage to history table."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                """INSERT INTO usage_history (session_id, tokens_used, cost, model)
                        VALUES (?, ?, ?, ?)""",
                (session_id, tokens_used, cost, model),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save usage: {e}")

    def _save_stats(self, stats: UsageStats):
        """Save stats to database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                """INSERT INTO session_usage
                        (session_id, tokens_hour, tokens_day, tokens_month,
                         cost_hour, cost_day, cost_month, requests_hour, requests_day,
                         last_reset_hour, last_reset_day, last_reset_month, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(session_id) DO UPDATE SET
                            tokens_hour=excluded.tokens_hour,
                            tokens_day=excluded.tokens_day,
                            tokens_month=excluded.tokens_month,
                            cost_hour=excluded.cost_hour,
                            cost_day=excluded.cost_day,
                            cost_month=excluded.cost_month,
                            requests_hour=excluded.requests_hour,
                            requests_day=excluded.requests_day,
                            last_reset_hour=excluded.last_reset_hour,
                            last_reset_day=excluded.last_reset_day,
                            last_reset_month=excluded.last_reset_month,
                            updated_at=CURRENT_TIMESTAMP""",
                (
                    stats.session_id,
                    stats.tokens_hour,
                    stats.tokens_day,
                    stats.tokens_month,
                    stats.cost_hour,
                    stats.cost_day,
                    stats.cost_month,
                    stats.requests_hour,
                    stats.requests_day,
                    stats.last_reset_hour.isoformat() if stats.last_reset_hour else None,
                    stats.last_reset_day.isoformat() if stats.last_reset_day else None,
                    stats.last_reset_month.isoformat() if stats.last_reset_month else None,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")

    def _log_throttle_event(self, session_id: str, level: ThrottleLevel, reason: str):
        """Log throttle event to database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            stats = self._get_session_stats(session_id)
            c.execute(
                """INSERT INTO throttle_events (session_id, throttle_level, reason, tokens_used, limit_value)
                        VALUES (?, ?, ?, ?, ?)""",
                (session_id, level.value, reason, stats.tokens_hour, self.config.tokens_per_hour),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log throttle event: {e}")

    def _queue_request(self, session_id: str, estimated_tokens: int, priority: str):
        """Queue a request for later processing."""
        if len(self.request_queue) >= self.config.max_queue_size:
            logger.warning(f"Request queue full, dropping request from {session_id}")
            return

        self.request_queue.append(
            {
                "session_id": session_id,
                "estimated_tokens": estimated_tokens,
                "priority": priority,
                "queued_at": time.time(),
            }
        )
        logger.info(f"Queued request from {session_id} (queue size: {len(self.request_queue)})")

    def get_stats(self, session_id: str = None) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            session_id: Session to get stats for (None for all)

        Returns:
            Dictionary of stats
        """
        with self.lock:
            if session_id:
                stats = self._get_session_stats(session_id)
                throttle_level = self.get_throttle_level(session_id)

                return {
                    "session_id": session_id,
                    "tokens_hour": stats.tokens_hour,
                    "tokens_day": stats.tokens_day,
                    "tokens_month": stats.tokens_month,
                    "cost_hour": round(stats.cost_hour, 4),
                    "cost_day": round(stats.cost_day, 4),
                    "cost_month": round(stats.cost_month, 4),
                    "requests_hour": stats.requests_hour,
                    "requests_day": stats.requests_day,
                    "throttle_level": throttle_level.value,
                    "limits": {
                        "tokens_per_hour": self.config.tokens_per_hour,
                        "tokens_per_day": self.config.tokens_per_day,
                        "cost_per_hour": self.config.cost_per_hour,
                        "cost_per_day": self.config.cost_per_day,
                    },
                }
            else:
                return {
                    "global": {
                        "tokens_hour": self.global_stats.tokens_hour,
                        "tokens_day": self.global_stats.tokens_day,
                        "cost_hour": round(self.global_stats.cost_hour, 4),
                        "cost_day": round(self.global_stats.cost_day, 4),
                    },
                    "sessions": {sid: self.get_stats(sid) for sid in self.session_stats.keys()},
                    "queue_size": len(self.request_queue),
                }

    def reset_session(self, session_id: str):
        """Reset usage counters for a session."""
        with self.lock:
            if session_id in self.session_stats:
                del self.session_stats[session_id]

                conn = sqlite3.connect(str(self.db_path))
                c = conn.cursor()
                c.execute("DELETE FROM session_usage WHERE session_id = ?", (session_id,))
                conn.commit()
                conn.close()

                logger.info(f"Reset usage stats for session {session_id}")


# Global throttler instance
_throttler = None


def get_throttler(config: ThrottleConfig = None) -> TokenThrottler:
    """Get global throttler instance."""
    global _throttler
    if _throttler is None:
        _throttler = TokenThrottler(config)
    return _throttler
