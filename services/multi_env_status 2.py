"""
Multi-Environment Status Management Service

Tracks and reports status of:
- 5 development directories (dev1-dev5) with git branches
- 3 sub-environments per directory (dev/qa/staging)
- 26 total sessions (5 dev workers, 3 PR review, 4 PR impl, 3 PR integ)
- PR agent group assignments and status
"""

import json
import logging
import os
import sqlite3
import subprocess
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class MultiEnvStatusManager:
    """Manages status tracking for multi-environment system."""

    def __init__(self, base_dir: str = None, db_path: str = None):
        """
        Initialize the status manager.

        Args:
            base_dir: Base directory containing architect-dev1 through dev5
            db_path: Path to status database
        """
        self.base_dir = base_dir or "/Users/jgirmay/Desktop/gitrepo/pyWork"
        self.main_repo = os.path.join(self.base_dir, "architect")
        self.db_path = db_path or os.path.join(self.main_repo, "data", "multi_env", "status.db")

        # Ensure db directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self._init_database()

        # Cache for git status (30 second TTL)
        self._git_cache = {}
        self._git_cache_time = {}

    def _init_database(self):
        """Initialize the status database with required tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Table for directory status
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS directories (
                name TEXT PRIMARY KEY,
                working_dir TEXT,
                git_branch TEXT,
                branch_ahead INTEGER DEFAULT 0,
                branch_behind INTEGER DEFAULT 0,
                is_dirty BOOLEAN DEFAULT 0,
                last_sync TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Table for sub-environment status
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS environments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directory TEXT NOT NULL,
                env_type TEXT NOT NULL,
                status TEXT DEFAULT 'stopped',
                port INTEGER,
                pid INTEGER,
                url TEXT,
                last_activity TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(directory) REFERENCES directories(name),
                UNIQUE(directory, env_type)
            )
        """
        )

        # Table for PR group assignments
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS pr_groups (
                group_name TEXT NOT NULL,
                session_name TEXT NOT NULL,
                provider TEXT,
                current_pr_id INTEGER,
                status TEXT DEFAULT 'idle',
                last_activity TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_name, session_name)
            )
        """
        )

        # Table for task assignments
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS task_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                task_type TEXT,
                task_description TEXT,
                assigned_at TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'assigned',
                provider TEXT,
                pr_id INTEGER
            )
        """
        )

        # Table for PR provider attribution
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS pr_provider_attribution (
                pr_id INTEGER PRIMARY KEY,
                pr_title TEXT,
                pr_branch TEXT,
                created_by TEXT,
                created_at TIMESTAMP,
                review_provider TEXT,
                implementation_provider TEXT,
                integration_provider TEXT,
                review_session TEXT,
                implementation_session TEXT,
                integration_session TEXT,
                status TEXT DEFAULT 'pending',
                last_updated TIMESTAMP
            )
        """
        )

        conn.commit()
        conn.close()

    def _run_git_command(self, repo_path: str, *args) -> str:
        """Run git command in a repository."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path] + list(args),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Git command failed in {repo_path}: {e}")
            return ""

    def get_directory_status(self, dir_name: str) -> Dict:
        """
        Get directory info including git status.

        Args:
            dir_name: Directory name (e.g., 'dev1')

        Returns:
            Dictionary with directory status
        """
        env_path = os.path.join(self.base_dir, f"architect-{dir_name}")

        if not os.path.isdir(env_path):
            return {
                "name": dir_name,
                "exists": False,
                "status": "not_found",
            }

        # Get git branch
        current_branch = self._run_git_command(env_path, "rev-parse", "--abbrev-ref", "HEAD")
        if not current_branch:
            current_branch = "unknown"

        # Get branch ahead/behind
        ahead_behind = self._run_git_command(
            env_path, "rev-list", "--left-right", "--count", "origin/main...HEAD"
        )

        ahead = 0
        behind = 0
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])

        # Check if dirty
        status_output = self._run_git_command(env_path, "status", "--porcelain")
        is_dirty = len(status_output) > 0
        dirty_count = len(status_output.split("\n")) if is_dirty else 0

        result = {
            "name": dir_name,
            "exists": True,
            "path": env_path,
            "git_branch": current_branch,
            "branch_ahead": ahead,
            "branch_behind": behind,
            "is_dirty": is_dirty,
            "dirty_files": dirty_count,
            "last_sync": datetime.now().isoformat(),
        }

        # Update database
        self._update_directory_status(dir_name, result)

        return result

    def _update_directory_status(self, dir_name: str, status: Dict):
        """Update directory status in database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT OR REPLACE INTO directories
            (name, working_dir, git_branch, branch_ahead, branch_behind, is_dirty, last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                dir_name,
                status["path"],
                status["git_branch"],
                status["branch_ahead"],
                status["branch_behind"],
                int(status["is_dirty"]),
                status["last_sync"],
            ),
        )

        conn.commit()
        conn.close()

    def get_environment_status(self, directory: str, env_type: str) -> Dict:
        """
        Get specific environment status (running/stopped, port, PID).

        Args:
            directory: Directory name (e.g., 'dev1')
            env_type: Environment type ('dev', 'qa', or 'staging')

        Returns:
            Dictionary with environment status
        """
        env_path = os.path.join(self.base_dir, f"architect-{directory}")

        # Map env_type to port offset
        port_offsets = {
            "dev": 0,
            "qa": 10,
            "staging": 20,
        }

        base_port = 8080 + int(directory[-1])  # 8081-8085
        port = base_port + port_offsets.get(env_type, 0)

        pid_file = f"/tmp/architect_dashboard_{directory}_{env_type}.pid"
        pid = None
        is_running = False

        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                    # Check if process is running
                    is_running = os.path.exists(f"/proc/{pid}")
            except (ValueError, IOError):
                pass

        status = "running" if is_running else "stopped"
        url = f"https://localhost:{port}" if is_running else None

        result = {
            "directory": directory,
            "env_type": env_type,
            "status": status,
            "port": port,
            "pid": pid,
            "url": url,
            "database": os.path.join(env_path, f"data/{env_type}/architect.db"),
            "last_activity": datetime.now().isoformat(),
        }

        # Update database
        self._update_environment_status(directory, env_type, result)

        return result

    def _update_environment_status(self, directory: str, env_type: str, status: Dict):
        """Update environment status in database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT OR REPLACE INTO environments
            (directory, env_type, status, port, pid, url, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                directory,
                env_type,
                status["status"],
                status["port"],
                status["pid"],
                status["url"],
                status["last_activity"],
            ),
        )

        conn.commit()
        conn.close()

    def get_pr_group_status(self, group: str = None) -> List[Dict]:
        """
        Get status of all sessions in PR group.

        Args:
            group: PR group name ('PRR', 'PRI', 'PRIG') or None for all

        Returns:
            List of session status dictionaries
        """
        # Map group names to session patterns and providers
        groups = {
            "PRR": {
                "sessions": [f"pr_review{i}" for i in range(1, 4)],
                "providers": {
                    "pr_review1": "claude",
                    "pr_review2": "claude",
                    "pr_review3": "ollama",
                },
            },
            "PRI": {
                "sessions": [f"pr_impl{i}" for i in range(1, 5)],
                "providers": {
                    "pr_impl1": "codex",
                    "pr_impl2": "codex",
                    "pr_impl3": "ollama",
                    "pr_impl4": "ollama",
                },
            },
            "PRIG": {
                "sessions": [f"pr_integ{i}" for i in range(1, 4)],
                "providers": {
                    "pr_integ1": "ollama",
                    "pr_integ2": "ollama",
                    "pr_integ3": "ollama",
                },
            },
        }

        if group and group not in groups:
            return []

        target_groups = [group] if group else list(groups.keys())
        results = []

        for group_name in target_groups:
            group_info = groups[group_name]

            for session_name in group_info["sessions"]:
                provider = group_info["providers"].get(session_name, "unknown")

                result = {
                    "group": group_name,
                    "session": session_name,
                    "provider": provider,
                    "status": self._get_session_status(session_name),
                }

                results.append(result)

        return results

    def _get_session_status(self, session_name: str) -> str:
        """Get tmux session status."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}", "-t", session_name],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and session_name in result.stdout:
                return "active"
            return "inactive"
        except Exception:
            return "unknown"

    def get_system_summary(self) -> Dict:
        """Overall health: directories, environments, sessions, PR groups."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "directories": {},
            "environments": {},
            "pr_groups": {},
            "totals": {
                "directories": 0,
                "environments_running": 0,
                "environments_stopped": 0,
                "sessions_active": 0,
                "sessions_inactive": 0,
            },
        }

        # Get all directories
        for i in range(1, 6):
            dir_name = f"dev{i}"
            dir_status = self.get_directory_status(dir_name)
            summary["directories"][dir_name] = dir_status

            if dir_status.get("exists"):
                summary["totals"]["directories"] += 1

                # Get sub-environments
                for env_type in ["dev", "qa", "staging"]:
                    env_status = self.get_environment_status(dir_name, env_type)
                    key = f"{dir_name}_{env_type}"
                    summary["environments"][key] = env_status

                    if env_status["status"] == "running":
                        summary["totals"]["environments_running"] += 1
                    else:
                        summary["totals"]["environments_stopped"] += 1

        # Get PR groups
        for group in ["PRR", "PRI", "PRIG"]:
            group_status = self.get_pr_group_status(group)
            summary["pr_groups"][group] = group_status

            for session in group_status:
                if session["status"] == "active":
                    summary["totals"]["sessions_active"] += 1
                else:
                    summary["totals"]["sessions_inactive"] += 1

        return summary

    def export_summary_json(self, output_path: str = None) -> str:
        """Export system summary as JSON."""
        summary = self.get_system_summary()
        output_path = output_path or os.path.join(
            self.main_repo, "data", "multi_env", "summary.json"
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        return output_path

    def export_summary_text(self) -> str:
        """Export system summary as formatted text."""
        summary = self.get_system_summary()
        lines = []

        lines.append("╔════════════════════════════════════════════════════════════╗")
        lines.append("║  Multi-Environment Status Report                          ║")
        lines.append(f"║  Last Update: {summary['timestamp'][:19]}                    ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")
        lines.append("║  System Summary:                                          ║")
        lines.append(f"║    Directories: {summary['totals']['directories']} active")
        lines.append(
            f"║    Environments: {summary['totals']['environments_running']} running, "
            f"{summary['totals']['environments_stopped']} stopped"
        )
        lines.append(
            f"║    Sessions: {summary['totals']['sessions_active']} active, "
            f"{summary['totals']['sessions_inactive']} inactive"
        )
        lines.append("║    PR Groups: PRR(3), PRI(4), PRIG(3)")
        lines.append("╚════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Directory status
        for dir_name in sorted(summary["directories"].keys()):
            dir_status = summary["directories"][dir_name]

            if not dir_status.get("exists"):
                lines.append(f"📁 {dir_name} (NOT FOUND)")
                continue

            lines.append(f"📁 {dir_name} ({dir_status['path']})")
            branch_line = f"   Branch: {dir_status['git_branch']}"

            if dir_status["branch_ahead"]:
                branch_line += f" [ahead {dir_status['branch_ahead']}]"
            if dir_status["branch_behind"]:
                branch_line += f" [behind {dir_status['branch_behind']}]"

            clean_status = (
                "clean"
                if not dir_status["is_dirty"]
                else f"dirty: {dir_status['dirty_files']} files"
            )
            branch_line += f" [{clean_status}]"
            lines.append(branch_line)

            # Sub-environments
            for env_type in ["dev", "qa", "staging"]:
                env_key = f"{dir_name}_{env_type}"
                if env_key in summary["environments"]:
                    env = summary["environments"][env_key]
                    status_icon = "🟢" if env["status"] == "running" else "⚫"
                    port_info = f"port {env['port']}"
                    status_info = (
                        f"{status_icon} {env_type.upper()} ({port_info}) - {env['status']}"
                    )
                    lines.append(f"   ├─ {status_info}")

            lines.append("")

        # PR Groups
        lines.append("🔍 PR Agent Groups:")
        for group in ["PRR", "PRI", "PRIG"]:
            if group in summary["pr_groups"]:
                sessions = summary["pr_groups"][group]
                group_names = {"PRR": "Review", "PRI": "Implement", "PRIG": "Integrate"}

                lines.append(f"   {group} ({group_names[group]}):")
                for session in sessions:
                    status_icon = "🔵" if session["status"] == "active" else "🟢"
                    lines.append(f"     {status_icon} {session['session']} ({session['provider']})")

        return "\n".join(lines)

    def track_pr_task(
        self,
        session_name: str,
        pr_id: int,
        task_type: str,
        provider: str,
        task_description: str = None,
    ) -> int:
        """
        Track a task assigned to a PR agent.

        Args:
            session_name: Name of the session (e.g., pr_review1, pr_impl1)
            pr_id: PR number/ID
            task_type: Type of task (review, implementation, integration)
            provider: Provider type (claude, codex, ollama)
            task_description: Optional task description

        Returns:
            Task ID
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO task_assignments
            (session_name, task_type, task_description, assigned_at, status, provider, pr_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_name,
                task_type,
                task_description,
                datetime.now().isoformat(),
                "assigned",
                provider,
                pr_id,
            ),
        )

        task_id = c.lastrowid
        conn.commit()
        conn.close()

        return task_id

    def record_pr_attribution(
        self,
        pr_id: int,
        pr_title: str = None,
        pr_branch: str = None,
        created_by: str = None,
        review_provider: str = None,
        implementation_provider: str = None,
        integration_provider: str = None,
        review_session: str = None,
        implementation_session: str = None,
        integration_session: str = None,
    ):
        """
        Record provider attribution for a PR.

        Tracks which provider (Claude, Codex, Ollama) worked on each stage
        of a pull request (review, implementation, integration).

        Args:
            pr_id: PR number
            pr_title: PR title/subject
            pr_branch: Source branch
            created_by: Original creator
            review_provider: Provider that did code review
            implementation_provider: Provider that implemented changes
            integration_provider: Provider that did integration/testing
            review_session: Session name for review
            implementation_session: Session name for implementation
            integration_session: Session name for integration
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get existing row if it exists
        c.execute("SELECT * FROM pr_provider_attribution WHERE pr_id = ?", (pr_id,))
        existing = c.fetchone()

        if existing:
            # Get column names to map
            cursor = sqlite3.connect(self.db_path).execute(
                "PRAGMA table_info(pr_provider_attribution)"
            )
            columns = [col[1] for col in cursor.fetchall()]
            existing_dict = dict(zip(columns, existing))

            # Merge: new values override existing, None values preserve existing
            final_title = (
                pr_title if pr_title is not None else existing_dict.get("pr_title", f"PR #{pr_id}")
            )
            final_branch = (
                pr_branch if pr_branch is not None else existing_dict.get("pr_branch", "unknown")
            )
            final_created_by = (
                created_by if created_by is not None else existing_dict.get("created_by", "unknown")
            )
            final_review_provider = (
                review_provider
                if review_provider is not None
                else existing_dict.get("review_provider")
            )
            final_review_session = (
                review_session
                if review_session is not None
                else existing_dict.get("review_session")
            )
            final_impl_provider = (
                implementation_provider
                if implementation_provider is not None
                else existing_dict.get("implementation_provider")
            )
            final_impl_session = (
                implementation_session
                if implementation_session is not None
                else existing_dict.get("implementation_session")
            )
            final_integ_provider = (
                integration_provider
                if integration_provider is not None
                else existing_dict.get("integration_provider")
            )
            final_integ_session = (
                integration_session
                if integration_session is not None
                else existing_dict.get("integration_session")
            )
        else:
            final_title = pr_title or f"PR #{pr_id}"
            final_branch = pr_branch or "unknown"
            final_created_by = created_by or "unknown"
            final_review_provider = review_provider
            final_review_session = review_session
            final_impl_provider = implementation_provider
            final_impl_session = implementation_session
            final_integ_provider = integration_provider
            final_integ_session = integration_session

        c.execute(
            """
            INSERT OR REPLACE INTO pr_provider_attribution
            (pr_id, pr_title, pr_branch, created_by, review_provider, implementation_provider,
             integration_provider, review_session, implementation_session, integration_session,
             status, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                pr_id,
                final_title,
                final_branch,
                final_created_by,
                final_review_provider,
                final_impl_provider,
                final_integ_provider,
                final_review_session,
                final_impl_session,
                final_integ_session,
                "pending",
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def get_pr_attribution(self, pr_id: int) -> Dict:
        """
        Get provider attribution for a specific PR.

        Returns dictionary showing which provider worked on each stage.

        Args:
            pr_id: PR number

        Returns:
            Dictionary with PR attribution details
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM pr_provider_attribution WHERE pr_id = ?", (pr_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return None

        # Get column names
        cursor = sqlite3.connect(self.db_path).execute("PRAGMA table_info(pr_provider_attribution)")
        columns = [col[1] for col in cursor.fetchall()]

        return dict(zip(columns, row))

    def get_all_pr_attributions(self) -> List[Dict]:
        """Get attribution info for all PRs."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM pr_provider_attribution ORDER BY pr_id DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return []

        # Get column names
        cursor = sqlite3.connect(self.db_path).execute("PRAGMA table_info(pr_provider_attribution)")
        columns = [col[1] for col in cursor.fetchall()]

        return [dict(zip(columns, row)) for row in rows]

    def format_pr_attribution_report(self) -> str:
        """
        Format PR provider attribution data for display.

        Returns:
            Formatted report showing which provider worked on each PR
        """
        attributions = self.get_all_pr_attributions()

        if not attributions:
            return "No PR attribution data available"

        lines = []
        lines.append("╔═══════════════════════════════════════════════════════════╗")
        lines.append("║  PR Provider Attribution Report                          ║")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"║  Last Update: {timestamp}                        ║")
        lines.append("╚═══════════════════════════════════════════════════════════╝")
        lines.append("")

        provider_icons = {
            "claude": "🔵",
            "codex": "🟠",
            "ollama": "🟡",
            "unknown": "⚪",
        }

        for attr in attributions:
            lines.append(f"PR #{attr['pr_id']}: {attr['pr_title'][:50]}")
            lines.append(f"  Branch: {attr['pr_branch']}")

            if attr["review_provider"]:
                icon = provider_icons.get(attr["review_provider"], "⚪")
                lines.append(
                    f"  {icon} Review: {attr['review_provider']} " f"({attr['review_session']})"
                )

            if attr["implementation_provider"]:
                icon = provider_icons.get(attr["implementation_provider"], "⚪")
                lines.append(
                    f"  {icon} Implementation: {attr['implementation_provider']} "
                    f"({attr['implementation_session']})"
                )

            if attr["integration_provider"]:
                icon = provider_icons.get(attr["integration_provider"], "⚪")
                lines.append(
                    f"  {icon} Integration: {attr['integration_provider']} "
                    f"({attr['integration_session']})"
                )

            lines.append(f"  Status: {attr['status']}")
            lines.append("")

        return "\n".join(lines)
