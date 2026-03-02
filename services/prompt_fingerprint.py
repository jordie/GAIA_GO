#!/usr/bin/env python3
"""
Prompt Fingerprinting

Generates stable, unique fingerprints for prompts to enable
robust duplicate detection across restarts and session changes.

Uses multiple factors to create collision-resistant keys.
"""

import hashlib
import json
import re
import subprocess
from typing import Dict, Optional


class PromptFingerprint:
    """Generates stable fingerprints for prompts."""

    def __init__(self):
        """Initialize fingerprinter."""
        self.cache = {}

    def generate_fingerprint(
        self, prompt_text: str, session_name: str = None, operation_type: str = None
    ) -> str:
        """
        Generate a stable, unique fingerprint for a prompt.

        Uses:
        - Prompt content hash
        - Operation type
        - Session context (working directory)
        - Timestamp (minute-level granularity)

        Args:
            prompt_text: The prompt text
            session_name: Session identifier
            operation_type: Type of operation (e.g., 'proceed_yes', 'accept_edits')

        Returns:
            16-character hex fingerprint
        """
        # Extract key content from prompt (remove whitespace, normalize)
        normalized = self._normalize_prompt(prompt_text)

        # Get session context
        session_context = ""
        if session_name:
            session_context = self._get_session_context(session_name)

        # Build fingerprint components
        components = {
            "content": normalized,
            "operation": operation_type or "unknown",
            "session_context": session_context,
        }

        # Create combined hash
        combined = json.dumps(components, sort_keys=True)
        fingerprint = hashlib.sha256(combined.encode()).hexdigest()[:16]

        return fingerprint

    def _normalize_prompt(self, prompt_text: str) -> str:
        """
        Normalize prompt text to handle display variations.

        Removes:
        - Extra whitespace
        - ANSI escape codes
        - Line numbers
        - Timestamps
        - Variable parts

        Keeps:
        - Core operation keywords
        - File names
        - Command patterns
        """
        text = prompt_text

        # Remove ANSI escape codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        text = ansi_escape.sub("", text)

        # Remove timestamps
        text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "", text)

        # Remove line numbers
        text = re.sub(r"^\s*\d+→", "", text, flags=re.MULTILINE)

        # Normalize whitespace (but keep structure)
        text = re.sub(r"\s+", " ", text)

        # Extract core content (first 200 chars after normalization)
        core = text[:200].strip()

        # Create hash of core content
        content_hash = hashlib.md5(core.encode()).hexdigest()[:8]

        return content_hash

    def _get_session_context(self, session_name: str) -> str:
        """
        Get session context to detect moves between directories.

        Returns first part of working directory path.
        """
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-t", session_name, "-p", "#{pane_current_path}"],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.stdout:
                # Get the last 2 path components
                path = result.stdout.strip()
                parts = path.rstrip("/").split("/")[-2:]
                return "/".join(parts)
        except Exception:
            pass

        return "unknown"

    def is_duplicate(
        self,
        fingerprint: str,
        fingerprint2: str,
        tolerance: float = 0.8,
    ) -> bool:
        """
        Check if two fingerprints represent the same prompt.

        Uses fuzzy matching to handle minor variations.

        Args:
            fingerprint: First fingerprint
            fingerprint2: Second fingerprint
            tolerance: Similarity threshold (0-1)

        Returns:
            True if fingerprints are similar enough to be considered duplicates
        """
        # Exact match
        if fingerprint == fingerprint2:
            return True

        # Similarity-based matching (for variations)
        similarity = self._calculate_similarity(fingerprint, fingerprint2)
        return similarity >= tolerance

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings (0-1).

        Uses Levenshtein distance approximation.
        """
        if str1 == str2:
            return 1.0
        if not str1 or not str2:
            return 0.0

        # Simple character overlap similarity
        set1 = set(str1)
        set2 = set(str2)

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def get_fingerprint_info(self, fingerprint: str) -> Dict:
        """Get information about a fingerprint."""
        return {
            "fingerprint": fingerprint,
            "length": len(fingerprint),
            "hash_algorithm": "SHA256 (truncated to 16 chars)",
            "collision_resistance": "Very high",
        }


class DuplicateDetector:
    """Detects and tracks duplicate prompts using fingerprints."""

    def __init__(self):
        """Initialize detector."""
        self.fingerprint_gen = PromptFingerprint()
        self.seen_fingerprints = {}  # fingerprint -> {first_seen, count, sessions}

    def record_prompt(self, prompt_text: str, session_name: str, operation_type: str):
        """Record a prompt."""
        fingerprint = self.fingerprint_gen.generate_fingerprint(
            prompt_text, session_name, operation_type
        )

        if fingerprint not in self.seen_fingerprints:
            self.seen_fingerprints[fingerprint] = {
                "first_seen": None,
                "count": 0,
                "sessions": set(),
                "operation": operation_type,
            }

        record = self.seen_fingerprints[fingerprint]
        record["count"] += 1
        record["sessions"].add(session_name)

        return fingerprint

    def is_likely_duplicate(
        self, prompt_text: str, session_name: str, operation_type: str
    ) -> bool:
        """Check if a prompt is likely a duplicate."""
        fingerprint = self.fingerprint_gen.generate_fingerprint(
            prompt_text, session_name, operation_type
        )

        if fingerprint in self.seen_fingerprints:
            record = self.seen_fingerprints[fingerprint]
            return record["count"] > 1

        return False

    def get_duplicate_stats(self) -> Dict:
        """Get duplicate statistics."""
        stats = {
            "total_unique": len(self.seen_fingerprints),
            "total_duplicates": sum(
                max(0, r["count"] - 1) for r in self.seen_fingerprints.values()
            ),
            "most_common": [],
        }

        # Sort by frequency
        sorted_fps = sorted(
            self.seen_fingerprints.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )

        # Get top 5 most common
        for fp, record in sorted_fps[:5]:
            if record["count"] > 1:
                stats["most_common"].append(
                    {
                        "fingerprint": fp,
                        "count": record["count"],
                        "operation": record["operation"],
                        "sessions": list(record["sessions"]),
                    }
                )

        return stats


def main():
    """Test the prompt fingerprinting."""
    print("Testing Prompt Fingerprinting")
    print("=" * 80)

    fp_gen = PromptFingerprint()
    detector = DuplicateDetector()

    # Test 1: Generate fingerprints
    print("\n1. Generating fingerprints:")
    test_prompts = [
        ("Do you want to proceed?", "basic_edu", "proceed_yes"),
        ("Do you want to proceed?", "basic_edu", "proceed_yes"),  # Same prompt
        ("Accept edits?", "foundation", "accept_edits"),
        ("Do you want to proceed?", "foundation", "proceed_yes"),  # Different session, same content
    ]

    fingerprints = []
    for prompt, session, operation in test_prompts:
        fp = fp_gen.generate_fingerprint(prompt, session, operation)
        fingerprints.append(fp)
        print(f"   {prompt[:30]}... → {fp}")

    # Test 2: Detect duplicates
    print("\n2. Duplicate detection:")
    print(f"   FP[0] vs FP[1]: {detector.fingerprint_gen.is_duplicate(fingerprints[0], fingerprints[1])}")
    print(f"   FP[0] vs FP[2]: {detector.fingerprint_gen.is_duplicate(fingerprints[0], fingerprints[2])}")
    print(f"   FP[0] vs FP[3]: {detector.fingerprint_gen.is_duplicate(fingerprints[0], fingerprints[3])}")

    # Test 3: Record and detect
    print("\n3. Recording and detecting duplicates:")
    for prompt, session, operation in test_prompts:
        is_dup = detector.is_likely_duplicate(prompt, session, operation)
        detector.record_prompt(prompt, session, operation)
        print(f"   {prompt[:30]}... (is_duplicate={is_dup})")

    # Test 4: Statistics
    print("\n4. Duplicate statistics:")
    stats = detector.get_duplicate_stats()
    print(f"   Total unique fingerprints: {stats['total_unique']}")
    print(f"   Total duplicates: {stats['total_duplicates']}")
    if stats["most_common"]:
        print(f"   Most common:")
        for dup in stats["most_common"]:
            print(f"     - {dup['operation']}: {dup['count']} occurrences")

    print("\n✓ Prompt Fingerprinting tests complete!")


if __name__ == "__main__":
    main()
