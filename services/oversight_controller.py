#!/usr/bin/env python3
"""
Oversight Controller

Enables high-level session to send strategic directives to manager/architect sessions.
Directives include guidance, constraints, and priority changes.
"""

import json
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional


class OversightController:
    """High-level control interface for managing agent behavior."""

    # Directive types
    DIRECTIVE_TYPES = {
        "guidance": {
            "description": "Strategic guidance for manager sessions",
            "priority": 5,
        },
        "constraint": {
            "description": "Constraint that manager must follow",
            "priority": 8,
        },
        "priority": {
            "description": "Change task priorities",
            "priority": 7,
        },
        "escalation_rule": {
            "description": "Add escalation rule for future decisions",
            "priority": 6,
        },
        "abort_task": {
            "description": "Abort current task immediately",
            "priority": 10,
        },
    }

    # Target sessions
    VALID_TARGETS = {
        "architect": "Main manager session",
        "wrapper_claude": "Alternative manager session",
        "all_managers": "All manager sessions",
    }

    def __init__(self, db_path: str = "/tmp/gaia_agent_management.db"):
        """Initialize oversight controller."""
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Ensure directives table exists."""
        conn = sqlite3.connect(self.db_path)

        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oversight_directives'"
        )
        exists = cursor.fetchone() is not None

        if not exists:
            # Create directives table if needed
            conn.execute(
                """
                CREATE TABLE oversight_directives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    directive_id TEXT UNIQUE,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    target_session TEXT NOT NULL,
                    issued_by TEXT DEFAULT 'high_level_session',
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TIMESTAMP,
                    acknowledged_by TEXT,
                    status TEXT DEFAULT 'pending',
                    metadata JSON
                )
            """
            )

        conn.commit()
        conn.close()

    def send_directive(
        self,
        directive_type: str,
        content: str,
        target_session: str,
        metadata: Dict = None,
    ) -> str:
        """
        Send a directive to a manager session.

        Args:
            directive_type: Type of directive (guidance, constraint, priority, etc.)
            content: The directive content
            target_session: Target session (architect, wrapper_claude, all_managers)
            metadata: Optional metadata dictionary

        Returns:
            Directive ID for tracking
        """
        if directive_type not in self.DIRECTIVE_TYPES:
            raise ValueError(f"Invalid directive type: {directive_type}")

        if target_session not in self.VALID_TARGETS:
            raise ValueError(f"Invalid target session: {target_session}")

        directive_id = str(uuid.uuid4())[:8]

        directive = {
            "id": directive_id,
            "type": directive_type,
            "content": content,
            "target_session": target_session,
            "issued_by": "high_level_session",
            "issued_at": datetime.now().isoformat(),
            "status": "pending",
        }

        # Store in database
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO oversight_directives
            (directive_id, type, content, target_session, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                directive_id,
                directive_type,
                content,
                target_session,
                "pending",
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        conn.close()

        return directive_id

    def send_guidance(
        self, target_session: str, guidance_text: str, metadata: Dict = None
    ) -> str:
        """
        Send guidance (lowest priority directive).

        Args:
            target_session: Target session
            guidance_text: Guidance content
            metadata: Optional metadata

        Returns:
            Directive ID
        """
        return self.send_directive("guidance", guidance_text, target_session, metadata)

    def send_constraint(
        self, target_session: str, constraint_text: str, metadata: Dict = None
    ) -> str:
        """
        Send constraint (must follow).

        Args:
            target_session: Target session
            constraint_text: Constraint content
            metadata: Optional metadata

        Returns:
            Directive ID
        """
        return self.send_directive("constraint", constraint_text, target_session, metadata)

    def send_priority_change(
        self, target_session: str, priority_info: Dict, metadata: Dict = None
    ) -> str:
        """
        Send priority change directive.

        Args:
            target_session: Target session
            priority_info: Priority information (task_id, new_priority, reason)
            metadata: Optional metadata

        Returns:
            Directive ID
        """
        priority_text = json.dumps(priority_info)
        return self.send_directive("priority", priority_text, target_session, metadata)

    def send_abort_task(self, target_session: str, reason: str = "") -> str:
        """
        Send task abort directive (highest priority).

        Args:
            target_session: Target session
            reason: Reason for abort

        Returns:
            Directive ID
        """
        abort_text = f"ABORT CURRENT TASK" + (f": {reason}" if reason else "")
        return self.send_directive("abort_task", abort_text, target_session)

    def acknowledge_directive(self, directive_id: str, session_name: str) -> bool:
        """
        Mark a directive as acknowledged.

        Args:
            directive_id: Directive ID
            session_name: Session that acknowledged

        Returns:
            True if updated, False if directive not found
        """
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute(
            """
            UPDATE oversight_directives
            SET status = 'acknowledged',
                acknowledged_at = CURRENT_TIMESTAMP,
                acknowledged_by = ?
            WHERE directive_id = ? AND status = 'pending'
        """,
            (session_name, directive_id),
        )

        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return updated

    def get_directive(self, directive_id: str) -> Optional[Dict]:
        """Get directive details."""
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute(
            """
            SELECT directive_id, type, content, target_session,
                   issued_at, acknowledged_at, acknowledged_by, status
            FROM oversight_directives
            WHERE directive_id = ?
        """,
            (directive_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "type": row[1],
            "content": row[2],
            "target_session": row[3],
            "issued_at": row[4],
            "acknowledged_at": row[5],
            "acknowledged_by": row[6],
            "status": row[7],
        }

    def get_pending_directives(self, target_session: str = None) -> List[Dict]:
        """
        Get pending directives.

        Args:
            target_session: Optional filter by session

        Returns:
            List of pending directives
        """
        conn = sqlite3.connect(self.db_path)

        if target_session:
            cursor = conn.execute(
                """
                SELECT directive_id, type, content, target_session,
                       issued_at, status
                FROM oversight_directives
                WHERE status = 'pending' AND target_session = ?
                ORDER BY issued_at DESC
            """,
                (target_session,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT directive_id, type, content, target_session,
                       issued_at, status
                FROM oversight_directives
                WHERE status = 'pending'
                ORDER BY issued_at DESC
            """
            )

        directives = []
        for row in cursor.fetchall():
            directives.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "content": row[2],
                    "target": row[3],
                    "issued_at": row[4],
                    "status": row[5],
                }
            )

        conn.close()
        return directives

    def get_directive_history(self, limit: int = 20) -> List[Dict]:
        """Get directive history."""
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute(
            """
            SELECT directive_id, type, target_session, status, issued_at
            FROM oversight_directives
            ORDER BY issued_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        history = []
        for row in cursor.fetchall():
            history.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "target": row[2],
                    "status": row[3],
                    "issued_at": row[4],
                }
            )

        conn.close()
        return history

    def get_statistics(self) -> Dict:
        """Get oversight statistics."""
        conn = sqlite3.connect(self.db_path)

        # Pending directives
        cursor = conn.execute("SELECT COUNT(*) FROM oversight_directives WHERE status = 'pending'")
        pending = cursor.fetchone()[0]

        # Acknowledged directives
        cursor = conn.execute(
            "SELECT COUNT(*) FROM oversight_directives WHERE status = 'acknowledged'"
        )
        acknowledged = cursor.fetchone()[0]

        # By type
        cursor = conn.execute(
            """
            SELECT type, COUNT(*) as count
            FROM oversight_directives
            GROUP BY type
            ORDER BY count DESC
        """
        )

        by_type = dict(cursor.fetchall())

        # By target
        cursor = conn.execute(
            """
            SELECT target_session, COUNT(*) as count
            FROM oversight_directives
            GROUP BY target_session
            ORDER BY count DESC
        """
        )

        by_target = dict(cursor.fetchall())

        conn.close()

        return {
            "total": pending + acknowledged,
            "pending": pending,
            "acknowledged": acknowledged,
            "by_type": by_type,
            "by_target": by_target,
        }


def main():
    """Test the oversight controller."""
    print("Testing Oversight Controller")
    print("=" * 80)

    controller = OversightController()

    # Test 1: Send directives
    print("\n1. Sending directives:")
    directive_ids = []

    guid_id = controller.send_guidance(
        "architect", "Focus on Phase 11.4 rate limiting completion before new work"
    )
    directive_ids.append(guid_id)
    print(f"   ✓ Guidance sent: {guid_id}")

    const_id = controller.send_constraint(
        "architect", "Do not deploy to production without full test suite passing"
    )
    directive_ids.append(const_id)
    print(f"   ✓ Constraint sent: {const_id}")

    priority_id = controller.send_priority_change(
        "architect", {"task": "Phase11.4", "priority": 10, "reason": "Critical path item"}
    )
    directive_ids.append(priority_id)
    print(f"   ✓ Priority change sent: {priority_id}")

    # Test 2: Get pending directives
    print("\n2. Pending directives:")
    pending = controller.get_pending_directives()
    print(f"   Total pending: {len(pending)}")
    for d in pending[:3]:
        print(f"     - {d['type']}: {d['content'][:40]}...")

    # Test 3: Acknowledge directive
    print("\n3. Acknowledging directive:")
    acked = controller.acknowledge_directive(guid_id, "architect")
    print(f"   Acknowledged: {acked}")

    # Test 4: Get statistics
    print("\n4. Oversight statistics:")
    stats = controller.get_statistics()
    print(f"   Total directives: {stats['total']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Acknowledged: {stats['acknowledged']}")
    print(f"   By type: {stats['by_type']}")
    print(f"   By target: {stats['by_target']}")

    print("\n✓ Oversight Controller tests complete!")


if __name__ == "__main__":
    main()
