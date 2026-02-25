# Claude Code Confirmation Templates

This document defines the confirmation prompt templates that Claude Code uses. Each template has a pattern, variable fields, and response options.

---

## Template Categories

| Category | Description | Options |
|----------|-------------|---------|
| `BASH_SIMPLE` | Basic bash command approval | 2 |
| `BASH_PATH_SCOPED` | Bash command with path-based "allow all" | 3 |
| `EDIT_FILE` | File edit approval | 3 |
| `WRITE_FILE` | New file creation | 2-3 |
| `READ_FILE` | File read approval | 2-3 |

---

## Template: BASH_SIMPLE

**Type:** `bash_simple` | **Options:** 2

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

{{command}}
{{description}}

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
```

| Variable | Example |
|----------|---------|
| `{{command}}` | `git add -A && git commit -m "Fix bug"` |
| `{{description}}` | `Stage and commit changes` |

**Responses:** `1` = Yes | `2` = Modify/Reject

---

## Template: BASH_PATH_SCOPED

**Type:** `bash_path_scoped` | **Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

{{command}}
{{description}}

Do you want to proceed?
❯ 1. Yes
  2. Yes, and don't ask again for {{command_pattern}} commands in
  {{directory_path}}
  3. Type here to tell Claude what to do differently

Esc to cancel
```

| Variable | Example |
|----------|---------|
| `{{command}}` | `timeout 3 python3 script.py` |
| `{{description}}` | `Quick test of wrapper startup` |
| `{{command_pattern}}` | `timeout 3 python3` |
| `{{directory_path}}` | `/Users/jgirmay/Desktop/gitrepo/pyWork` |

**Responses:** `1` = Yes once | `2` = Yes, allow all in directory | `3` = Modify/Reject

---

## Template: EDIT_FILE

**Type:** `edit_file` | **Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Edit file

{{file_path}}
{{description}}

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, allow all future edits to this file
  3. No

Esc to cancel
```

| Variable | Example |
|----------|---------|
| `{{file_path}}` | `/Users/.../unified_app.py` |
| `{{description}}` | `Update API endpoint` |

**Responses:** `1` = Yes once | `2` = Yes, allow all future edits | `3` = No

---

## Template: WRITE_FILE

**Type:** `write_file` | **Options:** 2

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Write file

{{file_path}}
{{description}}

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
```

| Variable | Example |
|----------|---------|
| `{{file_path}}` | `claude_confirmations.md` |
| `{{description}}` | `Create session log` |

**Responses:** `1` = Yes | `2` = Modify/Reject

---

## Template: READ_FILE

**Type:** `read_file` | **Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Read file

{{file_path}}

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, allow all future reads in {{directory_path}}
  3. No

Esc to cancel
```

| Variable | Example |
|----------|---------|
| `{{file_path}}` | `/etc/hosts` |
| `{{directory_path}}` | `/etc` |

**Responses:** `1` = Yes once | `2` = Yes, allow all in directory | `3` = No

---

## Auto-Response Rules

Based on collected templates, these rules can auto-respond:

### Safe to Auto-Allow (Response: 2 - Allow All)
```python
ALLOW_ALL_RULES = {
    # Git operations - safe, reversible
    'git_read': r'git (status|diff|log|branch|show)',
    'git_stage': r'git add',

    # Server starts in known directories
    'server_start': r'python3 unified_app\.py',

    # Frontend file edits
    'edit_html': r'\.html$',
    'edit_css': r'\.css$',
    'edit_js': r'\.js$',
}
```

### Ask Each Time (Response: 1 - Yes Once)
```python
ASK_EACH_TIME_RULES = {
    # Commits and pushes - want to verify message
    'git_commit': r'git commit',
    'git_push': r'git push',

    # Python edits - more critical
    'edit_python': r'\.py$',

    # Deployments
    'deploy': r'deploy\.sh',

    # Process management
    'kill': r'(kill|pkill|lsof.*kill)',
}
```

### Reject by Default (Response: 3 - No)
```python
REJECT_RULES = {
    # Dangerous operations
    'rm_rf': r'rm -rf',
    'force_push': r'git push.*--force',
    'drop_table': r'DROP TABLE',
}
```

---

## Collected Variables

Values extracted from prompts during sessions, grouped by template.

### {{command}} values (BASH_SIMPLE, BASH_PATH_SCOPED)
```
git add -A && git commit -m "..."
git tag v1.0.15 && git push github main --tags
./deploy.sh qa v1.0.15
lsof -ti:5063 | xargs kill
USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py
echo "test" | timeout 3 python3 claude_wrapper.py --no-log
```

### {{command_pattern}} values (BASH_PATH_SCOPED)
```
timeout 3 python3
git add
python3
```

### {{directory_path}} values (BASH_PATH_SCOPED, READ_FILE)
```
/Users/jgirmay/Desktop/gitrepo/pyWork
/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments
```

### {{file_path}} values (EDIT_FILE, WRITE_FILE, READ_FILE)
```
architect_templates/dashboard.html
unified_app.py
CHANGES.md
README.md
claude_confirmations.md
extract_prompts.py
claude_wrapper.sh
claude_wrapper.py
```

---

## Suggested Auto-Responses

Based on `{{variable}}` patterns, recommended default responses:

### Response 2 (Allow All)
| Pattern | Matches |
|---------|---------|
| `{{command}}` matches `git (status\|diff\|log\|branch)` | Read-only git |
| `{{command}}` matches `git add` | Staging (reversible) |
| `{{file_path}}` matches `*.(html\|css\|js\|md)` | Frontend/docs |
| `{{command}}` matches `python3 unified_app.py` | Server start |

### Response 1 (Ask Each Time)
| Pattern | Matches |
|---------|---------|
| `{{command}}` matches `git (commit\|push)` | Verify message/remote |
| `{{file_path}}` matches `*.py` | Backend code |
| `{{command}}` matches `deploy.sh` | Deployments |
| `{{command}}` matches `(kill\|pkill)` | Process termination |

### Response 3 (Reject)
| Pattern | Matches |
|---------|---------|
| `{{command}}` matches `rm -rf` | Dangerous delete |
| `{{command}}` matches `git push.*--force` | Force push |
| `{{command}}` matches `DROP TABLE` | Database drop |

---

## Extraction Regex

```python
# Match template type by option text patterns
TEMPLATES = {
    'bash_simple': r"2\.\s*Type here to tell Claude",
    'bash_path_scoped': r"2\.\s*Yes.*don't ask again for\s*(?P<command_pattern>.+?)\s*commands in",
    'edit_file': r"2\.\s*Yes.*all future edits to this file",
    'write_file': r"Write file.*\n.*\n.*Do you want",
    'read_file': r"2\.\s*Yes.*all future reads in",
}

# Extract {{variable}} values
VARIABLE_PATTERNS = {
    'command': r'Bash command\s*\n\s*\n?\s*(.+?)\s*\n',
    'file_path': r'(Edit|Write|Read) file\s*\n\s*\n?\s*(.+?)\s*\n',
    'command_pattern': r"don't ask again for\s*(.+?)\s*commands",
    'directory_path': r"commands in\s*\n?\s*(.+?)\s*\n",
}
```

---

## Usage

```bash
# Extract and classify prompts
pbpaste | python3 extract_prompts.py --analyze

# Run template tests
python3 extract_prompts.py --test

# Show auto-response rules
python3 extract_prompts.py --rules

# Use wrapper to auto-capture
./claude_wrapper.sh
```
