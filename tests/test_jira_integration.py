"""
Jira Integration Tests

Tests for the Jira integration service.
"""
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.jira_integration import (
    DEFAULT_PRIORITY_MAPPING,
    DEFAULT_STATUS_MAPPING,
    DEFAULT_TYPE_MAPPING,
    ConflictResolution,
    JiraConfig,
    JiraService,
    SyncDirection,
    SyncResult,
)


class TestJiraServiceInit:
    """Test JiraService initialization."""

    def test_init_with_default_path(self, tmp_path):
        """Service initializes with default path when db exists."""
        db_path = str(tmp_path / "test.db")
        service = JiraService(db_path)
        assert service.db_path == db_path

    def test_init_creates_tables(self, tmp_path):
        """Service creates required tables on init."""
        import sqlite3

        db_path = str(tmp_path / "test.db")
        service = JiraService(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "jira_config" in tables
        assert "jira_sync_mapping" in tables
        assert "jira_sync_log" in tables


class TestJiraServiceConfig:
    """Test Jira configuration methods."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a JiraService with temp database."""
        db_path = str(tmp_path / "test.db")
        return JiraService(db_path)

    def test_is_configured_false_initially(self, service):
        """is_configured returns False when not configured."""
        assert not service.is_configured()

    def test_configure_sets_config(self, service):
        """configure stores configuration."""
        service.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="TEST",
        )
        assert service.is_configured()

    def test_configure_with_base_url(self, service):
        """configure accepts base_url and extracts domain."""
        service.configure(
            base_url="https://company.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="PROJ",
        )
        config = service.get_config()
        assert config["domain"] == "company.atlassian.net"

    def test_get_config_returns_stored_config(self, service):
        """get_config returns stored configuration."""
        service.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="secret",
            project_key="TEST",
        )
        config = service.get_config()

        assert config["domain"] == "test.atlassian.net"
        assert config["email"] == "test@example.com"
        assert config["project_key"] == "TEST"
        # Token should not be in plain text
        assert "api_token" not in config or config.get("api_token") != "secret"

    def test_delete_config_removes_config(self, service):
        """delete_config removes stored configuration."""
        service.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="TEST",
        )
        assert service.is_configured()

        service.delete_config()
        assert not service.is_configured()

    def test_configure_with_custom_mappings(self, service):
        """configure stores custom mappings."""
        custom_status = {"Open": "pending", "Closed": "done"}
        service.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="TEST",
            status_mapping=custom_status,
        )
        config = service.get_config()
        assert config["status_mapping"] == custom_status


class TestJiraServiceMappings:
    """Test sync mapping methods."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a JiraService with temp database."""
        db_path = str(tmp_path / "test.db")
        svc = JiraService(db_path)
        svc.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="TEST",
        )
        return svc

    def test_get_mappings_empty_initially(self, service):
        """get_mappings returns empty list when no mappings exist."""
        mappings = service.get_mappings()
        assert mappings == []

    def test_unlink_by_key(self, service):
        """unlink removes mapping by Jira key."""
        # First add a mapping manually
        conn = service._get_connection()
        conn.execute(
            """
            INSERT INTO jira_sync_mapping
            (jira_issue_key, jira_issue_id, architect_type, architect_id)
            VALUES (?, ?, ?, ?)
        """,
            ("TEST-1", "10001", "bug", 1),
        )
        conn.commit()
        conn.close()

        # Verify it exists
        mappings = service.get_mappings()
        assert len(mappings) == 1

        # Unlink by key
        result = service.unlink("TEST-1")
        assert result is True

        # Verify it's gone
        mappings = service.get_mappings()
        assert len(mappings) == 0

    def test_unlink_by_id(self, service):
        """unlink removes mapping by mapping ID."""
        # Add a mapping
        conn = service._get_connection()
        conn.execute(
            """
            INSERT INTO jira_sync_mapping
            (jira_issue_key, jira_issue_id, architect_type, architect_id)
            VALUES (?, ?, ?, ?)
        """,
            ("TEST-2", "10002", "feature", 5),
        )
        conn.commit()

        # Get the mapping ID
        row = conn.execute(
            "SELECT id FROM jira_sync_mapping WHERE jira_issue_key = ?", ("TEST-2",)
        ).fetchone()
        mapping_id = row[0]
        conn.close()

        # Unlink by ID
        result = service.unlink(mapping_id)
        assert result is True

        # Verify it's gone
        mappings = service.get_mappings()
        assert len(mappings) == 0

    def test_get_mappings_filter_by_type(self, service):
        """get_mappings filters by architect type."""
        conn = service._get_connection()
        conn.execute(
            """
            INSERT INTO jira_sync_mapping
            (jira_issue_key, jira_issue_id, architect_type, architect_id)
            VALUES (?, ?, ?, ?), (?, ?, ?, ?)
        """,
            ("TEST-1", "10001", "bug", 1, "TEST-2", "10002", "feature", 2),
        )
        conn.commit()
        conn.close()

        bugs = service.get_mappings(item_type="bug")
        assert len(bugs) == 1
        assert bugs[0]["jira_issue_key"] == "TEST-1"

        features = service.get_mappings(architect_type="feature")
        assert len(features) == 1
        assert features[0]["jira_issue_key"] == "TEST-2"


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_sync_result_defaults(self):
        """SyncResult has correct defaults."""
        result = SyncResult(success=True, direction="jira_to_architect")
        assert result.created == 0
        assert result.updated == 0
        assert result.errors == []
        assert result.details == []

    def test_sync_result_to_dict(self):
        """SyncResult converts to dict."""
        result = SyncResult(success=True, direction="jira_to_architect", created=5, updated=3)
        data = result.to_dict()
        assert data["success"] is True
        assert data["created"] == 5


class TestDefaultMappings:
    """Test default field mappings."""

    def test_status_mapping_bidirectional(self):
        """Status mapping works in both directions."""
        # Jira -> Architect
        assert DEFAULT_STATUS_MAPPING["To Do"] == "pending"
        assert DEFAULT_STATUS_MAPPING["Done"] == "completed"
        # Architect -> Jira
        assert DEFAULT_STATUS_MAPPING["pending"] == "To Do"
        assert DEFAULT_STATUS_MAPPING["completed"] == "Done"

    def test_priority_mapping(self):
        """Priority mapping works correctly."""
        assert DEFAULT_PRIORITY_MAPPING["High"] == "high"
        assert DEFAULT_PRIORITY_MAPPING["critical"] == "Highest"

    def test_type_mapping(self):
        """Type mapping works correctly."""
        assert DEFAULT_TYPE_MAPPING["Bug"] == "bug"
        assert DEFAULT_TYPE_MAPPING["Story"] == "feature"
        assert DEFAULT_TYPE_MAPPING["feature"] == "Story"


class TestJiraServiceConnection:
    """Test Jira connection methods."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a configured JiraService."""
        db_path = str(tmp_path / "test.db")
        svc = JiraService(db_path)
        svc.configure(
            domain="test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project_key="TEST",
        )
        return svc

    @patch("services.jira_integration.urlopen")
    def test_test_connection_success(self, mock_urlopen, service):
        """test_connection returns success on valid response."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(
            {"displayName": "Test User", "emailAddress": "test@example.com", "accountId": "12345"}
        ).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = service.test_connection()

        assert result["success"] is True
        assert result["user"] == "Test User"

    @patch("services.jira_integration.urlopen")
    def test_test_connection_failure(self, mock_urlopen, service):
        """test_connection returns failure on error."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        result = service.test_connection()

        assert result["success"] is False
        assert "error" in result


class TestJiraConfig:
    """Test JiraConfig dataclass."""

    def test_base_url_property(self):
        """base_url property constructs correct URL."""
        config = JiraConfig(
            domain="company.atlassian.net",
            email="user@company.com",
            api_token="token",
            project_key="PROJ",
        )
        assert config.base_url == "https://company.atlassian.net/rest/api/3"

    def test_auth_header_property(self):
        """auth_header property creates valid Basic auth header."""
        config = JiraConfig(
            domain="company.atlassian.net",
            email="user@company.com",
            api_token="token",
            project_key="PROJ",
        )
        import base64

        expected_creds = base64.b64encode(b"user@company.com:token").decode()
        assert config.auth_header == f"Basic {expected_creds}"

    def test_default_values(self):
        """JiraConfig has correct default values."""
        config = JiraConfig(
            domain="test.atlassian.net",
            email="test@test.com",
            api_token="token",
            project_key="TEST",
        )
        assert config.sync_direction == SyncDirection.BIDIRECTIONAL
        assert config.conflict_resolution == ConflictResolution.NEWER_WINS
        assert config.sync_interval_minutes == 15
        assert "Bug" in config.issue_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
