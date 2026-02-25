"""
Dashboard Cache Management Module

Provides cache invalidation and refresh capabilities for dashboard components.
Supports both in-memory caching and cache control for API responses.
"""

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Cache TTL defaults (in seconds)
DEFAULT_CACHE_TTL = {
    "stats": 30,
    "errors": 15,
    "tmux": 30,
    "queue": 10,
    "nodes": 30,
    "activity": 5,
    "projects": 60,
    "milestones": 60,
    "features": 30,
    "bugs": 30,
    "workers": 30,
    "alerts": 10,
}

# Dashboard component definitions
DASHBOARD_COMPONENTS = {
    "stats": {
        "description": "Dashboard statistics (projects, features, bugs, errors)",
        "ttl": 30,
        "priority": "high",
    },
    "errors": {"description": "Error aggregation panel", "ttl": 15, "priority": "high"},
    "tmux": {"description": "tmux session list", "ttl": 30, "priority": "medium"},
    "queue": {"description": "Task queue status", "ttl": 10, "priority": "high"},
    "nodes": {"description": "Cluster node status", "ttl": 30, "priority": "medium"},
    "activity": {"description": "Recent activity log", "ttl": 5, "priority": "low"},
    "projects": {"description": "Project list", "ttl": 60, "priority": "medium"},
    "milestones": {"description": "Milestone data", "ttl": 60, "priority": "medium"},
    "features": {"description": "Feature list", "ttl": 30, "priority": "medium"},
    "bugs": {"description": "Bug list", "ttl": 30, "priority": "medium"},
    "workers": {"description": "Worker status", "ttl": 30, "priority": "medium"},
    "alerts": {"description": "User alerts and notifications", "ttl": 10, "priority": "high"},
}


class DashboardCacheManager:
    """Manages dashboard component caching and invalidation."""

    def __init__(self):
        # Cache storage: {component: {'data': ..., 'timestamp': ..., 'etag': ...}}
        self._cache: Dict[str, Dict] = {}
        # Cache metadata: {component: {'last_invalidated': ..., 'invalidation_count': ...}}
        self._metadata: Dict[str, Dict] = defaultdict(
            lambda: {
                "last_invalidated": None,
                "invalidation_count": 0,
                "last_refresh": None,
                "refresh_count": 0,
            }
        )
        # Registered refresh callbacks
        self._refresh_callbacks: Dict[str, Callable] = {}
        # Lock for thread safety
        self._lock = threading.RLock()
        # Global cache version (incremented on full invalidation)
        self._version = 1
        # Component-specific versions
        self._component_versions: Dict[str, int] = defaultdict(lambda: 1)

    def register_refresh_callback(self, component: str, callback: Callable):
        """Register a callback function to refresh a component.

        Args:
            component: Component name
            callback: Function to call for refresh (should return data)
        """
        with self._lock:
            self._refresh_callbacks[component] = callback

    def get_cache(self, component: str) -> Optional[Dict]:
        """Get cached data for a component if still valid.

        Args:
            component: Component name

        Returns:
            Cached data dict or None if expired/missing
        """
        with self._lock:
            if component not in self._cache:
                return None

            cache_entry = self._cache[component]
            ttl = DASHBOARD_COMPONENTS.get(component, {}).get("ttl", 30)

            # Check if cache is still valid
            if time.time() - cache_entry.get("timestamp", 0) > ttl:
                return None

            return cache_entry

    def set_cache(self, component: str, data: Any, etag: str = None):
        """Set cached data for a component.

        Args:
            component: Component name
            data: Data to cache
            etag: Optional ETag for the data
        """
        with self._lock:
            now = time.time()
            self._cache[component] = {
                "data": data,
                "timestamp": now,
                "etag": etag or self._generate_etag(component, now),
                "version": self._component_versions[component],
            }
            self._metadata[component]["last_refresh"] = datetime.now().isoformat()
            self._metadata[component]["refresh_count"] += 1

    def invalidate(self, component: str) -> Dict:
        """Invalidate cache for a specific component.

        Args:
            component: Component name

        Returns:
            Invalidation result
        """
        with self._lock:
            was_cached = component in self._cache

            if was_cached:
                del self._cache[component]

            self._component_versions[component] += 1
            self._metadata[component]["last_invalidated"] = datetime.now().isoformat()
            self._metadata[component]["invalidation_count"] += 1

            return {
                "component": component,
                "invalidated": was_cached,
                "version": self._component_versions[component],
            }

    def invalidate_all(self) -> Dict:
        """Invalidate all cached data.

        Returns:
            Invalidation result
        """
        with self._lock:
            invalidated = list(self._cache.keys())
            self._cache.clear()
            self._version += 1

            for component in DASHBOARD_COMPONENTS:
                self._component_versions[component] += 1
                self._metadata[component]["last_invalidated"] = datetime.now().isoformat()
                self._metadata[component]["invalidation_count"] += 1

            return {"invalidated": invalidated, "count": len(invalidated), "version": self._version}

    def refresh(self, component: str) -> Dict:
        """Refresh a specific component by calling its callback.

        Args:
            component: Component name

        Returns:
            Refresh result with new data
        """
        # First invalidate
        self.invalidate(component)

        # Then call refresh callback if registered
        if component in self._refresh_callbacks:
            try:
                callback = self._refresh_callbacks[component]
                callback()
                return {
                    "component": component,
                    "refreshed": True,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                logger.error(f"Error refreshing {component}: {e}")
                return {"component": component, "refreshed": False, "error": str(e)}

        return {
            "component": component,
            "refreshed": False,
            "reason": "No refresh callback registered",
        }

    def refresh_all(self) -> Dict:
        """Refresh all components.

        Returns:
            Refresh results for all components
        """
        results = []
        self.invalidate_all()

        for component in self._refresh_callbacks:
            result = self.refresh(component)
            results.append(result)

        return {
            "refreshed": [r["component"] for r in results if r.get("refreshed")],
            "failed": [r["component"] for r in results if not r.get("refreshed")],
            "timestamp": datetime.now().isoformat(),
            "version": self._version,
        }

    def refresh_by_priority(self, priority: str = "high") -> Dict:
        """Refresh components by priority level.

        Args:
            priority: Priority level ('high', 'medium', 'low')

        Returns:
            Refresh results
        """
        results = []

        for component, config in DASHBOARD_COMPONENTS.items():
            if config.get("priority") == priority:
                result = self.refresh(component)
                results.append(result)

        return {
            "priority": priority,
            "refreshed": [r["component"] for r in results if r.get("refreshed")],
            "failed": [r["component"] for r in results if not r.get("refreshed")],
            "timestamp": datetime.now().isoformat(),
        }

    def get_status(self) -> Dict:
        """Get cache status for all components.

        Returns:
            Status dict with cache info
        """
        with self._lock:
            now = time.time()
            status = {"version": self._version, "components": {}}

            for component, config in DASHBOARD_COMPONENTS.items():
                ttl = config.get("ttl", 30)
                cache_entry = self._cache.get(component)

                component_status = {
                    "description": config.get("description"),
                    "ttl_seconds": ttl,
                    "priority": config.get("priority"),
                    "cached": cache_entry is not None,
                    "version": self._component_versions[component],
                    **self._metadata[component],
                }

                if cache_entry:
                    age = now - cache_entry.get("timestamp", 0)
                    component_status["cache_age_seconds"] = round(age, 1)
                    component_status["expires_in_seconds"] = round(max(0, ttl - age), 1)
                    component_status["etag"] = cache_entry.get("etag")

                status["components"][component] = component_status

            return status

    def get_etag(self, component: str) -> Optional[str]:
        """Get ETag for a component's cached data.

        Args:
            component: Component name

        Returns:
            ETag string or None
        """
        with self._lock:
            cache_entry = self._cache.get(component)
            if cache_entry:
                return cache_entry.get("etag")
            return None

    def check_etag(self, component: str, etag: str) -> bool:
        """Check if an ETag matches the current cache.

        Args:
            component: Component name
            etag: ETag to check

        Returns:
            True if ETag matches (cache is still valid)
        """
        current_etag = self.get_etag(component)
        return current_etag is not None and current_etag == etag

    def _generate_etag(self, component: str, timestamp: float) -> str:
        """Generate an ETag for cached data."""
        import hashlib

        data = f"{component}:{self._component_versions[component]}:{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

    def get_cache_headers(self, component: str) -> Dict[str, str]:
        """Get HTTP cache headers for a component.

        Args:
            component: Component name

        Returns:
            Dict of header name -> value
        """
        ttl = DASHBOARD_COMPONENTS.get(component, {}).get("ttl", 30)
        etag = self.get_etag(component)

        headers = {
            "Cache-Control": f"private, max-age={ttl}",
            "X-Cache-Component": component,
            "X-Cache-Version": str(self._component_versions.get(component, 1)),
        }

        if etag:
            headers["ETag"] = f'"{etag}"'

        return headers

    def should_refresh(self, component: str, if_none_match: str = None) -> bool:
        """Check if a component should be refreshed.

        Args:
            component: Component name
            if_none_match: ETag from If-None-Match header

        Returns:
            True if refresh is needed
        """
        # Check ETag first
        if if_none_match:
            # Remove quotes if present
            etag = if_none_match.strip('"')
            if self.check_etag(component, etag):
                return False

        # Check if cache is valid
        cache_entry = self.get_cache(component)
        return cache_entry is None


# Global cache manager instance
_cache_manager: Optional[DashboardCacheManager] = None


def get_cache_manager() -> DashboardCacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = DashboardCacheManager()
    return _cache_manager


def get_component_info() -> Dict:
    """Get information about all dashboard components."""
    return DASHBOARD_COMPONENTS
