"""
Jira Integration Service

Provides bidirectional sync between Architect and Jira:
- Sync Jira issues to Architect tasks/bugs/features
- Push Architect items to Jira
- Map fields between systems
- Track sync status and conflicts

Usage:
    from services.jira_integration import JiraService

    service = JiraService(db_path)

    # Configure connection
    service.configure(
        domain='company.atlassian.net',
        email='user@company.com',
        api_token='xxx',
        project_key='PROJ'
    )

    # Sync issues
    result = service.sync_from_jira()

    # Push task to Jira
    issue = service.push_to_jira(task_id=123)
"""

import base64
import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Sync direction options."""

    JIRA_TO_ARCHITECT = "jira_to_architect"
    ARCHITECT_TO_JIRA = "architect_to_jira"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(Enum):
    """How to resolve sync conflicts."""

    JIRA_WINS = "jira_wins"
    ARCHITECT_WINS = "architect_wins"
    NEWER_WINS = "newer_wins"
    MANUAL = "manual"


@dataclass
class JiraConfig:
    """Jira connection configuration."""

    domain: str
    email: str
    api_token: str
    project_key: str
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: ConflictResolution = ConflictResolution.NEWER_WINS
    sync_interval_minutes: int = 15
    issue_types: List[str] = field(default_factory=lambda: ["Bug", "Task", "Story", "Epic"])
    status_mapping: Dict[str, str] = field(default_factory=dict)
    priority_mapping: Dict[str, str] = field(default_factory=dict)
    custom_field_mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}/rest/api/3"

    @property
    def auth_header(self) -> str:
        credentials = f"{self.email}:{self.api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    direction: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    conflicts: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    details: List[Dict] = field(default_factory=list)  # Detailed info about each item synced
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0

    def to_dict(self) -> Dict:
        return asdict(self)


# Default field mappings
DEFAULT_STATUS_MAPPING = {
    # Jira -> Architect
    "To Do": "pending",
    "In Progress": "in_progress",
    "In Review": "review",
    "Done": "completed",
    "Closed": "closed",
    "Backlog": "backlog",
    # Architect -> Jira (reverse)
    "pending": "To Do",
    "in_progress": "In Progress",
    "review": "In Review",
    "completed": "Done",
    "closed": "Closed",
    "backlog": "Backlog",
}

DEFAULT_PRIORITY_MAPPING = {
    # Jira -> Architect
    "Highest": "critical",
    "High": "high",
    "Medium": "medium",
    "Low": "low",
    "Lowest": "low",
    # Architect -> Jira (reverse)
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

DEFAULT_TYPE_MAPPING = {
    # Jira -> Architect
    "Bug": "bug",
    "Task": "task",
    "Story": "feature",
    "Epic": "feature",
    "Sub-task": "task",
    # Architect -> Jira (reverse)
    "bug": "Bug",
    "task": "Task",
    "feature": "Story",
}


class JiraService:
    """Service for Jira integration."""

    # Default database path
    DEFAULT_DB_PATH = "data/architect.db"

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Try to find the database path
            import os
            from pathlib import Path

            # Check common locations
            possible_paths = [
                os.environ.get("DB_PATH"),
                "data/architect.db",
                str(Path(__file__).parent.parent / "data" / "architect.db"),
            ]
            for p in possible_paths:
                if p and Path(p).exists():
                    db_path = p
                    break
            if not db_path:
                db_path = self.DEFAULT_DB_PATH

        self.db_path = db_path
        self._config: Optional[JiraConfig] = None
        self._ensure_tables()

    def is_configured(self) -> bool:
        """Check if Jira is configured."""
        return self.get_config() is not None

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Ensure required tables exist."""
        conn = self._get_connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jira_config (
                    id INTEGER PRIMARY KEY,
                    domain TEXT NOT NULL,
                    email TEXT NOT NULL,
                    api_token_hash TEXT NOT NULL,
                    api_token_encrypted TEXT NOT NULL,
                    project_key TEXT NOT NULL,
                    sync_direction TEXT DEFAULT 'bidirectional',
                    conflict_resolution TEXT DEFAULT 'newer_wins',
                    sync_interval_minutes INTEGER DEFAULT 15,
                    issue_types TEXT DEFAULT '["Bug","Task","Story","Epic"]',
                    status_mapping TEXT DEFAULT '{}',
                    priority_mapping TEXT DEFAULT '{}',
                    custom_field_mapping TEXT DEFAULT '{}',
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS jira_sync_mapping (
                    id INTEGER PRIMARY KEY,
                    jira_issue_key TEXT UNIQUE NOT NULL,
                    jira_issue_id TEXT NOT NULL,
                    architect_type TEXT NOT NULL,
                    architect_id INTEGER NOT NULL,
                    jira_updated_at TEXT,
                    architect_updated_at TEXT,
                    sync_status TEXT DEFAULT 'synced',
                    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS jira_sync_log (
                    id INTEGER PRIMARY KEY,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created INTEGER DEFAULT 0,
                    updated INTEGER DEFAULT 0,
                    skipped INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    conflicts TEXT DEFAULT '[]',
                    errors TEXT DEFAULT '[]',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_seconds REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_jira_mapping_key ON jira_sync_mapping(jira_issue_key);
                CREATE INDEX IF NOT EXISTS idx_jira_mapping_architect ON jira_sync_mapping(architect_type, architect_id);
            """
            )
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # Configuration
    # =========================================================================

    def configure(
        self,
        domain: str = None,
        email: str = None,
        api_token: str = None,
        project_key: str = None,
        base_url: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Configure Jira connection.

        Args:
            domain: Jira domain (e.g., 'company.atlassian.net')
            email: Jira account email
            api_token: Jira API token
            project_key: Default project key
            base_url: Alternative to domain - full URL like 'https://company.atlassian.net'
            **kwargs: Additional configuration options
        """
        # Handle base_url as alternative to domain
        if base_url and not domain:
            # Extract domain from base_url
            import re

            match = re.match(r"https?://([^/]+)", base_url)
            if match:
                domain = match.group(1)
            else:
                domain = base_url.rstrip("/")

        if not all([domain, email, api_token, project_key]):
            raise ValueError("domain, email, api_token, and project_key are required")

        # Encrypt/hash token for storage
        token_hash = hashlib.sha256(api_token.encode()).hexdigest()
        # Simple encoding - in production use proper encryption
        token_encrypted = base64.b64encode(api_token.encode()).decode()

        conn = self._get_connection()
        try:
            # Check if config exists
            existing = conn.execute("SELECT id FROM jira_config LIMIT 1").fetchone()

            config_data = {
                "domain": domain,
                "email": email,
                "api_token_hash": token_hash,
                "api_token_encrypted": token_encrypted,
                "project_key": project_key,
                "sync_direction": kwargs.get("sync_direction", "bidirectional"),
                "conflict_resolution": kwargs.get("conflict_resolution", "newer_wins"),
                "sync_interval_minutes": kwargs.get("sync_interval_minutes", 15),
                "issue_types": json.dumps(
                    kwargs.get("issue_types", ["Bug", "Task", "Story", "Epic"])
                ),
                "status_mapping": json.dumps(kwargs.get("status_mapping", {})),
                "priority_mapping": json.dumps(kwargs.get("priority_mapping", {})),
                "custom_field_mapping": json.dumps(kwargs.get("custom_field_mapping", {})),
                "enabled": 1,
                "updated_at": datetime.now().isoformat(),
            }

            if existing:
                # Update existing
                set_clause = ", ".join(f"{k} = ?" for k in config_data.keys())
                conn.execute(
                    f"UPDATE jira_config SET {set_clause} WHERE id = ?",
                    list(config_data.values()) + [existing["id"]],
                )
            else:
                # Insert new
                cols = ", ".join(config_data.keys())
                placeholders = ", ".join(["?"] * len(config_data))
                conn.execute(
                    f"INSERT INTO jira_config ({cols}) VALUES ({placeholders})",
                    list(config_data.values()),
                )

            conn.commit()

            # Load config
            self._load_config()

            return {
                "success": True,
                "domain": domain,
                "project_key": project_key,
                "message": "Jira configuration saved",
            }
        finally:
            conn.close()

    def _load_config(self) -> Optional[JiraConfig]:
        """Load configuration from database."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM jira_config WHERE enabled = 1 LIMIT 1").fetchone()
            if not row:
                return None

            # Decrypt token
            api_token = base64.b64decode(row["api_token_encrypted"]).decode()

            self._config = JiraConfig(
                domain=row["domain"],
                email=row["email"],
                api_token=api_token,
                project_key=row["project_key"],
                sync_direction=SyncDirection(row["sync_direction"]),
                conflict_resolution=ConflictResolution(row["conflict_resolution"]),
                sync_interval_minutes=row["sync_interval_minutes"],
                issue_types=json.loads(row["issue_types"]),
                status_mapping=json.loads(row["status_mapping"]) or DEFAULT_STATUS_MAPPING,
                priority_mapping=json.loads(row["priority_mapping"]) or DEFAULT_PRIORITY_MAPPING,
                custom_field_mapping=json.loads(row["custom_field_mapping"]),
            )
            return self._config
        finally:
            conn.close()

    def get_config(self) -> Optional[Dict]:
        """Get current configuration (without sensitive data)."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM jira_config WHERE enabled = 1 LIMIT 1").fetchone()
            if not row:
                return None

            return {
                "domain": row["domain"],
                "email": row["email"],
                "project_key": row["project_key"],
                "sync_direction": row["sync_direction"],
                "conflict_resolution": row["conflict_resolution"],
                "sync_interval_minutes": row["sync_interval_minutes"],
                "issue_types": json.loads(row["issue_types"]),
                "status_mapping": json.loads(row["status_mapping"]),
                "priority_mapping": json.loads(row["priority_mapping"]),
                "custom_field_mapping": json.loads(row["custom_field_mapping"]),
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    def delete_config(self) -> bool:
        """Delete Jira configuration."""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM jira_config")
            conn.commit()
            self._config = None
            return True
        finally:
            conn.close()

    # =========================================================================
    # Jira API
    # =========================================================================

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make request to Jira API."""
        if not self._config:
            self._load_config()
        if not self._config:
            raise ValueError("Jira not configured")

        url = f"{self._config.base_url}{endpoint}"

        headers = {
            "Authorization": self._config.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        body = json.dumps(data).encode() if data else None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"Jira API error: {e.code} - {error_body}")
            raise Exception(f"Jira API error: {e.code} - {error_body}")
        except URLError as e:
            logger.error(f"Jira connection error: {e}")
            raise Exception(f"Jira connection error: {e}")

    def test_connection(self) -> Dict[str, Any]:
        """Test Jira connection."""
        try:
            # Get current user
            result = self._make_request("GET", "/myself")
            return {
                "success": True,
                "user": result.get("displayName"),
                "email": result.get("emailAddress"),
                "account_id": result.get("accountId"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_project(self) -> Dict[str, Any]:
        """Get Jira project details."""
        if not self._config:
            self._load_config()
        if not self._config:
            raise ValueError("Jira not configured")

        result = self._make_request("GET", f"/project/{self._config.project_key}")
        return {
            "key": result.get("key"),
            "name": result.get("name"),
            "description": result.get("description"),
            "lead": result.get("lead", {}).get("displayName"),
            "issue_types": [
                {"id": it["id"], "name": it["name"]} for it in result.get("issueTypes", [])
            ],
        }

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get a single Jira issue."""
        result = self._make_request("GET", f"/issue/{issue_key}")
        return self._parse_jira_issue(result)

    def search_issues(
        self, jql: str = None, max_results: int = 100, start_at: int = 0
    ) -> List[Dict]:
        """Search Jira issues."""
        if not self._config:
            self._load_config()
        if not self._config:
            raise ValueError("Jira not configured")

        if not jql:
            jql = f"project = {self._config.project_key} ORDER BY updated DESC"

        params = f"?jql={jql}&maxResults={max_results}&startAt={start_at}"
        result = self._make_request("GET", f"/search{params}")

        return [self._parse_jira_issue(issue) for issue in result.get("issues", [])]

    def create_issue(
        self,
        summary: str,
        issue_type: str = "Task",
        description: str = None,
        priority: str = None,
        labels: List[str] = None,
        custom_fields: Dict = None,
    ) -> Dict[str, Any]:
        """Create a new Jira issue."""
        if not self._config:
            self._load_config()
        if not self._config:
            raise ValueError("Jira not configured")

        fields = {
            "project": {"key": self._config.project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                ],
            }

        if priority:
            fields["priority"] = {"name": priority}

        if labels:
            fields["labels"] = labels

        if custom_fields:
            fields.update(custom_fields)

        result = self._make_request("POST", "/issue", {"fields": fields})

        return {
            "key": result.get("key"),
            "id": result.get("id"),
            "self": result.get("self"),
        }

    def update_issue(self, issue_key: str, fields: Dict) -> Dict[str, Any]:
        """Update a Jira issue."""
        self._make_request("PUT", f"/issue/{issue_key}", {"fields": fields})
        return {"success": True, "key": issue_key}

    def _parse_jira_issue(self, issue: Dict) -> Dict[str, Any]:
        """Parse Jira issue to standard format."""
        fields = issue.get("fields", {})

        # Parse description
        description = ""
        desc_content = fields.get("description")
        if desc_content and isinstance(desc_content, dict):
            # ADF format
            description = self._extract_text_from_adf(desc_content)
        elif isinstance(desc_content, str):
            description = desc_content

        return {
            "key": issue.get("key"),
            "id": issue.get("id"),
            "summary": fields.get("summary"),
            "description": description,
            "issue_type": fields.get("issuetype", {}).get("name"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
            "assignee": fields.get("assignee", {}).get("displayName")
            if fields.get("assignee")
            else None,
            "reporter": fields.get("reporter", {}).get("displayName")
            if fields.get("reporter")
            else None,
            "labels": fields.get("labels", []),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "resolution": fields.get("resolution", {}).get("name")
            if fields.get("resolution")
            else None,
        }

    def _extract_text_from_adf(self, adf: Dict) -> str:
        """Extract plain text from Atlassian Document Format."""
        text_parts = []

        def extract(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    text_parts.append(node.get("text", ""))
                for child in node.get("content", []):
                    extract(child)
            elif isinstance(node, list):
                for item in node:
                    extract(item)

        extract(adf)
        return " ".join(text_parts)

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def sync_from_jira(self, since: datetime = None, issue_types: List[str] = None) -> SyncResult:
        """Sync issues from Jira to Architect."""
        result = SyncResult(
            success=True, direction="jira_to_architect", started_at=datetime.now().isoformat()
        )
        start_time = time.time()

        try:
            if not self._config:
                self._load_config()
            if not self._config:
                raise ValueError("Jira not configured")

            # Build JQL
            jql_parts = [f"project = {self._config.project_key}"]

            types = issue_types or self._config.issue_types
            if types:
                type_list = ", ".join(f'"{t}"' for t in types)
                jql_parts.append(f"issuetype IN ({type_list})")

            if since:
                jql_parts.append(f"updated >= '{since.strftime('%Y-%m-%d')}'")

            jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

            # Fetch issues
            issues = self.search_issues(jql=jql, max_results=500)

            conn = self._get_connection()
            try:
                for issue in issues:
                    try:
                        sync_status = self._sync_issue_to_architect(conn, issue)
                        if sync_status == "created":
                            result.created += 1
                        elif sync_status == "updated":
                            result.updated += 1
                        elif sync_status == "skipped":
                            result.skipped += 1
                        elif sync_status == "conflict":
                            result.conflicts.append(
                                {"jira_key": issue["key"], "reason": "Update conflict"}
                            )
                    except Exception as e:
                        result.failed += 1
                        result.errors.append(f"{issue['key']}: {str(e)}")

                conn.commit()
            finally:
                conn.close()

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = time.time() - start_time

        # Log sync
        self._log_sync(result)

        return result

    def _sync_issue_to_architect(self, conn: sqlite3.Connection, issue: Dict) -> str:
        """Sync a single issue to Architect."""
        # Check existing mapping
        mapping = conn.execute(
            "SELECT * FROM jira_sync_mapping WHERE jira_issue_key = ?", (issue["key"],)
        ).fetchone()

        # Determine Architect type
        jira_type = issue["issue_type"]
        architect_type = DEFAULT_TYPE_MAPPING.get(jira_type, "task")

        # Map fields
        status = self._config.status_mapping.get(
            issue["status"], DEFAULT_STATUS_MAPPING.get(issue["status"], "pending")
        )
        priority = (
            self._config.priority_mapping.get(
                issue["priority"], DEFAULT_PRIORITY_MAPPING.get(issue["priority"], "medium")
            )
            if issue["priority"]
            else "medium"
        )

        if mapping:
            # Update existing
            architect_id = mapping["architect_id"]

            # Check for conflicts
            if self._config.conflict_resolution == ConflictResolution.MANUAL:
                if mapping["jira_updated_at"] != issue["updated"]:
                    return "conflict"

            # Update based on type
            if architect_type == "bug":
                conn.execute(
                    """
                    UPDATE bugs SET
                        title = ?, description = ?, status = ?, severity = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (issue["summary"], issue["description"], status, priority, architect_id),
                )
            elif architect_type == "feature":
                conn.execute(
                    """
                    UPDATE features SET
                        title = ?, description = ?, status = ?, priority = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (issue["summary"], issue["description"], status, priority, architect_id),
                )
            else:  # task
                conn.execute(
                    """
                    UPDATE task_queue SET
                        title = ?, description = ?, status = ?, priority = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (issue["summary"], issue["description"], status, priority, architect_id),
                )

            # Update mapping
            conn.execute(
                """
                UPDATE jira_sync_mapping SET
                    jira_updated_at = ?, last_synced_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (issue["updated"], mapping["id"]),
            )

            return "updated"
        else:
            # Create new
            if architect_type == "bug":
                cursor = conn.execute(
                    """
                    INSERT INTO bugs (title, description, status, severity, source)
                    VALUES (?, ?, ?, ?, 'jira')
                """,
                    (issue["summary"], issue["description"], status, priority),
                )
                architect_id = cursor.lastrowid
            elif architect_type == "feature":
                cursor = conn.execute(
                    """
                    INSERT INTO features (title, description, status, priority, source)
                    VALUES (?, ?, ?, ?, 'jira')
                """,
                    (issue["summary"], issue["description"], status, priority),
                )
                architect_id = cursor.lastrowid
            else:  # task
                cursor = conn.execute(
                    """
                    INSERT INTO task_queue (title, description, status, priority, source)
                    VALUES (?, ?, ?, ?, 'jira')
                """,
                    (issue["summary"], issue["description"], status, priority),
                )
                architect_id = cursor.lastrowid

            # Create mapping
            conn.execute(
                """
                INSERT INTO jira_sync_mapping
                (jira_issue_key, jira_issue_id, architect_type, architect_id, jira_updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (issue["key"], issue["id"], architect_type, architect_id, issue["updated"]),
            )

            return "created"

    def push_to_jira(self, item_type: str, item_id: int) -> Dict[str, Any]:
        """Push an Architect item to Jira."""
        if not self._config:
            self._load_config()
        if not self._config:
            raise ValueError("Jira not configured")

        conn = self._get_connection()
        try:
            # Get item
            if item_type == "bug":
                item = conn.execute("SELECT * FROM bugs WHERE id = ?", (item_id,)).fetchone()
                jira_type = "Bug"
            elif item_type == "feature":
                item = conn.execute("SELECT * FROM features WHERE id = ?", (item_id,)).fetchone()
                jira_type = "Story"
            else:  # task
                item = conn.execute("SELECT * FROM task_queue WHERE id = ?", (item_id,)).fetchone()
                jira_type = "Task"

            if not item:
                raise ValueError(f"{item_type} {item_id} not found")

            # Check existing mapping
            mapping = conn.execute(
                "SELECT * FROM jira_sync_mapping WHERE architect_type = ? AND architect_id = ?",
                (item_type, item_id),
            ).fetchone()

            # Map priority
            priority = item.get("priority") or item.get("severity") or "medium"
            jira_priority = self._config.priority_mapping.get(
                priority, DEFAULT_PRIORITY_MAPPING.get(priority, "Medium")
            )

            if mapping:
                # Update existing issue
                fields = {
                    "summary": item["title"],
                    "priority": {"name": jira_priority},
                }
                if item.get("description"):
                    fields["description"] = {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": item["description"]}],
                            }
                        ],
                    }

                self.update_issue(mapping["jira_issue_key"], fields)

                # Update mapping
                conn.execute(
                    """
                    UPDATE jira_sync_mapping SET
                        architect_updated_at = ?, last_synced_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (datetime.now().isoformat(), mapping["id"]),
                )
                conn.commit()

                return {"success": True, "action": "updated", "jira_key": mapping["jira_issue_key"]}
            else:
                # Create new issue
                result = self.create_issue(
                    summary=item["title"],
                    issue_type=jira_type,
                    description=item.get("description"),
                    priority=jira_priority,
                    labels=["architect-sync"],
                )

                # Create mapping
                conn.execute(
                    """
                    INSERT INTO jira_sync_mapping
                    (jira_issue_key, jira_issue_id, architect_type, architect_id, architect_updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (result["key"], result["id"], item_type, item_id, datetime.now().isoformat()),
                )
                conn.commit()

                return {"success": True, "action": "created", "jira_key": result["key"]}
        finally:
            conn.close()

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status and statistics."""
        conn = self._get_connection()
        try:
            # Get mapping counts
            mappings = conn.execute(
                """
                SELECT architect_type, COUNT(*) as count
                FROM jira_sync_mapping
                GROUP BY architect_type
            """
            ).fetchall()

            # Get recent sync logs
            logs = conn.execute(
                """
                SELECT * FROM jira_sync_log
                ORDER BY started_at DESC
                LIMIT 10
            """
            ).fetchall()

            # Get last sync
            last_sync = logs[0] if logs else None

            return {
                "configured": self._config is not None,
                "mappings": {row["architect_type"]: row["count"] for row in mappings},
                "total_mapped": sum(row["count"] for row in mappings),
                "last_sync": {
                    "direction": last_sync["direction"],
                    "status": last_sync["status"],
                    "created": last_sync["created"],
                    "updated": last_sync["updated"],
                    "completed_at": last_sync["completed_at"],
                }
                if last_sync
                else None,
                "recent_syncs": [dict(row) for row in logs],
            }
        finally:
            conn.close()

    def get_mappings(
        self, architect_type: str = None, item_type: str = None, limit: int = 100
    ) -> List[Dict]:
        """Get sync mappings.

        Args:
            architect_type: Filter by architect type ('feature', 'bug', 'milestone')
            item_type: Alias for architect_type
            limit: Max number of mappings to return
        """
        # item_type is an alias for architect_type
        filter_type = architect_type or item_type

        conn = self._get_connection()
        try:
            query = "SELECT * FROM jira_sync_mapping"
            params = []

            if filter_type:
                query += " WHERE architect_type = ?"
                params.append(filter_type)

            query += " ORDER BY last_synced_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def unlink(self, identifier) -> bool:
        """Remove sync mapping for an issue.

        Args:
            identifier: Either jira_key (str) or mapping_id (int)

        Returns:
            True if a mapping was deleted, False otherwise
        """
        conn = self._get_connection()
        try:
            if isinstance(identifier, int):
                # Delete by mapping ID
                cursor = conn.execute("DELETE FROM jira_sync_mapping WHERE id = ?", (identifier,))
            else:
                # Delete by Jira key
                cursor = conn.execute(
                    "DELETE FROM jira_sync_mapping WHERE jira_issue_key = ?", (identifier,)
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _log_sync(self, result: SyncResult):
        """Log sync result to database."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO jira_sync_log
                (direction, status, created, updated, skipped, failed, conflicts, errors, started_at, completed_at, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    result.direction,
                    "success" if result.success else "failed",
                    result.created,
                    result.updated,
                    result.skipped,
                    result.failed,
                    json.dumps(result.conflicts),
                    json.dumps(result.errors),
                    result.started_at,
                    result.completed_at,
                    result.duration_seconds,
                ),
            )
            conn.commit()
        finally:
            conn.close()


# Singleton instance
_jira_service: Optional[JiraService] = None


def get_jira_service(db_path: str = None) -> JiraService:
    """Get or create Jira service instance."""
    global _jira_service
    if _jira_service is None:
        if db_path is None:
            from pathlib import Path

            db_path = str(Path(__file__).parent.parent / "data" / "prod" / "architect.db")
        _jira_service = JiraService(db_path)
    return _jira_service
