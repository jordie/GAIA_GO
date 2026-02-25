#!/usr/bin/env python3
"""
Error Triage System - Auto-group and create bugs from error patterns
Reduces AI token usage by handling recurring errors automatically
"""
import hashlib
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Database paths
ARCHITECT_DB = Path(__file__).parent.parent / "data/architect.db"
ERROR_PATTERNS_FILE = Path(__file__).parent.parent / "data/error_patterns.json"

# Error grouping threshold - errors are grouped if similarity > 80%
SIMILARITY_THRESHOLD = 0.8

# Auto-create bug threshold - create bug if error occurs N times in M minutes
AUTO_BUG_THRESHOLD = 5  # occurrences
AUTO_BUG_WINDOW = 30  # minutes


def get_db():
    """Get database connection"""
    return sqlite3.connect(str(ARCHITECT_DB))


def normalize_error(message):
    """Normalize error message for grouping

    Removes variable parts like:
    - File paths (keep only filename)
    - Line numbers
    - Timestamps
    - Memory addresses
    - Process IDs
    """
    if not message:
        return ""

    # Convert to lowercase
    normalized = message.lower()

    # Remove file paths, keep only filename
    normalized = re.sub(r"/[\w/.-]+/(\w+\.\w+)", r"\1", normalized)

    # Remove line numbers
    normalized = re.sub(r"line \d+", "line N", normalized)
    normalized = re.sub(r":\d+:", ":N:", normalized)

    # Remove timestamps
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", normalized)
    normalized = re.sub(r"\d{2}:\d{2}:\d{2}", "TIME", normalized)

    # Remove memory addresses
    normalized = re.sub(r"0x[0-9a-f]+", "0xADDR", normalized)

    # Remove PIDs
    normalized = re.sub(r"pid:?\s*\d+", "pid:N", normalized)
    normalized = re.sub(r"process \d+", "process N", normalized)

    # Remove numbers in general (but keep version numbers)
    normalized = re.sub(r"(?<!\d)(\d+)(?!\.\d)", "N", normalized)

    return normalized.strip()


def compute_similarity(str1, str2):
    """Compute Jaccard similarity between two strings"""
    if not str1 or not str2:
        return 0.0

    # Tokenize by whitespace
    tokens1 = set(str1.split())
    tokens2 = set(str2.split())

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def get_error_signature(error_type, message, source):
    """Generate unique signature for error pattern"""
    normalized = normalize_error(message)
    signature_str = f"{error_type}:{normalized}:{source}"
    return hashlib.md5(signature_str.encode()).hexdigest()[:16]


def group_errors():
    """Group similar errors and update database"""
    conn = get_db()
    c = conn.cursor()

    # Get all unresolved errors
    c.execute(
        """
        SELECT id, error_type, message, source, stack_trace
        FROM errors
        WHERE resolved = 0
        ORDER BY first_seen DESC
    """
    )

    errors = c.fetchall()
    groups = defaultdict(list)

    print(f"Analyzing {len(errors)} unresolved errors...")

    # Group errors by signature
    for error_id, error_type, message, source, stack_trace in errors:
        signature = get_error_signature(error_type, message, source)
        groups[signature].append(
            {
                "id": error_id,
                "type": error_type,
                "message": message,
                "source": source,
                "stack_trace": stack_trace,
            }
        )

    print(f"Found {len(groups)} unique error patterns")

    # Process each group
    for signature, error_list in groups.items():
        if len(error_list) > 1:
            print(f"\nGroup {signature}: {len(error_list)} occurrences")
            print(f"  Pattern: {normalize_error(error_list[0]['message'])}")

    conn.close()
    return groups


def check_auto_bug_creation(groups):
    """Check if any error group should auto-create a bug"""
    conn = get_db()
    c = conn.cursor()

    cutoff_time = datetime.now() - timedelta(minutes=AUTO_BUG_WINDOW)
    created_bugs = []

    for signature, error_list in groups.items():
        if len(error_list) < AUTO_BUG_THRESHOLD:
            continue

        # Get first error details
        first_error = error_list[0]
        error_id = first_error["id"]

        # Check if this error already has a bug
        c.execute(
            """
            SELECT bug_id FROM errors
            WHERE id = ? AND bug_id IS NOT NULL
        """,
            (error_id,),
        )

        if c.fetchone():
            print(f"  ⏭️  Error {error_id} already has a bug")
            continue

        # Check if errors occurred in the time window
        error_ids = [e["id"] for e in error_list]
        placeholders = ",".join("?" * len(error_ids))

        c.execute(
            f"""
            SELECT COUNT(*) FROM errors
            WHERE id IN ({placeholders})
            AND last_seen > ?
        """,
            (*error_ids, cutoff_time),
        )

        recent_count = c.fetchone()[0]

        if recent_count >= AUTO_BUG_THRESHOLD:
            # Create bug
            bug_title = f"Auto: {first_error['type']} in {first_error['source']}"
            bug_description = f"""
Automatically created from error pattern.

**Error Pattern:**
{normalize_error(first_error['message'])}

**Occurrences:** {recent_count} times in last {AUTO_BUG_WINDOW} minutes

**Source:** {first_error['source']}

**Stack Trace:**
```
{first_error['stack_trace'] or 'N/A'}
```

**Affected Error IDs:** {', '.join(f'#{e["id"]}' for e in error_list[:10])}
"""

            c.execute(
                """
                INSERT INTO bugs (title, description, status, severity, created_at)
                VALUES (?, ?, 'open', 'medium', ?)
            """,
                (bug_title, bug_description, datetime.now()),
            )

            bug_id = c.lastrowid

            # Link all errors to this bug
            for error_id in error_ids:
                c.execute("UPDATE errors SET bug_id = ? WHERE id = ?", (bug_id, error_id))

            conn.commit()
            created_bugs.append(bug_id)

            print(f"  ✅ Created Bug #{bug_id}: {bug_title}")
            print(f"     Linked {len(error_ids)} errors")

    conn.close()
    return created_bugs


def suggest_fixes(groups):
    """Suggest common fixes for error patterns"""
    suggestions = []

    for signature, error_list in groups.items():
        if len(error_list) < 2:
            continue

        first_error = error_list[0]
        message_lower = first_error["message"].lower()

        # Pattern-based suggestions
        fix = None

        if "connection refused" in message_lower or "econnrefused" in message_lower:
            fix = "Service not running. Check if the service is started and listening on the correct port."

        elif "no such file" in message_lower or "file not found" in message_lower:
            fix = "Missing file. Verify file path and ensure file exists."

        elif "permission denied" in message_lower:
            fix = "Permission issue. Check file/directory permissions with 'ls -la'. May need sudo or chmod."

        elif "timeout" in message_lower or "timed out" in message_lower:
            fix = "Timeout issue. Increase timeout value or check if service is responding."

        elif "cannot import" in message_lower or "modulenotfounderror" in message_lower:
            fix = "Missing Python module. Install with: pip install <module_name>"

        elif "syntax error" in message_lower or "syntaxerror" in message_lower:
            fix = "Syntax error in code. Check the file and line number mentioned in the error."

        elif "typeerror" in message_lower:
            fix = "Type mismatch. Check variable types and function arguments."

        elif "keyerror" in message_lower:
            fix = "Missing dictionary key. Add key or use .get() with default value."

        elif "database" in message_lower and "locked" in message_lower:
            fix = "Database locked. Close other connections or increase timeout."

        if fix:
            suggestions.append(
                {
                    "signature": signature,
                    "pattern": normalize_error(first_error["message"]),
                    "count": len(error_list),
                    "fix": fix,
                }
            )

    return suggestions


def run_triage():
    """Run full error triage process"""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║              ERROR TRIAGE SYSTEM                               ║")
    print("║  Grouping errors and creating bugs automatically               ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")

    # Group errors
    groups = group_errors()

    # Auto-create bugs
    print("\n🔍 Checking for auto-bug creation...")
    created_bugs = check_auto_bug_creation(groups)

    if created_bugs:
        print(f"\n✅ Created {len(created_bugs)} bugs: {', '.join(f'#{b}' for b in created_bugs)}")
    else:
        print("\n💤 No errors meet auto-bug threshold")

    # Suggest fixes
    print("\n💡 Suggested Fixes:")
    suggestions = suggest_fixes(groups)

    if suggestions:
        for s in suggestions:
            print(f"\n  Pattern ({s['count']}x): {s['pattern'][:60]}...")
            print(f"  Fix: {s['fix']}")
    else:
        print("  No common error patterns detected")

    print("\n✨ Triage complete!\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        print("Running in daemon mode (check every 15 minutes)...")
        import time

        while True:
            run_triage()
            print(f"Next check in 15 minutes...")
            time.sleep(900)  # 15 minutes
    else:
        run_triage()
