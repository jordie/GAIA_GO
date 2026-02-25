"""Database-backed rate limiting service with persistence and analytics."""
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimitService:
    """Enhanced rate limiting with database persistence and auto-throttling."""

    # High/critical load thresholds
    HIGH_LOAD_THRESHOLD = 80  # CPU/memory %
    CRITICAL_LOAD_THRESHOLD = 95

    def __init__(self, db_connection_factory):
        """Initialize rate limiting service.

        Args:
            db_connection_factory: Callable that returns DB connection
        """
        self.get_db = db_connection_factory
        self._local_cache: Dict[str, List[float]] = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = 300  # 5 minutes - local cache time-to-live
        self._cache_timestamps = {}

    def check_limit(
        self,
        scope: str,
        scope_value: str,
        resource_type: str = "default",
        request_path: str = "",
        user_agent: str = ""
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if request is within rate limit.

        Args:
            scope: Rate limit scope ('ip', 'user', 'api_key')
            scope_value: Value for the scope (IP address, user ID, etc.)
            resource_type: Type of resource being accessed
            request_path: HTTP request path for logging
            user_agent: User agent string for logging

        Returns:
            Tuple of (allowed: bool, info: dict)
            - allowed=True if request should proceed
            - info contains limit details if denied
        """
        # Get applicable limits from config
        limits = self._get_limits(scope, scope_value, resource_type)

        if not limits:
            return True, None

        # Check each limit type
        for limit_config in limits:
            allowed = self._check_single_limit(
                scope, scope_value, resource_type, limit_config
            )
            if not allowed:
                self._record_violation(
                    scope, scope_value, resource_type, limit_config,
                    request_path, user_agent
                )
                return False, {
                    "limit": limit_config["limit_value"],
                    "limit_type": limit_config["limit_type"],
                    "resource": resource_type,
                    "retry_after": 60
                }

        # Update buckets if all checks pass
        self._update_bucket(scope, scope_value, resource_type)
        return True, None

    def _get_limits(self, scope: str, scope_value: str, resource_type: str) -> List[Dict]:
        """Get applicable rate limit configurations from database.

        Prioritizes specific rules over default rules.
        """
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            # Check specific + default limits, prioritize specific ones
            cursor.execute("""
                SELECT * FROM rate_limit_configs
                WHERE enabled = 1
                AND scope = ?
                AND (scope_value = ? OR scope_value IS NULL)
                AND (resource_type = ? OR resource_type IS NULL)
                ORDER BY scope_value DESC, resource_type DESC
            """, (scope, scope_value, resource_type))

            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting rate limit configs: {e}")
            return []

    def _check_single_limit(
        self,
        scope: str,
        scope_value: str,
        resource_type: str,
        limit_config: Dict
    ) -> bool:
        """Check a single limit configuration against request history."""
        limit_type = limit_config["limit_type"]
        limit_value = limit_config["limit_value"]

        if limit_type == "requests_per_minute":
            window_seconds = 60
        elif limit_type == "requests_per_hour":
            window_seconds = 3600
        else:
            # Daily/monthly quota - different logic
            return self._check_quota(scope, scope_value, resource_type, limit_value)

        # Sliding window check
        try:
            window_start = datetime.now() - timedelta(seconds=window_seconds)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT SUM(request_count) as total FROM rate_limit_buckets
                WHERE scope = ? AND scope_value = ?
                AND (resource_type IS NULL OR resource_type = ?)
                AND window_end > ?
            """, (scope, scope_value, resource_type, window_start))

            row = cursor.fetchone()
            count = row[0] if row and row[0] else 0

            return count < limit_value
        except Exception as e:
            logger.error(f"Error checking single limit: {e}")
            return True  # Fail open - allow request if DB error

    def _check_quota(
        self,
        scope: str,
        scope_value: str,
        resource_type: str,
        limit: int
    ) -> bool:
        """Check daily/monthly quota usage."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            now = datetime.now()
            cursor.execute("""
                SELECT quota_used, quota_limit FROM resource_quotas
                WHERE scope = ? AND scope_value = ?
                AND resource_type = ?
                AND period_start <= ? AND period_end > ?
                LIMIT 1
            """, (scope, scope_value, resource_type, now, now))

            row = cursor.fetchone()
            if not row:
                return True  # No quota set

            return row[0] < row[1]
        except Exception as e:
            logger.error(f"Error checking quota: {e}")
            return True  # Fail open

    def _update_bucket(self, scope: str, scope_value: str, resource_type: str):
        """Update request count in current minute bucket."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            now = datetime.now()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + timedelta(minutes=1)

            # Try to update existing bucket, insert if not exists
            cursor.execute("""
                SELECT id, request_count FROM rate_limit_buckets
                WHERE scope = ? AND scope_value = ?
                AND resource_type = ?
                AND window_start = ?
                LIMIT 1
            """, (scope, scope_value, resource_type, window_start))

            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE rate_limit_buckets
                    SET request_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (existing[1] + 1, existing[0]))
            else:
                cursor.execute("""
                    INSERT INTO rate_limit_buckets
                    (scope, scope_value, resource_type, window_start, window_end, request_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (scope, scope_value, resource_type, window_start, window_end))

            conn.commit()
        except Exception as e:
            logger.error(f"Error updating bucket: {e}")

    def _record_violation(
        self,
        scope: str,
        scope_value: str,
        resource_type: str,
        limit_config: Dict,
        request_path: str = "",
        user_agent: str = ""
    ):
        """Record a rate limit violation for analytics and security."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO rate_limit_violations
                (scope, scope_value, resource_type, exceeded_limit, blocked, request_path, user_agent)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (scope, scope_value, resource_type, limit_config["limit_value"],
                  request_path[:255] if request_path else None,
                  user_agent[:255] if user_agent else None))

            conn.commit()
            logger.warning(
                f"Rate limit violation: {scope}={scope_value}, type={resource_type}, "
                f"limit={limit_config['limit_value']}"
            )
        except Exception as e:
            logger.error(f"Error recording violation: {e}")

    def cleanup_old_data(self, days: int = 7) -> int:
        """Clean up old buckets and violations.

        Args:
            days: Number of days to retain

        Returns:
            Number of records deleted
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            conn = self.get_db()
            cursor = conn.cursor()

            # Delete old buckets
            cursor.execute(
                "DELETE FROM rate_limit_buckets WHERE window_end < ?",
                (cutoff,)
            )
            buckets_deleted = cursor.rowcount

            # Delete old violations
            cursor.execute(
                "DELETE FROM rate_limit_violations WHERE violation_time < ?",
                (cutoff,)
            )
            violations_deleted = cursor.rowcount

            conn.commit()
            total = buckets_deleted + violations_deleted
            logger.info(f"Cleanup: deleted {buckets_deleted} buckets, {violations_deleted} violations")
            return total
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def get_stats(self, days: int = 7) -> Dict:
        """Get rate limiting statistics for dashboard.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            conn = self.get_db()
            cursor = conn.cursor()

            # Total violations by scope
            cursor.execute("""
                SELECT scope, COUNT(*) as count FROM rate_limit_violations
                WHERE violation_time > ?
                GROUP BY scope
            """, (cutoff,))
            violations_by_scope = {row[0]: row[1] for row in cursor.fetchall()}

            # Top violators
            cursor.execute("""
                SELECT scope_value, COUNT(*) as count FROM rate_limit_violations
                WHERE violation_time > ?
                GROUP BY scope_value
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff,))
            top_violators = [{"scope_value": row[0], "count": row[1]} for row in cursor.fetchall()]

            # Total requests
            cursor.execute("""
                SELECT SUM(request_count) FROM rate_limit_buckets
                WHERE window_end > ?
            """, (cutoff,))
            total_requests = cursor.fetchone()[0] or 0

            return {
                "total_requests": total_requests,
                "violations_by_scope": violations_by_scope,
                "top_violators": top_violators,
                "days_analyzed": days
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def create_config(
        self,
        rule_name: str,
        scope: str,
        limit_type: str,
        limit_value: int,
        scope_value: str = None,
        resource_type: str = None
    ) -> bool:
        """Create a new rate limit configuration.

        Args:
            rule_name: Unique name for this rule
            scope: 'ip', 'user', 'api_key'
            limit_type: 'requests_per_minute', 'requests_per_hour', 'daily_quota'
            limit_value: The limit number
            scope_value: Optional specific value (e.g., exact IP)
            resource_type: Optional resource type (e.g., 'login', 'upload')

        Returns:
            True if successful
        """
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO rate_limit_configs
                (rule_name, scope, limit_type, limit_value, scope_value, resource_type, enabled)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (rule_name, scope, limit_type, limit_value, scope_value, resource_type))

            conn.commit()
            logger.info(f"Created rate limit config: {rule_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating config: {e}")
            return False

    def disable_config(self, rule_name: str) -> bool:
        """Disable a rate limit configuration."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE rate_limit_configs SET enabled = 0 WHERE rule_name = ?",
                (rule_name,)
            )

            conn.commit()
            logger.info(f"Disabled rate limit config: {rule_name}")
            return True
        except Exception as e:
            logger.error(f"Error disabling config: {e}")
            return False

    def get_all_configs(self) -> List[Dict]:
        """Get all rate limit configurations."""
        try:
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM rate_limit_configs
                ORDER BY created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting configs: {e}")
            return []

    def get_violations_summary(self, hours: int = 24) -> Dict:
        """Get recent violations summary.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with violation summary
        """
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    scope, scope_value, resource_type, COUNT(*) as count,
                    MAX(violation_time) as last_violation
                FROM rate_limit_violations
                WHERE violation_time > ?
                GROUP BY scope, scope_value, resource_type
                ORDER BY count DESC
            """, (cutoff,))

            violations = [dict(row) for row in cursor.fetchall()]
            return {
                "hours_analyzed": hours,
                "total_violations": len(violations),
                "violations": violations
            }
        except Exception as e:
            logger.error(f"Error getting violations summary: {e}")
            return {}
