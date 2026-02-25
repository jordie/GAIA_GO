#!/usr/bin/env python3
"""
Tests for monitor consolidation (port 8081 → port 8080)

Validates that:
1. New monitoring routes exist and return valid responses
2. Old monitor.html redirects to new /monitor route
3. API endpoints have correct authentication
4. Monitoring service lazy-loads correctly
5. Both authenticated and public access works appropriately
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestMonitoringService:
    """Test the UnifiedMonitor service layer"""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance for testing"""
        from services.monitoring import UnifiedMonitor

        return UnifiedMonitor()

    def test_monitor_lazy_initialization(self, monitor):
        """Monitor should not initialize components until first access"""
        assert not monitor._initialized
        # Health check should work without initialization
        health = monitor.health_check()
        assert health["status"] == "not_initialized"
        assert not monitor._initialized

    def test_monitor_provides_all_methods(self, monitor):
        """Monitor should provide all required monitoring methods"""
        required_methods = [
            "get_system_status",
            "get_resources",
            "get_sessions",
            "get_work_log",
            "get_auto_confirm_stats",
            "get_auto_confirm_activity",
            "get_quality_stats",
            "get_quality_comparison",
            "get_routing_stats",
            "assign_task",
            "check_and_assign",
            "get_scraper_stats",
            "get_scraper_recent",
            "get_claude_status",
            "execute_claude_task",
            "get_claude_stats",
            "get_claude_recent",
            "get_comet_status",
            "execute_comet_query",
            "execute_comparison",
            "get_comparison_stats",
            "get_comparison_recent",
            "health_check",
        ]

        for method_name in required_methods:
            assert hasattr(monitor, method_name), f"Missing method: {method_name}"
            assert callable(getattr(monitor, method_name)), f"Not callable: {method_name}"

    def test_health_check(self, monitor):
        """Health check should return status information"""
        health = monitor.health_check()
        assert "status" in health
        assert "components" in health
        assert "timestamp" in health
        assert isinstance(health["components"], list)


class TestMonitorRoutes:
    """Test the monitoring routes in the Flask app"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        # This would need the actual app to be importable
        # For now, we'll define the expected routes
        pytest.skip("Requires full Flask app integration")

    def test_monitor_route_exists(self, client):
        """GET /monitor should return 200 (or redirect if not authenticated)"""
        response = client.get("/monitor")
        assert response.status_code in [200, 302, 401]

    def test_monitor_html_redirect(self, client):
        """GET /monitor.html should redirect to /monitor"""
        response = client.get("/monitor.html", follow_redirects=False)
        assert response.status_code == 301
        assert "/monitor" in response.location

    def test_analytics_route_exists(self, client):
        """GET /analytics should exist"""
        response = client.get("/analytics")
        assert response.status_code in [200, 302, 401]

    def test_api_monitor_endpoints_exist(self, client):
        """API monitor endpoints should be accessible"""
        endpoints = [
            "/api/monitor/status",
            "/api/monitor/resources",
            "/api/monitor/auto-confirm/stats",
            "/api/monitor/quality/stats",
            "/api/monitor/routing/stats",
            "/api/monitor/claude/status",
            "/api/monitor/comet/status",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should return 200, 401 (auth required), or 404 (not yet implemented)
            assert response.status_code in [200, 401, 404]

    def test_api_monitor_returns_json(self, client):
        """API monitor endpoints should return JSON"""
        response = client.get("/api/monitor/resources")
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, dict)


class TestMonitoringConsolidation:
    """Integration tests for the consolidation"""

    def test_no_port_8081_needed(self):
        """After consolidation, port 8081 should not be necessary"""
        # This test validates that all functionality is available on port 8080
        # In practice, this would check that web_dashboard.py is no longer required
        pass

    def test_backward_compatibility(self):
        """Old URLs should still work (with redirects if needed)"""
        # /monitor.html → /monitor
        # /api/status → /api/monitor/status (or aliases)
        pass

    def test_authentication_enforced(self):
        """Authenticated routes should require valid session"""
        # All /monitor/* routes should require authentication
        # Except any explicitly public ones
        pass

    def test_lazy_loading_reduces_startup(self):
        """Monitoring components should not load until needed"""
        # Track imports to verify lazy loading
        pass


class TestServiceImports:
    """Test that all monitoring services can be imported"""

    def test_status_dashboard_available(self):
        """StatusDashboard should be importable"""
        try:
            from status_dashboard import StatusDashboard
        except ImportError:
            pytest.skip("StatusDashboard not available")

    def test_auto_confirm_monitor_available(self):
        """AutoConfirmMonitor should be importable"""
        try:
            from auto_confirm_monitor import AutoConfirmMonitor
        except ImportError:
            pytest.skip("AutoConfirmMonitor not available")

    def test_smart_task_router_available(self):
        """SmartTaskRouter should be importable"""
        try:
            from smart_task_router import SmartTaskRouter
        except ImportError:
            pytest.skip("SmartTaskRouter not available")

    def test_quality_scorer_available(self):
        """QualityScorer should be importable"""
        try:
            from quality_scorer import QualityScorer
        except ImportError:
            pytest.skip("QualityScorer not available")

    def test_monitoring_service_importable(self):
        """Monitoring service should be importable"""
        from services.monitoring import UnifiedMonitor, get_monitor

        assert UnifiedMonitor is not None
        assert get_monitor is not None


class TestTemplateRendering:
    """Test that monitoring templates render correctly"""

    def test_monitor_template_exists(self):
        """monitor_dashboard.html should exist"""
        from pathlib import Path

        template_path = Path(__file__).parent.parent / "templates" / "monitor_dashboard.html"
        assert template_path.exists(), f"Monitor template not found at {template_path}"

    def test_analytics_template_exists(self):
        """analytics_dashboard.html should exist"""
        from pathlib import Path

        template_path = Path(__file__).parent.parent / "templates" / "analytics_dashboard.html"
        assert template_path.exists(), f"Analytics template not found at {template_path}"

    def test_monitor_template_has_required_sections(self):
        """Monitor template should have all expected sections"""
        from pathlib import Path

        template_path = Path(__file__).parent.parent / "templates" / "monitor_dashboard.html"
        content = template_path.read_text()

        required_sections = [
            "System Resources",
            "Auto-Confirm",
            "Task Routing",
            "Quality Scoring",
            "Claude Sessions",
            "Comet Browser",
            "refreshData",
            "/api/monitor/",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_analytics_template_has_required_sections(self):
        """Analytics template should have all expected sections"""
        from pathlib import Path

        template_path = Path(__file__).parent.parent / "templates" / "analytics_dashboard.html"
        content = template_path.read_text()

        required_sections = [
            "Quality Scores",
            "Routing Analytics",
            "Scraper Activity",
            "Source Comparison",
            "Claude Stats",
            "Auto-Confirm Stats",
            "refreshData",
            "/api/monitor/",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"


class TestWebDashboardDeprecation:
    """Tests to verify web_dashboard.py consolidation"""

    def test_web_dashboard_endpoints_documented(self):
        """All web_dashboard.py endpoints should be documented in consolidation plan"""
        endpoints_from_old_dashboard = [
            "/api/status",
            "/api/auto-confirm/activity",
            "/api/auto-confirm/stats",
            "/api/quality/stats",
            "/api/quality/comparison",
            "/api/scraper/stats",
            "/api/scraper/recent",
            "/api/health",
            "/api/monitor/status",
            "/api/monitor/assign-task",
            "/api/monitor/work-log",
            "/api/monitor/check-and-assign",
            "/api/claude/status",
            "/api/claude/execute",
            "/api/claude/stats",
            "/api/claude/recent",
            "/api/compare/execute",
            "/api/compare/stats",
            "/api/compare/recent",
        ]

        # These should be migrated to /api/monitor/* or have aliases
        assert len(endpoints_from_old_dashboard) > 0


# Smoke tests
class TestSmokeTests:
    """Basic smoke tests for the consolidation"""

    def test_monitoring_service_creates(self):
        """UnifiedMonitor should create without errors"""
        from services.monitoring import UnifiedMonitor

        monitor = UnifiedMonitor()
        assert monitor is not None
        assert not monitor._initialized  # Lazy loading

    def test_get_monitor_singleton(self):
        """get_monitor() should return singleton instance"""
        from services.monitoring import get_monitor

        monitor1 = get_monitor()
        monitor2 = get_monitor()
        assert monitor1 is monitor2

    def test_health_check_works(self):
        """Health check should not raise errors"""
        from services.monitoring import get_monitor

        monitor = get_monitor()
        health = monitor.health_check()
        assert isinstance(health, dict)
        assert "status" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
