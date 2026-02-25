# Claude Code Confirmation Samples

Raw confirmation prompts collected for testing and template development.

---

## Sample 1: BASH_SIMPLE - Server Start (PROD)

**Template:** `BASH_SIMPLE`
**Options:** 2

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py > /tmp/prod_server.log 2>&1 &
Start PROD server

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
```

**Extracted:**
- `{{command}}`: `USE_HTTPS=true APP_ENV=prod PORT=5063 python3 unified_app.py > /tmp/prod_server.log 2>&1 &`
- `{{description}}`: `Start PROD server`

---

## Sample 2: BASH_SIMPLE - Git Commit

**Template:** `BASH_SIMPLE`
**Options:** 2

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

git add -A && git commit -m "Fix bug"
Stage and commit changes

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
```

**Extracted:**
- `{{command}}`: `git add -A && git commit -m "Fix bug"`
- `{{description}}`: `Stage and commit changes`

---

## Sample 3: BASH_PATH_SCOPED - Python Command with Directory Scope

**Template:** `BASH_PATH_SCOPED`
**Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

echo "test" | timeout 3 python3 claude_wrapper.py --no-log 2>&1 || echo "Wrapper test completed (expected timeout)"
Quick test of wrapper startup

Do you want to proceed?
❯ 1. Yes
  2. Yes, and don't ask again for timeout 3 python3 commands in
  /Users/jgirmay/Desktop/gitrepo/pyWork
  3. Type here to tell Claude what to do differently

Esc to cancel
```

**Extracted:**
- `{{command}}`: `echo "test" | timeout 3 python3 claude_wrapper.py --no-log 2>&1 || echo "Wrapper test completed (expected timeout)"`
- `{{description}}`: `Quick test of wrapper startup`
- `{{command_pattern}}`: `timeout 3 python3`
- `{{directory_path}}`: `/Users/jgirmay/Desktop/gitrepo/pyWork`

---

## Sample 4: EDIT_FILE - Python File Edit

**Template:** `EDIT_FILE`
**Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Edit file

/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments/unified_app.py
Update API endpoint

Do you want to proceed?
❯ 1. Yes, allow this once
  2. Yes, allow all future edits to this file
  3. No

Esc to cancel
```

**Extracted:**
- `{{file_path}}`: `/Users/jgirmay/Desktop/gitrepo/pyWork/basic_edu_apps_final/environments/unified_app.py`
- `{{description}}`: `Update API endpoint`

---

## Sample 5: BASH_SIMPLE - Server Start (QA)

**Template:** `BASH_SIMPLE`
**Options:** 2

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

USE_HTTPS=true APP_ENV=qa PORT=5051 python3 unified_app.py > /tmp/qa_server.log 2>&1 &
Start QA server manually

Do you want to proceed?
❯ 1. Yes
  2. Type here to tell Claude what to do differently

Esc to cancel
```

**Extracted:**
- `{{command}}`: `USE_HTTPS=true APP_ENV=qa PORT=5051 python3 unified_app.py > /tmp/qa_server.log 2>&1 &`
- `{{description}}`: `Start QA server manually`

---

## Sample 6: BASH_TMP_ACCESS - Touch File with tmp/ Access

**Template:** `BASH_TMP_ACCESS`
**Options:** 3

```
───────────────────────────────────────────────────────────────────────────────────────────────────
Bash command

touch /tmp/test_confirmation_file.txt
Create test file in /tmp

Do you want to proceed?
❯ 1. Yes
  2. Yes, and always allow access to tmp/ from this project
  3. Type here to tell Claude what to do differently

Esc to cancel
```

**Extracted:**
- `{{command}}`: `touch /tmp/test_confirmation_file.txt`
- `{{description}}`: `Create test file in /tmp`
- `{{access_path}}`: `tmp/`

---

## Sample 7: BASH_PATH_SCOPED - tmux Capture Command

**Template:** `BASH_PATH_SCOPED`
**Options:** 3

```
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
```

**Extracted:**
- `{{command}}`: `tmux capture-pane -t claude-test-wrapper -p 2>/dev/null | tail -50`
- `{{description}}`: `Capture current Claude session output`
- `{{command_pattern}}`: `tmux capture-pane`
- `{{directory_path}}`: `/Users/jgirmay/Desktop/gitrepo/pyWork`

---

## Summary

| # | Template | Operation | Options | Key Variables |
|---|----------|-----------|---------|---------------|
| 1 | BASH_SIMPLE | Server start (PROD) | 2 | command, description |
| 2 | BASH_SIMPLE | Git commit | 2 | command, description |
| 3 | BASH_PATH_SCOPED | Python with scope | 3 | command, command_pattern, directory_path |
| 4 | EDIT_FILE | Python file edit | 3 | file_path, description |
| 5 | BASH_SIMPLE | Server start (QA) | 2 | command, description |
| 6 | BASH_TMP_ACCESS | tmp/ file access | 3 | command, description, access_path |
| 7 | BASH_PATH_SCOPED | tmux capture | 3 | command, command_pattern, directory_path |

---

## Usage

These samples can be used to:
1. Test regex patterns for prompt extraction
2. Develop new template types when unknown confirmations appear
3. Build auto-response rules based on patterns

```bash
# Run tests against these samples
python3 extract_prompts.py --test

# Add new samples by updating TEST_PROMPTS in extract_prompts.py
```
