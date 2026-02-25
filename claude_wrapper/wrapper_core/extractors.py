"""
Prompt extraction logic for Claude Code wrapper.

This module handles parsing terminal output to find permission prompts.
Includes dangerous command detection and auto-response suggestions.
"""

import re
from datetime import datetime

from . import config

__version__ = "2.0.0"


def strip_ansi(text):
    """Remove ANSI escape codes from text."""
    return config.ANSI_ESCAPE.sub("", text)


def classify_template(prompt):
    """Classify a prompt into a known template type."""
    op_type = prompt.get("operation_type", "").lower()
    options = prompt.get("options", [])
    num_options = len(options)

    # Check option text for template hints
    option_texts = " ".join([o.get("text", "") for o in options]).lower()

    if "bash" in op_type or "command" in op_type:
        if num_options == 3:
            if "don't ask again" in option_texts:
                return "BASH_PATH_SCOPED"
            elif "always allow access to" in option_texts:
                return "BASH_TMP_ACCESS"
        return "BASH_SIMPLE"
    elif "edit" in op_type:
        return "EDIT_FILE"
    elif "write" in op_type:
        return "WRITE_FILE"
    elif "read" in op_type:
        return "READ_FILE"
    else:
        return "UNKNOWN"


def parse_prompts(terminal_output, existing_prompts=None):
    """
    Extract permission prompts from terminal output.

    Args:
        terminal_output: Raw terminal output (may contain ANSI codes)
        existing_prompts: List of already-found prompts to avoid duplicates

    Returns:
        List of new prompts found
    """
    existing_prompts = existing_prompts or []
    existing_keys = {f"{p['operation_type']}:{p['command']}" for p in existing_prompts}

    # Strip ANSI codes before parsing
    clean_output = strip_ansi(terminal_output)

    prompts = []
    for match in config.PROMPT_PATTERN.finditer(clean_output):
        prompt = {
            "operation_type": match.group("operation_type").strip(),
            "command": match.group("command").strip(),
            "description": match.group("description").strip(),
            "timestamp": datetime.now().isoformat(),
            "options": [],
        }

        # Parse options
        options_text = match.group("options")
        for opt_match in re.finditer(r"[❯\s]*(\d+)\.\s*(.+?)(?:\n|$)", options_text):
            prompt["options"].append(
                {
                    "number": int(opt_match.group(1)),
                    "text": opt_match.group(2).strip(),
                    "selected": "❯" in opt_match.group(0),
                }
            )

        # Classify template type
        prompt["template"] = classify_template(prompt)

        # Avoid duplicates
        prompt_key = f"{prompt['operation_type']}:{prompt['command']}"
        if prompt_key not in existing_keys:
            prompts.append(prompt)
            existing_keys.add(prompt_key)

    return prompts


def is_dangerous(prompt):
    """Check if a prompt contains dangerous patterns that should NEVER be auto-approved."""
    command = prompt.get("command", "")

    for pattern in config.DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, pattern

    return False, None


def match_rule(prompt):
    """Find matching response rule for a prompt."""
    # First check if it's dangerous
    dangerous, pattern = is_dangerous(prompt)
    if dangerous:
        return "DANGEROUS", {"response": None, "description": f"Dangerous: {pattern}"}

    # Check operation type first (Edit file, Write file, etc.)
    op_type = prompt.get("operation_type", "").lower()
    command = prompt.get("command", "")

    # Build search strings
    search_strings = [
        op_type,
        command,
        f"{op_type}:{command}",
    ]

    for rule_name, rule in config.RESPONSE_RULES.items():
        for search_str in search_strings:
            if re.search(rule["pattern"], search_str, re.IGNORECASE):
                return rule_name, rule

    return None, None


def suggest_response(prompt):
    """
    Suggest a response based on matching rules.

    Returns:
        tuple: (response_number, description)
            - response_number: 1, 2, 3 or None (if should not auto-respond)
            - description: Reason for the suggestion
    """
    # Check for dangerous commands first
    dangerous, pattern = is_dangerous(prompt)
    if dangerous:
        return None, f"BLOCKED - dangerous pattern: {pattern}"

    # Find matching rule
    rule_name, rule = match_rule(prompt)
    if rule and rule.get("response") is not None:
        return rule["response"], rule.get("description", rule_name)

    # No matching rule - check if auto-approve-all is enabled
    if getattr(config, "AUTO_APPROVE_ALL", False):
        return 1, "AUTO_APPROVE_ALL enabled"

    return None, "No matching rule"


def format_prompt_for_log(prompt, number):
    """Format a prompt as a markdown table row for the log file."""
    op_type = prompt["operation_type"]
    command = prompt["command"]

    # Truncate long commands
    if len(command) > 50:
        command = command[:47] + "..."

    # Escape pipe characters for markdown
    command = command.replace("|", "\\|")

    # Determine prompt text based on operation type
    if "Bash" in op_type:
        prompt_text = f"`Allow Claude to run: {command}`"
    elif "Edit" in op_type:
        prompt_text = f"`Allow Claude to edit: {command}`"
    elif "Write" in op_type:
        prompt_text = f"`Allow Claude to create: {command}`"
    elif "Read" in op_type:
        prompt_text = f"`Allow Claude to read: {command}`"
    else:
        prompt_text = f"`{op_type}: {command}`"

    return f"| {number} | {op_type} | {prompt_text} | Prompted |"
