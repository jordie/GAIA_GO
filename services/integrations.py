"""
Third-Party Integrations Service

Manages external service connections for:
- Version Control: GitHub, GitLab, Bitbucket
- Issue Tracking: Jira, Linear, Trello
- Communication: Slack, Discord, Microsoft Teams
- CI/CD: Jenkins, CircleCI, GitHub Actions
- Monitoring: PagerDuty, Datadog, Sentry
- Custom Webhooks

Usage:
    from services.integrations import IntegrationService

    service = IntegrationService(db_path)

    # Create a GitHub integration
    integration = service.create_integration(
        name='github-main',
        integration_type='vcs',
        provider='github',
        config={'owner': 'myorg', 'repo': 'myrepo'},
        credentials={'token': 'ghp_xxx'}
    )

    # Test the connection
    result = service.test_connection(integration['id'])

    # Sync data
    service.sync(integration['id'])
"""

import base64
import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Supported integration types
INTEGRATION_TYPES = {
    "vcs": "Version Control System",
    "issues": "Issue Tracking",
    "communication": "Communication/Chat",
    "cicd": "CI/CD Pipeline",
    "monitoring": "Monitoring/Alerting",
    "webhook": "Custom Webhook",
    "storage": "Cloud Storage",
    "auth": "Authentication Provider",
}

# Supported providers by type
PROVIDERS = {
    "vcs": {
        "github": {
            "name": "GitHub",
            "auth_type": "token",
            "base_url": "https://api.github.com",
            "config_schema": {
                "owner": {
                    "type": "string",
                    "required": True,
                    "description": "Repository owner/organization",
                },
                "repo": {
                    "type": "string",
                    "required": False,
                    "description": "Repository name (optional for org-wide)",
                },
                "branch": {
                    "type": "string",
                    "required": False,
                    "default": "main",
                    "description": "Default branch",
                },
            },
            "credential_schema": {
                "token": {
                    "type": "string",
                    "required": True,
                    "sensitive": True,
                    "description": "Personal access token",
                },
            },
            "webhooks": ["push", "pull_request", "issues", "release"],
        },
        "gitlab": {
            "name": "GitLab",
            "auth_type": "token",
            "base_url": "https://gitlab.com/api/v4",
            "config_schema": {
                "project_id": {
                    "type": "string",
                    "required": True,
                    "description": "Project ID or path",
                },
                "branch": {"type": "string", "required": False, "default": "main"},
            },
            "credential_schema": {
                "token": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "bitbucket": {
            "name": "Bitbucket",
            "auth_type": "app_password",
            "base_url": "https://api.bitbucket.org/2.0",
            "config_schema": {
                "workspace": {"type": "string", "required": True},
                "repo_slug": {"type": "string", "required": True},
            },
            "credential_schema": {
                "username": {"type": "string", "required": True},
                "app_password": {"type": "string", "required": True, "sensitive": True},
            },
        },
    },
    "issues": {
        "jira": {
            "name": "Jira",
            "auth_type": "api_token",
            "config_schema": {
                "domain": {
                    "type": "string",
                    "required": True,
                    "description": "Jira domain (e.g., company.atlassian.net)",
                },
                "project_key": {
                    "type": "string",
                    "required": True,
                    "description": "Project key (e.g., PROJ)",
                },
            },
            "credential_schema": {
                "email": {"type": "string", "required": True},
                "api_token": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "linear": {
            "name": "Linear",
            "auth_type": "api_key",
            "base_url": "https://api.linear.app/graphql",
            "config_schema": {
                "team_id": {"type": "string", "required": False},
            },
            "credential_schema": {
                "api_key": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "trello": {
            "name": "Trello",
            "auth_type": "api_key",
            "base_url": "https://api.trello.com/1",
            "config_schema": {
                "board_id": {"type": "string", "required": True},
            },
            "credential_schema": {
                "api_key": {"type": "string", "required": True, "sensitive": True},
                "token": {"type": "string", "required": True, "sensitive": True},
            },
        },
    },
    "communication": {
        "slack": {
            "name": "Slack",
            "auth_type": "webhook",
            "config_schema": {
                "channel": {"type": "string", "required": False, "description": "Default channel"},
                "username": {"type": "string", "required": False, "default": "Architect Bot"},
                "icon_emoji": {"type": "string", "required": False, "default": ":robot_face:"},
            },
            "credential_schema": {
                "webhook_url": {"type": "string", "required": True, "sensitive": True},
                "bot_token": {"type": "string", "required": False, "sensitive": True},
            },
        },
        "discord": {
            "name": "Discord",
            "auth_type": "webhook",
            "config_schema": {
                "username": {"type": "string", "required": False, "default": "Architect"},
            },
            "credential_schema": {
                "webhook_url": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "teams": {
            "name": "Microsoft Teams",
            "auth_type": "webhook",
            "config_schema": {},
            "credential_schema": {
                "webhook_url": {"type": "string", "required": True, "sensitive": True},
            },
        },
    },
    "cicd": {
        "github_actions": {
            "name": "GitHub Actions",
            "auth_type": "token",
            "config_schema": {
                "owner": {"type": "string", "required": True},
                "repo": {"type": "string", "required": True},
            },
            "credential_schema": {
                "token": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "jenkins": {
            "name": "Jenkins",
            "auth_type": "api_token",
            "config_schema": {
                "base_url": {"type": "string", "required": True},
                "job_name": {"type": "string", "required": False},
            },
            "credential_schema": {
                "username": {"type": "string", "required": True},
                "api_token": {"type": "string", "required": True, "sensitive": True},
            },
        },
    },
    "monitoring": {
        "pagerduty": {
            "name": "PagerDuty",
            "auth_type": "integration_key",
            "config_schema": {
                "service_id": {"type": "string", "required": False},
            },
            "credential_schema": {
                "integration_key": {"type": "string", "required": True, "sensitive": True},
            },
        },
        "sentry": {
            "name": "Sentry",
            "auth_type": "dsn",
            "config_schema": {
                "project": {"type": "string", "required": True},
                "organization": {"type": "string", "required": True},
            },
            "credential_schema": {
                "dsn": {"type": "string", "required": True, "sensitive": True},
                "auth_token": {"type": "string", "required": False, "sensitive": True},
            },
        },
    },
    "webhook": {
        "generic": {
            "name": "Generic Webhook",
            "auth_type": "custom",
            "config_schema": {
                "url": {"type": "string", "required": True},
                "method": {"type": "string", "required": False, "default": "POST"},
                "headers": {"type": "object", "required": False},
                "events": {"type": "array", "required": False, "description": "Events to send"},
            },
            "credential_schema": {
                "auth_header": {"type": "string", "required": False, "sensitive": True},
                "secret": {"type": "string", "required": False, "sensitive": True},
            },
        },
    },
}


def encrypt_credentials(credentials: Dict, key: str = None) -> str:
    """Simple obfuscation for credentials (use proper encryption in production)."""
    # In production, use a proper encryption library like cryptography
    data = json.dumps(credentials)
    encoded = base64.b64encode(data.encode()).decode()
    return encoded


def decrypt_credentials(encrypted: str, key: str = None) -> Dict:
    """Decrypt credentials."""
    try:
        decoded = base64.b64decode(encrypted.encode()).decode()
        return json.loads(decoded)
    except Exception:
        return {}


class IntegrationService:
    """Service for managing third-party integrations."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_integration(
        self,
        name: str,
        integration_type: str,
        provider: str,
        config: Dict,
        credentials: Dict = None,
        enabled: bool = True,
        created_by: str = None,
    ) -> Dict:
        """
        Create a new integration.

        Args:
            name: Unique name for the integration
            integration_type: Type (vcs, issues, communication, etc.)
            provider: Provider (github, slack, jira, etc.)
            config: Provider-specific configuration
            credentials: Authentication credentials
            enabled: Whether integration is active
            created_by: User who created the integration

        Returns:
            Created integration record
        """
        # Validate type and provider
        if integration_type not in INTEGRATION_TYPES:
            raise ValueError(f"Invalid integration type: {integration_type}")

        if integration_type not in PROVIDERS:
            raise ValueError(f"No providers available for type: {integration_type}")

        if provider not in PROVIDERS.get(integration_type, {}):
            valid = list(PROVIDERS[integration_type].keys())
            raise ValueError(
                f"Invalid provider '{provider}' for type '{integration_type}'. Valid: {valid}"
            )

        provider_info = PROVIDERS[integration_type][provider]

        # Validate required config fields
        config_schema = provider_info.get("config_schema", {})
        for field, spec in config_schema.items():
            if spec.get("required") and field not in config:
                raise ValueError(f"Missing required config field: {field}")

        # Encrypt credentials if provided
        encrypted_creds = None
        if credentials:
            cred_schema = provider_info.get("credential_schema", {})
            for field, spec in cred_schema.items():
                if spec.get("required") and field not in credentials:
                    raise ValueError(f"Missing required credential: {field}")
            encrypted_creds = encrypt_credentials(credentials)

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO integrations
                    (name, type, provider, config, credentials, enabled, status, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                    (
                        name,
                        integration_type,
                        provider,
                        json.dumps(config),
                        encrypted_creds,
                        enabled,
                        created_by,
                    ),
                )
                conn.commit()
                integration_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"Integration with name '{name}' already exists")

        logger.info(f"Created integration '{name}' ({provider})")
        return self.get_integration(integration_id)

    def get_integration(
        self, integration_id: int, include_credentials: bool = False
    ) -> Optional[Dict]:
        """Get integration by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM integrations WHERE id = ?", (integration_id,)
            ).fetchone()

            if row:
                return self._row_to_dict(row, include_credentials)
            return None

    def get_integration_by_name(
        self, name: str, include_credentials: bool = False
    ) -> Optional[Dict]:
        """Get integration by name."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM integrations WHERE name = ?", (name,)).fetchone()

            if row:
                return self._row_to_dict(row, include_credentials)
            return None

    def list_integrations(
        self,
        integration_type: str = None,
        provider: str = None,
        enabled_only: bool = False,
        include_credentials: bool = False,
    ) -> List[Dict]:
        """List integrations with optional filters."""
        query = "SELECT * FROM integrations WHERE 1=1"
        params = []

        if integration_type:
            query += " AND type = ?"
            params.append(integration_type)
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        if enabled_only:
            query += " AND enabled = 1"

        query += " ORDER BY name"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row, include_credentials) for row in rows]

    def update_integration(self, integration_id: int, **kwargs) -> Optional[Dict]:
        """Update integration settings."""
        allowed = {"name", "config", "credentials", "enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return self.get_integration(integration_id)

        if "config" in updates:
            updates["config"] = json.dumps(updates["config"])
        if "credentials" in updates and updates["credentials"]:
            updates["credentials"] = encrypt_credentials(updates["credentials"])

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [integration_id]

        with self._get_connection() as conn:
            result = conn.execute(f"UPDATE integrations SET {set_clause} WHERE id = ?", values)
            conn.commit()

            if result.rowcount == 0:
                return None

        logger.info(f"Updated integration {integration_id}")
        return self.get_integration(integration_id)

    def delete_integration(self, integration_id: int) -> bool:
        """Delete an integration."""
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM integrations WHERE id = ?", (integration_id,))
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted integration {integration_id}")
                return True
            return False

    def enable_integration(self, integration_id: int) -> Optional[Dict]:
        """Enable an integration."""
        return self.update_integration(integration_id, enabled=True)

    def disable_integration(self, integration_id: int) -> Optional[Dict]:
        """Disable an integration."""
        return self.update_integration(integration_id, enabled=False)

    def test_connection(self, integration_id: int) -> Dict:
        """Test integration connection."""
        integration = self.get_integration(integration_id, include_credentials=True)
        if not integration:
            return {"success": False, "error": "Integration not found"}

        provider = integration["provider"]
        integration_type = integration["type"]
        config = integration["config"]
        credentials = integration.get("credentials", {})

        result = {"success": False, "error": None, "details": {}}

        try:
            if integration_type == "vcs" and provider == "github":
                result = self._test_github(config, credentials)
            elif integration_type == "communication" and provider == "slack":
                result = self._test_slack(config, credentials)
            elif integration_type == "communication" and provider == "discord":
                result = self._test_discord(config, credentials)
            elif integration_type == "webhook" and provider == "generic":
                result = self._test_webhook(config, credentials)
            else:
                result = {
                    "success": True,
                    "message": "Connection test not implemented for this provider",
                }

            # Update status
            status = "connected" if result.get("success") else "error"
            self._update_status(integration_id, status, result.get("error"))

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self._update_status(integration_id, "error", str(e))

        return result

    def _test_github(self, config: Dict, credentials: Dict) -> Dict:
        """Test GitHub connection."""
        token = credentials.get("token")
        if not token:
            return {"success": False, "error": "Missing token"}

        owner = config.get("owner")
        repo = config.get("repo")

        url = (
            f"https://api.github.com/users/{owner}"
            if not repo
            else f"https://api.github.com/repos/{owner}/{repo}"
        )

        req = Request(url)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github.v3+json")

        try:
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                return {
                    "success": True,
                    "details": {
                        "name": data.get("name") or data.get("login"),
                        "url": data.get("html_url"),
                    },
                }
        except HTTPError as e:
            return {"success": False, "error": f"GitHub API error: {e.code}"}
        except URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}

    def _test_slack(self, config: Dict, credentials: Dict) -> Dict:
        """Test Slack webhook."""
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing webhook URL"}

        payload = {
            "text": "Test connection from Architect Dashboard",
            "username": config.get("username", "Architect Bot"),
        }

        req = Request(webhook_url, data=json.dumps(payload).encode())
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=10) as response:
                return {"success": True, "message": "Slack webhook test successful"}
        except HTTPError as e:
            return {"success": False, "error": f"Slack error: {e.code}"}
        except URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}

    def _test_discord(self, config: Dict, credentials: Dict) -> Dict:
        """Test Discord webhook."""
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing webhook URL"}

        payload = {
            "content": "Test connection from Architect Dashboard",
            "username": config.get("username", "Architect"),
        }

        req = Request(webhook_url, data=json.dumps(payload).encode())
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=10) as response:
                return {"success": True, "message": "Discord webhook test successful"}
        except HTTPError as e:
            return {"success": False, "error": f"Discord error: {e.code}"}
        except URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}

    def _test_webhook(self, config: Dict, credentials: Dict) -> Dict:
        """Test generic webhook."""
        url = config.get("url")
        if not url:
            return {"success": False, "error": "Missing webhook URL"}

        method = config.get("method", "POST")
        headers = config.get("headers", {})

        payload = {"test": True, "source": "architect", "timestamp": datetime.now().isoformat()}

        req = Request(
            url, data=json.dumps(payload).encode() if method == "POST" else None, method=method
        )
        req.add_header("Content-Type", "application/json")

        for key, value in headers.items():
            req.add_header(key, value)

        if credentials.get("auth_header"):
            req.add_header("Authorization", credentials["auth_header"])

        try:
            with urlopen(req, timeout=10) as response:
                return {"success": True, "status_code": response.status}
        except HTTPError as e:
            return {"success": False, "error": f"HTTP error: {e.code}"}
        except URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}

    def _update_status(self, integration_id: int, status: str, error: str = None):
        """Update integration status."""
        with self._get_connection() as conn:
            if status == "error" and error:
                conn.execute(
                    """
                    UPDATE integrations
                    SET status = ?, status_message = ?, last_error_at = CURRENT_TIMESTAMP,
                        last_error = ?, error_count = error_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (status, error, error, integration_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE integrations
                    SET status = ?, status_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (status, "Connected" if status == "connected" else None, integration_id),
                )
            conn.commit()

    def send_event(self, integration_id: int, event_type: str, payload: Dict) -> Dict:
        """Send an event to an integration."""
        integration = self.get_integration(integration_id, include_credentials=True)
        if not integration:
            return {"success": False, "error": "Integration not found"}

        if not integration["enabled"]:
            return {"success": False, "error": "Integration is disabled"}

        provider = integration["provider"]
        config = integration["config"]
        credentials = integration.get("credentials", {})

        result = {"success": False}

        try:
            if provider == "slack":
                result = self._send_slack_event(config, credentials, event_type, payload)
            elif provider == "discord":
                result = self._send_discord_event(config, credentials, event_type, payload)
            elif provider == "generic":
                result = self._send_webhook_event(config, credentials, event_type, payload)
            else:
                result = {"success": False, "error": f"Event sending not supported for {provider}"}

            # Log the event
            self._log_event(integration_id, event_type, payload, result)

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self._log_event(integration_id, event_type, payload, result)

        return result

    def _send_slack_event(
        self, config: Dict, credentials: Dict, event_type: str, payload: Dict
    ) -> Dict:
        """Send event to Slack."""
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing webhook URL"}

        slack_payload = {
            "text": payload.get("text", f"Event: {event_type}"),
            "username": config.get("username", "Architect Bot"),
            "icon_emoji": config.get("icon_emoji", ":robot_face:"),
        }

        if payload.get("attachments"):
            slack_payload["attachments"] = payload["attachments"]

        req = Request(webhook_url, data=json.dumps(slack_payload).encode())
        req.add_header("Content-Type", "application/json")

        with urlopen(req, timeout=10):
            return {"success": True}

    def _send_discord_event(
        self, config: Dict, credentials: Dict, event_type: str, payload: Dict
    ) -> Dict:
        """Send event to Discord."""
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing webhook URL"}

        discord_payload = {
            "content": payload.get("text", f"Event: {event_type}"),
            "username": config.get("username", "Architect"),
        }

        if payload.get("embeds"):
            discord_payload["embeds"] = payload["embeds"]

        req = Request(webhook_url, data=json.dumps(discord_payload).encode())
        req.add_header("Content-Type", "application/json")

        with urlopen(req, timeout=10):
            return {"success": True}

    def _send_webhook_event(
        self, config: Dict, credentials: Dict, event_type: str, payload: Dict
    ) -> Dict:
        """Send event to generic webhook."""
        url = config.get("url")
        if not url:
            return {"success": False, "error": "Missing webhook URL"}

        webhook_payload = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": payload,
        }

        method = config.get("method", "POST")
        headers = config.get("headers", {})

        req = Request(url, data=json.dumps(webhook_payload).encode(), method=method)
        req.add_header("Content-Type", "application/json")

        for key, value in headers.items():
            req.add_header(key, value)

        if credentials.get("auth_header"):
            req.add_header("Authorization", credentials["auth_header"])

        with urlopen(req, timeout=10) as response:
            return {"success": True, "status_code": response.status}

    def _log_event(self, integration_id: int, event_type: str, payload: Dict, result: Dict):
        """Log an integration event."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO integration_events
                (integration_id, event_type, payload, processed, result, error)
                VALUES (?, ?, ?, 1, ?, ?)
            """,
                (
                    integration_id,
                    event_type,
                    json.dumps(payload),
                    json.dumps(result) if result.get("success") else None,
                    result.get("error"),
                ),
            )
            conn.commit()

    def get_events(self, integration_id: int, limit: int = 50) -> List[Dict]:
        """Get events for an integration."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM integration_events
                WHERE integration_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (integration_id, limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_stats(self, integration_id: int = None) -> Dict:
        """Get integration statistics."""
        with self._get_connection() as conn:
            if integration_id:
                integration = self.get_integration(integration_id)
                if not integration:
                    return {"error": "Integration not found"}

                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                events_24h = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM integration_events
                    WHERE integration_id = ? AND created_at > ?
                """,
                    (integration_id, yesterday),
                ).fetchone()["count"]

                errors_24h = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM integration_events
                    WHERE integration_id = ? AND created_at > ? AND error IS NOT NULL
                """,
                    (integration_id, yesterday),
                ).fetchone()["count"]

                return {
                    "integration_id": integration_id,
                    "name": integration["name"],
                    "status": integration["status"],
                    "sync_count": integration["sync_count"],
                    "error_count": integration["error_count"],
                    "events_24h": events_24h,
                    "errors_24h": errors_24h,
                    "last_sync": integration["last_sync_at"],
                }
            else:
                total = conn.execute("SELECT COUNT(*) as count FROM integrations").fetchone()[
                    "count"
                ]

                enabled = conn.execute(
                    "SELECT COUNT(*) as count FROM integrations WHERE enabled = 1"
                ).fetchone()["count"]

                by_status = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM integrations
                    GROUP BY status
                """
                ).fetchall()

                by_type = conn.execute(
                    """
                    SELECT type, COUNT(*) as count
                    FROM integrations
                    GROUP BY type
                """
                ).fetchall()

                return {
                    "total": total,
                    "enabled": enabled,
                    "disabled": total - enabled,
                    "by_status": {row["status"]: row["count"] for row in by_status},
                    "by_type": {row["type"]: row["count"] for row in by_type},
                }

    def _row_to_dict(self, row: sqlite3.Row, include_credentials: bool = False) -> Dict:
        """Convert row to dict."""
        d = dict(row)

        # Parse config JSON
        if d.get("config"):
            try:
                d["config"] = json.loads(d["config"])
            except json.JSONDecodeError:
                d["config"] = {}

        # Handle credentials
        if include_credentials and d.get("credentials"):
            d["credentials"] = decrypt_credentials(d["credentials"])
        else:
            # Remove credentials from response
            d.pop("credentials", None)

        # Add provider info
        provider_info = PROVIDERS.get(d["type"], {}).get(d["provider"], {})
        d["provider_name"] = provider_info.get("name", d["provider"])

        return d


# Singleton
_integration_service: Optional[IntegrationService] = None


def get_integration_service(db_path: str = None) -> IntegrationService:
    """Get or create integration service singleton."""
    global _integration_service
    if _integration_service is None:
        if db_path is None:
            raise ValueError("db_path required for first initialization")
        _integration_service = IntegrationService(db_path)
    elif db_path:
        _integration_service.db_path = db_path
    return _integration_service
