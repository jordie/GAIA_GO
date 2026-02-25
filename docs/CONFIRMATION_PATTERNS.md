# Claude Code Confirmation Patterns

This document defines the confirmation prompt patterns that `auto_confirm_worker` should detect and auto-approve.

## Pattern Types

### 1. Standard Yes/No Confirmation
**Format:**
```
 Do you want to proceed?
 ❯ 1. Yes
   2. No

 Esc to cancel · Tab to amend · ctrl+e to explain
```

**Detection:**
- Cursor indicator: `❯`
- Option 1: `1. Yes` or `1.Yes`
- Option 2: `2. No` or `2.Yes`
- Cancel indicator: `Esc to cancel` or `Tab to amend`
- Context: "Do you want to proceed?"

**Operation Type:** `confirm`

---

### 2. Multi-Option Confirmation (with "don't ask again")
**Format:**
```
 Do you want to proceed?
 ❯ 1. Yes
  2.Yes, and don't ask again for
    __NEW_LINE_token__ text continues
    on next lines
  3. No

 Esc to cancel · Tab to amend · ctrl+e to explain
```

**Detection:**
- Cursor indicator: `❯`
- Numbered options: `1.`, `2.`, `3.` (with or without space)
- Options can wrap across multiple lines
- Text may contain newline tokens like `__NEW_LINE_*__`
- Cancel indicator: `Esc to cancel`
- Typically contains "Run shell command" in context

**Operation Type:** `confirm` or `bash` (if "shell command" in context)

**Key:** Option text can be wrapped; look for numbered option markers `\d+\.` on separate lines.

---

### 3. Edit File Confirmation
**Format:**
```
 Do you want to make this edit to <filename>?
 ❯ 1. Yes
   2. No

 Esc to cancel · Tab to amend
```

**Detection:**
- Context contains: "edit", "make this edit", "filename"
- Cursor on numbered option
- Cancel indicator present

**Operation Type:** `edit`

---

### 4. Accept Edits Prompt
**Format:**
```
 ⏵⏵ accept edits on · 2 files +50 -10 · esc to interrupt
```

**Detection:**
- Line contains: `⏵⏵` and "accept edits"
- May contain file count: "N files +X -Y"
- Text "esc to interrupt"

**Operation Type:** `accept_edits`
**Send Key:** `Enter` (just press Enter, no number needed)

---

### 5. Plan Mode Confirmation
**Format:**
```
 Would you like to proceed?
 ❯ 1. Yes, clear context
   2. Yes, auto-accept edits
   3. Manually approve

 Esc to cancel
```

**Detection:**
- Text: "Would you like to proceed?"
- Cursor on numbered option with `Yes` variant
- Keywords like: "clear context", "auto-accept", "manually approve"

**Operation Type:** `plan_confirm`
**Send Key:** `1` then `Enter`

---

### 6. Bash/Command Confirmation
**Format:**
```
 Bash command

 Run shell command

 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again
   3. No

 Esc to cancel · Tab to amend
```

**Detection:**
- Context contains: "bash", "command", "execute", "Run shell command"
- Numbered options with cursor
- Cancel indicator

**Operation Type:** `bash`

---

## Common Detection Rules

### Must Have:
1. **Cursor Indicator:** `❯` on an option line
2. **Numbered Option:** `1.` or `1)` (can have variants like `1.Y` or `1.Yes`)
3. **Cancel Indicator:** At least one of:
   - `Esc to cancel`
   - `Tab to amend`
   - `ctrl+` (keyboard shortcut indicator)

### Variations to Handle:
- **Spacing:** `1. Yes`, `1.Yes`, `2. No`, `2.No`, `2.Yes`
- **Line Wrapping:** Option text can span multiple lines with newline tokens
- **Context Tokens:** May include `__NEW_LINE_*__` markers
- **Multi-line Options:** Second option may have full descriptive text on following lines
- **Case Insensitivity:** Match text case-insensitively

### Should NOT Match:
- Working indicators in last 3 lines: "reading", "writing", "processing", "executing", "analyzing", etc.
- Prompts already answered (content after "Esc to cancel" line)
- Bare `>` without the full cursor `❯`

---

## Safe Operations Whitelist

These operations are safe to auto-confirm automatically:

```python
SAFE_OPERATIONS = {
    "read",          # Reading files
    "grep",          # Searching content
    "glob",          # File pattern matching
    "accept_edits",  # Accepting pending edits
    "confirm",       # Generic confirmations
    "plan_confirm",  # Plan mode confirmations
    "edit",          # Editing files
    "write",         # Writing files
    "bash",          # Bash commands
}
```

Operations in `REQUIRES_APPROVAL` list need manual confirmation (currently empty).

---

## Response Keys

When confirming, send:

| Operation | Key | Notes |
|-----------|-----|-------|
| `accept_edits` | `Enter` | Just press Enter |
| `plan_confirm` | `1` then `Enter` | "Yes, clear context" (safest) |
| `confirm` | `1` then `Enter` | Option 1 (Yes) |
| `bash` | `1` then `Enter` | Option 1 (Yes) |
| `edit` | `2` then `Enter` | Option 2 (don't ask again) |
| `write` | `2` then `Enter` | Option 2 (don't ask again) |

---

## Testing Pattern Detection

To test if a pattern is detected:

```bash
python3 << 'EOF'
import re
import subprocess

output = subprocess.run(
    ["tmux", "capture-pane", "-t", "SESSION_NAME", "-p"],
    capture_output=True,
    text=True,
).stdout

# Check pattern matches
has_cursor = "❯" in output
has_option = "1." in output or "1)" in output
has_cancel = "Esc to cancel" in output or "Tab to amend" in output

print(f"Cursor: {has_cursor}, Option: {has_option}, Cancel: {has_cancel}")
if all([has_cursor, has_option, has_cancel]):
    print("✓ Pattern should be detected")
else:
    print("✗ Pattern missing required elements")
EOF
```

---

## Recent Updates (2026-02-17)

- Added support for multi-option confirmations with wrapped text
- Added `confirm` and `plan_confirm` to SAFE_OPERATIONS
- Improved handling of newline tokens in option text
- Enhanced bash command detection context
