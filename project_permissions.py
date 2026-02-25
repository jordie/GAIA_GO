"""
Project Permissions Module

Provides fine-grained project-level access control.
Users can have different access levels per project:
- owner: Full control, can delete project and manage all members
- admin: Can manage project settings and members (except owner)
- write: Can edit project items (features, bugs, tasks, etc.)
- read: View-only access

This is separate from global roles (admin, developer, viewer, etc.) and allows
for project-specific permissions.
"""

import json
import sqlite3
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import g, jsonify, request, session

# Access levels in order of privilege (higher index = more privilege)
ACCESS_LEVELS = ["read", "write", "admin", "owner"]

# What each access level can do
ACCESS_CAPABILITIES = {
    "read": ["view"],
    "write": ["view", "create", "update"],
    "admin": ["view", "create", "update", "delete", "manage_members"],
    "owner": [
        "view",
        "create",
        "update",
        "delete",
        "manage_members",
        "manage_owner",
        "delete_project",
    ],
}


def init_project_permissions_tables(conn):
    """Initialize project permissions tables."""
    conn.executescript(
        """
        -- Project members table - associates users with projects
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'read',
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (added_by) REFERENCES users(id),
            UNIQUE(project_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id);
        CREATE INDEX IF NOT EXISTS idx_project_members_level ON project_members(access_level);

        -- Project invitations for pending invitations
        CREATE TABLE IF NOT EXISTS project_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            email TEXT,
            user_id INTEGER,
            access_level TEXT NOT NULL DEFAULT 'read',
            invited_by INTEGER NOT NULL,
            token TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            message TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (invited_by) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_project_invitations_project ON project_invitations(project_id);
        CREATE INDEX IF NOT EXISTS idx_project_invitations_user ON project_invitations(user_id);
        CREATE INDEX IF NOT EXISTS idx_project_invitations_token ON project_invitations(token);
        CREATE INDEX IF NOT EXISTS idx_project_invitations_status ON project_invitations(status);

        -- Project permissions audit log
        CREATE TABLE IF NOT EXISTS project_permissions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            target_username TEXT,
            old_level TEXT,
            new_level TEXT,
            performed_by INTEGER,
            performed_by_username TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_permissions_log_project ON project_permissions_log(project_id);
        CREATE INDEX IF NOT EXISTS idx_permissions_log_action ON project_permissions_log(action);
    """
    )


def get_access_level_rank(level: str) -> int:
    """Get numeric rank of access level (higher = more privilege)."""
    try:
        return ACCESS_LEVELS.index(level)
    except ValueError:
        return -1


def has_capability(access_level: str, capability: str) -> bool:
    """Check if an access level has a specific capability."""
    capabilities = ACCESS_CAPABILITIES.get(access_level, [])
    return capability in capabilities


def get_user_project_access(conn, user_id: int, project_id: int) -> Optional[str]:
    """Get a user's access level for a project.

    Args:
        conn: Database connection
        user_id: User ID
        project_id: Project ID

    Returns:
        Access level string ('read', 'write', 'admin', 'owner') or None if no access
    """
    # Check if user is a global admin (has all access)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["role"] == "admin":
        return "owner"  # Admins have full access to all projects

    # Check project membership
    member = conn.execute(
        """
        SELECT access_level FROM project_members
        WHERE project_id = ? AND user_id = ?
    """,
        (project_id, user_id),
    ).fetchone()

    if member:
        return member["access_level"]

    # Check if project is public (no members = public for viewing)
    member_count = conn.execute(
        "SELECT COUNT(*) FROM project_members WHERE project_id = ?", (project_id,)
    ).fetchone()[0]

    if member_count == 0:
        # No members means project is accessible to all authenticated users
        return "read"

    return None


def check_project_access(conn, user_id: int, project_id: int, required_level: str) -> bool:
    """Check if user has at least the required access level.

    Args:
        conn: Database connection
        user_id: User ID
        project_id: Project ID
        required_level: Minimum required access level

    Returns:
        True if user has sufficient access
    """
    user_level = get_user_project_access(conn, user_id, project_id)
    if not user_level:
        return False

    return get_access_level_rank(user_level) >= get_access_level_rank(required_level)


def get_project_members(conn, project_id: int) -> List[Dict]:
    """Get all members of a project.

    Args:
        conn: Database connection
        project_id: Project ID

    Returns:
        List of member dicts with user info and access level
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT pm.*, u.username, u.role as global_role,
               added_user.username as added_by_username
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        LEFT JOIN users added_user ON pm.added_by = added_user.id
        WHERE pm.project_id = ?
        ORDER BY
            CASE pm.access_level
                WHEN 'owner' THEN 1
                WHEN 'admin' THEN 2
                WHEN 'write' THEN 3
                WHEN 'read' THEN 4
            END,
            u.username
    """,
        (project_id,),
    ).fetchall()

    return [dict(row) for row in rows]


def add_project_member(
    conn, project_id: int, user_id: int, access_level: str, added_by: int
) -> Dict:
    """Add a member to a project.

    Args:
        conn: Database connection
        project_id: Project ID
        user_id: User ID to add
        access_level: Access level to grant
        added_by: User ID of who is adding

    Returns:
        Dict with success status and member info

    Raises:
        ValueError: If invalid access level or insufficient permissions
    """
    if access_level not in ACCESS_LEVELS:
        raise ValueError(f"Invalid access level: {access_level}")

    # Check if adder has permission to add members
    adder_level = get_user_project_access(conn, added_by, project_id)
    if not adder_level or not has_capability(adder_level, "manage_members"):
        raise ValueError("Insufficient permissions to add members")

    # Can't add someone with higher or equal level unless you're owner
    if access_level == "owner" and adder_level != "owner":
        raise ValueError("Only owners can add other owners")

    if (
        get_access_level_rank(access_level) >= get_access_level_rank(adder_level)
        and adder_level != "owner"
    ):
        raise ValueError("Cannot add member with equal or higher access level")

    # Get usernames for logging
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    adder = conn.execute("SELECT username FROM users WHERE id = ?", (added_by,)).fetchone()

    if not user:
        raise ValueError("User not found")

    try:
        conn.execute(
            """
            INSERT INTO project_members (project_id, user_id, access_level, added_by)
            VALUES (?, ?, ?, ?)
        """,
            (project_id, user_id, access_level, added_by),
        )

        # Log the action
        log_permission_change(
            conn,
            project_id,
            "add_member",
            user_id,
            user["username"],
            None,
            access_level,
            added_by,
            adder["username"] if adder else None,
        )

        return {
            "success": True,
            "user_id": user_id,
            "username": user["username"],
            "access_level": access_level,
        }
    except sqlite3.IntegrityError:
        raise ValueError("User is already a member of this project")


def update_project_member(
    conn, project_id: int, user_id: int, new_level: str, updated_by: int
) -> Dict:
    """Update a member's access level.

    Args:
        conn: Database connection
        project_id: Project ID
        user_id: User ID to update
        new_level: New access level
        updated_by: User ID of who is updating

    Returns:
        Dict with success status

    Raises:
        ValueError: If invalid access level or insufficient permissions
    """
    if new_level not in ACCESS_LEVELS:
        raise ValueError(f"Invalid access level: {new_level}")

    conn.row_factory = sqlite3.Row

    # Get current member info
    member = conn.execute(
        """
        SELECT pm.*, u.username
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = ? AND pm.user_id = ?
    """,
        (project_id, user_id),
    ).fetchone()

    if not member:
        raise ValueError("User is not a member of this project")

    old_level = member["access_level"]

    # Check updater permissions
    updater_level = get_user_project_access(conn, updated_by, project_id)
    updater = conn.execute("SELECT username FROM users WHERE id = ?", (updated_by,)).fetchone()

    if not updater_level or not has_capability(updater_level, "manage_members"):
        raise ValueError("Insufficient permissions to update members")

    # Special rules for owners
    if old_level == "owner":
        if updater_level != "owner":
            raise ValueError("Only owners can modify other owners")
        # Check there's at least one other owner
        owner_count = conn.execute(
            """
            SELECT COUNT(*) FROM project_members
            WHERE project_id = ? AND access_level = 'owner'
        """,
            (project_id,),
        ).fetchone()[0]
        if owner_count <= 1 and new_level != "owner":
            raise ValueError("Cannot demote the last owner")

    if new_level == "owner" and updater_level != "owner":
        raise ValueError("Only owners can promote to owner")

    # Can't promote someone to your level or higher (unless you're owner)
    if updater_level != "owner" and get_access_level_rank(new_level) >= get_access_level_rank(
        updater_level
    ):
        raise ValueError("Cannot promote member to your level or higher")

    conn.execute(
        """
        UPDATE project_members
        SET access_level = ?, updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ? AND user_id = ?
    """,
        (new_level, project_id, user_id),
    )

    log_permission_change(
        conn,
        project_id,
        "update_member",
        user_id,
        member["username"],
        old_level,
        new_level,
        updated_by,
        updater["username"] if updater else None,
    )

    return {
        "success": True,
        "user_id": user_id,
        "username": member["username"],
        "old_level": old_level,
        "new_level": new_level,
    }


def remove_project_member(conn, project_id: int, user_id: int, removed_by: int) -> Dict:
    """Remove a member from a project.

    Args:
        conn: Database connection
        project_id: Project ID
        user_id: User ID to remove
        removed_by: User ID of who is removing

    Returns:
        Dict with success status

    Raises:
        ValueError: If insufficient permissions
    """
    conn.row_factory = sqlite3.Row

    # Get member info
    member = conn.execute(
        """
        SELECT pm.*, u.username
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = ? AND pm.user_id = ?
    """,
        (project_id, user_id),
    ).fetchone()

    if not member:
        raise ValueError("User is not a member of this project")

    remover_level = get_user_project_access(conn, removed_by, project_id)
    remover = conn.execute("SELECT username FROM users WHERE id = ?", (removed_by,)).fetchone()

    # Users can remove themselves
    if user_id == removed_by:
        # But not if they're the last owner
        if member["access_level"] == "owner":
            owner_count = conn.execute(
                """
                SELECT COUNT(*) FROM project_members
                WHERE project_id = ? AND access_level = 'owner'
            """,
                (project_id,),
            ).fetchone()[0]
            if owner_count <= 1:
                raise ValueError("Cannot leave project as the last owner")
    else:
        # Check permissions
        if not remover_level or not has_capability(remover_level, "manage_members"):
            raise ValueError("Insufficient permissions to remove members")

        # Can't remove someone with equal or higher level (unless you're owner)
        if remover_level != "owner" and get_access_level_rank(
            member["access_level"]
        ) >= get_access_level_rank(remover_level):
            raise ValueError("Cannot remove member with equal or higher access level")

        if member["access_level"] == "owner" and remover_level != "owner":
            raise ValueError("Only owners can remove other owners")

    conn.execute(
        """
        DELETE FROM project_members
        WHERE project_id = ? AND user_id = ?
    """,
        (project_id, user_id),
    )

    log_permission_change(
        conn,
        project_id,
        "remove_member",
        user_id,
        member["username"],
        member["access_level"],
        None,
        removed_by,
        remover["username"] if remover else None,
    )

    return {"success": True, "user_id": user_id, "username": member["username"]}


def create_project_invitation(
    conn,
    project_id: int,
    invited_by: int,
    user_id: int = None,
    email: str = None,
    access_level: str = "read",
    message: str = None,
    expires_days: int = 7,
) -> Dict:
    """Create an invitation to join a project.

    Args:
        conn: Database connection
        project_id: Project ID
        invited_by: User ID of inviter
        user_id: User ID to invite (if known)
        email: Email to invite (if user not in system)
        access_level: Access level to grant on acceptance
        message: Optional message to include
        expires_days: Days until invitation expires

    Returns:
        Dict with invitation details
    """
    import secrets

    if not user_id and not email:
        raise ValueError("Must provide either user_id or email")

    if access_level not in ACCESS_LEVELS:
        raise ValueError(f"Invalid access level: {access_level}")

    # Check inviter permissions
    inviter_level = get_user_project_access(conn, invited_by, project_id)
    if not inviter_level or not has_capability(inviter_level, "manage_members"):
        raise ValueError("Insufficient permissions to invite members")

    if access_level == "owner" and inviter_level != "owner":
        raise ValueError("Only owners can invite new owners")

    conn.row_factory = sqlite3.Row

    # Check if user is already a member
    if user_id:
        existing = conn.execute(
            """
            SELECT id FROM project_members
            WHERE project_id = ? AND user_id = ?
        """,
            (project_id, user_id),
        ).fetchone()
        if existing:
            raise ValueError("User is already a member of this project")

        # Check for pending invitation
        pending = conn.execute(
            """
            SELECT id FROM project_invitations
            WHERE project_id = ? AND user_id = ? AND status = 'pending'
        """,
            (project_id, user_id),
        ).fetchone()
        if pending:
            raise ValueError("User already has a pending invitation")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now().isoformat()  # Would add expires_days in production

    cursor = conn.execute(
        """
        INSERT INTO project_invitations
        (project_id, user_id, email, access_level, invited_by, token, message, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '+' || ? || ' days'))
    """,
        (project_id, user_id, email, access_level, invited_by, token, message, expires_days),
    )

    invitation_id = cursor.lastrowid

    # Get project name for response
    project = conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()

    return {
        "id": invitation_id,
        "project_id": project_id,
        "project_name": project["name"] if project else None,
        "user_id": user_id,
        "email": email,
        "access_level": access_level,
        "token": token,
        "status": "pending",
    }


def respond_to_invitation(
    conn, invitation_id: int = None, token: str = None, user_id: int = None, accept: bool = True
) -> Dict:
    """Accept or decline a project invitation.

    Args:
        conn: Database connection
        invitation_id: Invitation ID (or use token)
        token: Invitation token (or use invitation_id)
        user_id: User accepting/declining (required)
        accept: True to accept, False to decline

    Returns:
        Dict with result
    """
    if not invitation_id and not token:
        raise ValueError("Must provide invitation_id or token")

    conn.row_factory = sqlite3.Row

    if token:
        invitation = conn.execute(
            """
            SELECT * FROM project_invitations
            WHERE token = ? AND status = 'pending'
        """,
            (token,),
        ).fetchone()
    else:
        invitation = conn.execute(
            """
            SELECT * FROM project_invitations
            WHERE id = ? AND status = 'pending'
        """,
            (invitation_id,),
        ).fetchone()

    if not invitation:
        raise ValueError("Invitation not found or already responded")

    # Verify user can respond (either the invited user or matching email)
    if invitation["user_id"] and invitation["user_id"] != user_id:
        raise ValueError("This invitation was sent to a different user")

    # Check expiration
    if invitation["expires_at"]:
        expires = datetime.fromisoformat(invitation["expires_at"])
        if datetime.now() > expires:
            conn.execute(
                """
                UPDATE project_invitations
                SET status = 'expired', responded_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (invitation["id"],),
            )
            raise ValueError("Invitation has expired")

    if accept:
        # Add user as member
        try:
            conn.execute(
                """
                INSERT INTO project_members (project_id, user_id, access_level, added_by)
                VALUES (?, ?, ?, ?)
            """,
                (
                    invitation["project_id"],
                    user_id,
                    invitation["access_level"],
                    invitation["invited_by"],
                ),
            )
        except sqlite3.IntegrityError:
            raise ValueError("User is already a member of this project")

        status = "accepted"

        # Log the action
        user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        log_permission_change(
            conn,
            invitation["project_id"],
            "accept_invitation",
            user_id,
            user["username"] if user else None,
            None,
            invitation["access_level"],
            user_id,
            user["username"] if user else None,
            {"invitation_id": invitation["id"]},
        )
    else:
        status = "declined"

    conn.execute(
        """
        UPDATE project_invitations
        SET status = ?, responded_at = CURRENT_TIMESTAMP, user_id = ?
        WHERE id = ?
    """,
        (status, user_id, invitation["id"]),
    )

    project = conn.execute(
        "SELECT name FROM projects WHERE id = ?", (invitation["project_id"],)
    ).fetchone()

    return {
        "success": True,
        "status": status,
        "project_id": invitation["project_id"],
        "project_name": project["name"] if project else None,
        "access_level": invitation["access_level"] if accept else None,
    }


def get_project_invitations(
    conn, project_id: int = None, user_id: int = None, status: str = None
) -> List[Dict]:
    """Get project invitations.

    Args:
        conn: Database connection
        project_id: Filter by project
        user_id: Filter by invited user
        status: Filter by status ('pending', 'accepted', 'declined', 'expired')

    Returns:
        List of invitation dicts
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT pi.*,
               p.name as project_name,
               u.username as invited_username,
               inviter.username as invited_by_username
        FROM project_invitations pi
        JOIN projects p ON pi.project_id = p.id
        LEFT JOIN users u ON pi.user_id = u.id
        JOIN users inviter ON pi.invited_by = inviter.id
        WHERE 1=1
    """
    params = []

    if project_id:
        query += " AND pi.project_id = ?"
        params.append(project_id)
    if user_id:
        query += " AND pi.user_id = ?"
        params.append(user_id)
    if status:
        query += " AND pi.status = ?"
        params.append(status)

    query += " ORDER BY pi.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_user_accessible_projects(conn, user_id: int) -> List[Dict]:
    """Get all projects a user has access to.

    Args:
        conn: Database connection
        user_id: User ID

    Returns:
        List of projects with access level info
    """
    conn.row_factory = sqlite3.Row

    # Check if user is global admin
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    is_admin = user and user["role"] == "admin"

    if is_admin:
        # Admins see all projects
        rows = conn.execute(
            """
            SELECT p.*, 'owner' as access_level, NULL as member_since
            FROM projects p
            WHERE p.status != 'archived'
            ORDER BY p.name
        """
        ).fetchall()
    else:
        # Get projects user is a member of
        rows = conn.execute(
            """
            SELECT p.*, pm.access_level, pm.added_at as member_since
            FROM projects p
            JOIN project_members pm ON p.id = pm.project_id
            WHERE pm.user_id = ? AND p.status != 'archived'
            ORDER BY
                CASE pm.access_level
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'write' THEN 3
                    WHEN 'read' THEN 4
                END,
                p.name
        """,
            (user_id,),
        ).fetchall()

        # Also include public projects (those with no members)
        public_projects = conn.execute(
            """
            SELECT p.*, 'read' as access_level, NULL as member_since
            FROM projects p
            WHERE p.status != 'archived'
            AND p.id NOT IN (SELECT DISTINCT project_id FROM project_members)
            AND p.id NOT IN (
                SELECT project_id FROM project_members WHERE user_id = ?
            )
            ORDER BY p.name
        """,
            (user_id,),
        ).fetchall()

        rows = list(rows) + list(public_projects)

    return [dict(row) for row in rows]


def log_permission_change(
    conn,
    project_id: int,
    action: str,
    target_user_id: int,
    target_username: str,
    old_level: str,
    new_level: str,
    performed_by: int,
    performed_by_username: str,
    details: Dict = None,
):
    """Log a permission change to the audit log."""
    conn.execute(
        """
        INSERT INTO project_permissions_log
        (project_id, action, target_user_id, target_username, old_level, new_level,
         performed_by, performed_by_username, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            project_id,
            action,
            target_user_id,
            target_username,
            old_level,
            new_level,
            performed_by,
            performed_by_username,
            json.dumps(details) if details else None,
        ),
    )


def get_permission_log(
    conn,
    project_id: int = None,
    user_id: int = None,
    action: str = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Get permission audit log entries.

    Args:
        conn: Database connection
        project_id: Filter by project
        user_id: Filter by target user
        action: Filter by action type
        limit: Max entries to return
        offset: Offset for pagination

    Returns:
        List of log entry dicts
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT ppl.*, p.name as project_name
        FROM project_permissions_log ppl
        JOIN projects p ON ppl.project_id = p.id
        WHERE 1=1
    """
    params = []

    if project_id:
        query += " AND ppl.project_id = ?"
        params.append(project_id)
    if user_id:
        query += " AND ppl.target_user_id = ?"
        params.append(user_id)
    if action:
        query += " AND ppl.action = ?"
        params.append(action)

    query += " ORDER BY ppl.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        if entry.get("details"):
            try:
                entry["details"] = json.loads(entry["details"])
            except json.JSONDecodeError:
                pass
        entries.append(entry)
    return entries


def set_project_owner(conn, project_id: int, user_id: int) -> Dict:
    """Set the initial owner of a project (called when project is created).

    Args:
        conn: Database connection
        project_id: Project ID
        user_id: User ID of creator

    Returns:
        Dict with member info
    """
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()

    try:
        conn.execute(
            """
            INSERT INTO project_members (project_id, user_id, access_level, added_by)
            VALUES (?, ?, 'owner', ?)
        """,
            (project_id, user_id, user_id),
        )

        log_permission_change(
            conn,
            project_id,
            "create_project",
            user_id,
            user["username"] if user else None,
            None,
            "owner",
            user_id,
            user["username"] if user else None,
        )

        return {"success": True, "user_id": user_id, "access_level": "owner"}
    except sqlite3.IntegrityError:
        # Already a member, just return existing
        return {
            "success": True,
            "user_id": user_id,
            "access_level": "owner",
            "note": "User was already a member",
        }


def require_project_access(required_level: str):
    """Decorator to require a specific project access level.

    The project_id must be in the route as a URL parameter.

    Usage:
        @app.route('/api/projects/<int:project_id>/features', methods=['POST'])
        @require_auth
        @require_project_access('write')
        def create_feature(project_id):
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            project_id = kwargs.get("project_id")
            if not project_id:
                return jsonify({"error": "Project ID required"}), 400

            user_id = session.get("user_id")
            if not user_id:
                # Check for API key auth
                if hasattr(g, "api_key_auth") and g.api_key_auth:
                    user_id = getattr(g, "api_key_user", None)

            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

            # Import here to avoid circular imports
            from app import get_db_connection

            with get_db_connection() as conn:
                if not check_project_access(conn, user_id, project_id, required_level):
                    return (
                        jsonify(
                            {
                                "error": "Insufficient project permissions",
                                "required_level": required_level,
                            }
                        ),
                        403,
                    )

            return f(*args, **kwargs)

        return decorated

    return decorator


def get_project_access_summary(conn, project_id: int) -> Dict:
    """Get summary of project access settings.

    Args:
        conn: Database connection
        project_id: Project ID

    Returns:
        Dict with access summary
    """
    conn.row_factory = sqlite3.Row

    members = get_project_members(conn, project_id)

    # Count by level
    level_counts = {level: 0 for level in ACCESS_LEVELS}
    for member in members:
        level_counts[member["access_level"]] = level_counts.get(member["access_level"], 0) + 1

    # Pending invitations
    pending = conn.execute(
        """
        SELECT COUNT(*) FROM project_invitations
        WHERE project_id = ? AND status = 'pending'
    """,
        (project_id,),
    ).fetchone()[0]

    return {
        "total_members": len(members),
        "by_level": level_counts,
        "pending_invitations": pending,
        "is_public": len(members) == 0,
    }
