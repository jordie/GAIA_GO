#!/usr/bin/env python3
"""
Pattern Integration Module
Integrates pattern tracking into auto-confirm worker for adaptive learning.
"""

import re
import time
from typing import Dict, Optional, Tuple

from pattern_tracker import PatternTracker


class PatternDetector:
    """Detects and tracks patterns in tmux session output."""

    def __init__(self):
        self.tracker = PatternTracker()
        self.pattern_cache = {}
        self.last_cache_update = 0
        self.cache_ttl = 300  # 5 minutes

    def load_patterns(self):
        """Load active patterns from database into memory cache."""
        import sqlite3

        conn = sqlite3.connect(self.tracker.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT id, pattern_name, pattern_regex, tool_name, action, pattern_type
            FROM patterns
            WHERE active = 1
        """
        )

        self.pattern_cache = {}
        for row in c.fetchall():
            pattern_id, name, regex, tool, action, ptype = row

            if tool not in self.pattern_cache:
                self.pattern_cache[tool] = []

            try:
                compiled_regex = re.compile(regex, re.MULTILINE | re.IGNORECASE)
                self.pattern_cache[tool].append(
                    {
                        "id": pattern_id,
                        "name": name,
                        "regex": compiled_regex,
                        "action": action,
                        "type": ptype,
                    }
                )
            except re.error as e:
                print(f"Warning: Invalid regex for pattern {name}: {e}")

        conn.close()
        self.last_cache_update = time.time()

    def refresh_cache_if_needed(self):
        """Refresh pattern cache if TTL expired."""
        if time.time() - self.last_cache_update > self.cache_ttl:
            self.load_patterns()

    def detect_patterns(self, text: str, tool_name: str = None) -> list:
        """
        Detect patterns in text.

        Args:
            text: Text to analyze
            tool_name: LLM tool name (claude, gemini, etc.)

        Returns:
            List of detected patterns with match info
        """
        self.refresh_cache_if_needed()

        if not self.pattern_cache:
            self.load_patterns()

        detected = []

        # Check patterns for this tool
        if tool_name and tool_name in self.pattern_cache:
            for pattern in self.pattern_cache[tool_name]:
                match = pattern["regex"].search(text)
                if match:
                    detected.append(
                        {
                            "pattern_id": pattern["id"],
                            "pattern_name": pattern["name"],
                            "pattern_type": pattern["type"],
                            "action": pattern["action"],
                            "matched_text": match.group(0),
                            "match_groups": match.groups(),
                            "tool": tool_name,
                        }
                    )

        # Also check generic patterns (no tool specified)
        if None in self.pattern_cache:
            for pattern in self.pattern_cache[None]:
                match = pattern["regex"].search(text)
                if match:
                    detected.append(
                        {
                            "pattern_id": pattern["id"],
                            "pattern_name": pattern["name"],
                            "pattern_type": pattern["type"],
                            "action": pattern["action"],
                            "matched_text": match.group(0),
                            "match_groups": match.groups(),
                            "tool": "generic",
                        }
                    )

        return detected

    def identify_tool_from_session(self, session_name: str) -> Optional[str]:
        """Identify which LLM tool is running in the session."""
        # Check session name patterns
        if "claude" in session_name.lower() or "dev-backend" in session_name.lower():
            return "claude"
        elif "gemini" in session_name.lower() or "fullstack" in session_name.lower():
            return "gemini"
        elif "ollama" in session_name.lower():
            return "ollama"
        elif "claw" in session_name.lower():
            return "openclaw"

        # Could also check tmux pane content for tool-specific markers
        return None

    def should_skip_pattern(self, pattern: Dict) -> bool:
        """Check if pattern should be skipped (not acted upon)."""
        return pattern.get("action") == "skip"

    def get_action_for_pattern(self, pattern: Dict) -> Optional[str]:
        """Get the action to take for a detected pattern."""
        action = pattern.get("action", "")

        if not action or action == "skip":
            return None

        # Parse action format: "send_key:1" or "send_key:2" or "alert:..."
        if action.startswith("send_key:"):
            key = action.split(":", 1)[1]
            return f"send_key:{key}"
        elif action.startswith("alert:"):
            alert_type = action.split(":", 1)[1]
            return f"alert:{alert_type}"

        return None

    def record_pattern_occurrence(
        self,
        pattern_id: int,
        session_name: str,
        matched_text: str,
        context: str = "",
        action_taken: str = "",
        success: bool = True,
    ):
        """Record that a pattern was detected and handled."""
        self.tracker.record_occurrence(
            pattern_id=pattern_id,
            session_name=session_name,
            matched_text=matched_text,
            context=context,
            response_action=action_taken,
            response_success=success,
        )


def detect_unknown_patterns(text: str, session_name: str) -> Optional[Dict]:
    """
    Detect potential new patterns that aren't in the database yet.
    This helps discover new prompt formats when tools update.
    """
    unknown_patterns = []

    # Common prompt indicators
    prompt_indicators = [
        r"(Allow|Approve|Confirm|Accept|Continue)",
        r"(\d+\.\s+\w+)",  # Numbered options like "1. Allow"
        r"(y/n|\(y/n\))",  # Yes/No prompts
        r"(Press any key|Press Enter)",
        r"(\[Y/n\]|\[y/N\])",  # Default option prompts
    ]

    for indicator in prompt_indicators:
        matches = re.finditer(indicator, text, re.IGNORECASE)
        for match in matches:
            # Check if this might be a new pattern
            context = text[max(0, match.start() - 50) : min(len(text), match.end() + 50)]

            unknown_patterns.append(
                {
                    "potential_type": "permission_prompt",
                    "matched_text": match.group(0),
                    "context": context,
                    "session": session_name,
                    "timestamp": time.time(),
                }
            )

    return unknown_patterns if unknown_patterns else None


def adaptive_confirm(
    session_name: str, session_output: str, detector: PatternDetector
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Adaptively confirm prompts based on learned patterns.

    Returns:
        (should_confirm, key_to_send, detected_pattern)
    """
    # Identify tool
    tool = detector.identify_tool_from_session(session_name)

    # Detect patterns
    patterns = detector.detect_patterns(session_output, tool)

    if not patterns:
        # No known patterns - check for unknown ones
        unknown = detect_unknown_patterns(session_output, session_name)
        if unknown:
            # Log unknown pattern for learning
            print(f"⚠️  Unknown pattern detected in {session_name}: {unknown[0]['matched_text']}")

        return (False, None, None)

    # Use first matched pattern (could prioritize by pattern type/confidence later)
    pattern = patterns[0]

    # Check if we should skip this pattern
    if detector.should_skip_pattern(pattern):
        return (False, None, pattern)

    # Get action
    action = detector.get_action_for_pattern(pattern)

    if not action:
        return (False, None, pattern)

    # Parse action
    if action.startswith("send_key:"):
        key = action.split(":", 1)[1]
        return (True, key, pattern)
    elif action.startswith("alert:"):
        # Handle alerts
        alert_type = action.split(":", 1)[1]
        print(f"🚨 ALERT: {alert_type} in {session_name}")
        print(f"   Pattern: {pattern['pattern_name']}")
        print(f"   Matched: {pattern['matched_text']}")
        return (False, None, pattern)

    return (False, None, pattern)


if __name__ == "__main__":
    # Test pattern detection
    detector = PatternDetector()
    detector.load_patterns()

    # Test Claude pattern
    claude_output = """
╭────────────────────────────────────────────────────╮
│ Action Required                                    │
│                                                    │
│ ?  WriteFile Writing to tmp/test/solution.py      │
│                                                    │
│ ● 1. Allow once                                    │
│   2. Allow for this session                        │
│   3. No, suggest changes (esc)                     │
│                                                    │
╰────────────────────────────────────────────────────╯
"""

    print("Testing Claude output:")
    patterns = detector.detect_patterns(claude_output, "claude")
    for p in patterns:
        print(f"  Detected: {p['pattern_name']} -> {p['action']}")

    # Test Gemini pattern
    gemini_output = """
╭────────────────────────────────────────────────────╮
│ Action Required                                    │
│                                                    │
│ ?  Shell mkdir -p tmp/test                         │
│                                                    │
│ mkdir -p tmp/test                                  │
│ Allow execution of: 'mkdir'?                       │
│                                                    │
│ ● 1. Allow once                                    │
│   2. Allow for this session                        │
│   3. No, suggest changes (esc)                     │
│                                                    │
╰────────────────────────────────────────────────────╯
"""

    print("\nTesting Gemini output:")
    patterns = detector.detect_patterns(gemini_output, "gemini")
    for p in patterns:
        print(f"  Detected: {p['pattern_name']} -> {p['action']}")
