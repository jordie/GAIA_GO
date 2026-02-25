"""
Configuration and patterns for Claude Code wrapper.

This module can be reloaded to update patterns without restarting the wrapper.
Integrates with session_assigner for coordinated Claude session management.
"""

import re
from pathlib import Path

__version__ = "2.0.0"

# Auto-approve all prompts (set via --approve-all flag)
AUTO_APPROVE_ALL = False

# Paths
SCRIPT_DIR = Path(__file__).parent.parent
SESSION_LOG_PATH = SCRIPT_DIR / "claude_confirmations.md"
OUTPUT_BUFFER_PATH = Path("/tmp/claude_session_output.txt")
STATE_FILE_PATH = Path("/tmp/claude_wrapper_state.json")
RELOAD_SIGNAL_PATH = Path("/tmp/claude_wrapper_reload")
ASSIGNER_STATE_FILE = Path("/tmp/session_assigner_state.json")  # For integration

# Known operation types for confirmation prompts
OPERATION_TYPES = (
    r"(?:Bash command|Edit file|Write file|Read file|Create file|Delete file|Execute|Bash)"
)

# Pattern to detect permission prompts
PROMPT_PATTERN = re.compile(
    r"─{20,}\s*\n"  # Separator line (20+ dashes)
    r"\s*(?P<operation_type>" + OPERATION_TYPES + r")\s*\n"  # Operation type
    r"\s*\n?"  # Optional blank line
    r"\s*(?P<command>.+?)\s*\n"  # Command (may have indentation)
    r"\s*(?P<description>[^\n]*?)\s*\n"  # Description
    r"[\s\n]*"  # Optional whitespace
    r"\s*Do you want to proceed\?\s*\n"  # Question
    r"(?P<options>(?:.*?\d+\..*?\n)+)"  # Options
    r".*?Esc to cancel",  # Cancel instruction
    re.MULTILINE | re.DOTALL,
)

# Alternative simpler pattern for yes/no prompts
YES_NO_PATTERN = re.compile(
    r"(?:Do you want to|Would you like to|Proceed with|Accept|Allow)\s*[^?]*\?\s*"
    r"(?:\(y/n\)|(?:yes|no))",
    re.IGNORECASE,
)

# ANSI escape code pattern for stripping colors
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Response rules: patterns -> auto-response
# These are organized by safety level and operation type
RESPONSE_RULES = {
    # === GIT OPERATIONS (generally safe) ===
    "git_status": {
        "pattern": r"git\s+(status|diff|log|show|branch)",
        "response": 1,
        "description": "Git read-only operations",
    },
    "git_commit": {
        "pattern": r"git\s+(add|commit|tag)",
        "response": 1,
        "description": "Git local commit operations",
    },
    "git_push": {
        "pattern": r"git\s+(push|pull|fetch)",
        "response": 1,
        "description": "Git remote operations",
    },
    "git_branch": {
        "pattern": r"git\s+(checkout|switch|merge|rebase|stash|worktree)",
        "response": 1,
        "description": "Git branch operations",
    },
    # === FILE READ OPERATIONS (safe) ===
    "read_any": {"pattern": r"Read file", "response": 1, "description": "Read file operations"},
    "cat_head_tail": {
        "pattern": r"(cat|head|tail|less|more)\s+",
        "response": 1,
        "description": "File viewing commands",
    },
    "ls_find": {
        "pattern": r"(ls|find|tree|du|df|pwd)",
        "response": 1,
        "description": "Directory listing commands",
    },
    # === FILE EDIT OPERATIONS ===
    "edit_any": {"pattern": r"Edit file", "response": 1, "description": "File edit operations"},
    "write_any": {"pattern": r"Write file", "response": 1, "description": "File write operations"},
    "create_file": {"pattern": r"Create file", "response": 1, "description": "File creation"},
    # === DEVELOPMENT TOOLS ===
    "python_run": {"pattern": r"python3?\s+", "response": 1, "description": "Python execution"},
    "npm_yarn": {
        "pattern": r"(npm|yarn|pnpm)\s+(install|run|build|test|start)",
        "response": 1,
        "description": "Node package manager commands",
    },
    "pytest": {
        "pattern": r"(pytest|python3? -m pytest)",
        "response": 1,
        "description": "Python test runner",
    },
    "pip_install": {
        "pattern": r"pip3?\s+install",
        "response": 1,
        "description": "Python package installation",
    },
    # === SERVER/PROCESS MANAGEMENT ===
    "deploy_script": {
        "pattern": r"\./(deploy|start|run|build)\.sh",
        "response": 1,
        "description": "Deployment scripts",
    },
    "kill_processes": {
        "pattern": r"(kill|pkill|killall)\s+",
        "response": 1,
        "description": "Process termination",
    },
    "lsof_fuser": {
        "pattern": r"(lsof|fuser)\s+",
        "response": 1,
        "description": "Port/process inspection",
    },
    # === TMUX OPERATIONS (for session assigner integration) ===
    "tmux_send": {
        "pattern": r"tmux\s+(send-keys|send)",
        "response": 1,
        "description": "tmux send commands",
    },
    "tmux_capture": {
        "pattern": r"tmux\s+(capture-pane|list-sessions|list-panes)",
        "response": 1,
        "description": "tmux capture/list",
    },
    "tmux_create": {
        "pattern": r"tmux\s+(new-session|new-window)",
        "response": 1,
        "description": "tmux session creation",
    },
    # === SAFE BASH COMMANDS ===
    "echo_printf": {
        "pattern": r"(echo|printf)\s+",
        "response": 1,
        "description": "Output commands",
    },
    "mkdir_touch": {
        "pattern": r"(mkdir|touch)\s+",
        "response": 1,
        "description": "Directory/file creation",
    },
    "grep_sed_awk": {
        "pattern": r"(grep|sed|awk|sort|uniq|wc)\s+",
        "response": 1,
        "description": "Text processing commands",
    },
    "curl_wget": {"pattern": r"(curl|wget)\s+", "response": 1, "description": "Network requests"},
    "chmod_chown": {
        "pattern": r"(chmod|chown)\s+",
        "response": 1,
        "description": "Permission changes",
    },
}

# Template classifications
TEMPLATE_TYPES = {
    "BASH_SIMPLE": "Simple bash command (2 options)",
    "BASH_PATH_SCOPED": "Bash with path-scoped approval (3 options)",
    "BASH_TMP_ACCESS": "Bash with tmp access approval (3 options)",
    "EDIT_FILE": "File edit operation",
    "WRITE_FILE": "File write/create operation",
    "READ_FILE": "File read operation",
    "UNKNOWN": "Unknown operation type",
}

# Dangerous patterns - NEVER auto-approve these
DANGEROUS_PATTERNS = [
    r"rm\s+-rf?\s+/",  # rm -rf /
    r"rm\s+-rf?\s+\*",  # rm -rf *
    r">\s*/dev/",  # Writing to /dev/
    r"dd\s+if=",  # dd command
    r"mkfs",  # Filesystem formatting
    r"sudo\s+rm",  # sudo rm
    r":\(\)\{.*\}",  # Fork bomb
    r"chmod\s+777",  # Overly permissive
]
