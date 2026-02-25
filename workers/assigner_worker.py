#!/usr/bin/env python3
"""
Assigner Worker

A background worker that:
- Monitors a message queue for incoming prompts
    - Detects available/idle tmux sessions (Claude/Codex/Ollama)
    - Assigns prompts to available sessions via tmux send-keys
- Tracks assignments and collects responses
- Handles timeouts, retries, and session targeting

Usage:
    python3 assigner_worker.py                # Run worker in foreground
    python3 assigner_worker.py --daemon       # Run as daemon
    python3 assigner_worker.py --stop         # Stop daemon
    python3 assigner_worker.py --status       # Check status

    # Send prompts
    python3 assigner_worker.py --send "Fix bug"           # Queue prompt
    python3 assigner_worker.py --send "Fix" --priority 5  # High priority
    python3 assigner_worker.py --send "Fix" --target dev  # Target session
    python3 assigner_worker.py --send "Fix" --provider codex  # Target provider
    # Provider with fallback
    python3 assigner_worker.py --send "Fix" --provider claude --fallback codex,ollama
    # Provider preference order
    python3 assigner_worker.py --send "Fix" --providers codex,claude
    python3 assigner_worker.py --send "Fix" --timeout 60  # 60 min timeout

    # Retry/Reassign
    python3 assigner_worker.py --retry 42                 # Retry prompt #42
    python3 assigner_worker.py --retry-all                # Retry all failed
    python3 assigner_worker.py --reassign 42 --to dev     # Reassign to session

    # Cleanup
    python3 assigner_worker.py --clear                    # Clear completed
    python3 assigner_worker.py --clear --days 7           # Clear old prompts

    # List
    python3 assigner_worker.py --sessions                 # List sessions
    python3 assigner_worker.py --prompts                  # List prompts
"""

import json
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths
WORKER_DIR = Path(__file__).parent
BASE_DIR = WORKER_DIR.parent
DATA_DIR = BASE_DIR / "data"
ASSIGNER_DIR = DATA_DIR / "assigner"

# Add parent directory to Python path for services import
sys.path.insert(0, str(BASE_DIR))

# Worker configuration
PID_FILE = Path("/tmp/architect_assigner_worker.pid")
STATE_FILE = Path("/tmp/architect_assigner_worker_state.json")
LOG_FILE = Path("/tmp/architect_assigner_worker.log")

# Create assigner data directory
ASSIGNER_DIR.mkdir(parents=True, exist_ok=True)

# Assigner database
ASSIGNER_DB = ASSIGNER_DIR / "assigner.db"

# Configuration file
CONFIG_FILE = BASE_DIR / "config" / "session_assigner.yaml"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("AssignerWorker")


class PromptStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"


@dataclass
class Prompt:
    id: int
    content: str
    source: str  # 'terminal', 'api', 'dashboard'
    priority: int
    status: str
    assigned_session: Optional[str]
    created_at: str
    assigned_at: Optional[str]
    completed_at: Optional[str]
    response: Optional[str]
    error: Optional[str]
    metadata: Optional[str]  # JSON
    target_session: Optional[str] = None  # Preferred session
    target_provider: Optional[str] = None  # Preferred provider (claude/codex/ollama)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SessionInfo:
    name: str
    status: str
    last_activity: str
    current_task_id: Optional[int]
    working_dir: Optional[str]
    is_claude: bool
    provider: str


SUPPORTED_PROVIDERS = ("claude", "codex", "ollama", "comet")

# Sessions to EXCLUDE from task assignment (coordination/monitoring sessions)
EXCLUDED_SESSIONS = {
    "architect",  # High-level coordination session (this one)
    # claude_orchestrator receives ALL tasks for coordination and delegation
    "arch_dev",  # Development/testing session
}


# ============================================================================
# Provider Swapping Configuration
# ============================================================================


def load_provider_config() -> Dict[str, Any]:
    """Load provider configuration from YAML file."""
    try:
        import yaml

        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f)
                return config.get("providers", {})
    except Exception as e:
        logger.warning(f"Failed to load provider config: {e}")
    return {}


def get_preferred_provider_for_session(session_name: str) -> str:
    """Get the preferred provider for a session based on tier configuration.

    Returns 'ollama' for lower-level workers, 'claude' for high-level sessions.
    """
    config = load_provider_config()

    # Check tier assignments
    tiers = config.get("tiers", {})
    for tier_name, tier_config in tiers.items():
        sessions = tier_config.get("sessions", [])
        if session_name in sessions:
            return tier_config.get("provider", "ollama")

    # Check pattern-based assignments
    patterns = config.get("patterns", [])
    session_lower = session_name.lower()
    for pattern_config in patterns:
        pattern = pattern_config.get("pattern", "")
        if pattern and pattern in session_lower:
            return pattern_config.get("provider", "ollama")

    # Default to config default or ollama
    return config.get("default", "ollama")


# High-level sessions that should ALWAYS use Claude (not swappable)
HIGH_LEVEL_SESSIONS = {
    "architect",
    "foundation",
    "inspector",
    "manager1",
    "manager2",
    "manager3",
    "claude_architect",
    "claude_wrapper",
}

# Lower-level worker sessions that CAN be swapped to Ollama
SWAPPABLE_SESSIONS = {
    "dev_worker1",
    "dev_worker2",
    "dev_worker3",
    "claude_edu_worker1",
    "claude_task_worker1",
    "claude_concurrent_worker1",
    "qa_tester1",
    "qa_tester2",
    "qa_tester3",
    "mcp_worker1",
    "mcp_worker2",
}


# ============================================================================
# Environment Integration (Multi-Environment System)
# ============================================================================

# Path to basic_edu_apps_final env_manager
ENV_MANAGER_PATH = BASE_DIR / "env_manager.py"

# Environment routing rules based on project type
ENV_ROUTING_RULES = {
    "ui_improvement": {
        "requires_env": True,
        "preferred_sessions": ["claude_comet", "codex"],
        "port_range": (6001, 6010),
        "auto_create_env": True,
        "merge_via_pr": True,
    },
    "performance_optimization": {
        "requires_env": True,
        "preferred_sessions": ["codex", "dev_worker1"],
        "port_range": (6001, 6010),
        "auto_create_env": True,
        "merge_via_pr": True,
    },
    "bug_fix": {
        "requires_env": False,  # Use production
        "preferred_sessions": ["dev_worker2", "codex"],
        "urgent": True,
        "merge_via_pr": False,
    },
    "feature_development": {
        "requires_env": True,
        "preferred_sessions": ["dev_worker1", "dev_worker2"],
        "port_range": (6001, 6010),
        "auto_create_env": True,
        "merge_via_pr": True,
    },
    "infrastructure": {
        "requires_env": False,  # Use main branch
        "preferred_sessions": ["architect", "dev_worker1"],
        "urgent": False,
        "merge_via_pr": True,
    },
}


def get_environment_info(env_name: str) -> Optional[Dict]:
    """Get environment information using env_manager.py"""
    if not ENV_MANAGER_PATH.exists():
        logger.warning(f"env_manager.py not found at {ENV_MANAGER_PATH}")
        return None

    try:
        result = subprocess.run(
            ["python3", str(ENV_MANAGER_PATH), "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            envs = json.loads(result.stdout)
            for env in envs:
                if env["name"] == env_name:
                    return env
    except Exception as e:
        logger.error(f"Failed to get environment info: {e}")

    return None


def create_environment(env_name: str) -> bool:
    """Create a new environment using env_manager.py"""
    if not ENV_MANAGER_PATH.exists():
        logger.warning(f"env_manager.py not found at {ENV_MANAGER_PATH}")
        return False

    try:
        logger.info(f"Creating environment: {env_name}")
        result = subprocess.run(
            ["python3", str(ENV_MANAGER_PATH), "create", env_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Environment {env_name} created successfully")
            return True
        else:
            logger.error(f"Failed to create environment: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error creating environment: {e}")
        return False


def start_environment(env_name: str) -> bool:
    """Start an environment using env_manager.py"""
    if not ENV_MANAGER_PATH.exists():
        logger.warning(f"env_manager.py not found at {ENV_MANAGER_PATH}")
        return False

    try:
        logger.info(f"Starting environment: {env_name}")
        result = subprocess.run(
            ["python3", str(ENV_MANAGER_PATH), "start", env_name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info(f"Environment {env_name} started successfully")
            return True
        else:
            logger.error(f"Failed to start environment: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error starting environment: {e}")
        return False


def route_task_to_environment(content: str, metadata: Optional[Dict] = None) -> Dict:
    """
    Route task to appropriate environment based on project type.

    Returns updated metadata with environment information.

    DISABLED: Environment creation causing failures (port exhaustion, JSON parsing)
    """
    if not metadata:
        metadata = {}

    # DISABLED: Skip environment routing to prevent failures
    metadata["environment_required"] = False
    return metadata

    project_type = metadata.get("project_type")
    if not project_type:
        # Try to infer project type from content
        content_lower = content.lower()
        if "ui" in content_lower or "interface" in content_lower or "design" in content_lower:
            project_type = "ui_improvement"
        elif (
            "performance" in content_lower
            or "optimize" in content_lower
            or "speed" in content_lower
        ):
            project_type = "performance_optimization"
        elif "bug" in content_lower or "fix" in content_lower or "error" in content_lower:
            project_type = "bug_fix"
        elif "feature" in content_lower or "add" in content_lower:
            project_type = "feature_development"
        else:
            project_type = "feature_development"  # Default

        metadata["project_type"] = project_type

    routing = ENV_ROUTING_RULES.get(project_type, {})
    metadata["routing_rules"] = routing

    # Check if environment is required
    if not routing.get("requires_env"):
        logger.info(f"Task type '{project_type}' does not require environment (production work)")
        metadata["environment_required"] = False
        return metadata

    metadata["environment_required"] = True

    # Get or create environment name
    env_name = metadata.get("environment")
    if not env_name:
        # Auto-generate environment name from content
        # Extract app name if mentioned (reading, math, piano, typing, etc.)
        content_lower = content.lower()
        app_name = None
        for app in ["reading", "math", "piano", "typing", "comprehension", "spelling"]:
            if app in content_lower:
                app_name = app
                break

        if app_name:
            env_name = f"{app_name}-{project_type.replace('_', '-')}"
        else:
            # Use generic name with timestamp
            import time

            env_name = f"{project_type}-{int(time.time())}"

        metadata["environment"] = env_name

    # Check if environment exists
    env_info = get_environment_info(env_name)

    if not env_info:
        # Create environment if auto_create is enabled
        if routing.get("auto_create_env"):
            if create_environment(env_name):
                env_info = get_environment_info(env_name)
            else:
                logger.error(f"Failed to create environment {env_name}")
                return metadata
        else:
            logger.info(f"Environment {env_name} does not exist and auto_create is disabled")
            return metadata

    # Start environment if stopped
    if env_info and env_info.get("status") == "stopped":
        logger.info(f"Environment {env_name} is stopped, starting it...")
        start_environment(env_name)
        # Refresh environment info
        env_info = get_environment_info(env_name)

    # Add environment details to metadata
    if env_info:
        metadata["environment_info"] = {
            "name": env_info.get("name"),
            "port": env_info.get("port"),
            "url": env_info.get("url"),
            "branch": env_info.get("branch"),
            "status": env_info.get("status"),
            "pid": env_info.get("pid"),
        }
        logger.info(f"Task routed to environment: {env_name} (port {env_info.get('port')})")

    return metadata


class AssignerDatabase:
    """Database manager for the assigner queue."""

    def __init__(self, db_path: Path = ASSIGNER_DB):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self):
        """Initialize the assigner database."""
        with self._get_conn() as conn:
            conn.executescript(
                """
                -- Prompt queue
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'api',
                    priority INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    assigned_session TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    response TEXT,
                    error TEXT,
                    metadata TEXT,
                    target_session TEXT,
                    target_provider TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    timeout_minutes INTEGER DEFAULT 30
                );

                -- Session tracking
                CREATE TABLE IF NOT EXISTS sessions (
                    name TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'unknown',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id INTEGER,
                    working_dir TEXT,
                    is_claude INTEGER DEFAULT 0,
                    provider TEXT,
                    last_output TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (current_task_id) REFERENCES prompts(id)
                );

                -- Assignment history
                CREATE TABLE IF NOT EXISTS assignment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id INTEGER NOT NULL,
                    session_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT,
                    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(status);
                CREATE INDEX IF NOT EXISTS idx_prompts_priority
                    ON prompts(priority DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
            """
            )

            # Migrate existing tables - add new columns if missing
            for column_sql in [
                (
                    "target_session",
                    "ALTER TABLE prompts ADD COLUMN target_session TEXT",
                ),
                (
                    "target_provider",
                    "ALTER TABLE prompts ADD COLUMN target_provider TEXT",
                ),
                (
                    "retry_count",
                    "ALTER TABLE prompts ADD COLUMN retry_count INTEGER DEFAULT 0",
                ),
                (
                    "max_retries",
                    "ALTER TABLE prompts ADD COLUMN max_retries INTEGER DEFAULT 3",
                ),
                (
                    "timeout_minutes",
                    "ALTER TABLE prompts ADD COLUMN timeout_minutes INTEGER DEFAULT 30",
                ),
            ]:
                column_name, alter_sql = column_sql
                try:
                    conn.execute(f"SELECT {column_name} FROM prompts LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute(alter_sql)

            try:
                conn.execute("SELECT provider FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE sessions ADD COLUMN provider TEXT")

            # Phase 1 Context Management: Add context tracking columns
            for column_sql in [
                ("current_dir", "ALTER TABLE sessions ADD COLUMN current_dir TEXT"),
                ("git_branch", "ALTER TABLE sessions ADD COLUMN git_branch TEXT"),
                (
                    "last_context_update",
                    "ALTER TABLE sessions ADD COLUMN last_context_update TIMESTAMP",
                ),
            ]:
                column_name, alter_sql = column_sql
                try:
                    conn.execute(f"SELECT {column_name} FROM sessions LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute(alter_sql)
                    logger.info(f"Added column {column_name} to sessions table")

            # Phase 2 Context Management: Add env_vars tracking
            try:
                conn.execute("SELECT env_vars FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE sessions ADD COLUMN env_vars TEXT")
                logger.info("Added column env_vars to sessions table (Phase 2)")

    def add_prompt(
        self,
        content: str,
        source: str = "api",
        priority: int = 0,
        metadata: Optional[Dict] = None,
        target_session: Optional[str] = None,
        target_provider: Optional[str] = None,
        timeout_minutes: int = 30,
    ) -> int:
        """Add a new prompt to the queue."""
        if target_provider and target_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {target_provider}")
        if metadata:
            fallback_providers = metadata.get("fallback_providers") or []
            preferred_providers = metadata.get("preferred_providers") or []
            for provider in list(fallback_providers) + list(preferred_providers):
                if provider not in SUPPORTED_PROVIDERS:
                    raise ValueError(f"Unsupported provider: {provider}")
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO prompts (
                    content, source, priority, metadata,
                    target_session, target_provider, timeout_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    content,
                    source,
                    priority,
                    json.dumps(metadata) if metadata else None,
                    target_session,
                    target_provider,
                    timeout_minutes,
                ),
            )
            return cursor.lastrowid

    def get_pending_prompts(self, limit: int = 10) -> List[Dict]:
        """Get pending prompts ordered by priority."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompts
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()
            prompts = []
            for r in rows:
                prompt = dict(r)
                if prompt.get("metadata"):
                    try:
                        prompt["metadata"] = json.loads(prompt["metadata"])
                    except json.JSONDecodeError:
                        prompt["metadata"] = {}
                prompts.append(prompt)
            return prompts

    def get_prompt(self, prompt_id: int) -> Optional[Dict]:
        """Get a specific prompt."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
            return dict(row) if row else None

    def update_prompt_status(
        self,
        prompt_id: int,
        status: str,
        session: Optional[str] = None,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Update prompt status."""
        with self._get_conn() as conn:
            updates = ["status = ?"]
            params = [status]

            if session:
                updates.append("assigned_session = ?")
                params.append(session)
                if status == PromptStatus.ASSIGNED:
                    updates.append("assigned_at = CURRENT_TIMESTAMP")

            if response:
                updates.append("response = ?")
                params.append(response)

            if error:
                updates.append("error = ?")
                params.append(error)

            if status in (PromptStatus.COMPLETED, PromptStatus.FAILED):
                updates.append("completed_at = CURRENT_TIMESTAMP")

            params.append(prompt_id)
            conn.execute(
                f"""
                UPDATE prompts SET {', '.join(updates)} WHERE id = ?
            """,
                params,
            )

    def update_session(
        self,
        name: str,
        status: str,
        is_claude: bool = False,
        working_dir: Optional[str] = None,
        current_task_id: Optional[int] = None,
        last_output: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """Update or insert session info."""
        resolved_provider = provider
        if not resolved_provider and is_claude:
            resolved_provider = "claude"
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    name, status, is_claude, working_dir, current_task_id,
                    last_output, provider, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    status = excluded.status,
                    is_claude = excluded.is_claude,
                    working_dir = COALESCE(excluded.working_dir, sessions.working_dir),
                    current_task_id = excluded.current_task_id,
                    last_output = COALESCE(excluded.last_output, sessions.last_output),
                    provider = COALESCE(excluded.provider, sessions.provider),
                    last_activity = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    name,
                    status,
                    1 if is_claude else 0,
                    working_dir,
                    current_task_id,
                    last_output,
                    resolved_provider,
                ),
            )

    def update_session_context(
        self,
        name: str,
        current_dir: Optional[str] = None,
        git_branch: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ):
        """Update session context tracking (Phase 1 & 2 Context Management)."""
        with self._get_conn() as conn:
            updates, params = [], []
            if current_dir is not None:
                updates.append("current_dir = ?")
                params.append(current_dir)
            if git_branch is not None:
                updates.append("git_branch = ?")
                params.append(git_branch)
            if env_vars is not None:
                updates.append("env_vars = ?")
                params.append(json.dumps(env_vars))
            if updates:
                updates.append("last_context_update = CURRENT_TIMESTAMP")
                params.append(name)
                conn.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE name = ?", params)

    def get_session_context(self, name: str) -> Optional[Dict]:
        """Get current context for a session including env_vars."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT current_dir, git_branch, env_vars, last_context_update
                FROM sessions WHERE name = ?""",
                (name,),
            ).fetchone()
            if row:
                result = dict(row)
                # Parse env_vars JSON
                if result.get("env_vars"):
                    try:
                        result["env_vars"] = json.loads(result["env_vars"])
                    except (json.JSONDecodeError, TypeError):
                        result["env_vars"] = {}
                return result
            return None

    def get_sessions_with_env(self, env_key: str, env_value: str = None) -> List[Dict]:
        """Get sessions that have a specific environment variable set (Phase 2)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT name, env_vars, current_dir FROM sessions WHERE env_vars IS NOT NULL"
            ).fetchall()
            matching = []
            for row in rows:
                try:
                    env = json.loads(row["env_vars"]) if row["env_vars"] else {}
                    if env_key in env:
                        if env_value is None or env.get(env_key) == env_value:
                            matching.append(dict(row))
                except (json.JSONDecodeError, TypeError):
                    pass
            return matching

    # Phase 3: Context-based session selection
    def get_available_sessions_with_context(self, provider: Optional[str] = None) -> List[Dict]:
        """Get available sessions with their context info (Phase 3)."""
        with self._get_conn() as conn:
            if provider:
                rows = conn.execute(
                    """
                    SELECT name, status, provider, is_claude, current_dir,
                           env_vars, git_branch, last_activity
                    FROM sessions
                    WHERE status IN ('idle', 'waiting_input')
                      AND (
                        provider = ?
                        OR (provider IS NULL AND ? = 'claude' AND is_claude = 1)
                      )
                    ORDER BY last_activity ASC
                """,
                    (provider, provider),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT name, status, provider, is_claude, current_dir,
                           env_vars, git_branch, last_activity
                    FROM sessions
                    WHERE status IN ('idle', 'waiting_input')
                      AND (
                        provider IN ('claude', 'codex', 'ollama', 'comet')
                        OR (provider IS NULL AND is_claude = 1)
                      )
                    ORDER BY last_activity ASC
                """
                ).fetchall()
            sessions = []
            for row in rows:
                if row["name"] in EXCLUDED_SESSIONS:
                    continue
                session = dict(row)
                if session.get("env_vars"):
                    try:
                        session["env_vars"] = json.loads(session["env_vars"])
                    except (json.JSONDecodeError, TypeError):
                        session["env_vars"] = {}
                else:
                    session["env_vars"] = {}
                sessions.append(session)
            return sessions

    def calculate_context_match_score(
        self,
        session: Dict,
        required_dir: Optional[str] = None,
        required_env: Optional[Dict[str, str]] = None,
        required_branch: Optional[str] = None,
    ) -> int:
        """Calculate how well a session matches context requirements (Phase 3).

        Score: 100=exact dir, 50=parent dir, 25=child dir, 20/env var, 30=branch.
        """
        score = 0
        session_dir = session.get("current_dir") or ""
        session_env = session.get("env_vars") or {}
        session_branch = session.get("git_branch") or ""

        if required_dir and session_dir:
            required_dir = required_dir.rstrip("/")
            session_dir = session_dir.rstrip("/")
            if session_dir == required_dir:
                score += 100
            elif required_dir.startswith(session_dir + "/"):
                score += 50
            elif session_dir.startswith(required_dir + "/"):
                score += 25

        if required_env and session_env:
            for key, value in required_env.items():
                if session_env.get(key) == value:
                    score += 20

        if required_branch and session_branch == required_branch:
            score += 30

        return score

    def select_best_session_by_context(
        self,
        sessions: List[Dict],
        required_dir: Optional[str] = None,
        required_env: Optional[Dict[str, str]] = None,
        required_branch: Optional[str] = None,
        min_score: int = 0,
    ) -> Optional[Dict]:
        """Select the best session based on context match (Phase 3)."""
        if not sessions:
            return None

        scored = []
        for session in sessions:
            score = self.calculate_context_match_score(
                session, required_dir, required_env, required_branch
            )
            scored.append((score, session))

        scored.sort(key=lambda x: (-x[0], x[1].get("last_activity", "")))

        if scored and scored[0][0] >= min_score:
            best_score, best_session = scored[0]
            if best_score > 0:
                logger.debug(f"Context match: {best_session['name']} score={best_score}")
            return best_session
        return None

    def get_available_sessions(self, provider: Optional[str] = None) -> List[Dict]:
        """Get sessions that are available for assignment.

        Excludes coordination sessions (architect, orchestrator, arch_dev).
        """
        with self._get_conn() as conn:
            if provider:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE status IN ('idle', 'waiting_input')
                      AND (
                        provider = ?
                        OR (provider IS NULL AND ? = 'claude' AND is_claude = 1)
                      )
                    ORDER BY last_activity ASC
                """,
                    (provider, provider),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE status IN ('idle', 'waiting_input')
                      AND (
                        provider IN ('claude', 'codex', 'ollama', 'comet')
                        OR (provider IS NULL AND is_claude = 1)
                      )
                    ORDER BY last_activity ASC
                """
                ).fetchall()
            # Filter out excluded sessions (coordination/monitoring sessions)
            return [dict(r) for r in rows if r["name"] not in EXCLUDED_SESSIONS]

    def get_all_sessions(self) -> List[Dict]:
        """Get all tracked sessions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT s.*, p.content as current_task_content
                FROM sessions s
                LEFT JOIN prompts p ON s.current_task_id = p.id
                ORDER BY s.name
            """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_active_assignments(self) -> List[Dict]:
        """Get prompts currently assigned to sessions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT p.*, s.status as session_status
                FROM prompts p
                LEFT JOIN sessions s ON p.assigned_session = s.name
                WHERE p.status IN ('assigned', 'in_progress')
                ORDER BY p.assigned_at DESC
            """
            ).fetchall()
            return [dict(r) for r in rows]

    def log_assignment(
        self,
        prompt_id: int,
        session_name: str,
        action: str,
        details: Optional[str] = None,
    ):
        """Log an assignment action."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO assignment_history (prompt_id, session_name, action, details)
                VALUES (?, ?, ?, ?)
            """,
                (prompt_id, session_name, action, details),
            )

    def get_stats(self) -> Dict:
        """Get assigner statistics."""
        with self._get_conn() as conn:
            # Combine all prompt stats into single query (fix multiple COUNT queries)
            prompt_stats = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'pending' THEN 1 END)
                        AS pending_prompts,
                    COUNT(CASE WHEN status IN ('assigned', 'in_progress') THEN 1 END)
                        AS active_assignments,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END)
                        AS completed_prompts,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END)
                        AS failed_prompts
                FROM prompts
            """
            ).fetchone()

            # Combine all session stats into single query
            session_stats = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_sessions,
                    COUNT(CASE WHEN status IN ('idle', 'waiting_input')
                               AND (provider IN ('claude', 'codex', 'ollama')
                                    OR (provider IS NULL AND is_claude = 1))
                          THEN 1 END) AS available_sessions,
                    COUNT(CASE WHEN status = 'busy' THEN 1 END) AS busy_sessions
                FROM sessions
            """
            ).fetchone()

            stats = {
                "pending_prompts": prompt_stats[0] or 0,
                "active_assignments": prompt_stats[1] or 0,
                "completed_prompts": prompt_stats[2] or 0,
                "failed_prompts": prompt_stats[3] or 0,
                "total_sessions": session_stats[0] or 0,
                "available_sessions": session_stats[1] or 0,
                "busy_sessions": session_stats[2] or 0,
            }
            return stats

    def retry_prompt(self, prompt_id: int) -> bool:
        """Retry a failed prompt."""
        with self._get_conn() as conn:
            prompt = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()

            if not prompt:
                return False

            if prompt["status"] not in ("failed", "cancelled"):
                return False

            retry_count = (prompt["retry_count"] or 0) + 1
            conn.execute(
                """
                UPDATE prompts SET
                    status = 'pending',
                    retry_count = ?,
                    assigned_session = NULL,
                    assigned_at = NULL,
                    completed_at = NULL,
                    error = NULL
                WHERE id = ?
            """,
                (retry_count, prompt_id),
            )
            return True

    def retry_all_failed(self) -> int:
        """Retry all failed prompts that haven't exceeded max retries."""
        with self._get_conn() as conn:
            result = conn.execute(
                """
                UPDATE prompts SET
                    status = 'pending',
                    retry_count = retry_count + 1,
                    assigned_session = NULL,
                    assigned_at = NULL,
                    completed_at = NULL,
                    error = NULL
                WHERE status = 'failed'
                  AND retry_count < max_retries
            """
            )
            return result.rowcount

    def get_timed_out_assignments(self) -> List[Dict]:
        """Get assignments that have exceeded their timeout."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prompts
                WHERE status IN ('assigned', 'in_progress')
                  AND assigned_at IS NOT NULL
                  AND datetime(assigned_at, '+' || timeout_minutes || ' minutes') < datetime('now')
            """
            ).fetchall()
            return [dict(r) for r in rows]

    def timeout_stuck_assignments(self) -> int:
        """Mark timed-out assignments as failed."""
        with self._get_conn() as conn:
            result = conn.execute(
                """
                UPDATE prompts SET
                    status = 'failed',
                    error = 'Assignment timed out',
                    completed_at = CURRENT_TIMESTAMP
                WHERE status IN ('assigned', 'in_progress')
                  AND assigned_at IS NOT NULL
                  AND datetime(assigned_at, '+' || timeout_minutes || ' minutes') < datetime('now')
            """
            )

            # Also free up the sessions
            if result.rowcount > 0:
                conn.execute(
                    """
                    UPDATE sessions SET current_task_id = NULL
                    WHERE current_task_id IN (
                        SELECT id FROM prompts
                        WHERE status = 'failed'
                          AND error = 'Assignment timed out'
                    )
                """
                )

            return result.rowcount

    def clear_completed(self, days_old: int = 7) -> int:
        """Delete completed prompts older than N days."""
        with self._get_conn() as conn:
            result = conn.execute(
                """
                DELETE FROM prompts
                WHERE status IN ('completed', 'cancelled')
                  AND completed_at < datetime('now', '-' || ? || ' days')
            """,
                (days_old,),
            )
            return result.rowcount

    def clear_all_completed(self) -> int:
        """Delete all completed and cancelled prompts."""
        with self._get_conn() as conn:
            result = conn.execute(
                """
                DELETE FROM prompts WHERE status IN ('completed', 'cancelled')
            """
            )
            return result.rowcount

    def reassign_prompt(self, prompt_id: int, session_name: Optional[str] = None) -> bool:
        """Reassign a prompt (set back to pending with optional target session)."""
        with self._get_conn() as conn:
            prompt = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()

            if not prompt:
                return False

            conn.execute(
                """
                UPDATE prompts SET
                    status = 'pending',
                    target_session = ?,
                    assigned_session = NULL,
                    assigned_at = NULL
                WHERE id = ?
            """,
                (session_name, prompt_id),
            )

            # Free up any session that had this task
            conn.execute(
                """
                UPDATE sessions SET current_task_id = NULL
                WHERE current_task_id = ?
            """,
                (prompt_id,),
            )

            return True

    def update_session_state(self, session_name: str, working_dir: Optional[str] = None) -> None:
        """
        Update session state tracking information (Phase 1: Context Management).

        Args:
            session_name: Name of the tmux session
            working_dir: Explicitly set working directory (if not provided, will poll from tmux)
        """
        try:
            # Get working directory from tmux if not provided
            if not working_dir:
                result = subprocess.run(
                    [
                        "tmux",
                        "display-message",
                        "-t",
                        session_name,
                        "-p",
                        "#{pane_current_path}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    working_dir = result.stdout.strip()

            # Try to detect git branch if in a git repo
            git_branch = None
            if working_dir:
                try:
                    result = subprocess.run(
                        ["git", "-C", working_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.returncode == 0:
                        git_branch = result.stdout.strip()
                except Exception:
                    pass  # Not in a git repo

            # Update database with context information
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE sessions SET
                        current_dir = ?,
                        git_branch = ?,
                        last_context_update = CURRENT_TIMESTAMP
                    WHERE name = ?
                """,
                    (working_dir, git_branch, session_name),
                )
                logger.debug(
                    f"Updated session state for {session_name}: "
                    f"dir={working_dir}, branch={git_branch}"
                )

        except Exception as e:
            logger.warning(f"Error updating session state for {session_name}: {e}")


class SessionDetector:
    """Detects and monitors tmux sessions."""

    # Patterns that indicate Claude is idle and waiting for input
    IDLE_PATTERNS = [
        r"^\s*>\s*$",  # Just a prompt
        r"Claude Code.*\$",  # Claude Code prompt
        r"What would you like to do\?",
        r"How can I help",
        r"Enter your prompt",
        r"\(y/n\)",  # Waiting for confirmation
        r"\[Y/n\]",
        r"Press Enter",
        r"claude>",  # Claude CLI prompt
        r"codex>",  # Codex worker prompt
        r"worker>",  # Generic worker prompt
        r"\$ $",  # Shell prompt at end of line
        r"waiting for input",
        r"Waiting for prompts",  # Codex worker startup message
        r"ready for",
        r"What.*next",  # "What's next", "What would you like next"
        r"Do you want to",  # Claude Code confirmation prompts
        r"Esc to cancel",  # Claude Code prompt footer
        r"Tab to amend",  # Claude Code prompt option
        r"❯\s*\d+\.",  # Claude Code menu selection arrow
        r"❯\s+Try",  # Claude Code "Try" suggestions
        r"❯\s+\w",  # Claude Code prompt with command (e.g., "❯ echo", "❯ fix")
        r"^\s*❯\s*$",  # Just the ❯ prompt
        r'Try "',  # Claude Code startup prompt: Try "how do I..."
        r"Try '",  # Claude Code startup prompt with single quotes
        r"\? for shortcuts",  # Claude Code help prompt
    ]

    # Patterns that indicate Claude is busy processing
    BUSY_PATTERNS = [
        r"Thinking\.{3}",
        r"Processing",
        r"Running",
        r"Executing",
        r"Writing to",
        r"Reading",
        r"Searching",
        r"\[\d+/\d+\]",  # Progress indicator
        # r'─+',  # Removed: Causes false positives with Claude Code UI separators
        r"\.{3,}",  # Loading dots
        r"Analyzing",
        r"Generating",
        r"Compiling",
        r"Building",
        r"Installing",
        r"Downloading",
        r"Fetching",
        r"Scanning",
        r"Testing",
        r"\d+%",  # Percentage progress
    ]

    # Patterns that indicate specific AI providers
    PROVIDER_SESSION_PATTERNS = {
        "claude": [
            r"claude",
            r"Claude Code",
            r"anthropic",
            r"Claude>",
            r"claude-code",
            r"CC>",
            r"concurrent_worker",  # Concurrent worker sessions run Claude
            r"worker\d+",  # worker1, worker2, etc.
            r"Do you want to",  # Claude Code confirmation prompts
        ],
        "codex": [
            r"codex",
            r"codex>",  # Codex worker prompt
            r"openai",
            r"codex_chat",  # Codex chat worker
            r"Codex Worker",  # Codex worker startup
        ],
        "comet": [
            r"comet",
            r"ui_worker",
            r"frontend",
        ],
        "ollama": [
            r"ollama",
        ],
    }

    def __init__(self):
        self.idle_regex = re.compile("|".join(self.IDLE_PATTERNS), re.IGNORECASE)
        self.busy_regex = re.compile("|".join(self.BUSY_PATTERNS), re.IGNORECASE)
        self.provider_regex = {
            provider: re.compile("|".join(patterns), re.IGNORECASE)
            for provider, patterns in self.PROVIDER_SESSION_PATTERNS.items()
        }

    def detect_provider(self, session: str, output: str) -> str:
        """Detect provider based on session name and output."""
        # Check session name first for explicit matches (more specific)
        session_lower = session.lower()
        if "comet" in session_lower or "ui_worker" in session_lower:
            return "comet"
        if "codex" in session_lower:
            return "codex"
        if "concurrent_worker" in session_lower or re.match(r"worker\d+", session_lower):
            return "claude"

        # Then check output patterns
        for provider, regex in self.provider_regex.items():
            if regex.search(output):
                return provider

        # Fallback to session name pattern matching
        for provider, regex in self.provider_regex.items():
            if regex.search(session):
                return provider

        return "unknown"

    def list_sessions(self) -> List[str]:
        """List all tmux sessions."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
        return []

    def capture_pane(self, session: str, lines: int = 50) -> Optional[str]:
        """Capture the last N lines from a session's pane."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            logger.debug(f"Failed to capture pane for {session}: {e}")
        return None

    def get_working_dir(self, session: str) -> Optional[str]:
        """Get the working directory of a session."""
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "display-message",
                    "-t",
                    session,
                    "-p",
                    "#{pane_current_path}",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Failed to get working dir for {session}: {e}")
        return None

    def detect_session_status(self, session: str) -> tuple[str, str, Optional[str]]:
        """
        Detect the status of a session.

        Returns: (status, provider, last_output)
        """
        output = self.capture_pane(session)
        if not output:
            return SessionStatus.UNKNOWN, "unknown", None

        provider = self.detect_provider(session, output)
        is_known_provider = provider in SUPPORTED_PROVIDERS

        # Get last few lines for status detection
        lines = output.strip().split("\n")
        last_lines = "\n".join(lines[-10:]) if len(lines) > 10 else output

        # Check for busy patterns first
        if self.busy_regex.search(last_lines):
            return SessionStatus.BUSY, provider, last_lines

        # Check for idle/waiting patterns
        if self.idle_regex.search(last_lines):
            return (
                (SessionStatus.WAITING_INPUT if is_known_provider else SessionStatus.IDLE),
                provider,
                last_lines,
            )

        # Default to busy if a known provider is detected but no clear pattern
        if is_known_provider:
            return SessionStatus.BUSY, provider, last_lines

        return SessionStatus.IDLE, provider, last_lines

    def scan_all_sessions(self) -> List[SessionInfo]:
        """Scan all sessions and return their info."""
        sessions = []
        for name in self.list_sessions():
            status, provider, last_output = self.detect_session_status(name)
            working_dir = self.get_working_dir(name)
            sessions.append(
                SessionInfo(
                    name=name,
                    status=status,
                    last_activity=datetime.now().isoformat(),
                    current_task_id=None,
                    working_dir=working_dir,
                    is_claude=(provider == "claude"),
                    provider=provider,
                )
            )
        return sessions


class AssignerWorker:
    """
    Main assigner worker that coordinates prompts and sessions.
    """

    def __init__(
        self,
        poll_interval: int = 3,
        session_scan_interval: int = 10,
        timeout_check_interval: int = 60,
    ):
        self.poll_interval = poll_interval
        self.session_scan_interval = session_scan_interval
        self.timeout_check_interval = timeout_check_interval
        self.running = False
        self.worker_id = f"assigner-{os.getpid()}"

        self.db = AssignerDatabase()
        self.detector = SessionDetector()

        self._last_session_scan = 0
        self._last_timeout_check = 0
        self._lock = threading.Lock()

    def start(self):
        """Start the worker."""
        self.running = True
        logger.info(f"Starting AssignerWorker {self.worker_id}")

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._save_state()

        try:
            while self.running:
                # Scan sessions periodically
                if time.time() - self._last_session_scan > self.session_scan_interval:
                    self._scan_sessions()
                    self._last_session_scan = time.time()

                # Check for timed out assignments periodically
                if time.time() - self._last_timeout_check > self.timeout_check_interval:
                    self._check_timeouts()
                    self._last_timeout_check = time.time()

                # Process pending prompts
                self._process_prompts()

                # Check active assignments
                self._check_assignments()

                self._save_state()
                time.sleep(self.poll_interval)

        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            self._save_state()
            logger.info("AssignerWorker stopped")

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Stopping AssignerWorker")

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop()

    def _scan_sessions(self):
        """Scan all tmux sessions and update database."""
        logger.debug("Scanning sessions...")
        sessions = self.detector.scan_all_sessions()

        # Fetch all existing sessions once (fix N+1 query)
        existing = self.db.get_all_sessions()
        existing_map = {s["name"]: s for s in existing}

        # Get set of current session names from tmux
        current_session_names = {s.name for s in sessions}

        # Remove stale sessions (in DB but not in tmux)
        stale_count = 0
        for db_session in existing:
            if db_session["name"] not in current_session_names:
                logger.info(f"Removing stale session from DB: {db_session['name']}")
                with self.db._get_conn() as conn:
                    # Free any assigned tasks from stale session
                    if db_session.get("current_task_id"):
                        conn.execute(
                            """
                            UPDATE prompts SET status = 'pending',
                                   assigned_session = NULL,
                                   assigned_at = NULL
                            WHERE id = ? AND status IN ('assigned', 'in_progress')
                        """,
                            (db_session["current_task_id"],),
                        )
                        logger.info(
                            f"Freed task {db_session['current_task_id']} "
                            f"from stale session {db_session['name']}"
                        )
                    # Delete stale session
                    conn.execute("DELETE FROM sessions WHERE name = ?", (db_session["name"],))
                stale_count += 1

        if stale_count > 0:
            logger.info(f"Removed {stale_count} stale sessions from database")

        for session in sessions:
            # Get current task if any from pre-fetched data
            current_task = None
            if session.name in existing_map:
                current_task = existing_map[session.name].get("current_task_id")

            self.db.update_session(
                name=session.name,
                status=session.status,
                is_claude=session.is_claude,
                working_dir=session.working_dir,
                current_task_id=current_task,
                provider=session.provider,
            )

            # Phase 1: Update session context state (git branch, working dir, etc.)
            try:
                self.db.update_session_state(session.name, session.working_dir)
            except Exception as e:
                logger.debug(f"Failed to update session state for {session.name}: {e}")

        logger.debug(f"Scanned {len(sessions)} sessions")

    def _process_prompts(self):
        """Process pending prompts and assign to available sessions."""
        pending = self.db.get_pending_prompts(limit=5)
        if not pending:
            return

        for prompt in pending:
            target = prompt.get("target_session")

            # If prompt has a target session, check if it's available
            if target:
                available = self.db.get_available_sessions()
                available_names = {s["name"] for s in available}
                if target in available_names:
                    self._assign_prompt(prompt, target)
                    continue
                else:
                    # Target session not available, try to match by provider
                    # Treat target_session as provider hint (e.g., 'codex' → any codex session)
                    logger.debug(
                        f"Prompt {prompt['id']}: target session '{target}' not "
                        f"available, trying provider match"
                    )
                    # Check if target matches a provider name
                    if target in SUPPORTED_PROVIDERS:
                        available_by_provider = self.db.get_available_sessions(provider=target)
                        if available_by_provider:
                            session = available_by_provider[0]
                            logger.info(
                                f"Prompt {prompt['id']}: matched provider '{target}' "
                                f"→ session '{session['name']}'"
                            )
                            self._assign_prompt(prompt, session["name"])
                            continue
                    # Still no match, fall through to general selection
                    logger.debug(
                        f"Prompt {prompt['id']}: no provider match for '{target}', "
                        f"trying general selection"
                    )

            session = self._select_session_for_prompt(prompt)
            if not session:
                provider_msg = ""
                if prompt.get("target_provider"):
                    provider_msg = f" provider={prompt['target_provider']}"
                logger.debug(f"Prompt {prompt['id']} waiting, no available sessions{provider_msg}")
                continue

            self._assign_prompt(prompt, session["name"])

    def _select_session_for_prompt(self, prompt: Dict) -> Optional[Dict]:
        """Select the best available session for a prompt (Phase 3 Context Management).

        Selection priority:
        1. If context requirements exist, prefer sessions with matching context
        2. If target_provider specified, filter by that provider
        3. Use provider router based on task type/rate limits
        4. Fallback to any available provider
        """
        metadata = prompt.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        target_provider = prompt.get("target_provider")
        preferred_providers = metadata.get("preferred_providers") or []
        fallback_providers = metadata.get("fallback_providers") or []
        allow_fallback = bool(metadata.get("allow_fallback"))

        # Phase 3: Extract context requirements
        required_dir = metadata.get("working_dir")
        required_env = metadata.get("env_vars") or {}
        required_branch = metadata.get("git_branch")
        prefer_context = metadata.get("prefer_context_match", True)

        # Check if this requires Claude (high complexity tasks)
        task_complexity = metadata.get("complexity", "normal")
        requires_claude = task_complexity == "high" or metadata.get("requires_claude", False)

        # Build provider order
        provider_order: List[str] = []

        if target_provider:
            provider_order.append(target_provider)
            if fallback_providers:
                for p in fallback_providers:
                    if p not in provider_order:
                        provider_order.append(p)
            elif allow_fallback:
                for p in SUPPORTED_PROVIDERS:
                    if p != target_provider:
                        provider_order.append(p)
        elif preferred_providers:
            provider_order.extend([p for p in preferred_providers if p in SUPPORTED_PROVIDERS])
        elif requires_claude:
            provider_order = ["claude", "openai", "ollama"]
        else:
            try:
                from services.rate_limit_handler import should_use_claude

                if should_use_claude():
                    provider_order = ["claude", "ollama", "codex", "comet"]
                else:
                    provider_order = ["ollama", "codex", "comet", "claude"]
            except ImportError:
                provider_order = ["claude", "ollama", "codex", "comet"]

        # Phase 3: Context-based selection
        has_context = required_dir or required_env or required_branch
        if has_context and prefer_context:
            for provider in provider_order if provider_order else [None]:
                available = self.db.get_available_sessions_with_context(provider=provider)
                if available:
                    best = self.db.select_best_session_by_context(
                        available,
                        required_dir=required_dir,
                        required_env=required_env,
                        required_branch=required_branch,
                        min_score=20,
                    )
                    if best:
                        logger.info(
                            f"Prompt {prompt.get('id')}: Context match - "
                            f"{best['name']} (dir={best.get('current_dir')})"
                        )
                        return best

        # Provider-based selection
        for provider in provider_order:
            available = self.db.get_available_sessions(provider=provider)
            if available:
                return available[0]

        # Fallback to any available session
        available = self.db.get_available_sessions()
        return available[0] if available else None

    def _check_timeouts(self):
        """Check for and handle timed-out assignments."""
        timed_out = self.db.timeout_stuck_assignments()
        if timed_out > 0:
            logger.warning(f"Timed out {timed_out} stuck assignments")

    def _assign_prompt(self, prompt: Dict, session_name: str):
        """Assign a prompt to a session with throttle checking."""
        prompt_id = prompt["id"]
        content = prompt["content"]
        priority_num = prompt.get("priority", 0)

        # Convert numeric priority to string priority for throttling
        if priority_num >= 8:
            priority = "critical"
        elif priority_num >= 5:
            priority = "high"
        elif priority_num >= 3:
            priority = "normal"
        else:
            priority = "low"

        # Check throttle limits before assigning
        try:
            from services.token_throttle import get_throttler

            throttler = get_throttler()

            # Estimate tokens (rough: ~4 chars per token)
            estimated_tokens = len(content) // 4 + 1000  # Add buffer for response

            # Check if assignment is allowed
            if not throttler.allow_request(session_name, estimated_tokens, priority):
                throttle_level = throttler.get_throttle_level(session_name, estimated_tokens)
                logger.warning(
                    f"Prompt {prompt_id} throttled for session {session_name}: "
                    f"{throttle_level.value}"
                )
                # Re-queue for later (keep as pending)
                self.db.log_assignment(
                    prompt_id,
                    session_name,
                    "throttled",
                    f"Throttled: {throttle_level.value}",
                )
                return

        except Exception as e:
            logger.warning(f"Throttle check failed, proceeding anyway: {e}")

        # VERIFY SESSION EXISTS before attempting to send
        current_sessions = self.detector.list_sessions()
        if session_name not in current_sessions:
            logger.warning(
                f"Session {session_name} not found in tmux "
                f"(detected {len(current_sessions)} sessions), re-scanning..."
            )
            self._scan_sessions()

            # Check again after re-scan
            current_sessions = self.detector.list_sessions()
            if session_name not in current_sessions:
                logger.error(
                    f"Session {session_name} does not exist in tmux after re-scan, "
                    f"marking prompt as failed"
                )
                self.db.update_prompt_status(
                    prompt_id,
                    PromptStatus.FAILED,
                    error=f"Target session '{session_name}' not found in tmux",
                )
                self.db.log_assignment(
                    prompt_id,
                    session_name,
                    "failed",
                    f"Session '{session_name}' not found",
                )
                return

        logger.info(
            f"Assigning prompt {prompt_id} to session {session_name} (priority: {priority})"
        )

        try:
            # Phase 1 Context Management: Prepare session context before sending
            metadata = None
            if prompt.get("metadata"):
                try:
                    metadata = (
                        json.loads(prompt["metadata"])
                        if isinstance(prompt["metadata"], str)
                        else prompt["metadata"]
                    )
                except (json.JSONDecodeError, TypeError):
                    pass
            if metadata and metadata.get("working_dir"):
                self._prepare_session_context(session_name, metadata)

            # Send the prompt to the session
            self._send_to_session(session_name, content)

            # Update database
            self.db.update_prompt_status(prompt_id, PromptStatus.ASSIGNED, session=session_name)
            self.db.update_session(session_name, SessionStatus.BUSY, current_task_id=prompt_id)
            self.db.log_assignment(prompt_id, session_name, "assigned", "Sent prompt to session")

            logger.info(f"Assigned prompt {prompt_id} to {session_name}")

        except Exception as e:
            logger.error(f"Failed to assign prompt {prompt_id}: {e}")
            self.db.update_prompt_status(prompt_id, PromptStatus.FAILED, error=str(e))
            self.db.log_assignment(prompt_id, session_name, "failed", str(e))

    def _prepare_session_context(self, session_name: str, metadata: Optional[Dict] = None) -> bool:
        """Prepare session context before sending a task (Phase 1 Context Management)."""
        if not metadata or not metadata.get("working_dir"):
            return True
        working_dir = metadata["working_dir"]
        try:
            logger.info(f"Setting context for {session_name}: cd {working_dir}")
            result = subprocess.run(
                ["tmux", "send-keys", "-t", session_name, f"cd {working_dir}", "Enter"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"Failed to cd in {session_name}: {result.stderr}")
                return False
            time.sleep(0.5)

            # Phase 2: Track env_vars in database
            env_vars = metadata.get("env_vars", {})
            self.db.update_session_context(
                session_name, current_dir=working_dir, env_vars=env_vars if env_vars else None
            )

            # Set environment variables in session
            for key, value in env_vars.items():
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, f"export {key}={value}", "Enter"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                time.sleep(0.3)
                logger.debug(f"Set env var {key} in {session_name}")

            for cmd in metadata.get("prerequisites", []):
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, cmd, "Enter"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                time.sleep(0.5)
            logger.info(f"Context prepared for {session_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to prepare context for {session_name}: {e}")
            return False

    def _send_to_session(self, session: str, content: str):
        """Send content to a tmux session."""
        # Use tmux send-keys with Enter
        result = subprocess.run(
            ["tmux", "send-keys", "-t", session, content, "Enter"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise RuntimeError(f"tmux send-keys failed: {result.stderr}")

        # For long multi-line prompts, Claude Code may enter paste mode
        # Send Enter to submit the pasted text
        if len(content) > 200 or "\n" in content:
            time.sleep(0.5)  # Give paste mode time to activate
            subprocess.run(
                ["tmux", "send-keys", "-t", session, "Enter"],
                capture_output=True,
                text=True,
                timeout=5,
            )

    def _check_assignments(self):
        """Check status of active assignments."""
        active = self.db.get_active_assignments()

        for assignment in active:
            prompt_id = assignment["id"]
            session_name = assignment["assigned_session"]

            if not session_name:
                continue

            # Check session status
            status, provider, output = self.detector.detect_session_status(session_name)

            # Update session in DB
            self.db.update_session(
                session_name,
                status,
                is_claude=(provider == "claude"),
                last_output=output,
                provider=provider,
            )

            # If session is now idle/waiting, the task might be complete
            if status in (SessionStatus.IDLE, SessionStatus.WAITING_INPUT):
                # Check if this is a new idle state (task completed)
                if assignment["status"] == PromptStatus.ASSIGNED:
                    self.db.update_prompt_status(prompt_id, PromptStatus.IN_PROGRESS)
                    self.db.log_assignment(prompt_id, session_name, "started")

                # If it was already in_progress and now idle, check if actually complete
                elif assignment["status"] == PromptStatus.IN_PROGRESS:
                    # Don't mark complete if worker is blocked or actively working
                    blocked_indicators = [
                        "Do you want to",
                        "want to proceed",
                        "Behavior ask",
                        "[Pasted text",
                        "Esc to cancel",
                        "shift+tab to cycle",
                        "esc to interrupt",
                        "accept edits on",
                    ]
                    active_indicators = [
                        "thinking",
                        "Cooking",
                        "Running",
                        "Analyzing",
                        "Processing",
                        "Executing",
                        "Working",
                        "Building",
                        "Testing",
                        "Searching",
                        "Reading",
                        "Writing",
                        "Crunched",
                        "Effecting",
                        "Pondering",
                        "Mustering",
                    ]
                    is_blocked = any(
                        indicator in (output or "") for indicator in blocked_indicators
                    )
                    is_active = any(indicator in (output or "") for indicator in active_indicators)

                    if is_blocked:
                        # Worker is blocked on approval, don't mark complete
                        logger.debug(f"Prompt {prompt_id} blocked on approval in {session_name}")
                        continue

                    if is_active:
                        # Worker is actively working, don't mark complete
                        logger.debug(f"Prompt {prompt_id} still active in {session_name}")
                        continue

                    # Only mark complete if worker has been idle for at least 30 seconds
                    # to give time for thinking/processing
                    assigned_at = assignment.get("assigned_at")
                    if assigned_at:
                        from datetime import datetime

                        try:
                            assigned_time = datetime.fromisoformat(assigned_at)
                            time_elapsed = (datetime.now() - assigned_time).total_seconds()
                            if time_elapsed < 30:
                                logger.debug(
                                    f"Prompt {prompt_id} too recent ({time_elapsed}s), waiting..."
                                )
                                continue
                        except Exception:
                            pass

                    # Mark as complete
                    self.db.update_prompt_status(prompt_id, PromptStatus.COMPLETED, response=output)
                    self.db.update_session(session_name, status, current_task_id=None)
                    self.db.log_assignment(prompt_id, session_name, "completed")
                    logger.info(f"Prompt {prompt_id} completed in session {session_name}")

    def _save_state(self):
        """Save worker state to file."""
        stats = self.db.get_stats()
        state = {
            "worker_id": self.worker_id,
            "running": self.running,
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
        }
        STATE_FILE.write_text(json.dumps(state, indent=2))


# ============================================================================
# CLI Functions
# ============================================================================


def daemonize():
    """Run as daemon process."""
    if os.fork() > 0:
        sys.exit(0)

    os.setsid()

    if os.fork() > 0:
        sys.exit(0)

    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    with open(str(LOG_FILE), "a") as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())


def stop_daemon():
    """Stop the daemon process."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            print(f"Stopped daemon (PID {pid})")
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink()
            print("Daemon not running")
    else:
        print("No PID file found")


def check_status():
    """Check daemon status."""
    running = False
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            print(f"Daemon running (PID {pid})")
            running = True
        except (ProcessLookupError, ValueError):
            print("Daemon not running (stale PID file)")

    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        print(f"\nLast update: {state.get('timestamp', 'N/A')}")
        stats = state.get("stats", {})
        print("\nQueue Stats:")
        print(f"  Pending prompts:    {stats.get('pending_prompts', 0)}")
        print(f"  Active assignments: {stats.get('active_assignments', 0)}")
        print(f"  Completed prompts:  {stats.get('completed_prompts', 0)}")
        print(f"  Failed prompts:     {stats.get('failed_prompts', 0)}")
        print("\nSession Stats:")
        print(f"  Total sessions:     {stats.get('total_sessions', 0)}")
        print(f"  Available sessions: {stats.get('available_sessions', 0)}")
        print(f"  Busy sessions:      {stats.get('busy_sessions', 0)}")

    return running


def send_prompt(
    content: str,
    priority: int = 0,
    source: str = "cli",
    target_session: Optional[str] = None,
    target_provider: Optional[str] = None,
    timeout: int = 30,
    preferred_providers: Optional[List[str]] = None,
    fallback_providers: Optional[List[str]] = None,
    allow_fallback: bool = False,
    use_delegation: bool = True,
    project_type: Optional[str] = None,
    environment: Optional[str] = None,
    use_environment_routing: bool = True,
    working_dir: Optional[str] = None,
    env_vars: Optional[Dict[str, str]] = None,
    prerequisites: Optional[List[str]] = None,
    git_branch: Optional[str] = None,
    prefer_context_match: bool = True,
):
    """
    Send a prompt to the queue with optional automatic delegation and environment routing.

    Args:
        content: Prompt content
        priority: Priority (0-10, higher = more urgent)
        source: Source of the prompt
        target_session: Specific session to target
        target_provider: Specific provider to target
        timeout: Timeout in minutes
        preferred_providers: List of preferred providers
        fallback_providers: List of fallback providers
        allow_fallback: Allow fallback to other providers
        use_delegation: Use task delegation to auto-select optimal provider
        project_type: Type of project (ui_improvement, performance_optimization, etc.)
        environment: Specific environment name to use
        use_environment_routing: Use environment-aware routing
        working_dir: Working directory for task (Phase 1 Context Management)
        env_vars: Environment variables to set (Phase 2 Context Management)
        prerequisites: Commands to run before task (Phase 1 Context Management)
        git_branch: Preferred git branch for session (Phase 3 Context Management)
        prefer_context_match: Use context-based session selection (Phase 3)
    """
    metadata: Dict[str, Any] = {}

    # Context Management: Add working_dir, env_vars, prerequisites
    if working_dir:
        metadata["working_dir"] = working_dir
    if env_vars:
        metadata["env_vars"] = env_vars
    if prerequisites:
        metadata["prerequisites"] = prerequisites
    # Phase 3: Context matching preferences
    if git_branch:
        metadata["git_branch"] = git_branch
    metadata["prefer_context_match"] = prefer_context_match

    # Let intelligent routing determine the best session based on task content and availability
    # Explicit target_session or target_provider takes precedence over content-based routing

    # Add project type and environment if specified
    if project_type:
        metadata["project_type"] = project_type
    if environment:
        metadata["environment"] = environment

    # Route task to appropriate environment
    if use_environment_routing:
        metadata = route_task_to_environment(content, metadata)

        # If environment routing determined preferred sessions, update target
        if not target_session and metadata.get("routing_rules"):
            preferred_sessions = metadata["routing_rules"].get("preferred_sessions", [])
            if preferred_sessions and not preferred_providers:
                # Map session names to providers
                session_to_provider = {
                    "claude_comet": "comet",
                    "codex": "codex",
                    "dev_worker1": "claude",
                    "dev_worker2": "claude",
                    "architect": "claude",
                }
                # Try to find a matching session or provider
                for session in preferred_sessions:
                    if session_to_provider.get(session):
                        if not preferred_providers:
                            preferred_providers = []
                        provider = session_to_provider[session]
                        if provider not in preferred_providers:
                            preferred_providers.append(provider)
                        break

    # Skip delegation if task is routed to orchestrator (orchestrator handles delegation)
    if target_session == "claude_orchestrator":
        use_delegation = False

    # Use delegation to determine optimal provider if not explicitly specified
    if use_delegation and not target_provider and not preferred_providers:
        try:
            from services.task_delegator import get_delegator

            delegator = get_delegator()
            delegation_result = delegator.delegate_task(content, priority="normal")

            # Map agent to provider/session
            agent_to_provider = {
                "COMET": "comet",
                "CODEX": "codex",
                "CLAUDE-HAIKU": "claude",
                "CLAUDE-SONNET": "claude",
                "OLLAMA": "ollama",
            }

            agent_name = delegation_result.agent.value.upper()
            suggested_provider = agent_to_provider.get(agent_name, "claude")
            suggested_session = delegation_result.session_target

            # Store delegation info in metadata
            metadata["delegated"] = True
            metadata["task_type"] = delegation_result.task_type.value
            metadata["suggested_agent"] = delegation_result.agent.value
            metadata["suggested_model"] = delegation_result.model
            metadata["suggested_session"] = suggested_session
            metadata["delegation_reasoning"] = delegation_result.reasoning

            # Set provider preference based on delegation
            if not target_provider:
                target_provider = suggested_provider
            if not target_session:
                target_session = suggested_session

            logger.info(
                f"Delegated task: {delegation_result.task_type.value} → "
                f"{delegation_result.agent.value} (session: {suggested_session})"
            )

        except Exception as e:
            logger.warning(f"Delegation failed, using defaults: {e}")

    if preferred_providers:
        metadata["preferred_providers"] = preferred_providers
    if fallback_providers:
        metadata["fallback_providers"] = fallback_providers
    if allow_fallback:
        metadata["allow_fallback"] = True
    if not metadata:
        metadata = None

    db = AssignerDatabase()
    prompt_id = db.add_prompt(
        content,
        source=source,
        priority=priority,
        metadata=metadata,
        target_session=target_session,
        target_provider=target_provider,
        timeout_minutes=timeout,
    )

    msg = f"Added prompt {prompt_id} to queue"
    if target_session:
        msg += f" (target: {target_session})"
    if target_provider:
        msg += f" (provider: {target_provider})"
    if metadata and metadata.get("delegated"):
        msg += f" [delegated: {metadata.get('task_type')} → {metadata.get('suggested_agent')}]"
    print(msg)
    return prompt_id


def retry_prompt(prompt_id: int):
    """Retry a failed prompt."""
    db = AssignerDatabase()
    if db.retry_prompt(prompt_id):
        print(f"Prompt {prompt_id} queued for retry")
    else:
        print(f"Could not retry prompt {prompt_id} (not found or not failed)")


def retry_all_failed():
    """Retry all failed prompts."""
    db = AssignerDatabase()
    count = db.retry_all_failed()
    print(f"Queued {count} prompts for retry")


def clear_completed(days: int = 0):
    """Clear completed prompts."""
    db = AssignerDatabase()
    if days > 0:
        count = db.clear_completed(days)
        print(f"Cleared {count} prompts older than {days} days")
    else:
        count = db.clear_all_completed()
        print(f"Cleared {count} completed/cancelled prompts")


def reassign_prompt(prompt_id: int, target: Optional[str] = None):
    """Reassign a prompt."""
    db = AssignerDatabase()
    if db.reassign_prompt(prompt_id, target):
        msg = f"Prompt {prompt_id} reassigned"
        if target:
            msg += f" to {target}"
        print(msg)
    else:
        print(f"Could not reassign prompt {prompt_id}")


def cancel_prompt(prompt_id: int):
    """Cancel a pending prompt."""
    db = AssignerDatabase()
    with db._get_conn() as conn:
        result = conn.execute(
            """
            UPDATE prompts SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
        """,
            (prompt_id,),
        )
        if result.rowcount > 0:
            print(f"Prompt {prompt_id} cancelled")
        else:
            print(f"Could not cancel prompt {prompt_id} (not found or not pending)")


def list_sessions():
    """List all tracked sessions."""
    db = AssignerDatabase()
    sessions = db.get_all_sessions()

    if not sessions:
        print("No sessions tracked yet. Start the worker to scan sessions.")
        return

    print(
        f"\n{'Session':<20} {'Status':<15} {'Provider':<10} {'Claude':<8} "
        f"{'Task ID':<10} {'Working Dir'}"
    )
    print("-" * 110)
    for s in sessions:
        provider = s.get("provider") or ("claude" if s.get("is_claude") else "unknown")
        is_claude = "Yes" if s.get("is_claude") else "No"
        print(
            f"{s['name']:<20} {s['status']:<15} {provider:<10} {is_claude:<8} "
            f"{s.get('current_task_id') or '-':<10} {s.get('working_dir', '-')[:40]}"
        )


def list_prompts(status: Optional[str] = None):
    """List prompts in the queue."""
    db = AssignerDatabase()

    with db._get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM prompts WHERE status = ? ORDER BY created_at DESC LIMIT 20",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM prompts ORDER BY created_at DESC LIMIT 20"
            ).fetchall()

    if not rows:
        print("No prompts found")
        return

    print(f"\n{'ID':<6} {'Status':<12} {'Session':<15} {'Created':<20} {'Content'}")
    print("-" * 100)
    for r in rows:
        content = r["content"][:40] + "..." if len(r["content"]) > 40 else r["content"]
        content = content.replace("\n", " ")
        print(
            f"{r['id']:<6} {r['status']:<12} {r['assigned_session'] or '-':<15} "
            f"{r['created_at'][:19]:<20} {content}"
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Assigner Worker")

    # Worker control
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--poll-interval", type=int, default=3, help="Poll interval in seconds")

    # Prompt operations
    parser.add_argument("--send", metavar="PROMPT", help="Send a prompt to the queue")
    parser.add_argument("--priority", type=int, default=0, help="Prompt priority (default: 0)")
    parser.add_argument("--target", metavar="SESSION", help="Target session for --send")
    parser.add_argument(
        "--provider", metavar="PROVIDER", help="Target provider (claude, codex, ollama)"
    )
    parser.add_argument(
        "--providers",
        metavar="PROVIDERS",
        help="Preferred provider order (comma-separated)",
    )
    parser.add_argument(
        "--fallback",
        metavar="PROVIDERS",
        help="Fallback providers if target unavailable (comma-separated)",
    )
    parser.add_argument(
        "--allow-fallback", action="store_true", help="Allow fallback to any provider"
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in minutes (default: 30)")

    # Context Management (Phase 1, 2 & 3)
    parser.add_argument(
        "--workdir",
        "-w",
        metavar="DIR",
        help="Working directory for task execution (cd before task)",
    )
    parser.add_argument(
        "--env",
        "-e",
        metavar="KEY=VALUE",
        action="append",
        help="Set environment variable (can be used multiple times)",
    )
    parser.add_argument(
        "--prereq",
        metavar="CMD",
        action="append",
        help="Prerequisite command to run before task (can be used multiple times)",
    )
    # Phase 3: Context matching
    parser.add_argument(
        "--git-branch",
        "-b",
        metavar="BRANCH",
        help="Prefer sessions on this git branch (Phase 3)",
    )
    parser.add_argument(
        "--no-context-match",
        action="store_true",
        help="Disable smart context-based session selection (Phase 3)",
    )

    # Environment integration
    parser.add_argument(
        "--project-type",
        metavar="TYPE",
        help="Project type (ui_improvement, performance_optimization, "
        "bug_fix, feature_development)",
    )
    parser.add_argument("--environment", metavar="ENV", help="Specific environment name to use")
    parser.add_argument(
        "--no-env-routing",
        action="store_true",
        help="Disable automatic environment routing",
    )

    # Retry operations
    parser.add_argument("--retry", type=int, metavar="ID", help="Retry a failed prompt by ID")
    parser.add_argument("--retry-all", action="store_true", help="Retry all failed prompts")

    # Reassign operations
    parser.add_argument("--reassign", type=int, metavar="ID", help="Reassign a prompt by ID")
    parser.add_argument("--to", metavar="SESSION", help="Target session for --reassign")

    # Cancel operations
    parser.add_argument("--cancel", type=int, metavar="ID", help="Cancel a pending prompt by ID")

    # Clear operations
    parser.add_argument("--clear", action="store_true", help="Clear completed prompts")
    parser.add_argument("--days", type=int, default=0, help="Only clear prompts older than N days")

    # List operations
    parser.add_argument("--sessions", action="store_true", help="List tracked sessions")
    parser.add_argument("--prompts", action="store_true", help="List prompts")

    args = parser.parse_args()

    if args.stop:
        stop_daemon()
    elif args.status:
        check_status()
    elif args.send:
        try:
            preferred_providers = None
            fallback_providers = None
            if args.providers:
                preferred_providers = [p.strip() for p in args.providers.split(",") if p.strip()]
            if args.fallback:
                fallback_providers = [p.strip() for p in args.fallback.split(",") if p.strip()]
            # Parse --env KEY=VALUE into dict
            env_vars = {}
            if getattr(args, "env", None):
                for env_str in args.env:
                    if "=" in env_str:
                        key, value = env_str.split("=", 1)
                        env_vars[key] = value

            send_prompt(
                args.send,
                priority=args.priority,
                target_session=args.target,
                target_provider=args.provider,
                timeout=args.timeout,
                preferred_providers=preferred_providers,
                fallback_providers=fallback_providers,
                allow_fallback=args.allow_fallback,
                project_type=getattr(args, "project_type", None),
                environment=getattr(args, "environment", None),
                use_environment_routing=not getattr(args, "no_env_routing", False),
                working_dir=getattr(args, "workdir", None),
                env_vars=env_vars if env_vars else None,
                prerequisites=getattr(args, "prereq", None),
                # Phase 3: Context matching
                git_branch=getattr(args, "git_branch", None),
                prefer_context_match=not getattr(args, "no_context_match", False),
            )
        except ValueError as e:
            print(f"Error: {e}")
    elif args.retry is not None:
        retry_prompt(args.retry)
    elif args.retry_all:
        retry_all_failed()
    elif args.reassign is not None:
        reassign_prompt(args.reassign, args.to)
    elif args.cancel is not None:
        cancel_prompt(args.cancel)
    elif args.clear:
        clear_completed(args.days)
    elif args.sessions:
        list_sessions()
    elif args.prompts:
        list_prompts()
    elif args.daemon:
        print("Starting assigner worker daemon...")
        daemonize()
        worker = AssignerWorker(poll_interval=args.poll_interval)
        worker.start()
    else:
        # Run in foreground
        worker = AssignerWorker(poll_interval=args.poll_interval)
        worker.start()


if __name__ == "__main__":
    main()
