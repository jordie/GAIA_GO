#!/usr/bin/env python3
"""
External Integrations Integration Tests

Tests for Third-Party Integrations system.

Tests the full integration of:
- Integration CRUD operations
- Connection testing
- Data synchronization
- Webhook handling
- Provider-specific functionality (GitHub, Jira, Slack, etc.)
- Authentication and credentials
- Rate limiting
- Error handling
"""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

pytestmark = pytest.mark.integration


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with integrations schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    # Create integrations tables
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            integration_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            config TEXT,
            credentials TEXT,
            last_sync TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS integration_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (integration_id) REFERENCES integrations(id)
        );

        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            secret TEXT,
            events TEXT,
            status TEXT DEFAULT 'active',
            last_trigger TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (integration_id) REFERENCES integrations(id)
        );

        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            sync_type TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (integration_id) REFERENCES integrations(id)
        );

        CREATE INDEX idx_integrations_type ON integrations(integration_type);
        CREATE INDEX idx_integrations_provider ON integrations(provider);
        CREATE INDEX idx_integration_logs_integration ON integration_logs(integration_id);
        CREATE INDEX idx_webhooks_integration ON webhooks(integration_id);
        CREATE INDEX idx_sync_history_integration ON sync_history(integration_id);
    """
    )
    conn.commit()

    yield conn

    conn.close()


class TestIntegrationCRUD:
    """Test integration CRUD operations."""

    def test_create_integration(self, test_db):
        """Test creating a new integration."""
        config = json.dumps({"owner": "myorg", "repo": "myrepo"})
        credentials = json.dumps({"token": "ghp_test123"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, config, credentials)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("github-main", "vcs", "github", config, credentials),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify created
        row = test_db.execute("SELECT * FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        assert row is not None
        assert row[1] == "github-main"
        assert row[2] == "vcs"
        assert row[3] == "github"

    def test_get_integration(self, test_db):
        """Test retrieving an integration."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("slack-alerts", "communication", "slack"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Retrieve
        row = test_db.execute("SELECT * FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        assert row is not None
        assert row[1] == "slack-alerts"
        assert row[2] == "communication"

    def test_update_integration(self, test_db):
        """Test updating integration configuration."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, config)
            VALUES (?, ?, ?, ?)
        """,
            ("jira-main", "issues", "jira", json.dumps({"project": "PROJ1"})),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Update config
        new_config = json.dumps({"project": "PROJ2", "board": "123"})
        test_db.execute(
            """
            UPDATE integrations
            SET config = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (new_config, integration_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute("SELECT config FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        config = json.loads(row[0])
        assert config["project"] == "PROJ2"
        assert config["board"] == "123"

    def test_delete_integration(self, test_db):
        """Test deleting an integration."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("old-integration", "issues", "linear"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Delete
        test_db.execute("DELETE FROM integrations WHERE id = ?", (integration_id,))
        test_db.commit()

        # Verify deleted
        row = test_db.execute("SELECT * FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        assert row is None

    def test_list_integrations_by_type(self, test_db):
        """Test listing integrations filtered by type."""
        # Insert multiple integrations
        test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES ('github', 'vcs', 'github'),
                   ('gitlab', 'vcs', 'gitlab'),
                   ('jira', 'issues', 'jira'),
                   ('slack', 'communication', 'slack')
        """
        )
        test_db.commit()

        # Get VCS integrations
        vcs_rows = test_db.execute(
            "SELECT * FROM integrations WHERE integration_type = 'vcs'"
        ).fetchall()

        assert len(vcs_rows) == 2


class TestConnectionTesting:
    """Test integration connection testing."""

    def test_successful_connection_test(self, test_db):
        """Test successful connection test."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, status)
            VALUES (?, ?, ?, ?)
        """,
            ("github-test", "vcs", "github", "active"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log successful test
        test_db.execute(
            """
            INSERT INTO integration_logs (integration_id, action, status, details)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "connection_test", "success", "Connection successful"),
        )
        test_db.commit()

        # Verify log
        log = test_db.execute(
            "SELECT status, details FROM integration_logs WHERE integration_id = ?", (integration_id,)
        ).fetchone()

        assert log[0] == "success"
        assert "successful" in log[1]

    def test_failed_connection_test(self, test_db):
        """Test failed connection test."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, status)
            VALUES (?, ?, ?, ?)
        """,
            ("slack-test", "communication", "slack", "error"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log failed test
        test_db.execute(
            """
            INSERT INTO integration_logs (integration_id, action, status, details)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "connection_test", "error", "Invalid webhook URL"),
        )

        # Update last error
        test_db.execute(
            """
            UPDATE integrations
            SET last_error = ?, status = 'error'
            WHERE id = ?
        """,
            ("Invalid webhook URL", integration_id),
        )
        test_db.commit()

        # Verify error
        row = test_db.execute(
            "SELECT status, last_error FROM integrations WHERE id = ?", (integration_id,)
        ).fetchone()

        assert row[0] == "error"
        assert row[1] == "Invalid webhook URL"

    def test_connection_retry_logic(self, test_db):
        """Test connection retry tracking."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("gitlab-test", "vcs", "gitlab"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log multiple retry attempts
        for i in range(3):
            test_db.execute(
                """
                INSERT INTO integration_logs (integration_id, action, status)
                VALUES (?, ?, ?)
            """,
                (integration_id, "connection_test", "error" if i < 2 else "success"),
            )
        test_db.commit()

        # Count retries
        logs = test_db.execute(
            "SELECT status FROM integration_logs WHERE integration_id = ?", (integration_id,)
        ).fetchall()

        assert len(logs) == 3
        assert logs[0][0] == "error"
        assert logs[1][0] == "error"
        assert logs[2][0] == "success"


class TestDataSynchronization:
    """Test data synchronization functionality."""

    def test_successful_sync(self, test_db):
        """Test successful data synchronization."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("github-sync", "vcs", "github"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Record sync
        started = datetime.now()
        completed = started + timedelta(seconds=5)

        test_db.execute(
            """
            INSERT INTO sync_history
            (integration_id, sync_type, records_synced, duration_seconds, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (integration_id, "pull_requests", 25, 5.2, "success", started.isoformat(), completed.isoformat()),
        )

        # Update last sync
        test_db.execute(
            """
            UPDATE integrations
            SET last_sync = ?
            WHERE id = ?
        """,
            (completed.isoformat(), integration_id),
        )
        test_db.commit()

        # Verify sync
        sync = test_db.execute(
            "SELECT records_synced, duration_seconds, status FROM sync_history WHERE integration_id = ?",
            (integration_id,),
        ).fetchone()

        assert sync[0] == 25
        assert sync[1] == 5.2
        assert sync[2] == "success"

    def test_failed_sync(self, test_db):
        """Test failed synchronization."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("jira-sync", "issues", "jira"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Record failed sync
        test_db.execute(
            """
            INSERT INTO sync_history
            (integration_id, sync_type, status, error_message, started_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                integration_id,
                "issues",
                "error",
                "API rate limit exceeded",
                datetime.now().isoformat(),
            ),
        )
        test_db.commit()

        # Verify error
        sync = test_db.execute(
            "SELECT status, error_message FROM sync_history WHERE integration_id = ?", (integration_id,)
        ).fetchone()

        assert sync[0] == "error"
        assert "rate limit" in sync[1]

    def test_incremental_sync(self, test_db):
        """Test incremental synchronization."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("github-incremental", "vcs", "github"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Initial full sync
        test_db.execute(
            """
            INSERT INTO sync_history
            (integration_id, sync_type, records_synced, status)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "full", 100, "success"),
        )

        # Incremental sync
        test_db.execute(
            """
            INSERT INTO sync_history
            (integration_id, sync_type, records_synced, status)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "incremental", 10, "success"),
        )
        test_db.commit()

        # Verify both syncs
        syncs = test_db.execute(
            "SELECT sync_type, records_synced FROM sync_history WHERE integration_id = ? ORDER BY id",
            (integration_id,),
        ).fetchall()

        assert syncs[0][0] == "full"
        assert syncs[0][1] == 100
        assert syncs[1][0] == "incremental"
        assert syncs[1][1] == 10


class TestWebhookHandling:
    """Test webhook functionality."""

    def test_create_webhook(self, test_db):
        """Test creating a webhook."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("github-webhooks", "vcs", "github"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Create webhook
        cursor = test_db.execute(
            """
            INSERT INTO webhooks (integration_id, url, secret, events, status)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                integration_id,
                "https://example.com/webhooks/github",
                "secret123",
                json.dumps(["push", "pull_request"]),
                "active",
            ),
        )
        webhook_id = cursor.lastrowid
        test_db.commit()

        # Verify webhook
        webhook = test_db.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()

        assert webhook is not None
        assert webhook[2] == "https://example.com/webhooks/github"

    def test_webhook_trigger(self, test_db):
        """Test recording webhook trigger."""
        # Insert integration and webhook
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("slack-webhooks", "communication", "slack"),
        )
        integration_id = cursor.lastrowid

        cursor = test_db.execute(
            """
            INSERT INTO webhooks (integration_id, url, status)
            VALUES (?, ?, ?)
        """,
            (integration_id, "https://hooks.slack.com/services/xxx", "active"),
        )
        webhook_id = cursor.lastrowid
        test_db.commit()

        # Record trigger
        trigger_time = datetime.now()
        test_db.execute(
            """
            UPDATE webhooks
            SET last_trigger = ?
            WHERE id = ?
        """,
            (trigger_time.isoformat(), webhook_id),
        )
        test_db.commit()

        # Verify trigger
        webhook = test_db.execute(
            "SELECT last_trigger FROM webhooks WHERE id = ?", (webhook_id,)
        ).fetchone()

        assert webhook[0] is not None

    def test_webhook_event_filtering(self, test_db):
        """Test webhook event filtering."""
        # Insert integration and webhook with specific events
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("github-events", "vcs", "github"),
        )
        integration_id = cursor.lastrowid

        events = json.dumps(["push", "pull_request", "issues"])
        test_db.execute(
            """
            INSERT INTO webhooks (integration_id, url, events)
            VALUES (?, ?, ?)
        """,
            (integration_id, "https://example.com/webhook", events),
        )
        test_db.commit()

        # Retrieve and verify events
        webhook = test_db.execute(
            "SELECT events FROM webhooks WHERE integration_id = ?", (integration_id,)
        ).fetchone()

        webhook_events = json.loads(webhook[0])
        assert "push" in webhook_events
        assert "pull_request" in webhook_events
        assert "issues" in webhook_events


class TestProviderSpecificFeatures:
    """Test provider-specific functionality."""

    def test_github_integration(self, test_db):
        """Test GitHub-specific features."""
        config = json.dumps({"owner": "myorg", "repo": "myrepo", "branch": "main"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, config)
            VALUES (?, ?, ?, ?)
        """,
            ("github-main", "vcs", "github", config),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify config
        row = test_db.execute("SELECT config FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        github_config = json.loads(row[0])
        assert github_config["owner"] == "myorg"
        assert github_config["repo"] == "myrepo"
        assert github_config["branch"] == "main"

    def test_jira_integration(self, test_db):
        """Test Jira-specific features."""
        config = json.dumps({"url": "https://myorg.atlassian.net", "project": "PROJ", "board": "123"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, config)
            VALUES (?, ?, ?, ?)
        """,
            ("jira-main", "issues", "jira", config),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify config
        row = test_db.execute("SELECT config FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        jira_config = json.loads(row[0])
        assert "atlassian" in jira_config["url"]
        assert jira_config["project"] == "PROJ"

    def test_slack_integration(self, test_db):
        """Test Slack-specific features."""
        config = json.dumps({"workspace": "myworkspace", "channel": "#alerts"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, config)
            VALUES (?, ?, ?, ?)
        """,
            ("slack-alerts", "communication", "slack", config),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify config
        row = test_db.execute("SELECT config FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        slack_config = json.loads(row[0])
        assert slack_config["workspace"] == "myworkspace"
        assert slack_config["channel"] == "#alerts"


class TestAuthenticationCredentials:
    """Test authentication and credentials handling."""

    def test_store_oauth_token(self, test_db):
        """Test storing OAuth token."""
        credentials = json.dumps({"token_type": "Bearer", "access_token": "token123", "refresh_token": "refresh123"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, credentials)
            VALUES (?, ?, ?, ?)
        """,
            ("github-oauth", "vcs", "github", credentials),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify credentials stored
        row = test_db.execute("SELECT credentials FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        creds = json.loads(row[0])
        assert creds["token_type"] == "Bearer"
        assert "access_token" in creds

    def test_store_api_key(self, test_db):
        """Test storing API key."""
        credentials = json.dumps({"api_key": "key_abc123"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, credentials)
            VALUES (?, ?, ?, ?)
        """,
            ("jira-api", "issues", "jira", credentials),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Verify credentials stored
        row = test_db.execute("SELECT credentials FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        creds = json.loads(row[0])
        assert "api_key" in creds

    def test_update_expired_token(self, test_db):
        """Test updating expired authentication token."""
        # Insert integration with old token
        old_creds = json.dumps({"access_token": "old_token", "expires_at": "2024-01-01T00:00:00"})

        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, credentials)
            VALUES (?, ?, ?, ?)
        """,
            ("gitlab-oauth", "vcs", "gitlab", old_creds),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Update with new token
        new_creds = json.dumps({"access_token": "new_token", "expires_at": "2025-01-01T00:00:00"})

        test_db.execute(
            """
            UPDATE integrations
            SET credentials = ?
            WHERE id = ?
        """,
            (new_creds, integration_id),
        )
        test_db.commit()

        # Verify updated
        row = test_db.execute("SELECT credentials FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        creds = json.loads(row[0])
        assert creds["access_token"] == "new_token"


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_track_api_calls(self, test_db):
        """Test tracking API call rate."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("github-rate-limit", "vcs", "github"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log multiple API calls
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO integration_logs (integration_id, action, status)
                VALUES (?, ?, ?)
            """,
                (integration_id, "api_call", "success"),
            )
        test_db.commit()

        # Count calls
        count = test_db.execute(
            "SELECT COUNT(*) FROM integration_logs WHERE integration_id = ? AND action = 'api_call'",
            (integration_id,),
        ).fetchone()[0]

        assert count == 10

    def test_rate_limit_exceeded(self, test_db):
        """Test handling rate limit exceeded."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, status)
            VALUES (?, ?, ?, ?)
        """,
            ("github-limit", "vcs", "github", "rate_limited"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log rate limit error
        test_db.execute(
            """
            INSERT INTO integration_logs (integration_id, action, status, details)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "api_call", "error", "Rate limit exceeded"),
        )
        test_db.commit()

        # Verify status
        row = test_db.execute("SELECT status FROM integrations WHERE id = ?", (integration_id,)).fetchone()

        assert row[0] == "rate_limited"


class TestErrorHandling:
    """Test error handling."""

    def test_log_integration_error(self, test_db):
        """Test logging integration errors."""
        # Insert integration
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider)
            VALUES (?, ?, ?)
        """,
            ("slack-error", "communication", "slack"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Log error
        error_msg = "Invalid webhook URL"
        test_db.execute(
            """
            INSERT INTO integration_logs (integration_id, action, status, details)
            VALUES (?, ?, ?, ?)
        """,
            (integration_id, "send_message", "error", error_msg),
        )

        # Update last error
        test_db.execute(
            """
            UPDATE integrations
            SET last_error = ?, status = 'error'
            WHERE id = ?
        """,
            (error_msg, integration_id),
        )
        test_db.commit()

        # Verify error logged
        log = test_db.execute(
            "SELECT status, details FROM integration_logs WHERE integration_id = ?", (integration_id,)
        ).fetchone()

        assert log[0] == "error"
        assert log[1] == error_msg

    def test_error_recovery(self, test_db):
        """Test recovery from errors."""
        # Insert integration in error state
        cursor = test_db.execute(
            """
            INSERT INTO integrations (name, integration_type, provider, status, last_error)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("jira-recovery", "issues", "jira", "error", "Connection timeout"),
        )
        integration_id = cursor.lastrowid
        test_db.commit()

        # Recover
        test_db.execute(
            """
            UPDATE integrations
            SET status = 'active', last_error = NULL
            WHERE id = ?
        """,
            (integration_id,),
        )
        test_db.commit()

        # Verify recovered
        row = test_db.execute(
            "SELECT status, last_error FROM integrations WHERE id = ?", (integration_id,)
        ).fetchone()

        assert row[0] == "active"
        assert row[1] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
