"""
Task Dependencies Visualization Service

Provides graph analysis and visualization data for task dependencies.
"""

from typing import Dict, List, Optional, Set, Tuple


def build_dependency_graph(tasks: List[Dict], dependencies: List[Dict]) -> Dict:
    """Build a graph structure from tasks and dependencies.

    Args:
        tasks: List of task dicts with 'id', 'task_type', 'status', etc.
        dependencies: List of dependency dicts with 'task_id', 'depends_on_id'

    Returns:
        Dict with nodes, edges, and computed metrics
    """
    task_ids = {t["id"] for t in tasks}

    # Build edges list
    edges = [
        {
            "id": d.get("id"),
            "task_id": d["task_id"],
            "depends_on_id": d["depends_on_id"],
            "dependency_type": d.get("dependency_type", "blocks"),
            "created_at": d.get("created_at"),
        }
        for d in dependencies
        if d["task_id"] in task_ids and d["depends_on_id"] in task_ids
    ]

    # Compute in/out degrees
    in_degree = {}
    out_degree = {}
    for edge in edges:
        out_degree[edge["depends_on_id"]] = out_degree.get(edge["depends_on_id"], 0) + 1
        in_degree[edge["task_id"]] = in_degree.get(edge["task_id"], 0) + 1

    # Build nodes with computed fields
    nodes = []
    for t in tasks:
        node = dict(t)
        node["in_degree"] = in_degree.get(t["id"], 0)
        node["out_degree"] = out_degree.get(t["id"], 0)
        nodes.append(node)

    # Find root and leaf nodes
    root_nodes = [n["id"] for n in nodes if n["in_degree"] == 0]
    leaf_nodes = [n["id"] for n in nodes if n["out_degree"] == 0]

    return {
        "nodes": nodes,
        "edges": edges,
        "root_nodes": root_nodes,
        "leaf_nodes": leaf_nodes,
        "in_degree": in_degree,
        "out_degree": out_degree,
    }


def detect_cycles(nodes: List[Dict], edges: List[Dict]) -> List[List[int]]:
    """Detect cycles in the dependency graph using DFS.

    Args:
        nodes: List of node dicts with 'id'
        edges: List of edge dicts with 'task_id', 'depends_on_id'

    Returns:
        List of cycles, each cycle is a list of task IDs
    """
    cycles = []
    visited = set()
    rec_stack = set()

    # Build adjacency: task_id -> depends_on_id (reverse direction for cycle detection)
    adj = {}
    for edge in edges:
        if edge["task_id"] not in adj:
            adj[edge["task_id"]] = []
        adj[edge["task_id"]].append(edge["depends_on_id"])

    def dfs(node_id: int, path: List[int]):
        visited.add(node_id)
        rec_stack.add(node_id)
        path.append(node_id)

        for next_id in adj.get(node_id, []):
            if next_id in rec_stack:
                # Found a cycle
                cycle_start = path.index(next_id)
                cycles.append(path[cycle_start:] + [next_id])
            elif next_id not in visited:
                dfs(next_id, path.copy())

        rec_stack.discard(node_id)

    for node in nodes:
        if node["id"] not in visited:
            dfs(node["id"], [])

    return cycles


def compute_levels(nodes: List[Dict], edges: List[Dict], root_nodes: List[int]) -> Dict[int, int]:
    """Compute hierarchical levels for each node (distance from roots).

    Args:
        nodes: List of node dicts
        edges: List of edge dicts
        root_nodes: List of root node IDs

    Returns:
        Dict mapping node ID to level (0-indexed)
    """
    levels = {}

    if not root_nodes:
        return levels

    # Build adjacency: depends_on_id -> [task_ids]
    adj = {}
    for edge in edges:
        if edge["depends_on_id"] not in adj:
            adj[edge["depends_on_id"]] = []
        adj[edge["depends_on_id"]].append(edge["task_id"])

    # BFS from root nodes
    frontier = [(r, 0) for r in root_nodes]
    while frontier:
        node_id, level = frontier.pop(0)
        if node_id in levels:
            continue
        levels[node_id] = level
        for next_id in adj.get(node_id, []):
            frontier.append((next_id, level + 1))

    return levels


def find_critical_path(
    task_map: Dict[int, Dict], dependencies: List[Dict]
) -> Tuple[List[Dict], int, Optional[int]]:
    """Find the critical path (longest dependency chain).

    Args:
        task_map: Dict mapping task ID to task dict
        dependencies: List of dependency dicts

    Returns:
        Tuple of (critical_path tasks, path_length, end_task_id)
    """
    task_ids = set(task_map.keys())

    if not task_ids:
        return [], 0, None

    # Build adjacency list (depends_on_id -> [task_ids that depend on it])
    adj = {tid: [] for tid in task_ids}
    in_degree = {tid: 0 for tid in task_ids}

    for d in dependencies:
        if d["task_id"] in task_ids and d["depends_on_id"] in task_ids:
            adj[d["depends_on_id"]].append(d["task_id"])
            in_degree[d["task_id"]] += 1

    # Find longest path using topological sort with DP
    # dist[node] = (longest_path_length, predecessor)
    dist = {tid: (0, None) for tid in task_ids}

    # Start with nodes that have no dependencies
    queue = [tid for tid in task_ids if in_degree[tid] == 0]

    while queue:
        node = queue.pop(0)

        for next_node in adj[node]:
            if dist[node][0] + 1 > dist[next_node][0]:
                dist[next_node] = (dist[node][0] + 1, node)

            in_degree[next_node] -= 1
            if in_degree[next_node] == 0:
                queue.append(next_node)

    # Find the node with the longest path
    end_node = max(task_ids, key=lambda x: dist[x][0])

    # Reconstruct the critical path
    critical_path = []
    current = end_node
    while current is not None:
        critical_path.append(task_map[current])
        current = dist[current][1]

    critical_path.reverse()

    return critical_path, len(critical_path), end_node


def build_adjacency_matrix(
    task_ids: List[int], dependencies: List[Dict]
) -> Tuple[List[List[int]], Dict[int, int]]:
    """Build an adjacency matrix for the dependency graph.

    Args:
        task_ids: List of task IDs (determines matrix order)
        dependencies: List of dependency dicts

    Returns:
        Tuple of (matrix, id_to_index mapping)
    """
    id_to_idx = {tid: i for i, tid in enumerate(task_ids)}
    size = len(task_ids)
    matrix = [[0] * size for _ in range(size)]

    for d in dependencies:
        from_idx = id_to_idx.get(d["depends_on_id"])
        to_idx = id_to_idx.get(d["task_id"])
        if from_idx is not None and to_idx is not None:
            matrix[from_idx][to_idx] = 1

    return matrix, id_to_idx


def get_subgraph(root_task_id: int, all_dependencies: List[Dict], max_depth: int = 10) -> Set[int]:
    """Get all task IDs connected to a root task up to max_depth.

    Args:
        root_task_id: Starting task ID
        all_dependencies: All dependencies in the system
        max_depth: Maximum traversal depth

    Returns:
        Set of connected task IDs
    """
    connected = set()
    frontier = {root_task_id}

    # Build bidirectional adjacency
    forward = {}  # depends_on_id -> [task_ids]
    backward = {}  # task_id -> [depends_on_ids]

    for d in all_dependencies:
        if d["depends_on_id"] not in forward:
            forward[d["depends_on_id"]] = []
        forward[d["depends_on_id"]].append(d["task_id"])

        if d["task_id"] not in backward:
            backward[d["task_id"]] = []
        backward[d["task_id"]].append(d["depends_on_id"])

    for _ in range(max_depth):
        if not frontier:
            break
        connected.update(frontier)
        next_frontier = set()

        for node_id in frontier:
            # Tasks that depend on this node
            next_frontier.update(forward.get(node_id, []))
            # Tasks this node depends on
            next_frontier.update(backward.get(node_id, []))

        frontier = next_frontier - connected

    return connected


def format_for_d3(nodes: List[Dict], edges: List[Dict]) -> Dict:
    """Format graph data for D3.js force-directed layout.

    Args:
        nodes: List of node dicts
        edges: List of edge dicts

    Returns:
        Dict with 'nodes' and 'links' arrays for D3
    """
    node_index = {n["id"]: i for i, n in enumerate(nodes)}

    links = [
        {
            "source": node_index.get(e["depends_on_id"], 0),
            "target": node_index.get(e["task_id"], 0),
            "type": e.get("dependency_type", "blocks"),
        }
        for e in edges
        if e["depends_on_id"] in node_index and e["task_id"] in node_index
    ]

    return {"nodes": nodes, "links": links}
