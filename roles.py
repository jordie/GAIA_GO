"""
Role Management Module

Provides functions for managing user roles and permissions.
Supports role-based access control (RBAC) for the Architect Dashboard.
"""

import json
import sqlite3
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import jsonify, request, session

# Default roles with their permissions
DEFAULT_ROLES = {
    "admin": {
        "description": "Full system administrator with all permissions",
        "permissions": ["*"],  # Wildcard = all permissions
        "is_system": True,
    },
    "manager": {
        "description": "Project manager with broad access",
        "permissions": [
            "projects.*",
            "milestones.*",
            "features.*",
            "bugs.*",
            "tasks.*",
            "users.view",
            "reports.*",
            "webhooks.view",
        ],
        "is_system": True,
    },
    "developer": {
        "description": "Developer with project access",
        "permissions": [
            "projects.view",
            "milestones.view",
            "features.*",
            "bugs.*",
            "tasks.view",
            "tasks.claim",
            "tasks.complete",
            "tmux.*",
        ],
        "is_system": True,
    },
    "viewer": {
        "description": "Read-only access to view data",
        "permissions": [
            "projects.view",
            "milestones.view",
            "features.view",
            "bugs.view",
            "tasks.view",
            "reports.view",
        ],
        "is_system": True,
    },
    "user": {
        "description": "Standard user with basic access",
        "permissions": [
            "projects.view",
            "milestones.view",
            "features.view",
            "bugs.view",
            "tasks.view",
            "tasks.create",
        ],
        "is_system": True,
    },
}

# All available permissions grouped by resource
AVAILABLE_PERMISSIONS = {
    "projects": ["view", "create", "update", "delete", "archive"],
    "milestones": ["view", "create", "update", "delete"],
    "features": ["view", "create", "update", "delete", "assign"],
    "bugs": ["view", "create", "update", "delete", "assign"],
    "tasks": ["view", "create", "update", "delete", "claim", "complete", "assign"],
    "users": ["view", "create", "update", "delete", "manage_roles"],
    "roles": ["view", "create", "update", "delete"],
    "webhooks": ["view", "create", "update", "delete", "test"],
    "tmux": ["view", "create", "send", "kill"],
    "nodes": ["view", "create", "update", "delete"],
    "reports": ["view", "create", "export"],
    "settings": ["view", "update"],
    "audit": ["view"],
}


def init_roles_tables(conn):
    """Initialize roles and permissions tables."""
    conn.executescript(
        """
        -- Roles table
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            permissions TEXT,  -- JSON array of permissions
            is_system INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- User roles junction table (for multiple roles per user)
        CREATE TABLE IF NOT EXISTS user_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_by TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            UNIQUE(user_id, role_id)
        );

        -- Role audit log
        CREATE TABLE IF NOT EXISTS role_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER,
            target_name TEXT,
            performed_by TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);
        CREATE INDEX IF NOT EXISTS idx_role_audit_target ON role_audit_log(target_type, target_id);
    """
    )


def seed_default_roles(conn):
    """Seed default roles if they don't exist."""
    for role_name, role_data in DEFAULT_ROLES.items():
        existing = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO roles (name, description, permissions, is_system)
                VALUES (?, ?, ?, ?)
            """,
                (
                    role_name,
                    role_data["description"],
                    json.dumps(role_data["permissions"]),
                    1 if role_data.get("is_system") else 0,
                ),
            )


def get_roles(conn, include_system: bool = True) -> List[Dict]:
    """Get all roles."""
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM roles"
    if not include_system:
        query += " WHERE is_system = 0"
    query += " ORDER BY is_system DESC, name"

    rows = conn.execute(query).fetchall()
    roles = []
    for row in rows:
        role = dict(row)
        role["permissions"] = json.loads(role["permissions"]) if role["permissions"] else []
        # Count users with this role
        user_count = conn.execute(
            "SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (role["id"],)
        ).fetchone()[0]
        role["user_count"] = user_count
        roles.append(role)
    return roles


def get_role(conn, role_id: int = None, role_name: str = None) -> Optional[Dict]:
    """Get a specific role by ID or name."""
    conn.row_factory = sqlite3.Row
    if role_id:
        row = conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    elif role_name:
        row = conn.execute("SELECT * FROM roles WHERE name = ?", (role_name,)).fetchone()
    else:
        return None

    if not row:
        return None

    role = dict(row)
    role["permissions"] = json.loads(role["permissions"]) if role["permissions"] else []
    return role


def create_role(
    conn, name: str, description: str = None, permissions: List[str] = None, created_by: str = None
) -> int:
    """Create a new role.

    Args:
        conn: Database connection
        name: Role name (must be unique)
        description: Role description
        permissions: List of permissions
        created_by: Username of creator

    Returns:
        ID of created role
    """
    # Validate permissions
    if permissions:
        for perm in permissions:
            if perm != "*" and ".*" not in perm:
                resource, action = perm.rsplit(".", 1) if "." in perm else (perm, None)
                if resource not in AVAILABLE_PERMISSIONS:
                    raise ValueError(f"Invalid resource: {resource}")
                if action and action not in AVAILABLE_PERMISSIONS.get(resource, []):
                    raise ValueError(f"Invalid permission: {perm}")

    cursor = conn.execute(
        """
        INSERT INTO roles (name, description, permissions, is_system)
        VALUES (?, ?, ?, 0)
    """,
        (name, description, json.dumps(permissions or [])),
    )

    role_id = cursor.lastrowid

    # Log the action
    log_role_action(
        conn, "create_role", "role", role_id, name, created_by, {"permissions": permissions}
    )

    return role_id


def update_role(
    conn,
    role_id: int,
    name: str = None,
    description: str = None,
    permissions: List[str] = None,
    updated_by: str = None,
) -> bool:
    """Update a role.

    Args:
        conn: Database connection
        role_id: Role ID to update
        name: New name (optional)
        description: New description (optional)
        permissions: New permissions (optional)
        updated_by: Username of updater

    Returns:
        True if updated, False if not found or system role
    """
    # Check if role exists and is not system role
    role = get_role(conn, role_id=role_id)
    if not role:
        return False
    if role["is_system"]:
        raise ValueError("Cannot modify system roles")

    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if permissions is not None:
        # Validate permissions
        for perm in permissions:
            if perm != "*" and ".*" not in perm:
                resource = perm.rsplit(".", 1)[0] if "." in perm else perm
                if resource not in AVAILABLE_PERMISSIONS:
                    raise ValueError(f"Invalid resource: {resource}")
        updates.append("permissions = ?")
        params.append(json.dumps(permissions))

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(role_id)

    conn.execute(f"UPDATE roles SET {', '.join(updates)} WHERE id = ?", params)

    log_role_action(
        conn,
        "update_role",
        "role",
        role_id,
        role["name"],
        updated_by,
        {"name": name, "description": description, "permissions": permissions},
    )

    return True


def delete_role(conn, role_id: int, deleted_by: str = None) -> bool:
    """Delete a role.

    Args:
        conn: Database connection
        role_id: Role ID to delete
        deleted_by: Username of deleter

    Returns:
        True if deleted, False if not found or system role
    """
    role = get_role(conn, role_id=role_id)
    if not role:
        return False
    if role["is_system"]:
        raise ValueError("Cannot delete system roles")

    # Remove all user assignments first
    conn.execute("DELETE FROM user_roles WHERE role_id = ?", (role_id,))
    conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))

    log_role_action(conn, "delete_role", "role", role_id, role["name"], deleted_by)

    return True


def get_user_roles(conn, user_id: int) -> List[Dict]:
    """Get all roles assigned to a user."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.*, ur.assigned_by, ur.assigned_at
        FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
        ORDER BY r.name
    """,
        (user_id,),
    ).fetchall()

    roles = []
    for row in rows:
        role = dict(row)
        role["permissions"] = json.loads(role["permissions"]) if role["permissions"] else []
        roles.append(role)
    return roles


def get_user_permissions(conn, user_id: int) -> List[str]:
    """Get all permissions for a user (aggregated from all roles)."""
    roles = get_user_roles(conn, user_id)
    permissions = set()

    for role in roles:
        for perm in role["permissions"]:
            if perm == "*":
                # Admin has all permissions
                return ["*"]
            permissions.add(perm)

    return list(permissions)


def assign_role(conn, user_id: int, role_id: int, assigned_by: str = None) -> bool:
    """Assign a role to a user.

    Args:
        conn: Database connection
        user_id: User ID
        role_id: Role ID
        assigned_by: Username of assigner

    Returns:
        True if assigned, False if already assigned
    """
    # Verify user exists
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise ValueError("User not found")

    # Verify role exists
    role = get_role(conn, role_id=role_id)
    if not role:
        raise ValueError("Role not found")

    try:
        conn.execute(
            """
            INSERT INTO user_roles (user_id, role_id, assigned_by)
            VALUES (?, ?, ?)
        """,
            (user_id, role_id, assigned_by),
        )

        log_role_action(
            conn,
            "assign_role",
            "user",
            user_id,
            user[0],
            assigned_by,
            {"role_id": role_id, "role_name": role["name"]},
        )
        return True
    except sqlite3.IntegrityError:
        return False  # Already assigned


def revoke_role(conn, user_id: int, role_id: int, revoked_by: str = None) -> bool:
    """Revoke a role from a user.

    Args:
        conn: Database connection
        user_id: User ID
        role_id: Role ID
        revoked_by: Username of revoker

    Returns:
        True if revoked, False if not assigned
    """
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    role = get_role(conn, role_id=role_id)

    result = conn.execute(
        "DELETE FROM user_roles WHERE user_id = ? AND role_id = ?", (user_id, role_id)
    )

    if result.rowcount > 0:
        log_role_action(
            conn,
            "revoke_role",
            "user",
            user_id,
            user[0] if user else str(user_id),
            revoked_by,
            {"role_id": role_id, "role_name": role["name"] if role else str(role_id)},
        )
        return True
    return False


def get_role_users(conn, role_id: int) -> List[Dict]:
    """Get all users assigned to a role."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.role as legacy_role, u.created_at, u.last_login,
               ur.assigned_by, ur.assigned_at
        FROM users u
        JOIN user_roles ur ON u.id = ur.user_id
        WHERE ur.role_id = ?
        ORDER BY u.username
    """,
        (role_id,),
    ).fetchall()

    return [dict(row) for row in rows]


def has_permission(conn, user_id: int, permission: str) -> bool:
    """Check if a user has a specific permission.

    Args:
        conn: Database connection
        user_id: User ID
        permission: Permission to check (e.g., 'projects.create')

    Returns:
        True if user has permission
    """
    permissions = get_user_permissions(conn, user_id)

    if "*" in permissions:
        return True

    if permission in permissions:
        return True

    # Check for wildcard permissions (e.g., 'projects.*' matches 'projects.create')
    resource = permission.rsplit(".", 1)[0] if "." in permission else permission
    if f"{resource}.*" in permissions:
        return True

    return False


def log_role_action(
    conn,
    action: str,
    target_type: str,
    target_id: int,
    target_name: str,
    performed_by: str,
    details: Dict = None,
):
    """Log a role-related action to the audit log."""
    conn.execute(
        """
        INSERT INTO role_audit_log (action, target_type, target_id, target_name, performed_by, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            action,
            target_type,
            target_id,
            target_name,
            performed_by,
            json.dumps(details) if details else None,
        ),
    )


def get_role_audit_log(
    conn,
    target_type: str = None,
    target_id: int = None,
    action: str = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Get role audit log entries."""
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM role_audit_log WHERE 1=1"
    params = []

    if target_type:
        query += " AND target_type = ?"
        params.append(target_type)
    if target_id:
        query += " AND target_id = ?"
        params.append(target_id)
    if action:
        query += " AND action = ?"
        params.append(action)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
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


def require_permission(permission: str):
    """Decorator to require a specific permission.

    Usage:
        @app.route('/api/projects', methods=['POST'])
        @require_auth
        @require_permission('projects.create')
        def create_project():
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

            # Import here to avoid circular imports
            from app import get_db_connection

            with get_db_connection() as conn:
                if not has_permission(conn, user_id, permission):
                    return (
                        jsonify({"error": "Permission denied", "required_permission": permission}),
                        403,
                    )

            return f(*args, **kwargs)

        return decorated

    return decorator


def require_role(role_name: str):
    """Decorator to require a specific role.

    Usage:
        @app.route('/api/admin/settings')
        @require_auth
        @require_role('admin')
        def admin_settings():
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

            from app import get_db_connection

            with get_db_connection() as conn:
                roles = get_user_roles(conn, user_id)
                role_names = [r["name"] for r in roles]

                if role_name not in role_names and "admin" not in role_names:
                    return jsonify({"error": "Insufficient role", "required_role": role_name}), 403

            return f(*args, **kwargs)

        return decorated

    return decorator
