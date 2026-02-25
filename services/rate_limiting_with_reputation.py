"""Enhanced rate limiting service that integrates with reputation system.

This module wraps the base RateLimitService and applies reputation-based
limit adjustments to provide adaptive rate limiting based on user behavior.

Key Features:
- Applies reputation multipliers to base limits
- Records violations as reputation events
- Supports VIP tier overrides
- Gradual feature flag rollout
- Backward compatible with existing rate limiter
"""

import logging
from typing import Dict, Optional, Tuple
from services.rate_limiting import RateLimitService
from services.reputation_system import get_reputation_system

logger = logging.getLogger(__name__)


class EnhancedRateLimitService(RateLimitService):
    """Rate limiting service with reputation-based adjustments."""

    def __init__(self, db_connection_factory, enable_reputation: bool = True):
        """Initialize enhanced rate limiting service.

        Args:
            db_connection_factory: Callable that returns DB connection
            enable_reputation: Whether to apply reputation multipliers
        """
        super().__init__(db_connection_factory)
        self.reputation_system = get_reputation_system()
        self.enable_reputation = enable_reputation

    def check_limit_with_reputation(
        self,
        scope: str,
        scope_value: str,
        resource_type: str = "default",
        request_path: str = "",
        user_agent: str = "",
        user_id: int = None,
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if request is within rate limit, applying reputation adjustments.

        This is the main integration point that applies reputation multipliers
        to the rate limit checks.

        Args:
            scope: Rate limit scope ('ip', 'user', 'api_key')
            scope_value: Value for the scope (IP address, user ID, etc.)
            resource_type: Type of resource being accessed
            request_path: HTTP request path for logging
            user_agent: User agent string for logging
            user_id: User ID (if available) for reputation lookup

        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        # If reputation system disabled or no user ID, fall back to base check
        if not self.enable_reputation or user_id is None:
            return self.check_limit(scope, scope_value, resource_type, request_path, user_agent)

        # Get applicable limits
        limits = self._get_limits(scope, scope_value, resource_type)
        if not limits:
            return True, None

        # Apply reputation multiplier to limits
        reputation_multiplier = self.reputation_system.get_limit_multiplier(user_id)

        # Check each adjusted limit
        for limit_config in limits:
            # Adjust limit by reputation multiplier
            adjusted_limit = int(limit_config["limit_value"] * reputation_multiplier)

            # Check with adjusted limit
            allowed = self._check_single_limit_with_adjusted_value(
                scope,
                scope_value,
                resource_type,
                limit_config,
                adjusted_limit,
            )

            if not allowed:
                # Record violation both in rate limit system and reputation system
                self._record_violation(
                    scope, scope_value, resource_type, limit_config,
                    request_path, user_agent
                )

                # Record as reputation event
                self._record_reputation_violation(user_id, limit_config)

                return False, {
                    "limit": adjusted_limit,
                    "base_limit": limit_config["limit_value"],
                    "limit_multiplier": reputation_multiplier,
                    "limit_type": limit_config["limit_type"],
                    "resource": resource_type,
                    "retry_after": 60,
                    "reputation_score": self.reputation_system.get_reputation(user_id),
                }

        # Update buckets if all checks pass
        self._update_bucket(scope, scope_value, resource_type)

        # Record clean request as reputation event
        self._record_clean_request(user_id)

        return True, None

    def _check_single_limit_with_adjusted_value(
        self,
        scope: str,
        scope_value: str,
        resource_type: str,
        limit_config: Dict,
        adjusted_limit: int,
    ) -> bool:
        """Check a limit using an adjusted limit value.

        Args:
            scope: Rate limit scope
            scope_value: Scope value
            resource_type: Resource type
            limit_config: Original limit configuration
            adjusted_limit: Adjusted limit to check against

        Returns:
            True if within adjusted limit, False otherwise
        """
        limit_type = limit_config["limit_type"]

        if limit_type == "requests_per_minute":
            window_seconds = 60
        elif limit_type == "requests_per_hour":
            window_seconds = 3600
        else:
            # Daily/monthly quota - use base method
            return self._check_quota(scope, scope_value, resource_type, adjusted_limit)

        # Sliding window check with adjusted limit
        try:
            from datetime import datetime, timedelta
            window_start = datetime.now() - timedelta(seconds=window_seconds)
            conn = self.get_db()
            cursor = conn.cursor()

            cursor.execute(
                """SELECT SUM(request_count) as total FROM rate_limit_buckets
                   WHERE scope = ? AND scope_value = ?
                   AND (resource_type IS NULL OR resource_type = ?)
                   AND window_end > ?""",
                (scope, scope_value, resource_type, window_start),
            )

            row = cursor.fetchone()
            count = row[0] if row and row[0] else 0

            return count < adjusted_limit
        except Exception as e:
            logger.error(f"Error checking single limit with adjusted value: {e}")
            return True  # Fail open

    def _record_reputation_violation(self, user_id: int, limit_config: Dict):
        """Record a violation as a reputation event.

        Args:
            user_id: User ID
            limit_config: Limit configuration
        """
        try:
            # Determine severity based on limit type
            if "request" in limit_config.get("limit_type", "").lower():
                severity = 3  # Moderate severity for rate limit violations
            else:
                severity = 5  # Higher severity for quota violations

            self.reputation_system.record_event(
                user_id,
                self.reputation_system.EVENT_VIOLATION,
                severity=severity,
                description=f"{limit_config.get('limit_type', 'unknown')} exceeded",
            )

            logger.info(f"Recorded reputation violation for user {user_id}")
        except Exception as e:
            logger.error(f"Error recording reputation violation: {e}")

    def _record_clean_request(self, user_id: int):
        """Record a successful request for reputation.

        Args:
            user_id: User ID
        """
        try:
            self.reputation_system.record_event(
                user_id,
                self.reputation_system.EVENT_CLEAN_REQUEST,
                severity=1,
            )
        except Exception as e:
            logger.error(f"Error recording clean request for user {user_id}: {e}")

    def get_user_reputation_info(self, user_id: int) -> Optional[Dict]:
        """Get reputation information for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with reputation details
        """
        if not self.enable_reputation:
            return None

        try:
            return self.reputation_system.get_reputation_details(user_id)
        except Exception as e:
            logger.error(f"Error getting reputation info for user {user_id}: {e}")
            return None

    def get_adjusted_limit(
        self,
        base_limit: int,
        user_id: int = None,
    ) -> Dict:
        """Get adjusted rate limit for a user.

        Args:
            base_limit: Base rate limit
            user_id: User ID (optional)

        Returns:
            Dictionary with adjusted limit info
        """
        if not self.enable_reputation or user_id is None:
            return {"limit": base_limit, "multiplier": 1.0}

        try:
            multiplier = self.reputation_system.get_limit_multiplier(user_id)
            adjusted = int(base_limit * multiplier)
            reputation = self.reputation_system.get_reputation(user_id)
            tier = self.reputation_system.get_tier_for_score(reputation)

            return {
                "limit": adjusted,
                "base_limit": base_limit,
                "multiplier": multiplier,
                "reputation_score": reputation,
                "tier": tier,
            }
        except Exception as e:
            logger.error(f"Error calculating adjusted limit: {e}")
            return {"limit": base_limit, "multiplier": 1.0}


# Global instance for enhanced rate limiting
_enhanced_rate_limiter = None


def get_enhanced_rate_limiter(
    db_connection_factory,
    enable_reputation: bool = True,
) -> EnhancedRateLimitService:
    """Get or create global enhanced rate limiter instance.

    Args:
        db_connection_factory: Callable that returns DB connection
        enable_reputation: Whether to enable reputation-based adjustments

    Returns:
        EnhancedRateLimitService instance
    """
    global _enhanced_rate_limiter
    if _enhanced_rate_limiter is None:
        _enhanced_rate_limiter = EnhancedRateLimitService(
            db_connection_factory,
            enable_reputation=enable_reputation,
        )
    return _enhanced_rate_limiter
