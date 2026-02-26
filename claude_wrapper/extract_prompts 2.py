#!/usr/bin/env python3
"""
Extract Claude Code permission prompts from terminal output and save to session log.

Goal: Collect enough prompt samples to build auto-response rules.

Usage:
    # From clipboard (macOS)
    pbpaste | python3 extract_prompts.py

    # From file
    python3 extract_prompts.py < terminal_output.txt

    # Preview without saving
    python3 extract_prompts.py --preview < terminal_output.txt

    # Show response rules
    python3 extract_prompts.py --rules

Response Options:
    1 = Yes, allow this once
    2 = Yes, allow all similar (don't ask again)
    3 = No (for 3-option prompts)
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# ============================================================================
# TEST DATA - Sample prompts collected from Claude Code sessions
# ============================================================================
TEST_PROMPTS = [
    # 2-option: Simple Yes/No
    {
        "name": "2-option-bash-simple",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py > /tmp/prod_server.log 2>&1 &
Start PROD server

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
""",
        "expected": {
            "operation_type": "Bash command",
            "command": "USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py > /tmp/prod_server.log 2>&1 &",
            "options_count": 2,
        },
    },
    # 2-option: Git command
    {
        "name": "2-option-git-commit",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

git add -A && git commit -m "Fix bug"
Stage and commit changes

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
""",
        "expected": {
            "operation_type": "Bash command",
            "command": 'git add -A && git commit -m "Fix bug"',
            "options_count": 2,
        },
    },
    # 3-option: Path-specific allowance
    {
        "name": "3-option-path-specific",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
 Bash command

   echo "test" | timeout 3 python3 claude_wrapper.py --no-log 2>&1 || echo "Wrapper test
   completed (expected timeout)"
   Quick test of wrapper startup

 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again for timeout 3 python3 commands in
   /Users/jgirmay/Desktop/gitrepo/pyWork
   3. Type here to tell Claude what to do differently

 Esc to cancel
""",
        "expected": {"operation_type": "Bash command", "options_count": 3},
    },
    # 3-option: File edit with "allow all future edits"
    {
        "name": "3-option-edit-file",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Edit file

/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments/unified_app.py
Update API endpoint

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, allow all future edits to this file
  3. No

Esc to cancel
""",
        "expected": {"operation_type": "Edit file", "options_count": 3},
    },
    # 2-option: Server start with background redirect
    {
        "name": "2-option-server-start-background",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

USE_HTTPS=true APP_ENV=qa PORT=5051 python3 unified_app.py > /tmp/qa_server.log 2>&1 &
Start QA server manually

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
""",
        "expected": {
            "operation_type": "Bash command",
            "command": "USE_HTTPS=true APP_ENV=qa PORT=5051 python3 unified_app.py",
            "options_count": 2,
        },
    },
    # 3-option: tmp/ access permission
    {
        "name": "3-option-tmp-access",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

touch /tmp/test_confirmation_file.txt
Create test file in /tmp

Do you want to proceed?
❯ 1. Yes
  2. Yes, and always allow access to tmp/ from this project
  3. Type here to tell Claude what to do differently

Esc to cancel
""",
        "expected": {
            "operation_type": "Bash command",
            "command": "touch /tmp/test_confirmation_file.txt",
            "options_count": 3,
        },
    },
    # 3-option: tmux capture-pane with path scope
    {
        "name": "3-option-tmux-capture",
        "input": """
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

tmux capture-pane -t claude-test-wrapper -p 2>/dev/null | tail -50
Capture current Claude session output

Do you want to proceed?
❯ 1. Yes
  2. Yes, and don't ask again for tmux capture-pane commands in
  /Users/jgirmay/Desktop/gitrepo/pyWork
  3. Type here to tell Claude what to do differently

Esc to cancel
""",
        "expected": {
            "operation_type": "Bash command",
            "command": "tmux capture-pane -t claude-test-wrapper -p",
            "options_count": 3,
        },
    },
]

# Response rules: patterns -> auto-response
# Once we have enough samples, add patterns here
RESPONSE_RULES = {
    # Git operations - usually safe to auto-approve
    "git_commit": {
        "pattern": r"git (add|commit|tag|push|status|diff|log|branch)",
        "response": 2,  # Yes, allow all
        "description": "Git version control commands",
    },
    "git_checkout": {
        "pattern": r"git (checkout|switch|merge|rebase|stash)",
        "response": 1,  # Yes, but ask each time (more destructive)
        "description": "Git branch operations",
    },
    # File edits - depends on the file
    "edit_templates": {
        "pattern": r"edit:.*\.(html|css|js)$",
        "response": 2,  # Allow all edits to frontend files
        "description": "Frontend template edits",
    },
    "edit_python": {
        "pattern": r"edit:.*\.py$",
        "response": 1,  # Ask each time for Python
        "description": "Python file edits",
    },
    # Server operations
    "server_start": {
        "pattern": r"python3 unified_app\.py",
        "response": 2,  # Allow server starts
        "description": "Start application server",
    },
    "server_kill": {
        "pattern": r"(lsof|kill|pkill)",
        "response": 1,  # Ask each time
        "description": "Process management",
    },
    # Deploy operations
    "deploy": {
        "pattern": r"deploy\.sh",
        "response": 1,  # Always ask for deploys
        "description": "Deployment scripts",
    },
}

# Known operation types for confirmation prompts
OPERATION_TYPES = r"(?:Bash command|Edit file|Write file|Read file|Create file|Delete file|Execute)"

# Pattern to extract permission prompts from terminal output
# Updated to handle both aligned and indented formats from live Claude sessions
PROMPT_PATTERN = re.compile(
    r"─{20,}\s*\n"  # Separator line (20+ dashes)
    r"\s*(?P<operation_type>" + OPERATION_TYPES + r")\s*\n"  # Operation type (known types only)
    r"\s*\n?"  # Optional blank line
    r"\s*(?P<command>.+?)\s*\n"  # Command (may span lines, may have indentation)
    r"\s*(?P<description>[^\n]*?)\s*\n"  # Description
    r"[\s\n]*"  # Optional whitespace/newlines
    r"\s*Do you want to proceed\?\s*\n"  # Question (may have leading space)
    r"(?P<options>(?:.*?\d+\..*?\n)+)"  # Options (lines with "1.", "2.", etc.)
    r".*?Esc to cancel",  # Cancel instruction
    re.MULTILINE | re.DOTALL,
)

# Simpler pattern that's more lenient
SIMPLE_PROMPT_PATTERN = re.compile(
    r"─{20,}\s*\n"  # Separator line
    r"\s*(?P<operation_type>\S[^\n]*?)\s*\n"  # Operation type
    r"[\s\S]*?"  # Any content
    r"Do you want to proceed\?",  # Question marker
    re.MULTILINE,
)

SESSION_LOG_PATH = Path(__file__).parent / "claude_confirmations.md"
UNKNOWN_CONFIRMATIONS_PATH = Path(__file__).parent / "claude_logs" / "unknown_confirmations.log"


def log_unknown_confirmation(text, reason="Unknown pattern"):
    """Log confirmations that don't match known templates for review."""
    UNKNOWN_CONFIRMATIONS_PATH.parent.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat()
    entry = f"\n{'='*60}\n[{timestamp}] {reason}\n{'='*60}\n{text[:500]}\n"

    with open(UNKNOWN_CONFIRMATIONS_PATH, "a") as f:
        f.write(entry)

    print(f"[WARNING] Unknown confirmation logged: {reason}", file=sys.stderr)


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


def strip_ansi(text):
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07")
    return ansi_pattern.sub("", text)


def parse_prompts(terminal_output, log_unknown=True):
    """Extract permission prompts from terminal output."""
    # Strip ANSI codes before parsing
    terminal_output = strip_ansi(terminal_output)
    prompts = []

    for match in PROMPT_PATTERN.finditer(terminal_output):
        prompt = {
            "operation_type": match.group("operation_type").strip(),
            "command": match.group("command").strip(),
            "description": match.group("description").strip(),
            "options": [],
            "response": "Allowed",  # Default assumption
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

        # Classify into template type
        prompt["template"] = classify_template(prompt)

        # Log unknown templates for review
        if log_unknown and prompt["template"] == "UNKNOWN":
            log_unknown_confirmation(
                f"Operation: {prompt['operation_type']}\n"
                f"Command: {prompt['command']}\n"
                f"Options: {len(prompt['options'])}",
                reason=f"Unknown operation type: {prompt['operation_type']}",
            )

        prompts.append(prompt)

    # Also check for potential prompts that didn't match the main pattern
    if log_unknown:
        # Look for "Do you want to proceed?" that we might have missed
        proceed_matches = list(re.finditer(r"Do you want to proceed\?", terminal_output))
        if len(proceed_matches) > len(prompts):
            log_unknown_confirmation(
                terminal_output[:1000],
                reason=f"Found {len(proceed_matches)} 'proceed' prompts but only extracted {len(prompts)}",
            )

    return prompts


def format_as_table_row(prompt, index):
    """Format a prompt as a markdown table row."""
    op_type = prompt["operation_type"]
    command = prompt["command"]

    # Truncate long commands
    if len(command) > 60:
        command = command[:57] + "..."

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

    return f"| {index} | {op_type} | {prompt_text} | {prompt['response']} |"


def get_next_prompt_number(log_path):
    """Get the next prompt number from the existing log."""
    if not log_path.exists():
        return 1

    content = log_path.read_text()
    # Find all existing prompt numbers in the table
    numbers = re.findall(r"^\| (\d+) \|", content, re.MULTILINE)
    if numbers:
        return max(int(n) for n in numbers) + 1
    return 1


def append_to_log(prompts, log_path, preview=False):
    """Append prompts to the session log."""
    if not prompts:
        print("No prompts found to save.")
        return

    start_num = get_next_prompt_number(log_path)

    rows = []
    for i, prompt in enumerate(prompts):
        rows.append(format_as_table_row(prompt, start_num + i))

    new_content = "\n".join(rows)

    if preview:
        print("=== Preview (would append to log) ===")
        print(new_content)
        print(f"\n=== {len(prompts)} prompt(s) found ===")
        return

    # Read existing content
    if log_path.exists():
        content = log_path.read_text()

        # Find the table section and append
        # Look for the last row of the Permission Prompts table
        table_pattern = r"(\| \d+ \| [^|]+ \| [^|]+ \| [^|]+ \|)\n(\n---|\n###|\Z)"

        match = list(re.finditer(table_pattern, content))
        if match:
            last_match = match[-1]
            insert_pos = last_match.end(1)
            content = content[:insert_pos] + "\n" + new_content + content[insert_pos:]
        else:
            # Table not found, append at end
            content += (
                f"\n\n### Extracted Prompts ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
            )
            content += "| # | Operation Type | Prompt Text | User Response |\n"
            content += "|---|----------------|-------------|---------------|\n"
            content += new_content + "\n"

        log_path.write_text(content)
        print(f"Appended {len(prompts)} prompt(s) to {log_path}")
    else:
        print(f"Log file not found: {log_path}")


def match_rule(prompt):
    """Find matching response rule for a prompt."""
    # Create a searchable string from the prompt
    search_str = f"{prompt['operation_type'].lower()}:{prompt['command']}"

    for rule_name, rule in RESPONSE_RULES.items():
        if re.search(rule["pattern"], search_str, re.IGNORECASE):
            return rule_name, rule

    return None, None


def suggest_response(prompt):
    """Suggest a response based on matching rules."""
    rule_name, rule = match_rule(prompt)
    if rule:
        return rule["response"], rule["description"]
    return None, "No matching rule"


def show_rules():
    """Display all response rules."""
    print("=== Claude Code Auto-Response Rules ===\n")
    print("Response codes: 1=Yes once, 2=Yes always, 3=No\n")

    for name, rule in RESPONSE_RULES.items():
        print(f"[{name}]")
        print(f"  Pattern: {rule['pattern']}")
        print(
            f"  Response: {rule['response']} ({['', 'Yes once', 'Yes always', 'No'][rule['response']]})"
        )
        print(f"  Description: {rule['description']}")
        print()


def analyze_prompts(prompts):
    """Analyze prompts and show suggested responses."""
    print("=== Prompt Analysis ===\n")

    for i, prompt in enumerate(prompts, 1):
        response, desc = suggest_response(prompt)
        rule_name, _ = match_rule(prompt)

        print(f"{i}. {prompt['operation_type']}")
        print(f"   Command: {prompt['command'][:60]}...")
        print(f"   Options: {len(prompt['options'])}")
        if response:
            print(f"   Suggested: {response} ({desc})")
            print(f"   Rule: {rule_name}")
        else:
            print(f"   Suggested: ? (no matching rule)")
        print()


def run_tests():
    """Run tests on all sample prompts."""
    print("=" * 60)
    print("CLAUDE WRAPPER PROMPT EXTRACTION TESTS")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for test in TEST_PROMPTS:
        name = test["name"]
        expected = test["expected"]

        print(f"Test: {name}")
        print("-" * 40)

        # Parse the prompt
        prompts = parse_prompts(test["input"])

        if not prompts:
            print(f"  FAIL: No prompts extracted")
            failed += 1
            print()
            continue

        prompt = prompts[0]
        test_passed = True
        errors = []

        # Check operation type
        if "operation_type" in expected:
            if expected["operation_type"].lower() not in prompt["operation_type"].lower():
                errors.append(
                    f"operation_type: expected '{expected['operation_type']}', got '{prompt['operation_type']}'"
                )
                test_passed = False

        # Check command (partial match)
        if "command" in expected:
            if expected["command"][:30] not in prompt["command"]:
                errors.append(
                    f"command: expected to contain '{expected['command'][:30]}...', got '{prompt['command'][:50]}...'"
                )
                test_passed = False

        # Check options count
        if "options_count" in expected:
            if len(prompt["options"]) != expected["options_count"]:
                errors.append(
                    f"options_count: expected {expected['options_count']}, got {len(prompt['options'])}"
                )
                test_passed = False

        if test_passed:
            print(f"  PASS")
            print(f"    operation_type: {prompt['operation_type']}")
            print(f"    command: {prompt['command'][:50]}...")
            print(f"    options: {len(prompt['options'])}")
            passed += 1
        else:
            print(f"  FAIL:")
            for error in errors:
                print(f"    - {error}")
            failed += 1

        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Extract Claude Code permission prompts")
    parser.add_argument("--input", "-i", type=str, help="Input file (default: stdin)")
    parser.add_argument(
        "--output", "-o", type=str, help="Output log file", default=str(SESSION_LOG_PATH)
    )
    parser.add_argument(
        "--preview", "-p", action="store_true", help="Preview extracted prompts without saving"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="Output as JSON instead of appending to log"
    )
    parser.add_argument("--rules", "-r", action="store_true", help="Show all response rules")
    parser.add_argument(
        "--analyze", "-a", action="store_true", help="Analyze prompts and suggest responses"
    )
    parser.add_argument("--test", "-t", action="store_true", help="Run tests on sample prompts")

    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    if args.rules:
        show_rules()
        return

    # Read input
    if args.input:
        terminal_output = Path(args.input).read_text()
    else:
        if sys.stdin.isatty():
            print("Paste terminal output (Ctrl+D when done):")
        terminal_output = sys.stdin.read()

    # Parse prompts
    prompts = parse_prompts(terminal_output)

    if args.analyze:
        analyze_prompts(prompts)
    elif args.json:
        import json

        print(json.dumps(prompts, indent=2))
    else:
        append_to_log(prompts, Path(args.output), preview=args.preview)


if __name__ == "__main__":
    main()
