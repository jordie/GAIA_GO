#!/usr/bin/env python3
"""
Unified Monitoring Service

Consolidates all system monitoring, task routing, quality scoring,
and integration functionality from web_dashboard.py into a reusable service layer.

This service is lazy-loaded by app.py to minimize startup time.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UnifiedMonitor:
    """
    Unified interface for all monitoring functionality.
    Lazily initializes monitoring components on first access.
    """

    def __init__(self):
        self._initialized = False
        self._components = {}

    def _ensure_initialized(self):
        """Initialize monitoring components on first use."""
        if self._initialized:
            return

        try:
            from auto_confirm_monitor import AutoConfirmMonitor
            from claude_auto_integration import ClaudeIntegration
            from comet_auto_integration import CometIntegration
            from perplexity_scraper import PerplexityScraper
            from quality_scorer import QualityScorer
            from result_comparator import ResultComparator
            from smart_task_router import SmartTaskRouter
            from status_dashboard import StatusDashboard

            self._components = {
                "status": StatusDashboard(),
                "auto_confirm": AutoConfirmMonitor(),
                "router": SmartTaskRouter(),
                "scorer": QualityScorer(),
                "comparator": ResultComparator(),
                "scraper": PerplexityScraper(),
                "claude": ClaudeIntegration(),
                "comet": CometIntegration(),
            }

            # Optional session monitor
            try:
                from scripts.foundation_session_monitor import FoundationSessionMonitor

                self._components["session_monitor"] = FoundationSessionMonitor()
            except ImportError:
                logger.debug("Foundation session monitor not available")

            self._initialized = True
            logger.info("Monitoring components initialized")

        except ImportError as e:
            logger.error(f"Failed to initialize monitoring components: {e}")
            raise

    # ========== System Status APIs ==========

    def get_system_status(self) -> Dict[str, Any]:
        """Get combined system status from all monitoring sources."""
        self._ensure_initialized()

        try:
            status = self._components["status"].get_status()
            ac_data = (
                self._components["auto_confirm"].get_activity_summary()
                if "auto_confirm" in self._components
                else {}
            )

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "system": status,
                "auto_confirm": ac_data,
                "healthy": True,
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"timestamp": datetime.utcnow().isoformat(), "error": str(e), "healthy": False}

    def get_resources(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        self._ensure_initialized()
        return self._components["status"].get_resources() if "status" in self._components else {}

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Get tmux session information."""
        self._ensure_initialized()
        return self._components["status"].get_sessions() if "status" in self._components else []

    def get_work_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent work log entries."""
        self._ensure_initialized()
        return (
            self._components["status"].get_work_log(limit) if "status" in self._components else []
        )

    # ========== Auto-Confirm APIs ==========

    def get_auto_confirm_stats(self) -> Dict[str, Any]:
        """Get auto-confirm statistics."""
        self._ensure_initialized()
        return (
            self._components["auto_confirm"].get_stats()
            if "auto_confirm" in self._components
            else {}
        )

    def get_auto_confirm_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent auto-confirm activity."""
        self._ensure_initialized()
        return (
            self._components["auto_confirm"].get_recent_activity(limit)
            if "auto_confirm" in self._components
            else []
        )

    # ========== Quality & Scoring APIs ==========

    def get_quality_stats(self) -> Dict[str, Any]:
        """Get quality scoring statistics."""
        self._ensure_initialized()
        return self._components["scorer"].get_stats() if "scorer" in self._components else {}

    def get_quality_comparison(self) -> Dict[str, Any]:
        """Get comparison of quality across sources."""
        self._ensure_initialized()
        return (
            self._components["comparator"].get_comparison()
            if "comparator" in self._components
            else {}
        )

    # ========== Task Routing APIs ==========

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get smart task routing statistics."""
        self._ensure_initialized()
        return self._components["router"].get_stats() if "router" in self._components else {}

    def assign_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assign a task via smart routing."""
        self._ensure_initialized()
        if "router" not in self._components:
            return {"error": "Router not available"}

        try:
            return self._components["router"].assign(task_data)
        except Exception as e:
            logger.error(f"Error assigning task: {e}")
            return {"error": str(e)}

    def check_and_assign(self) -> Dict[str, Any]:
        """Run check and assign cycle."""
        self._ensure_initialized()
        if "router" not in self._components:
            return {"error": "Router not available"}

        try:
            return self._components["router"].check_and_assign()
        except Exception as e:
            logger.error(f"Error in check_and_assign: {e}")
            return {"error": str(e)}

    # ========== Scraper APIs ==========

    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get scraper statistics."""
        self._ensure_initialized()
        return self._components["scraper"].get_stats() if "scraper" in self._components else {}

    def get_scraper_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent scraper results."""
        self._ensure_initialized()
        return (
            self._components["scraper"].get_recent(limit) if "scraper" in self._components else []
        )

    # ========== Claude Integration APIs ==========

    def get_claude_status(self) -> Dict[str, Any]:
        """Get Claude session status."""
        self._ensure_initialized()
        return self._components["claude"].get_status() if "claude" in self._components else {}

    def execute_claude_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task on Claude."""
        self._ensure_initialized()
        if "claude" not in self._components:
            return {"error": "Claude integration not available"}

        try:
            return self._components["claude"].execute(task_data)
        except Exception as e:
            logger.error(f"Error executing Claude task: {e}")
            return {"error": str(e)}

    def get_claude_stats(self) -> Dict[str, Any]:
        """Get Claude execution statistics."""
        self._ensure_initialized()
        return self._components["claude"].get_stats() if "claude" in self._components else {}

    def get_claude_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent Claude executions."""
        self._ensure_initialized()
        return self._components["claude"].get_recent(limit) if "claude" in self._components else []

    # ========== Comet Integration APIs ==========

    def get_comet_status(self) -> Dict[str, Any]:
        """Get Comet browser status."""
        self._ensure_initialized()
        return self._components["comet"].get_status() if "comet" in self._components else {}

    def execute_comet_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query on Comet."""
        self._ensure_initialized()
        if "comet" not in self._components:
            return {"error": "Comet integration not available"}

        try:
            return self._components["comet"].execute(query_data)
        except Exception as e:
            logger.error(f"Error executing Comet query: {e}")
            return {"error": str(e)}

    # ========== Result Comparison APIs ==========

    def execute_comparison(self, comparison_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute result comparison across sources."""
        self._ensure_initialized()
        if "comparator" not in self._components:
            return {"error": "Comparator not available"}

        try:
            return self._components["comparator"].execute(comparison_data)
        except Exception as e:
            logger.error(f"Error executing comparison: {e}")
            return {"error": str(e)}

    def get_comparison_stats(self) -> Dict[str, Any]:
        """Get comparison statistics."""
        self._ensure_initialized()
        return (
            self._components["comparator"].get_stats() if "comparator" in self._components else {}
        )

    def get_comparison_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent comparisons."""
        self._ensure_initialized()
        return (
            self._components["comparator"].get_recent(limit)
            if "comparator" in self._components
            else []
        )

    # ========== Health Check ==========

    def health_check(self) -> Dict[str, Any]:
        """Check monitoring service health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "components": list(self._components.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global instance - lazy loaded on first access
_monitor_instance: Optional[UnifiedMonitor] = None


def get_monitor() -> UnifiedMonitor:
    """Get or create the global monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = UnifiedMonitor()
    return _monitor_instance
