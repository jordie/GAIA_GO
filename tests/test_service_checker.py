"""
Unit tests for service_checker.py module.

Tests the Service Health Checker Worker that monitors configured services
and reports their status to the dashboard.
"""

import json
import os
import socket
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.service_checker import (
    ServiceCheckerDaemon,
    check_all_services,
    check_http_health,
    check_port_open,
    check_service,
    get_daemon_status,
    load_services_config,
    load_state,
    report_to_dashboard,
    save_state,
    stop_daemon,
)


class TestLoadServicesConfig:
    """Tests for load_services_config function."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid services.json file."""
        config_data = {
            "apps": {"app1": {"health_endpoint": "/health"}},
            "services": {"svc1": {"port": 8080, "app": "app1"}},
            "hosts": {"local": "localhost"},
        }
        config_file = tmp_path / "services.json"
        config_file.write_text(json.dumps(config_data))

        with patch("workers.service_checker.SERVICES_FILE", config_file):
            result = load_services_config()

        assert result == config_data
        assert "apps" in result
        assert "services" in result

    def test_missing_config_file(self, tmp_path):
        """Test handling of missing config file."""
        missing_file = tmp_path / "nonexistent.json"

        with patch("workers.service_checker.SERVICES_FILE", missing_file):
            result = load_services_config()

        assert result == {"apps": {}, "services": {}, "hosts": {}}

    def test_empty_config(self, tmp_path):
        """Test loading empty config file."""
        config_file = tmp_path / "services.json"
        config_file.write_text("{}")

        with patch("workers.service_checker.SERVICES_FILE", config_file):
            result = load_services_config()

        assert result == {}


class TestCheckPortOpen:
    """Tests for check_port_open function."""

    def test_port_open_success(self):
        """Test detecting an open port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0

        with patch("socket.socket", return_value=mock_socket):
            result = check_port_open("localhost", 8080)

        assert result is True
        mock_socket.connect_ex.assert_called_once_with(("localhost", 8080))
        mock_socket.close.assert_called_once()

    def test_port_closed(self):
        """Test detecting a closed port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 111  # Connection refused

        with patch("socket.socket", return_value=mock_socket):
            result = check_port_open("localhost", 9999)

        assert result is False

    def test_port_check_timeout(self):
        """Test port check with custom timeout."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0

        with patch("socket.socket", return_value=mock_socket):
            check_port_open("localhost", 8080, timeout=5.0)

        mock_socket.settimeout.assert_called_once_with(5.0)

    def test_port_check_exception(self):
        """Test handling socket exception."""
        with patch("socket.socket", side_effect=socket.error("Network error")):
            result = check_port_open("localhost", 8080)

        assert result is False


class TestCheckHttpHealth:
    """Tests for check_http_health function."""

    def test_healthy_endpoint(self):
        """Test checking a healthy HTTP endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        with patch("requests.get", return_value=mock_response):
            result = check_http_health("http://localhost:8080/health")

        assert result["reachable"] is True
        assert result["status_code"] == 200
        assert result["response_time_ms"] is not None
        assert result["error"] is None
        assert result["health_data"] == {"status": "ok"}

    def test_unhealthy_endpoint(self):
        """Test checking an unhealthy HTTP endpoint."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("requests.get", return_value=mock_response):
            result = check_http_health("http://localhost:8080/health")

        assert result["reachable"] is True
        assert result["status_code"] == 500

    def test_timeout_error(self):
        """Test handling request timeout."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
            result = check_http_health("http://localhost:8080/health")

        assert result["reachable"] is False
        assert result["error"] == "timeout"

    def test_connection_error(self):
        """Test handling connection refused."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
            result = check_http_health("http://localhost:8080/health")

        assert result["reachable"] is False
        assert result["error"] == "connection_refused"

    def test_generic_exception(self):
        """Test handling generic exception."""
        with patch("requests.get", side_effect=Exception("Unknown error")):
            result = check_http_health("http://localhost:8080/health")

        assert result["reachable"] is False
        assert "Unknown error" in result["error"]


class TestCheckService:
    """Tests for check_service function."""

    @patch("workers.service_checker.check_port_open")
    @patch("workers.service_checker.check_http_health")
    def test_healthy_service(self, mock_http, mock_port):
        """Test checking a healthy service."""
        mock_port.return_value = True
        mock_http.return_value = {"reachable": True, "status_code": 200, "response_time_ms": 50}

        service_config = {"port": 8080, "app": "myapp", "env": "prod", "protocol": "http"}
        app_config = {"health_endpoint": "/health"}

        result = check_service("svc1", service_config, app_config, "localhost")

        assert result["status"] == "healthy"
        assert result["port_open"] is True
        assert result["service_id"] == "svc1"
        assert result["port"] == 8080

    @patch("workers.service_checker.check_port_open")
    def test_service_port_closed(self, mock_port):
        """Test service with closed port."""
        mock_port.return_value = False

        service_config = {"port": 8080, "app": "myapp"}
        app_config = {}

        result = check_service("svc1", service_config, app_config, "localhost")

        assert result["status"] == "down"
        assert result["port_open"] is False

    @patch("workers.service_checker.check_port_open")
    @patch("workers.service_checker.check_http_health")
    def test_service_auth_required(self, mock_http, mock_port):
        """Test service requiring authentication."""
        mock_port.return_value = True
        mock_http.return_value = {"reachable": True, "status_code": 401, "response_time_ms": 30}

        service_config = {"port": 8080, "app": "myapp"}
        app_config = {}

        result = check_service("svc1", service_config, app_config)

        assert result["status"] == "auth_required"

    @patch("workers.service_checker.check_port_open")
    @patch("workers.service_checker.check_http_health")
    def test_service_unreachable(self, mock_http, mock_port):
        """Test service that is unreachable."""
        mock_port.return_value = True
        mock_http.return_value = {
            "reachable": False,
            "status_code": None,
            "error": "connection_refused",
        }

        service_config = {"port": 8080, "app": "myapp"}
        app_config = {}

        result = check_service("svc1", service_config, app_config)

        assert result["status"] == "unreachable"


class TestCheckAllServices:
    """Tests for check_all_services function."""

    @patch("workers.service_checker.load_services_config")
    @patch("workers.service_checker.check_service")
    def test_check_multiple_services(self, mock_check, mock_config):
        """Test checking multiple services."""
        mock_config.return_value = {
            "apps": {"app1": {}},
            "services": {
                "svc1": {"port": 8080, "app": "app1"},
                "svc2": {"port": 8081, "app": "app1"},
            },
        }
        mock_check.side_effect = [
            {"service_id": "svc1", "status": "healthy"},
            {"service_id": "svc2", "status": "down"},
        ]

        result = check_all_services("localhost")

        assert result["summary"]["total"] == 2
        assert result["summary"]["healthy"] == 1
        assert result["summary"]["down"] == 1
        assert "svc1" in result["services"]
        assert "svc2" in result["services"]

    @patch("workers.service_checker.load_services_config")
    def test_empty_services(self, mock_config):
        """Test with no services configured."""
        mock_config.return_value = {"apps": {}, "services": {}}

        result = check_all_services()

        assert result["summary"]["total"] == 0
        assert result["services"] == {}

    @patch("workers.service_checker.load_services_config")
    @patch("workers.service_checker.check_service")
    def test_service_check_exception(self, mock_check, mock_config):
        """Test handling exception during service check."""
        mock_config.return_value = {"apps": {}, "services": {"svc1": {"port": 8080}}}
        mock_check.side_effect = Exception("Check failed")

        result = check_all_services()

        assert "svc1" in result["services"]
        assert result["services"]["svc1"]["status"] == "error"


class TestSaveLoadState:
    """Tests for save_state and load_state functions."""

    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading state."""
        state_file = tmp_path / "state.json"
        state_data = {
            "timestamp": "2024-01-01T00:00:00",
            "services": {"svc1": {"status": "healthy"}},
            "summary": {"total": 1, "healthy": 1},
        }

        with patch("workers.service_checker.STATE_FILE", state_file):
            save_state(state_data)
            loaded = load_state()

        assert loaded == state_data

    def test_load_missing_state(self, tmp_path):
        """Test loading non-existent state file."""
        missing_file = tmp_path / "missing.json"

        with patch("workers.service_checker.STATE_FILE", missing_file):
            result = load_state()

        assert result is None

    def test_save_state_error(self, tmp_path):
        """Test save_state handles write errors gracefully."""
        # Use a directory path instead of file to cause error
        with patch("workers.service_checker.STATE_FILE", tmp_path):
            # Should not raise exception
            save_state({"test": "data"})


class TestReportToDashboard:
    """Tests for report_to_dashboard function."""

    @patch("requests.post")
    def test_successful_report(self, mock_post):
        """Test successful report to dashboard."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        results = {"summary": {"total": 1}}
        report_to_dashboard(results, "http://localhost:8080")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8080/api/services/health-report"

    @patch("requests.post")
    def test_report_connection_error(self, mock_post):
        """Test handling connection error when reporting."""
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError()

        # Should not raise exception
        report_to_dashboard({"summary": {}}, "http://localhost:8080")


class TestServiceCheckerDaemon:
    """Tests for ServiceCheckerDaemon class."""

    def test_daemon_init_default_interval(self):
        """Test daemon initialization with default interval."""
        daemon = ServiceCheckerDaemon()
        assert daemon.check_interval == 60
        assert daemon.running is False

    def test_daemon_init_custom_interval(self):
        """Test daemon initialization with custom interval."""
        daemon = ServiceCheckerDaemon(check_interval=30)
        assert daemon.check_interval == 30

    def test_daemon_signal_handler(self):
        """Test daemon signal handler stops the daemon."""
        daemon = ServiceCheckerDaemon()
        daemon.running = True

        daemon._handle_signal(15, None)

        assert daemon.running is False

    @patch("workers.service_checker.check_all_services")
    @patch("workers.service_checker.save_state")
    @patch("workers.service_checker.report_to_dashboard")
    def test_daemon_single_iteration(self, mock_report, mock_save, mock_check):
        """Test daemon performs check and saves state."""
        mock_check.return_value = {
            "summary": {"total": 1, "healthy": 1, "down": 0, "unhealthy": 0},
            "services": {},
        }

        daemon = ServiceCheckerDaemon(check_interval=1)

        # Run one iteration by starting and quickly stopping
        def stop_after_check(*args):
            daemon.running = False

        mock_save.side_effect = stop_after_check

        daemon.start()

        mock_check.assert_called_once()
        mock_save.assert_called_once()


class TestGetDaemonStatus:
    """Tests for get_daemon_status function."""

    def test_daemon_not_running(self, tmp_path):
        """Test status when daemon is not running."""
        pid_file = tmp_path / "service_checker.pid"

        with patch("workers.service_checker.PID_FILE", pid_file):
            with patch("workers.service_checker.load_state", return_value=None):
                status = get_daemon_status()

        assert status["running"] is False
        assert status["pid"] is None

    def test_daemon_running(self, tmp_path):
        """Test status when daemon is running."""
        pid_file = tmp_path / "service_checker.pid"
        pid_file.write_text(str(os.getpid()))  # Use current PID (will exist)

        with patch("workers.service_checker.PID_FILE", pid_file):
            with patch(
                "workers.service_checker.load_state",
                return_value={
                    "timestamp": "2024-01-01T00:00:00",
                    "summary": {"total": 5, "healthy": 4},
                },
            ):
                status = get_daemon_status()

        assert status["running"] is True
        assert status["pid"] == os.getpid()
        assert status["last_check"] == "2024-01-01T00:00:00"

    def test_stale_pid_file(self, tmp_path):
        """Test handling stale PID file."""
        pid_file = tmp_path / "service_checker.pid"
        pid_file.write_text("99999999")  # Non-existent PID

        with patch("workers.service_checker.PID_FILE", pid_file):
            with patch("workers.service_checker.load_state", return_value=None):
                status = get_daemon_status()

        assert status["running"] is False


class TestStopDaemon:
    """Tests for stop_daemon function."""

    def test_stop_no_pid_file(self, tmp_path):
        """Test stopping when no PID file exists."""
        pid_file = tmp_path / "nonexistent.pid"

        with patch("workers.service_checker.PID_FILE", pid_file):
            result = stop_daemon()

        assert result is False

    @patch("os.kill")
    def test_stop_running_daemon(self, mock_kill, tmp_path):
        """Test stopping a running daemon."""
        pid_file = tmp_path / "service_checker.pid"
        pid_file.write_text("12345")

        with patch("workers.service_checker.PID_FILE", pid_file):
            with patch("time.sleep"):
                result = stop_daemon()

        assert result is True
        mock_kill.assert_called_once_with(12345, 15)  # SIGTERM
        assert not pid_file.exists()

    @patch("os.kill")
    def test_stop_daemon_kill_fails(self, mock_kill, tmp_path):
        """Test stopping daemon when kill fails."""
        pid_file = tmp_path / "service_checker.pid"
        pid_file.write_text("12345")
        mock_kill.side_effect = OSError("No such process")

        with patch("workers.service_checker.PID_FILE", pid_file):
            result = stop_daemon()

        assert result is False


class TestIntegration:
    """Integration tests for service checker."""

    @patch("workers.service_checker.SERVICES_FILE")
    def test_full_check_cycle(self, mock_services_file, tmp_path):
        """Test a full check cycle with mocked services."""
        # Setup config file
        config_file = tmp_path / "services.json"
        config_data = {
            "apps": {"dashboard": {"health_endpoint": "/health"}},
            "services": {
                "dashboard_prod": {
                    "app": "dashboard",
                    "port": 8080,
                    "env": "prod",
                    "protocol": "http",
                }
            },
        }
        config_file.write_text(json.dumps(config_data))

        with patch("workers.service_checker.SERVICES_FILE", config_file):
            with patch("workers.service_checker.check_port_open", return_value=True):
                with patch(
                    "workers.service_checker.check_http_health",
                    return_value={
                        "reachable": True,
                        "status_code": 200,
                        "response_time_ms": 45,
                        "health_data": {"status": "ok"},
                    },
                ):
                    results = check_all_services("localhost")

        assert results["summary"]["total"] == 1
        assert results["summary"]["healthy"] == 1
        assert "dashboard_prod" in results["services"]
        assert results["services"]["dashboard_prod"]["status"] == "healthy"
