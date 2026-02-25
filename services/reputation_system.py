"""User Reputation System for Rate Limiting Phase 2.

This module implements a reputation-based system that tracks user behavior
and adjusts rate limits based on reputation scores.

Key Features:
- Tracks reputation scores (0-100) for users
- Records events (violations, clean requests, etc.)
- Applies decay to forgive old behavior
- Returns limit multipliers based on reputation tier
- Supports manual VIP tier overrides
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
import logging
import json
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReputationTier:
    """Represents a reputation tier."""
    name: str
    min_score: float
    max_score: float
    limit_multiplier: float
    description: str
    color_code: str


class ReputationSystem:
    """Manages user reputation scores and limit adjustments."""

    # Event type constants
    EVENT_VIOLATION = "rate_limit_violation"
    EVENT_ATTACK = "suspected_attack"
    EVENT_CLEAN_REQUEST = "clean_request"
    EVENT_SUCCESS = "successful_request"
    EVENT_ERROR = "error_request"
    EVENT_MANUAL_ADJUSTMENT = "manual_adjustment"

    # Default configuration
    DEFAULT_CONFIG = {
        "initial_score": 50.0,
        "min_score": 0.0,
        "max_score": 100.0,
        "violation_penalty": 5.0,
        "attack_penalty": 10.0,
        "clean_request_reward": 0.5,
        "daily_decay_rate": 0.99,
    }

    # Reputation tiers (score ranges -> multipliers)
    TIERS = {
        "excellent": ReputationTier("excellent", 90, 100, 2.0, "Highly trusted (2x limits)", "#4CAF50"),
        "good": ReputationTier("good", 75, 89, 1.5, "Trusted (1.5x limits)", "#8BC34A"),
        "neutral": ReputationTier("neutral", 50, 74, 1.0, "Normal (1x limits)", "#2196F3"),
        "caution": ReputationTier("caution", 25, 49, 0.8, "Cautious (0.8x limits)", "#FF9800"),
        "restricted": ReputationTier("restricted", 0, 24, 0.5, "Restricted (0.5x limits)", "#F44336"),
    }

    def __init__(self, db_path: str = None):
        """Initialize reputation system.

        Args:
            db_path: Path to SQLite database. If None, uses default.
        """
        self.db_path = db_path or "data/architect.db"
        self._config_cache: Dict[str, float] = None
        self._config_cache_time = 0
        self._config_cache_ttl = 300  # 5 minutes

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_config(self, force_reload: bool = False) -> Dict[str, float]:
        """Load configuration from database with caching.

        Args:
            force_reload: Force reload from database

        Returns:
            Configuration dictionary
        """
        now = datetime.now()
        if (
            self._config_cache is not None
            and not force_reload
            and (now.timestamp() - self._config_cache_time) < self._config_cache_ttl
        ):
            return self._config_cache

        config = self.DEFAULT_CONFIG.copy()
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT config_key, config_value FROM reputation_config")
            for row in cursor.fetchall():
                try:
                    config[row[0]] = float(row[1])
                except ValueError:
                    pass
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to load reputation config: {e}")

        self._config_cache = config
        self._config_cache_time = now.timestamp()
        return config

    def get_reputation(self, user_id: int) -> float:
        """Get user's current reputation score.

        Args:
            user_id: User ID

        Returns:
            Reputation score (0-100), or None if user not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT reputation_score FROM user_reputation WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return row[0]
        except Exception as e:
            logger.error(f"Error getting reputation for user {user_id}: {e}")
            return None

    def get_reputation_details(self, user_id: int) -> Optional[Dict]:
        """Get detailed reputation information for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with reputation details or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, reputation_score, tier, total_violations,
                           total_clean_requests, last_violation, created_at, updated_at
                   FROM user_reputation WHERE user_id = ?""",
                (user_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            details = dict(row)
            details["user_id"] = user_id
            details["tier"] = self.get_tier_for_score(details["reputation_score"])
            details["limit_multiplier"] = self.get_limit_multiplier(user_id)

            conn.close()
            return details
        except Exception as e:
            logger.error(f"Error getting reputation details for user {user_id}: {e}")
            return None

    def record_event(
        self,
        user_id: int,
        event_type: str,
        severity: int = 1,
        description: str = None,
    ) -> bool:
        """Record a reputation event for a user.

        Args:
            user_id: User ID
            event_type: Type of event (violation, attack, clean, error, etc.)
            severity: Event severity (1-10)
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Ensure user exists in reputation table
            cursor.execute(
                """INSERT OR IGNORE INTO user_reputation (user_id)
                   VALUES (?)""",
                (user_id,),
            )

            # Record the event
            score_delta = self._calculate_score_delta(event_type, severity)
            cursor.execute(
                """INSERT INTO reputation_events
                   (user_id, event_type, severity, description, score_delta)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, event_type, severity, description, score_delta),
            )

            # Update violation tracking
            if event_type == self.EVENT_VIOLATION:
                cursor.execute(
                    """UPDATE user_reputation
                       SET total_violations = total_violations + 1,
                           last_violation = CURRENT_TIMESTAMP
                       WHERE user_id = ?""",
                    (user_id,),
                )
            elif event_type == self.EVENT_CLEAN_REQUEST:
                cursor.execute(
                    """UPDATE user_reputation
                       SET total_clean_requests = total_clean_requests + 1
                       WHERE user_id = ?""",
                    (user_id,),
                )

            conn.commit()
            conn.close()

            # Recalculate score after recording event
            self._update_score(user_id)

            return True
        except Exception as e:
            logger.error(f"Error recording reputation event for user {user_id}: {e}")
            return False

    def _calculate_score_delta(self, event_type: str, severity: int = 1) -> float:
        """Calculate score change for an event.

        Args:
            event_type: Type of event
            severity: Event severity (1-10)

        Returns:
            Score delta (positive or negative)
        """
        config = self._load_config()

        if event_type == self.EVENT_VIOLATION:
            return -config["violation_penalty"] * (severity / 10)
        elif event_type == self.EVENT_ATTACK:
            return -config["attack_penalty"] * (severity / 10)
        elif event_type == self.EVENT_CLEAN_REQUEST:
            return config["clean_request_reward"]
        elif event_type == self.EVENT_SUCCESS:
            return 1.0
        elif event_type == self.EVENT_ERROR:
            return -1.0
        else:
            return 0.0

    def _update_score(self, user_id: int) -> float:
        """Recalculate and update reputation score for a user.

        Args:
            user_id: User ID

        Returns:
            Updated reputation score
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            config = self._load_config()

            # Get recent events (last 100)
            cursor.execute(
                """SELECT event_type, severity, score_delta, timestamp
                   FROM reputation_events
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT 100""",
                (user_id,),
            )

            events = cursor.fetchall()

            if not events:
                # No events, return initial score
                cursor.execute(
                    """SELECT reputation_score FROM user_reputation
                       WHERE user_id = ?""",
                    (user_id,),
                )
                row = cursor.fetchone()
                return row[0] if row else config["initial_score"]

            # Start with initial score
            score = config["initial_score"]

            # Add event deltas with time-based decay
            now = datetime.now()
            for event in events:
                event_time = datetime.fromisoformat(event[3])
                days_old = (now - event_time).days

                # Apply decay: older events have less impact
                decay_factor = config["daily_decay_rate"] ** days_old
                score += event[2] * decay_factor

            # Clamp to valid range
            score = max(config["min_score"], min(config["max_score"], score))

            # Update in database
            cursor.execute(
                """UPDATE user_reputation
                   SET reputation_score = ?,
                       tier = ?,
                       decay_last_applied = CURRENT_TIMESTAMP,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (score, self.get_tier_for_score(score), user_id),
            )

            conn.commit()
            conn.close()

            return score
        except Exception as e:
            logger.error(f"Error updating score for user {user_id}: {e}")
            return None

    def get_tier_for_score(self, score: float) -> str:
        """Get reputation tier name for a score.

        Args:
            score: Reputation score

        Returns:
            Tier name (excellent, good, neutral, caution, restricted)
        """
        for tier_name, tier in self.TIERS.items():
            if tier.min_score <= score <= tier.max_score:
                return tier_name
        return "neutral"

    def get_limit_multiplier(self, user_id: int) -> float:
        """Get rate limit multiplier for a user based on reputation.

        Takes into account both reputation score and VIP status.

        Args:
            user_id: User ID

        Returns:
            Limit multiplier (e.g., 1.0, 1.5, 2.0)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check for VIP override first
            cursor.execute(
                """SELECT limit_multiplier FROM vip_users
                   WHERE user_id = ?""",
                (user_id,),
            )
            vip_row = cursor.fetchone()
            if vip_row:
                conn.close()
                return vip_row[0]

            # Get tier from reputation
            cursor.execute(
                """SELECT reputation_score FROM user_reputation
                   WHERE user_id = ?""",
                (user_id,),
            )
            rep_row = cursor.fetchone()
            conn.close()

            if not rep_row:
                # No reputation data, use neutral
                return self.TIERS["neutral"].limit_multiplier

            score = rep_row[0]
            tier_name = self.get_tier_for_score(score)
            tier = self.TIERS[tier_name]

            return tier.limit_multiplier
        except Exception as e:
            logger.error(f"Error getting limit multiplier for user {user_id}: {e}")
            return 1.0

    def set_vip_tier(
        self,
        user_id: int,
        tier: str,
        limit_multiplier: float = None,
        notes: str = None,
        approved_by: int = None,
    ) -> bool:
        """Manually set a user as VIP with custom limit multiplier.

        Args:
            user_id: User ID
            tier: VIP tier name (premium, enterprise, internal, etc.)
            limit_multiplier: Custom limit multiplier (overrides reputation)
            notes: Admin notes
            approved_by: ID of admin who approved

        Returns:
            True if successful
        """
        try:
            if limit_multiplier is None:
                limit_multiplier = 2.0  # Default VIP multiplier

            conn = self._get_connection()
            cursor = conn.cursor()

            # Ensure user exists in reputation table
            cursor.execute(
                "INSERT OR IGNORE INTO user_reputation (user_id) VALUES (?)",
                (user_id,),
            )

            # Insert or update VIP status
            cursor.execute(
                """INSERT OR REPLACE INTO vip_users
                   (user_id, tier, limit_multiplier, notes, approved_by, approved_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, tier, limit_multiplier, notes, approved_by),
            )

            conn.commit()
            conn.close()

            logger.info(f"User {user_id} set as VIP tier '{tier}' with {limit_multiplier}x limits")
            return True
        except Exception as e:
            logger.error(f"Error setting VIP tier for user {user_id}: {e}")
            return False

    def remove_vip_tier(self, user_id: int) -> bool:
        """Remove VIP status for a user (reverts to reputation-based limits).

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vip_users WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()

            logger.info(f"VIP status removed for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing VIP status for user {user_id}: {e}")
            return False

    def get_event_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get event history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, event_type, severity, description, score_delta, timestamp
                   FROM reputation_events
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (user_id, limit),
            )

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return events
        except Exception as e:
            logger.error(f"Error getting event history for user {user_id}: {e}")
            return []

    def get_top_users(self, limit: int = 10, metric: str = "score") -> List[Dict]:
        """Get top users by reputation metric.

        Args:
            limit: Number of users to return
            metric: Metric to sort by (score, violations, clean_requests)

        Returns:
            List of user dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if metric == "violations":
                order_col = "total_violations DESC"
            elif metric == "clean":
                order_col = "total_clean_requests DESC"
            else:  # score
                order_col = "reputation_score DESC"

            query = f"""SELECT user_id, reputation_score, tier,
                               total_violations, total_clean_requests
                        FROM user_reputation
                        ORDER BY {order_col}
                        LIMIT ?"""

            cursor.execute(query, (limit,))
            users = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return users
        except Exception as e:
            logger.error(f"Error getting top users: {e}")
            return []

    def get_statistics(self) -> Dict:
        """Get system-wide reputation statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Overall stats
            cursor.execute(
                """SELECT
                   COUNT(*) as total_users,
                   AVG(reputation_score) as avg_score,
                   MIN(reputation_score) as min_score,
                   MAX(reputation_score) as max_score,
                   SUM(total_violations) as total_violations,
                   SUM(total_clean_requests) as total_clean_requests
                FROM user_reputation"""
            )
            overall = dict(cursor.fetchone())

            # Tier distribution
            cursor.execute(
                """SELECT tier, COUNT(*) as count
                FROM user_reputation
                GROUP BY tier"""
            )
            tiers = {row[0]: row[1] for row in cursor.fetchall()}

            conn.close()

            return {
                "overall": overall,
                "tier_distribution": tiers,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting reputation statistics: {e}")
            return {}


# Global instance
_reputation_system = None


def get_reputation_system(db_path: str = None) -> ReputationSystem:
    """Get or create global reputation system instance.

    Args:
        db_path: Path to SQLite database

    Returns:
        ReputationSystem instance
    """
    global _reputation_system
    if _reputation_system is None:
        _reputation_system = ReputationSystem(db_path)
    return _reputation_system
