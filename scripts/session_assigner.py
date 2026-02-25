#!/usr/bin/env python3
"""
Session Assigner - Coordinates Claude/Codex/Ollama sessions with proper environment isolation.

Enforces SOP:
1. Each session works in isolated environment (feature env or branch)
2. No two sessions work on same files
3. Database access is coordinated
4. Tasks tracked in central queue

Usage:
    python3 session_assigner.py assign <session|auto> <task> [--env <env>] [--project <project>] [--provider <p>] [--fallback <p1,p2>]
    python3 session_assigner.py status
    python3 session_assigner.py list-sessions
    python3 session_assigner.py list-envs
    python3 session_assigner.py release <session>
    python3 session_assigner.py reload-config

Ollama Commands:
    python3 session_assigner.py ollama-status              # Show Ollama status
    python3 session_assigner.py ollama-models              # List available models
    python3 session_assigner.py ollama-start <session> [--model <m>] [--task <t>]
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# =============================================================================
# CONFIG LOADER
# =============================================================================


class ConfigLoader:
    """Load and access session assigner configuration from YAML."""

    def __init__(self, config_path: Path = None):
        self.script_dir = Path(__file__).parent
        self.project_dir = self.script_dir.parent

        if config_path is None:
            config_path = self.project_dir / "config" / "session_assigner.yaml"

        self.config_path = config_path
        self._config = None
        self._load_config()

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve path variables and expand home directory."""
        if not path_str:
            return None

        # Replace variables
        path_str = path_str.replace("${PROJECT_DIR}", str(self.project_dir))
        path_str = path_str.replace("${DATA_DIR}", str(self.data_dir))

        # Expand ~ to home directory
        if path_str.startswith("~"):
            path_str = str(Path.home()) + path_str[1:]

        return Path(path_str)

    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self._config = yaml.safe_load(f)

        # Resolve data_dir first (needed for other paths)
        raw_data_dir = self._config.get("paths", {}).get("data_dir", "${PROJECT_DIR}/data")
        self.data_dir = Path(raw_data_dir.replace("${PROJECT_DIR}", str(self.project_dir)))

    def reload(self):
        """Reload configuration from file."""
        self._load_config()

    @property
    def principles(self) -> List[str]:
        """Get core principles."""
        return self._config.get("principles", [])

    @property
    def state_file(self) -> Path:
        """Get state file path."""
        raw = self._config.get("paths", {}).get("state_file", "${DATA_DIR}/session_state.json")
        return self._resolve_path(raw)

    @property
    def lock_dir(self) -> Path:
        """Get lock directory path."""
        raw = self._config.get("paths", {}).get("lock_dir", "${DATA_DIR}/locks")
        return self._resolve_path(raw)

    def get_project(self, name: str) -> Optional[Dict]:
        """Get project configuration by name."""
        return self._config.get("projects", {}).get(name)

    def get_project_path(self, name: str) -> Optional[Path]:
        """Get resolved project path."""
        project = self.get_project(name)
        if project and "path" in project:
            return self._resolve_path(project["path"])
        return None

    def get_all_projects(self) -> Dict[str, Dict]:
        """Get all project configurations."""
        return self._config.get("projects", {})

    def get_environments(self, project: str) -> Dict[str, Dict]:
        """Get environments for a project."""
        proj = self.get_project(project)
        if proj:
            return proj.get("environments", {})
        return {}

    def get_scopes(self, project: str) -> Dict[str, Dict]:
        """Get scopes for a project (architect only)."""
        proj = self.get_project(project)
        if proj:
            return proj.get("scopes", {})
        return {}

    def get_sop_rules(self, project: str) -> List[str]:
        """Get SOP rules for a project."""
        proj = self.get_project(project)
        if proj:
            return proj.get("sop_rules", [])
        return []

    def get_scope_rules(self, project: str, scope: str) -> List[str]:
        """Get SOP rules for a specific scope."""
        scopes = self.get_scopes(project)
        if scope in scopes:
            return scopes[scope].get("sop_rules", [])
        return []

    def detect_project_from_session(self, session_name: str) -> str:
        """Detect project from session name using patterns."""
        patterns = self._config.get("session_patterns", [])
        for pattern_config in patterns:
            pattern = pattern_config.get("pattern", "")
            project = pattern_config.get("project", "edu_apps")
            if re.match(pattern, session_name, re.IGNORECASE):
                return project
        return "edu_apps"  # Default fallback

    def detect_scope_from_task(self, task: str) -> str:
        """Detect architect scope from task keywords."""
        task_lower = task.lower()
        keywords = self._config.get("scope_keywords", {})

        for scope, scope_keywords in keywords.items():
            for keyword in scope_keywords:
                if keyword in task_lower:
                    return scope
        return "readonly"  # Default fallback

    def get_preferred_env_order(self, project: str) -> List[str]:
        """Get preferred environment assignment order."""
        proj = self.get_project(project)
        if proj:
            return proj.get(
                "preferred_assignment_order", list(self.get_environments(project).keys())
            )
        return []

    def get_completion_instructions(self, context: str) -> List[str]:
        """Get completion instructions for a context."""
        instructions = self._config.get("completion_instructions", {})
        return instructions.get(context, instructions.get("default", []))

    def get_task_history_max(self) -> int:
        """Get maximum task history items."""
        return self._config.get("task_history", {}).get("max_items", 100)

    def get_prompt_template_settings(self) -> Dict:
        """Get prompt template settings."""
        return self._config.get("prompt_template", {"header_width": 60, "header_char": "="})

    def get_provider_config(self) -> Dict:
        """Get provider configuration."""
        return self._config.get("providers", {})

    def get_provider_order(self) -> List[str]:
        """Get provider preference order."""
        providers = self.get_provider_config()
        order = providers.get("order", [])
        return order or ["claude", "codex", "ollama"]

    def get_provider_patterns(self) -> Dict[str, List[str]]:
        """Get provider detection patterns."""
        providers = self.get_provider_config()
        patterns = providers.get("detect", {})
        if patterns:
            return patterns
        return {
            "claude": ["claude", "anthropic", "claude-code"],
            "codex": ["codex", "openai"],
            "ollama": ["ollama"],
        }


# =============================================================================
# GLOBAL CONFIG INSTANCE
# =============================================================================

# Load config on module import
CONFIG = ConfigLoader()

# Convenience accessors
SCRIPT_DIR = CONFIG.script_dir
PROJECT_DIR = CONFIG.project_dir
DATA_DIR = CONFIG.data_dir
STATE_FILE = CONFIG.state_file
LOCK_DIR = CONFIG.lock_dir

# Ensure directories exist
LOCK_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================


def load_state() -> Dict:
    """Load session state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "sessions": {},
        "env_assignments": {},
        "scope_locks": {},
        "task_history": [],
    }


def save_state(state: Dict):
    """Save session state to file."""
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# =============================================================================
# TMUX UTILITIES
# =============================================================================

PROVIDER_PATTERNS = {
    provider: re.compile("|".join(patterns), re.IGNORECASE)
    for provider, patterns in CONFIG.get_provider_patterns().items()
}


def detect_provider(session_name: str, output: str = "") -> str:
    """Detect provider based on session name or output."""
    for provider, regex in PROVIDER_PATTERNS.items():
        if session_name and regex.search(session_name):
            return provider
    for provider, regex in PROVIDER_PATTERNS.items():
        if output and regex.search(output):
            return provider
    return "unknown"


def get_tmux_sessions() -> List[str]:
    """Get list of active tmux sessions."""
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
    )
    if result.returncode == 0:
        return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
    return []


def send_to_session(session: str, message: str) -> bool:
    """Send a message to a tmux session."""
    # First, send Ctrl-C to interrupt any current work
    subprocess.run(["tmux", "send-keys", "-t", session, "C-c"], capture_output=True)
    time.sleep(0.5)

    # Then send the message
    result = subprocess.run(
        ["tmux", "send-keys", "-t", session, message, "Enter"], capture_output=True
    )
    return result.returncode == 0


def get_session_info(session: str) -> Optional[Dict]:
    """Get info about a tmux session."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p"], capture_output=True, text=True
    )
    if result.returncode == 0:
        output = result.stdout
        provider = detect_provider(session, output)
        # Check if Claude is running (kept for backward compatibility)
        is_claude = (
            provider == "claude" or "bypass permissions" in output or "accept edits" in output
        )
        is_working = "(running)" in output or "(thinking)" in output
        return {
            "active": True,
            "is_claude": is_claude,
            "is_working": is_working,
            "provider": provider,
            "last_output": output[-500:] if output else "",
        }
    return None


# =============================================================================
# ENVIRONMENT ASSIGNMENT
# =============================================================================


def assign_env(session: str, project: str, state: Dict) -> Optional[str]:
    """Assign an available environment to a session."""
    envs = CONFIG.get_environments(project)
    used_envs = set(state["env_assignments"].get(project, {}).values())

    # Get preferred order or use all keys
    preferred = CONFIG.get_preferred_env_order(project)
    if not preferred:
        preferred = list(envs.keys())

    for env_name in preferred:
        if env_name in envs and env_name not in used_envs:
            # Check if environment is protected
            if envs[env_name].get("protected", False):
                continue
            if project not in state["env_assignments"]:
                state["env_assignments"][project] = {}
            state["env_assignments"][project][session] = env_name
            return env_name
    return None


def assign_scope(session: str, scope: str, state: Dict) -> bool:
    """Assign an architect scope to a session."""
    scopes = CONFIG.get_scopes("architect")
    if scope not in scopes:
        return False

    scope_info = scopes[scope]

    # Check if scope is exclusive and already taken
    if scope_info.get("exclusive", False):
        current_locks = state.get("scope_locks", {}).get("architect", {})
        for locked_session, locked_scope in current_locks.items():
            if locked_scope == scope and locked_session != session:
                return False

    if "architect" not in state.get("scope_locks", {}):
        state["scope_locks"]["architect"] = {}
    state["scope_locks"]["architect"][session] = scope
    return True


def release_session(session: str, state: Dict):
    """Release all assignments for a session."""
    # Release all project environments
    for project in CONFIG.get_all_projects():
        if project in state.get("env_assignments", {}):
            if session in state["env_assignments"][project]:
                del state["env_assignments"][project][session]

    # Release architect scope
    if "architect" in state.get("scope_locks", {}):
        if session in state["scope_locks"]["architect"]:
            del state["scope_locks"]["architect"][session]

    # Clear session info
    if session in state.get("sessions", {}):
        del state["sessions"][session]


# =============================================================================
# PROMPT BUILDING
# =============================================================================


def build_task_prompt(
    task: str, project: str, env_info: Dict, provider: Optional[str] = None
) -> str:
    """Build a complete task prompt with environment context and SOP rules."""
    template = CONFIG.get_prompt_template_settings()
    header_width = template.get("header_width", 60)
    header_char = template.get("header_char", "=")

    lines = []

    # Header with principles
    lines.append(header_char * header_width)
    lines.append("AGENT SESSION ASSIGNMENT")
    lines.append(header_char * header_width)
    lines.append("")
    lines.append("PRINCIPLES: " + ", ".join(CONFIG.principles))
    if provider:
        lines.append(f"PROVIDER: {provider}")
    lines.append("")

    project_config = CONFIG.get_project(project)
    project_path = CONFIG.get_project_path(project)

    if project == "edu_apps":
        env_path = project_path / env_info.get("path", "") if project_path else Path(".")
        lines.append(f"PROJECT: {project_config.get('name', project)}")
        lines.append(f"ENVIRONMENT: {env_info.get('path', 'unknown')}")
        lines.append(f"BRANCH: {env_info.get('branch', 'unknown')}")
        lines.append(f"PORT: {env_info.get('port', 'unknown')}")
        lines.append(f"DIRECTORY: {env_path}")
        lines.append("")
        lines.append("SETUP COMMANDS:")
        lines.append(f"cd {env_path}")
        lines.append(f"git checkout {env_info.get('branch', 'dev')}")
        lines.append("")
        lines.append("SOP RULES - YOU MUST FOLLOW:")
        for i, rule in enumerate(CONFIG.get_sop_rules(project), 1):
            lines.append(f"{i}. {rule}")
        lines.append("")
        lines.append("TESTING:")
        port = env_info.get("port", 5054)
        start_cmd = project_config.get("start_command", "").format(port=port)
        test_url = project_config.get("test_url_template", "").format(port=port)
        lines.append(f"- Start: {start_cmd}")
        lines.append(f"- URL: {test_url}")
        lines.append("")

    elif project == "kanbanflow":
        lines.append(f"PROJECT: {project_config.get('name', project)}")
        lines.append(f"ENVIRONMENT: {env_info.get('branch', 'dev')}")
        lines.append(f"PORT: {env_info.get('port', 6051)}")
        lines.append(f"DIRECTORY: {project_path}")
        lines.append("")
        lines.append("SETUP COMMANDS:")
        lines.append(f"cd {project_path}")
        branch = env_info.get("branch", "dev")
        lines.append(f"git checkout {branch} 2>/dev/null || git checkout -b {branch}")
        lines.append("")
        lines.append("SOP RULES - YOU MUST FOLLOW:")
        for i, rule in enumerate(CONFIG.get_sop_rules(project), 1):
            lines.append(f"{i}. {rule}")
        lines.append("")
        lines.append("TESTING:")
        port = env_info.get("port", 6051)
        start_cmd = project_config.get("start_command", "").format(port=port)
        test_url = project_config.get("test_url_template", "").format(port=port)
        lines.append(f"- Start: {start_cmd}")
        lines.append(f"- URL: {test_url}")
        lines.append("")

    elif project == "architect":
        scope = env_info.get("scope", "readonly")
        scopes = CONFIG.get_scopes("architect")
        scope_info = scopes.get(scope, {})

        lines.append(f"PROJECT: {project_config.get('name', project)}")
        lines.append(f"SCOPE: {scope.upper()}")
        exclusive = scope_info.get("exclusive", False)
        lines.append(
            f"EXCLUSIVE: {'YES - only you can modify these files' if exclusive else 'NO - others may also work here'}"
        )
        lines.append(f"FILES: {', '.join(scope_info.get('files', ['none']))}")
        lines.append(f"DIRECTORY: {project_path}")
        lines.append("")
        lines.append("SETUP COMMANDS:")
        lines.append(f"cd {project_path}")
        lines.append("")
        lines.append("SOP RULES - YOU MUST FOLLOW:")
        for i, rule in enumerate(CONFIG.get_scope_rules("architect", scope), 1):
            lines.append(f"{i}. {rule}")
        lines.append("")
        lines.append("TESTING:")
        lines.append(f"- Dashboard: {project_config.get('test_url', 'http://localhost:8086/')}")
        lines.append(
            f"- Health: curl {project_config.get('health_url', 'http://localhost:8086/health')}"
        )
        lines.append("")

    # Task
    lines.append(header_char * header_width)
    lines.append("YOUR TASK:")
    lines.append(header_char * header_width)
    lines.append(task)
    lines.append("")
    lines.append("WHEN COMPLETE:")

    # Context-aware completion instructions
    scope = env_info.get("scope", "")
    if scope == "readonly":
        context = "readonly"
    elif project == "kanbanflow" and env_info.get("branch") == "main":
        context = "protected_branch"
    else:
        context = "default"

    for instruction in CONFIG.get_completion_instructions(context):
        lines.append(f"- {instruction}")
    lines.append(header_char * header_width)

    return "\n".join(lines)


def _normalize_provider_list(provider: Optional[str], fallback: Optional[List[str]]) -> List[str]:
    """Normalize provider preference list with optional fallbacks."""
    providers: List[str] = []
    if provider and provider != "auto":
        providers.append(provider)
    else:
        providers.extend(CONFIG.get_provider_order())

    if fallback:
        for fb in fallback:
            if fb not in providers:
                providers.append(fb)

    # Remove unknown/empty
    return [p for p in providers if p and p != "unknown"]


def select_available_session(
    state: Dict, providers: Optional[List[str]] = None
) -> Optional[Tuple[str, Dict]]:
    """Select an available session, optionally filtered by provider preference."""
    tmux_sessions = get_tmux_sessions()
    assigned = set(state.get("sessions", {}).keys())

    candidates: List[Tuple[str, Dict]] = []
    for session in tmux_sessions:
        if session in assigned:
            continue
        info = get_session_info(session)
        if not info or info.get("is_working"):
            continue
        candidates.append((session, info))

    if not candidates:
        return None

    if providers:
        for provider in providers:
            for session, info in candidates:
                if info.get("provider") == provider:
                    return session, info

    return candidates[0]


# =============================================================================
# TASK ASSIGNMENT
# =============================================================================


def assign_task(
    session: str,
    task: str,
    project: str = None,
    env: str = None,
    provider: Optional[str] = None,
    fallback_providers: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Assign a task to a session with proper environment."""
    state = load_state()

    # Auto-select session if requested
    if session in (None, "auto", "any", "*"):
        preferred = _normalize_provider_list(provider, fallback_providers)
        selection = select_available_session(state, providers=preferred)
        if not selection:
            provider_msg = f" (providers: {', '.join(preferred)})" if preferred else ""
            return False, f"No available sessions{provider_msg}"
        session, session_info = selection
    else:
        session_info = get_session_info(session)

    # Check if session exists
    tmux_sessions = get_tmux_sessions()
    if session not in tmux_sessions:
        return False, f"Session '{session}' not found in tmux"

    # Determine project from session name if not specified
    if not project:
        project = CONFIG.detect_project_from_session(session)

    # Assign environment
    env_info = {}

    if project == "edu_apps":
        envs = CONFIG.get_environments("edu_apps")
        if env:
            if env in envs:
                env_info = envs[env]
                state["env_assignments"].setdefault("edu_apps", {})[session] = env
            else:
                return False, f"Unknown edu_apps environment: {env}"
        else:
            # Auto-assign
            assigned_env = assign_env(session, "edu_apps", state)
            if assigned_env:
                env_info = envs[assigned_env]
            else:
                return False, "No available edu_apps environments"

    elif project == "kanbanflow":
        envs = CONFIG.get_environments("kanbanflow")
        if env:
            if env in envs:
                env_info = envs[env]
                state["env_assignments"].setdefault("kanbanflow", {})[session] = env
            else:
                return False, f"Unknown kanbanflow environment: {env}"
        else:
            assigned_env = assign_env(session, "kanbanflow", state)
            if assigned_env:
                env_info = envs[assigned_env]
            else:
                return False, "No available kanbanflow environments"

    elif project == "architect":
        # Determine scope from task or env parameter
        scope = env if env else CONFIG.detect_scope_from_task(task)

        if not assign_scope(session, scope, state):
            return False, f"Architect scope '{scope}' is locked by another session"

        env_info = {"scope": scope}

    session_provider = (session_info or {}).get("provider") if session_info else None
    if provider and provider != "auto" and (not session_provider or session_provider == "unknown"):
        session_provider = provider

    # Build and send prompt
    prompt = build_task_prompt(task, project, env_info, provider=session_provider)

    # Record assignment
    state["sessions"][session] = {
        "project": project,
        "env_info": env_info,
        "task": task,
        "assigned_at": datetime.now().isoformat(),
        "status": "assigned",
        "provider": session_provider or "unknown",
        "provider_preference": provider or "auto",
        "provider_fallback": fallback_providers or [],
    }

    state["task_history"].append(
        {
            "session": session,
            "project": project,
            "task": task,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Keep only last N history items
    max_history = CONFIG.get_task_history_max()
    state["task_history"] = state["task_history"][-max_history:]

    save_state(state)

    # Send to session
    if send_to_session(session, prompt):
        return True, f"Assigned to {session} [{project}/{env_info}]"
    else:
        return False, "Failed to send to tmux session"


# =============================================================================
# STATUS & LISTING
# =============================================================================


def show_status():
    """Show current assignment status."""
    state = load_state()
    tmux_sessions = get_tmux_sessions()

    print("\n" + "=" * 80)
    print("  SESSION ASSIGNER STATUS")
    print("=" * 80)

    # Edu Apps Environments
    print("\n  EDU APPS FEATURE ENVIRONMENTS:")
    edu_envs = CONFIG.get_environments("edu_apps")
    edu_assignments = state.get("env_assignments", {}).get("edu_apps", {})
    for env_name, env_info in edu_envs.items():
        assigned_to = None
        for session, assigned_env in edu_assignments.items():
            if assigned_env == env_name:
                assigned_to = session
                break
        status = f"→ {assigned_to}" if assigned_to else "AVAILABLE"
        print(f"    {env_name} (:{env_info['port']}) {env_info['branch']}: {status}")

    # KanbanFlow Environments
    print("\n  KANBANFLOW ENVIRONMENTS:")
    kanban_envs = CONFIG.get_environments("kanbanflow")
    kanban_assignments = state.get("env_assignments", {}).get("kanbanflow", {})
    for env_name, env_info in kanban_envs.items():
        assigned_to = None
        for session, assigned_env in kanban_assignments.items():
            if assigned_env == env_name:
                assigned_to = session
                break
        status = f"→ {assigned_to}" if assigned_to else "AVAILABLE"
        protected = " [PROTECTED]" if env_info.get("protected") else ""
        print(f"    {env_name} (:{env_info['port']}) {env_info['branch']}{protected}: {status}")

    # Architect Scopes
    print("\n  ARCHITECT SCOPES:")
    arch_scopes = CONFIG.get_scopes("architect")
    arch_locks = state.get("scope_locks", {}).get("architect", {})
    for scope, info in arch_scopes.items():
        assigned_to = None
        for session, assigned_scope in arch_locks.items():
            if assigned_scope == scope:
                assigned_to = session
                break
        exclusive = "[EXCLUSIVE]" if info.get("exclusive") else ""
        status = f"→ {assigned_to}" if assigned_to else "AVAILABLE"
        print(f"    {scope} {exclusive}: {status}")

    # Active Sessions
    print("\n  ACTIVE SESSIONS:")
    for session in sorted(tmux_sessions):
        info = state.get("sessions", {}).get(session, {})
        if info:
            project = info.get("project", "?")
            provider = info.get("provider", "unknown")
            task = info.get("task", "")[:50]
            print(f"    {session}: [{project}] [{provider}] {task}...")
        else:
            print(f"    {session}: (unassigned)")

    print("\n" + "=" * 80)


def list_available_sessions():
    """List available tmux sessions."""
    state = load_state()
    tmux_sessions = get_tmux_sessions()
    assigned = set(state.get("sessions", {}).keys())

    print("\nTmux Sessions:")
    print("-" * 60)
    for session in sorted(tmux_sessions):
        info = get_session_info(session)
        status = []
        if info:
            provider = info.get("provider")
            if provider and provider != "unknown":
                status.append(provider)
            if info["is_working"]:
                status.append("working")
        if session in assigned:
            status.append("assigned")

        status_str = f"[{', '.join(status)}]" if status else ""
        print(f"  {session} {status_str}")
    print("-" * 60)


def list_environments():
    """List all environments from config."""
    print("\nEdu Apps Environments:")
    for name, info in CONFIG.get_environments("edu_apps").items():
        print(f"  {name}: port {info['port']}, branch {info['branch']}")

    print("\nKanbanFlow Environments:")
    for name, info in CONFIG.get_environments("kanbanflow").items():
        protected = " (PROTECTED)" if info.get("protected") else ""
        print(f"  {name}: port {info['port']}, branch {info['branch']}{protected}")

    print("\nArchitect Scopes:")
    for name, info in CONFIG.get_scopes("architect").items():
        exclusive = "(exclusive)" if info.get("exclusive") else ""
        print(f"  {name}: {info.get('files', [])} {exclusive}")


# =============================================================================
# OLLAMA INTEGRATION
# =============================================================================


def get_ollama_config() -> Dict:
    """Get Ollama configuration from YAML."""
    return CONFIG._config.get("ollama", {})


def check_ollama_status() -> Tuple[bool, str]:
    """Check if Ollama server is running."""
    import urllib.error
    import urllib.request

    config = get_ollama_config()
    base_url = config.get("base_url", "http://100.112.58.92:11434")

    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            return True, f"Ollama running with {len(models)} models"
    except urllib.error.URLError as e:
        return False, f"Ollama not available: {e}"
    except Exception as e:
        return False, f"Error checking Ollama: {e}"


def list_ollama_models() -> List[Dict]:
    """List available Ollama models."""
    import urllib.request

    config = get_ollama_config()
    base_url = config.get("base_url", "http://100.112.58.92:11434")

    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("models", [])
    except Exception:
        return []


def start_ollama_session(
    session_name: str, model: str = None, task: str = None
) -> Tuple[bool, str]:
    """Start an Ollama session in tmux."""
    config = get_ollama_config()

    if not config.get("enabled", True):
        return False, "Ollama is disabled in configuration"

    model = model or config.get("default_model", "llama3.2:latest")

    # Check if Ollama is running
    available, msg = check_ollama_status()
    if not available:
        return False, msg

    # Build command
    wrapper_path = Path.home() / "Desktop/gitrepo/pyWork/basic_edu_apps_final/claude_wrapper.py"
    if not wrapper_path.exists():
        return False, f"Wrapper not found: {wrapper_path}"

    cmd = f"python3 {wrapper_path} --ollama --model {model}"

    # Create or attach to tmux session
    existing = get_tmux_sessions()
    if session_name in existing:
        # Send command to existing session
        subprocess.run(["tmux", "send-keys", "-t", session_name, cmd, "Enter"], check=True)
    else:
        # Create new session with command
        subprocess.run(["tmux", "new-session", "-d", "-s", session_name, cmd], check=True)

    # Send task if provided
    if task:
        time.sleep(2)  # Wait for session to start
        subprocess.run(["tmux", "send-keys", "-t", session_name, task, "Enter"], check=True)

    return True, f"Ollama session '{session_name}' started with model {model}"


def show_ollama_status():
    """Show Ollama status and configuration."""
    config = get_ollama_config()
    available, msg = check_ollama_status()

    print("\n" + "=" * 60)
    print("  OLLAMA STATUS")
    print("=" * 60)

    status = "RUNNING" if available else "OFFLINE"
    print(f"\n  Status: {status}")
    print(f"  Base URL: {config.get('base_url', 'http://100.112.58.92:11434')}")
    print(f"  Default Model: {config.get('default_model', 'llama3.2:latest')}")
    print(f"  Enabled: {config.get('enabled', True)}")

    if available:
        models = list_ollama_models()
        print(f"\n  Available Models ({len(models)}):")
        for m in models:
            size_gb = m.get("size", 0) / 1e9
            print(f"    - {m['name']} ({size_gb:.1f}GB)")

    # Show configured models
    configured = config.get("models", [])
    if configured:
        print(f"\n  Configured Models:")
        for m in configured:
            print(f"    - {m['name']}: {m.get('description', '')}")
            print(f"      Use for: {', '.join(m.get('use_for', []))}")

    print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "assign":
        if len(sys.argv) < 4:
            print(
                "Usage: session_assigner.py assign <session|auto> <task> [--project <p>] [--env <e>] [--provider <p>] [--fallback <p1,p2>]"
            )
            return

        session = sys.argv[2]
        task = sys.argv[3]
        project = None
        env = None
        provider = None
        fallback = None

        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project = sys.argv[idx + 1]

        if "--env" in sys.argv:
            idx = sys.argv.index("--env")
            if idx + 1 < len(sys.argv):
                env = sys.argv[idx + 1]

        if "--provider" in sys.argv:
            idx = sys.argv.index("--provider")
            if idx + 1 < len(sys.argv):
                provider = sys.argv[idx + 1]

        if "--fallback" in sys.argv:
            idx = sys.argv.index("--fallback")
            if idx + 1 < len(sys.argv):
                raw = sys.argv[idx + 1]
                fallback = [p.strip() for p in raw.split(",") if p.strip()]

        success, message = assign_task(
            session, task, project, env, provider=provider, fallback_providers=fallback
        )
        print(message)

    elif cmd == "status":
        show_status()

    elif cmd == "list-sessions":
        list_available_sessions()

    elif cmd == "list-envs":
        list_environments()

    elif cmd == "release":
        if len(sys.argv) < 3:
            print("Usage: session_assigner.py release <session>")
            return
        session = sys.argv[2]
        state = load_state()
        release_session(session, state)
        save_state(state)
        print(f"Released assignments for {session}")

    elif cmd == "release-all":
        state = load_state()
        state["sessions"] = {}
        state["env_assignments"] = {}
        state["scope_locks"] = {}
        save_state(state)
        print("Released all assignments")

    elif cmd == "reload-config":
        CONFIG.reload()
        print("Configuration reloaded")

    elif cmd == "ollama-status":
        show_ollama_status()

    elif cmd == "ollama-models":
        models = list_ollama_models()
        if models:
            print("Available Ollama models:")
            for m in models:
                size_gb = m.get("size", 0) / 1e9
                print(f"  - {m['name']} ({size_gb:.1f}GB)")
        else:
            print("No Ollama models found or Ollama not running")

    elif cmd == "ollama-start":
        if len(sys.argv) < 3:
            print("Usage: session_assigner.py ollama-start <session> [--model <m>] [--task <t>]")
            return

        session = sys.argv[2]
        model = None
        task = None

        if "--model" in sys.argv:
            idx = sys.argv.index("--model")
            if idx + 1 < len(sys.argv):
                model = sys.argv[idx + 1]

        if "--task" in sys.argv:
            idx = sys.argv.index("--task")
            if idx + 1 < len(sys.argv):
                task = sys.argv[idx + 1]

        success, message = start_ollama_session(session, model, task)
        print(message)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
