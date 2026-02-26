"""
Project Dependencies Module

Provides functions for managing dependencies between projects,
including dependency tracking, validation, and impact analysis.
"""

import json
import logging
import sqlite3
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Dependency types
DEPENDENCY_TYPES = {
    "depends_on": {
        "description": "This project depends on another project",
        "inverse": "required_by",
        "blocking": True,
    },
    "required_by": {
        "description": "This project is required by another project",
        "inverse": "depends_on",
        "blocking": True,
    },
    "blocks": {
        "description": "This project blocks another project",
        "inverse": "blocked_by",
        "blocking": True,
    },
    "blocked_by": {
        "description": "This project is blocked by another project",
        "inverse": "blocks",
        "blocking": True,
    },
    "related_to": {
        "description": "This project is related to another project",
        "inverse": "related_to",
        "blocking": False,
    },
    "extends": {
        "description": "This project extends another project",
        "inverse": "extended_by",
        "blocking": False,
    },
    "extended_by": {
        "description": "This project is extended by another project",
        "inverse": "extends",
        "blocking": False,
    },
    "includes": {
        "description": "This project includes another project as a component",
        "inverse": "included_in",
        "blocking": False,
    },
    "included_in": {
        "description": "This project is included in another project",
        "inverse": "includes",
        "blocking": False,
    },
}


def get_dependency_types() -> Dict:
    """Get all available dependency types."""
    return DEPENDENCY_TYPES


def get_dependencies(
    conn, project_id: int = None, dependency_type: str = None, include_transitive: bool = False
) -> List[Dict]:
    """Get project dependencies.

    Args:
        conn: Database connection
        project_id: Filter by source project
        dependency_type: Filter by dependency type
        include_transitive: Include transitive dependencies

    Returns:
        List of dependency records
    """
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            pd.*,
            p1.name as source_project_name,
            p1.status as source_project_status,
            p2.name as target_project_name,
            p2.status as target_project_status
        FROM project_dependencies pd
        JOIN projects p1 ON pd.source_project_id = p1.id
        JOIN projects p2 ON pd.target_project_id = p2.id
        WHERE 1=1
    """
    params = []

    if project_id is not None:
        query += " AND (pd.source_project_id = ? OR pd.target_project_id = ?)"
        params.extend([project_id, project_id])

    if dependency_type:
        query += " AND pd.dependency_type = ?"
        params.append(dependency_type)

    query += " ORDER BY pd.source_project_id, pd.dependency_type"

    rows = conn.execute(query, params).fetchall()
    dependencies = [dict(row) for row in rows]

    if include_transitive and project_id:
        # Get transitive dependencies
        transitive = get_transitive_dependencies(conn, project_id)
        for dep in dependencies:
            dep["is_direct"] = True
        for t_dep in transitive:
            if not any(d["id"] == t_dep["id"] for d in dependencies):
                t_dep["is_direct"] = False
                dependencies.append(t_dep)

    return dependencies


def get_project_dependencies(conn, project_id: int, direction: str = "both") -> Dict:
    """Get all dependencies for a specific project.

    Args:
        conn: Database connection
        project_id: Project ID
        direction: 'outgoing' (this project depends on),
                   'incoming' (other projects depend on this),
                   or 'both'

    Returns:
        Dict with outgoing and incoming dependencies
    """
    conn.row_factory = sqlite3.Row

    result = {
        "project_id": project_id,
        "outgoing": [],
        "incoming": [],
        "blocking": [],
        "blocked_by": [],
    }

    if direction in ("outgoing", "both"):
        # Dependencies this project has on others
        rows = conn.execute(
            """
            SELECT pd.*, p.name as target_name, p.status as target_status
            FROM project_dependencies pd
            JOIN projects p ON pd.target_project_id = p.id
            WHERE pd.source_project_id = ?
            ORDER BY pd.dependency_type, p.name
        """,
            (project_id,),
        ).fetchall()

        for row in rows:
            dep = dict(row)
            result["outgoing"].append(dep)
            if DEPENDENCY_TYPES.get(dep["dependency_type"], {}).get("blocking"):
                if dep["dependency_type"] in ("depends_on", "blocked_by"):
                    result["blocked_by"].append(dep)

    if direction in ("incoming", "both"):
        # Projects that depend on this one
        rows = conn.execute(
            """
            SELECT pd.*, p.name as source_name, p.status as source_status
            FROM project_dependencies pd
            JOIN projects p ON pd.source_project_id = p.id
            WHERE pd.target_project_id = ?
            ORDER BY pd.dependency_type, p.name
        """,
            (project_id,),
        ).fetchall()

        for row in rows:
            dep = dict(row)
            result["incoming"].append(dep)
            if DEPENDENCY_TYPES.get(dep["dependency_type"], {}).get("blocking"):
                if dep["dependency_type"] in ("depends_on", "blocked_by"):
                    result["blocking"].append(dep)

    result["outgoing_count"] = len(result["outgoing"])
    result["incoming_count"] = len(result["incoming"])
    result["is_blocked"] = len(result["blocked_by"]) > 0
    result["is_blocking"] = len(result["blocking"]) > 0

    return result


def add_dependency(
    conn,
    source_project_id: int,
    target_project_id: int,
    dependency_type: str,
    description: str = None,
    created_by: str = None,
    metadata: Dict = None,
) -> Dict:
    """Add a dependency between two projects.

    Args:
        conn: Database connection
        source_project_id: Source project ID
        target_project_id: Target project ID
        dependency_type: Type of dependency
        description: Optional description
        created_by: User creating the dependency
        metadata: Additional metadata

    Returns:
        Created dependency record
    """
    # Validate dependency type
    if dependency_type not in DEPENDENCY_TYPES:
        raise ValueError(f"Invalid dependency type: {dependency_type}")

    # Prevent self-dependency
    if source_project_id == target_project_id:
        raise ValueError("A project cannot depend on itself")

    # Verify both projects exist
    source = conn.execute(
        "SELECT id, name FROM projects WHERE id = ?", (source_project_id,)
    ).fetchone()
    target = conn.execute(
        "SELECT id, name FROM projects WHERE id = ?", (target_project_id,)
    ).fetchone()

    if not source:
        raise ValueError(f"Source project {source_project_id} not found")
    if not target:
        raise ValueError(f"Target project {target_project_id} not found")

    # Check for existing dependency
    existing = conn.execute(
        """
        SELECT id FROM project_dependencies
        WHERE source_project_id = ? AND target_project_id = ? AND dependency_type = ?
    """,
        (source_project_id, target_project_id, dependency_type),
    ).fetchone()

    if existing:
        raise ValueError("This dependency already exists")

    # Check for circular dependencies (for blocking types)
    if DEPENDENCY_TYPES[dependency_type].get("blocking"):
        if would_create_cycle(conn, source_project_id, target_project_id, dependency_type):
            raise ValueError("This dependency would create a circular dependency")

    # Insert the dependency
    cursor = conn.execute(
        """
        INSERT INTO project_dependencies
        (source_project_id, target_project_id, dependency_type, description, created_by, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            source_project_id,
            target_project_id,
            dependency_type,
            description,
            created_by,
            json.dumps(metadata) if metadata else None,
        ),
    )

    return {
        "id": cursor.lastrowid,
        "source_project_id": source_project_id,
        "source_project_name": source["name"],
        "target_project_id": target_project_id,
        "target_project_name": target["name"],
        "dependency_type": dependency_type,
        "description": description,
    }


def remove_dependency(conn, dependency_id: int) -> bool:
    """Remove a dependency by ID.

    Args:
        conn: Database connection
        dependency_id: Dependency ID

    Returns:
        True if removed
    """
    result = conn.execute("DELETE FROM project_dependencies WHERE id = ?", (dependency_id,))
    return result.rowcount > 0


def remove_dependency_by_projects(
    conn, source_project_id: int, target_project_id: int, dependency_type: str = None
) -> int:
    """Remove dependencies between two projects.

    Args:
        conn: Database connection
        source_project_id: Source project ID
        target_project_id: Target project ID
        dependency_type: Optional specific type to remove

    Returns:
        Number of dependencies removed
    """
    if dependency_type:
        result = conn.execute(
            """
            DELETE FROM project_dependencies
            WHERE source_project_id = ? AND target_project_id = ? AND dependency_type = ?
        """,
            (source_project_id, target_project_id, dependency_type),
        )
    else:
        result = conn.execute(
            """
            DELETE FROM project_dependencies
            WHERE source_project_id = ? AND target_project_id = ?
        """,
            (source_project_id, target_project_id),
        )

    return result.rowcount


def update_dependency(
    conn, dependency_id: int, description: str = None, metadata: Dict = None
) -> bool:
    """Update a dependency.

    Args:
        conn: Database connection
        dependency_id: Dependency ID
        description: New description
        metadata: New metadata

    Returns:
        True if updated
    """
    updates = []
    params = []

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(dependency_id)

    result = conn.execute(
        f"UPDATE project_dependencies SET {', '.join(updates)} WHERE id = ?", params
    )
    return result.rowcount > 0


def would_create_cycle(conn, source_id: int, target_id: int, dependency_type: str) -> bool:
    """Check if adding a dependency would create a cycle.

    Args:
        conn: Database connection
        source_id: Source project ID
        target_id: Target project ID
        dependency_type: Dependency type

    Returns:
        True if it would create a cycle
    """
    # Build adjacency list of existing dependencies
    rows = conn.execute(
        """
        SELECT source_project_id, target_project_id
        FROM project_dependencies
        WHERE dependency_type IN ('depends_on', 'blocked_by', 'requires')
    """
    ).fetchall()

    graph = defaultdict(set)
    for row in rows:
        graph[row[0]].add(row[1])

    # Add the proposed edge
    graph[source_id].add(target_id)

    # Check for cycle using DFS
    visited = set()
    rec_stack = set()

    def has_cycle(node):
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph[node]:
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    # Check starting from source
    return has_cycle(source_id)


def get_transitive_dependencies(
    conn, project_id: int, dependency_types: List[str] = None
) -> List[Dict]:
    """Get all transitive dependencies for a project.

    Args:
        conn: Database connection
        project_id: Project ID
        dependency_types: Types to follow (default: blocking types)

    Returns:
        List of transitive dependencies
    """
    if dependency_types is None:
        dependency_types = ["depends_on", "blocked_by"]

    conn.row_factory = sqlite3.Row

    visited = set()
    result = []
    queue = deque([project_id])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        placeholders = ",".join("?" * len(dependency_types))
        rows = conn.execute(
            f"""
            SELECT pd.*, p.name as target_name, p.status as target_status
            FROM project_dependencies pd
            JOIN projects p ON pd.target_project_id = p.id
            WHERE pd.source_project_id = ?
            AND pd.dependency_type IN ({placeholders})
        """,
            [current] + dependency_types,
        ).fetchall()

        for row in rows:
            dep = dict(row)
            if dep["target_project_id"] not in visited:
                dep["transitive_from"] = current if current != project_id else None
                result.append(dep)
                queue.append(dep["target_project_id"])

    return result


def get_dependency_tree(
    conn, project_id: int, direction: str = "downstream", max_depth: int = 10
) -> Dict:
    """Get dependency tree for a project.

    Args:
        conn: Database connection
        project_id: Root project ID
        direction: 'downstream' (what this depends on) or 'upstream' (what depends on this)
        max_depth: Maximum depth to traverse

    Returns:
        Tree structure of dependencies
    """
    conn.row_factory = sqlite3.Row

    # Get project info
    project = conn.execute(
        "SELECT id, name, status FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    if not project:
        return None

    def build_tree(pid, depth):
        if depth > max_depth:
            return {"truncated": True}

        node = {"project_id": pid, "depth": depth, "children": []}

        # Get project info
        p = conn.execute("SELECT name, status FROM projects WHERE id = ?", (pid,)).fetchone()
        if p:
            node["name"] = p["name"]
            node["status"] = p["status"]

        # Get dependencies based on direction
        if direction == "downstream":
            rows = conn.execute(
                """
                SELECT pd.target_project_id as child_id, pd.dependency_type,
                       p.name as child_name, p.status as child_status
                FROM project_dependencies pd
                JOIN projects p ON pd.target_project_id = p.id
                WHERE pd.source_project_id = ?
            """,
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT pd.source_project_id as child_id, pd.dependency_type,
                       p.name as child_name, p.status as child_status
                FROM project_dependencies pd
                JOIN projects p ON pd.source_project_id = p.id
                WHERE pd.target_project_id = ?
            """,
                (pid,),
            ).fetchall()

        for row in rows:
            child = build_tree(row["child_id"], depth + 1)
            child["dependency_type"] = row["dependency_type"]
            node["children"].append(child)

        return node

    tree = build_tree(project_id, 0)
    tree["direction"] = direction
    tree["max_depth"] = max_depth

    return tree


def get_impact_analysis(conn, project_id: int) -> Dict:
    """Analyze the impact of changes to a project.

    Args:
        conn: Database connection
        project_id: Project ID

    Returns:
        Impact analysis including affected projects
    """
    conn.row_factory = sqlite3.Row

    # Get project info
    project = conn.execute(
        "SELECT id, name, status FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    if not project:
        return None

    # Get all projects that depend on this one (upstream)
    upstream = get_dependency_tree(conn, project_id, "upstream", max_depth=5)

    # Count affected projects
    def count_nodes(node):
        count = 1
        for child in node.get("children", []):
            count += count_nodes(child)
        return count

    affected_count = count_nodes(upstream) - 1  # Exclude the root

    # Get direct dependents
    direct_dependents = conn.execute(
        """
        SELECT p.id, p.name, p.status, pd.dependency_type
        FROM project_dependencies pd
        JOIN projects p ON pd.source_project_id = p.id
        WHERE pd.target_project_id = ?
        AND pd.dependency_type IN ('depends_on', 'blocked_by')
    """,
        (project_id,),
    ).fetchall()

    # Get blocking status
    blocking_projects = [dict(d) for d in direct_dependents]

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "project_status": project["status"],
        "affected_projects_count": affected_count,
        "direct_dependents": blocking_projects,
        "direct_dependents_count": len(blocking_projects),
        "impact_tree": upstream,
        "risk_level": "high" if affected_count > 5 else "medium" if affected_count > 0 else "low",
    }


def get_dependency_stats(conn) -> Dict:
    """Get statistics about project dependencies.

    Returns:
        Dict with dependency statistics
    """
    conn.row_factory = sqlite3.Row

    stats = {
        "total_dependencies": 0,
        "by_type": {},
        "projects_with_dependencies": 0,
        "projects_depended_on": 0,
        "most_dependencies": [],
        "most_dependents": [],
    }

    # Total count
    row = conn.execute("SELECT COUNT(*) as count FROM project_dependencies").fetchone()
    stats["total_dependencies"] = row["count"]

    # By type
    rows = conn.execute(
        """
        SELECT dependency_type, COUNT(*) as count
        FROM project_dependencies
        GROUP BY dependency_type
    """
    ).fetchall()
    for row in rows:
        stats["by_type"][row["dependency_type"]] = row["count"]

    # Projects with outgoing dependencies
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT source_project_id) as count
        FROM project_dependencies
    """
    ).fetchone()
    stats["projects_with_dependencies"] = row["count"]

    # Projects with incoming dependencies
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT target_project_id) as count
        FROM project_dependencies
    """
    ).fetchone()
    stats["projects_depended_on"] = row["count"]

    # Most dependencies (outgoing)
    rows = conn.execute(
        """
        SELECT p.id, p.name, COUNT(*) as dep_count
        FROM project_dependencies pd
        JOIN projects p ON pd.source_project_id = p.id
        GROUP BY pd.source_project_id
        ORDER BY dep_count DESC
        LIMIT 5
    """
    ).fetchall()
    stats["most_dependencies"] = [dict(r) for r in rows]

    # Most dependents (incoming)
    rows = conn.execute(
        """
        SELECT p.id, p.name, COUNT(*) as dep_count
        FROM project_dependencies pd
        JOIN projects p ON pd.target_project_id = p.id
        GROUP BY pd.target_project_id
        ORDER BY dep_count DESC
        LIMIT 5
    """
    ).fetchall()
    stats["most_dependents"] = [dict(r) for r in rows]

    return stats


def validate_all_dependencies(conn) -> Dict:
    """Validate all dependencies for issues.

    Returns:
        Dict with validation results
    """
    conn.row_factory = sqlite3.Row

    issues = []

    # Check for orphaned dependencies (missing projects)
    rows = conn.execute(
        """
        SELECT pd.id, pd.source_project_id, pd.target_project_id
        FROM project_dependencies pd
        LEFT JOIN projects p1 ON pd.source_project_id = p1.id
        LEFT JOIN projects p2 ON pd.target_project_id = p2.id
        WHERE p1.id IS NULL OR p2.id IS NULL
    """
    ).fetchall()

    for row in rows:
        issues.append(
            {
                "type": "orphaned",
                "dependency_id": row["id"],
                "message": "Dependency references non-existent project",
            }
        )

    # Check for circular dependencies
    # Build graph
    rows = conn.execute(
        """
        SELECT source_project_id, target_project_id
        FROM project_dependencies
        WHERE dependency_type IN ('depends_on', 'blocked_by')
    """
    ).fetchall()

    graph = defaultdict(set)
    for row in rows:
        graph[row[0]].add(row[1])

    # Find cycles using DFS
    def find_cycles():
        cycles = []
        visited = set()
        rec_stack = []

        def dfs(node, path):
            visited.add(node)
            path.append(node)

            for neighbor in graph[node]:
                if neighbor in path:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    dfs(neighbor, path.copy())

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    cycles = find_cycles()
    for cycle in cycles:
        issues.append(
            {
                "type": "circular",
                "projects": cycle,
                "message": f'Circular dependency detected: {" -> ".join(map(str, cycle))}',
            }
        )

    return {"valid": len(issues) == 0, "issues": issues, "issue_count": len(issues)}
