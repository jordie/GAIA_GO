#!/usr/bin/env python3
"""
Database MCP Server - Production Server
Provides unified database access for all Claude sessions.

Supports both architect.db (SQLite) and PostgreSQL.

Tools:
- query: Execute SQL query
- list_tables: List all tables
- describe_table: Get table schema
- get_projects: List all projects
- get_features: List features (with filters)
- get_bugs: List bugs (with filters)
- get_sessions: List tmux sessions from assigner.db
- get_tasks: List queued tasks
- create_project: Create new project
- update_feature: Update feature status
"""

import asyncio
import sqlite3
from pathlib import Path
from typing import Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("database-architect")

# Database paths
ARCHITECT_DB = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/architect.db")
ASSIGNER_DB = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/assigner/assigner.db")


def execute_query(db_path: Path, query: str, params: tuple = ()) -> tuple[List[Dict], List[str]]:
    """Execute query and return results with column names."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        results = [dict(row) for row in rows]
        conn.close()

        return results, columns
    except Exception as e:
        raise Exception(f"Query failed: {e}")


def format_results_as_table(results: List[Dict], columns: List[str]) -> str:
    """Format query results as ASCII table."""
    if not results:
        return "No results found."

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in results:
        for col in columns:
            val_str = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val_str))

    # Build table
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)

    lines = [header, separator]
    for row in results:
        line = " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        lines.append(line)

    return "\n".join(lines)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available database tools."""
    return [
        Tool(
            name="query",
            description="Execute SQL query on architect database",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL query to execute"},
                    "database": {
                        "type": "string",
                        "description": "Database: 'architect' or 'assigner' (default: architect)",
                        "enum": ["architect", "assigner"],
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="list_tables",
            description="List all tables in database",
            inputSchema={
                "type": "object",
                "properties": {"database": {"type": "string", "enum": ["architect", "assigner"]}},
            },
        ),
        Tool(
            name="describe_table",
            description="Get table schema (columns, types)",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "database": {"type": "string", "enum": ["architect", "assigner"]},
                },
                "required": ["table"],
            },
        ),
        Tool(
            name="get_projects",
            description="List all projects",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (optional)"}
                },
            },
        ),
        Tool(
            name="get_features",
            description="List features with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "number", "description": "Filter by project ID"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "number", "description": "Max results (default: 50)"},
                },
            },
        ),
        Tool(
            name="get_bugs",
            description="List bugs with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "number", "description": "Filter by project ID"},
                    "severity": {"type": "string", "description": "Filter by severity"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "number", "description": "Max results (default: 50)"},
                },
            },
        ),
        Tool(
            name="get_prompts",
            description="List queued prompts from assigner",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (pending, assigned, completed, failed)",
                        "enum": [
                            "pending",
                            "assigned",
                            "in_progress",
                            "completed",
                            "failed",
                            "cancelled",
                        ],
                    },
                    "limit": {"type": "number", "description": "Max results (default: 20)"},
                },
            },
        ),
        Tool(
            name="get_stats",
            description="Get dashboard statistics",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "query":
        sql = arguments["sql"]
        db_name = arguments.get("database", "architect")
        db_path = ASSIGNER_DB if db_name == "assigner" else ARCHITECT_DB

        if not db_path.exists():
            return [TextContent(type="text", text=f"❌ Database not found: {db_path}")]

        try:
            results, columns = execute_query(db_path, sql)
            table = format_results_as_table(results, columns)

            return [
                TextContent(type="text", text=f"📊 Query Results ({len(results)} rows):\n\n{table}")
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Query error: {e}")]

    elif name == "list_tables":
        db_name = arguments.get("database", "architect")
        db_path = ASSIGNER_DB if db_name == "assigner" else ARCHITECT_DB

        query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        results, _ = execute_query(db_path, query)

        tables = [r["name"] for r in results]
        return [
            TextContent(
                type="text",
                text=f"📋 Tables in {db_name} ({len(tables)}):\n\n"
                + "\n".join(f"  • {t}" for t in tables),
            )
        ]

    elif name == "describe_table":
        table = arguments["table"]
        db_name = arguments.get("database", "architect")
        db_path = ASSIGNER_DB if db_name == "assigner" else ARCHITECT_DB

        query = f"PRAGMA table_info({table})"
        results, _ = execute_query(db_path, query)

        if not results:
            return [TextContent(type="text", text=f"❌ Table not found: {table}")]

        schema = f"📊 Schema for table '{table}':\n\n"
        for col in results:
            schema += f"  • {col['name']}: {col['type']}"
            if col["notnull"]:
                schema += " NOT NULL"
            if col["pk"]:
                schema += " PRIMARY KEY"
            schema += "\n"

        return [TextContent(type="text", text=schema)]

    elif name == "get_projects":
        status_filter = arguments.get("status")

        query = "SELECT * FROM projects"
        params = ()
        if status_filter:
            query += " WHERE status = ?"
            params = (status_filter,)
        query += " ORDER BY created_at DESC"

        results, columns = execute_query(ARCHITECT_DB, query, params)
        table = format_results_as_table(results, columns)

        return [TextContent(type="text", text=f"📁 Projects ({len(results)}):\n\n{table}")]

    elif name == "get_features":
        project_id = arguments.get("project_id")
        status = arguments.get("status")
        limit = arguments.get("limit", 50)

        query = "SELECT id, project_id, name, status, priority, created_at FROM features WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results, columns = execute_query(ARCHITECT_DB, query, tuple(params))
        table = format_results_as_table(results, columns)

        return [TextContent(type="text", text=f"✨ Features ({len(results)}):\n\n{table}")]

    elif name == "get_bugs":
        project_id = arguments.get("project_id")
        severity = arguments.get("severity")
        status = arguments.get("status")
        limit = arguments.get("limit", 50)

        query = "SELECT id, project_id, title, severity, status, created_at FROM bugs WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results, columns = execute_query(ARCHITECT_DB, query, tuple(params))
        table = format_results_as_table(results, columns)

        return [TextContent(type="text", text=f"🐛 Bugs ({len(results)}):\n\n{table}")]

    elif name == "get_prompts":
        status_filter = arguments.get("status")
        limit = arguments.get("limit", 20)

        query = (
            "SELECT id, content, status, priority, target_session, created_at "
            "FROM prompts WHERE 1=1"
        )
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results, columns = execute_query(ASSIGNER_DB, query, tuple(params))
        table = format_results_as_table(results, columns)

        return [TextContent(type="text", text=f"📋 Prompts ({len(results)}):\n\n{table}")]

    elif name == "get_stats":
        stats = {}

        # Project count
        results, _ = execute_query(ARCHITECT_DB, "SELECT COUNT(*) as count FROM projects")
        stats["projects"] = results[0]["count"]

        # Feature count by status
        results, _ = execute_query(
            ARCHITECT_DB, "SELECT status, COUNT(*) as count FROM features GROUP BY status"
        )
        stats["features"] = {r["status"]: r["count"] for r in results}

        # Bug count by severity
        results, _ = execute_query(
            ARCHITECT_DB, "SELECT severity, COUNT(*) as count FROM bugs GROUP BY severity"
        )
        stats["bugs"] = {r["severity"]: r["count"] for r in results}

        # Prompt queue status
        results, _ = execute_query(
            ASSIGNER_DB, "SELECT status, COUNT(*) as count FROM prompts GROUP BY status"
        )
        stats["prompts"] = {r["status"]: r["count"] for r in results}

        output = f"""📊 Dashboard Statistics

Projects: {stats['projects']}

Features by Status:
"""
        for status, count in stats["features"].items():
            output += f"  • {status}: {count}\n"

        output += "\nBugs by Severity:\n"
        for severity, count in stats["bugs"].items():
            output += f"  • {severity}: {count}\n"

        output += "\nPrompt Queue:\n"
        for status, count in stats["prompts"].items():
            output += f"  • {status}: {count}\n"

        return [TextContent(type="text", text=output)]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
