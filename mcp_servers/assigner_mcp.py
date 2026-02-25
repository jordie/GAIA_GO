#!/usr/bin/env python3
"""
Assigner MCP Server - Production Server
Provides prompt routing and task delegation for multi-agent system.

Wraps the existing assigner_worker.py system with MCP interface.

Tools:
- send_prompt: Queue a prompt for assignment to a Claude session
- list_prompts: List prompts with filters (status, limit)
- get_prompt: Get detailed prompt information
- list_sessions: List available Claude sessions
- retry_prompt: Retry a failed prompt
- cancel_prompt: Cancel a pending prompt
- get_queue_stats: Get queue statistics and health
"""

import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Server("assigner-architect")

# Database path
ASSIGNER_DB = Path(
    "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/data/assigner/assigner.db"
)


def execute_query(query: str, params: tuple = ()) -> tuple[List[Dict], List[str]]:
    """Execute query and return results with column names."""
    try:
        conn = sqlite3.connect(str(ASSIGNER_DB))
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
    """List available assigner tools."""
    return [
        Tool(
            name="send_prompt",
            description="Queue a prompt for assignment to a Claude session",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Prompt content to send",
                    },
                    "priority": {
                        "type": "number",
                        "description": "Priority (0-10, higher = more urgent, default: 5)",
                    },
                    "target_session": {
                        "type": "string",
                        "description": "Target session name (optional, auto-assign if not specified)",
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Timeout in minutes (default: 30)",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="list_prompts",
            description="List prompts with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": [
                            "pending",
                            "assigned",
                            "in_progress",
                            "completed",
                            "failed",
                            "cancelled",
                        ],
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max results (default: 20)",
                    },
                },
            },
        ),
        Tool(
            name="get_prompt",
            description="Get detailed information about a specific prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "number", "description": "Prompt ID"}
                },
                "required": ["prompt_id"],
            },
        ),
        Tool(
            name="list_sessions",
            description="List available Claude sessions for prompt assignment",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="retry_prompt",
            description="Retry a failed prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "number", "description": "Prompt ID to retry"}
                },
                "required": ["prompt_id"],
            },
        ),
        Tool(
            name="cancel_prompt",
            description="Cancel a pending prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {
                        "type": "number",
                        "description": "Prompt ID to cancel",
                    }
                },
                "required": ["prompt_id"],
            },
        ),
        Tool(
            name="get_queue_stats",
            description="Get queue statistics and health metrics",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "send_prompt":
        content = arguments["content"]
        priority = arguments.get("priority", 5)
        target_session = arguments.get("target_session")
        timeout_minutes = arguments.get("timeout_minutes", 30)

        # Insert prompt into database
        query = """
            INSERT INTO prompts
            (content, priority, target_session, timeout_minutes, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', datetime('now'))
        """
        conn = sqlite3.connect(str(ASSIGNER_DB))
        cursor = conn.cursor()
        cursor.execute(query, (content, priority, target_session, timeout_minutes))
        prompt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return [
            TextContent(
                type="text",
                text=(
                    f"✅ Prompt queued successfully\n\n"
                    f"Prompt ID: {prompt_id}\n"
                    f"Priority: {priority}\n"
                    f"Target: {target_session or 'auto-assign'}\n"
                    f"Timeout: {timeout_minutes} minutes\n"
                    f"Status: pending\n\n"
                    f"The assigner worker will process this prompt."
                ),
            )
        ]

    elif name == "list_prompts":
        status_filter = arguments.get("status")
        limit = arguments.get("limit", 20)

        query = (
            "SELECT id, status, target_session, priority, "
            "substr(content, 1, 60) as content_preview, created_at "
            "FROM prompts WHERE 1=1"
        )
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results, columns = execute_query(query, tuple(params))
        table = format_results_as_table(results, columns)

        return [
            TextContent(
                type="text", text=f"📋 Prompts ({len(results)}):\n\n{table}"
            )
        ]

    elif name == "get_prompt":
        prompt_id = arguments["prompt_id"]

        query = "SELECT * FROM prompts WHERE id = ?"
        results, _ = execute_query(query, (prompt_id,))

        if not results:
            return [
                TextContent(type="text", text=f"❌ Prompt {prompt_id} not found")
            ]

        prompt = results[0]
        output = f"""📝 Prompt #{prompt['id']}

Status: {prompt['status']}
Priority: {prompt['priority']}
Target Session: {prompt['target_session'] or 'auto-assign'}
Assigned To: {prompt.get('assigned_session', 'N/A')}

Content:
{prompt['content']}

Timestamps:
- Created: {prompt['created_at']}
- Assigned: {prompt.get('assigned_at', 'N/A')}
- Completed: {prompt.get('completed_at', 'N/A')}

Retry Count: {prompt.get('retry_count', 0)}
Timeout: {prompt.get('timeout_minutes', 30)} minutes
"""
        return [TextContent(type="text", text=output)]

    elif name == "list_sessions":
        query = (
            "SELECT name, status, last_activity, is_claude, provider "
            "FROM sessions ORDER BY name"
        )
        results, columns = execute_query(query)
        table = format_results_as_table(results, columns)

        return [
            TextContent(
                type="text",
                text=f"🖥️  Available Sessions ({len(results)}):\n\n{table}",
            )
        ]

    elif name == "retry_prompt":
        prompt_id = arguments["prompt_id"]

        # Update prompt status to pending and increment retry count
        query = """
            UPDATE prompts
            SET status = 'pending',
                assigned_session = NULL,
                assigned_at = NULL,
                retry_count = retry_count + 1
            WHERE id = ?
        """
        conn = sqlite3.connect(str(ASSIGNER_DB))
        cursor = conn.cursor()
        cursor.execute(query, (prompt_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected == 0:
            return [
                TextContent(type="text", text=f"❌ Prompt {prompt_id} not found")
            ]

        return [
            TextContent(
                type="text",
                text=(
                    f"✅ Prompt {prompt_id} reset to pending\n\n"
                    f"The assigner worker will retry this prompt."
                ),
            )
        ]

    elif name == "cancel_prompt":
        prompt_id = arguments["prompt_id"]

        query = "UPDATE prompts SET status = 'cancelled' WHERE id = ? AND status = 'pending'"
        conn = sqlite3.connect(str(ASSIGNER_DB))
        cursor = conn.cursor()
        cursor.execute(query, (prompt_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected == 0:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"❌ Prompt {prompt_id} not found or not pending\n"
                        f"Only pending prompts can be cancelled."
                    ),
                )
            ]

        return [
            TextContent(
                type="text",
                text=f"✅ Prompt {prompt_id} cancelled successfully",
            )
        ]

    elif name == "get_queue_stats":
        # Get stats by status
        query = "SELECT status, COUNT(*) as count FROM prompts GROUP BY status"
        results, _ = execute_query(query)
        stats_by_status = {r["status"]: r["count"] for r in results}

        # Get session stats
        query = (
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN is_claude = 1 THEN 1 ELSE 0 END) as claude_sessions "
            "FROM sessions"
        )
        results, _ = execute_query(query)
        session_stats = results[0] if results else {"total": 0, "claude_sessions": 0}

        # Get recent activity
        query = """
            SELECT COUNT(*) as count
            FROM prompts
            WHERE created_at > datetime('now', '-1 hour')
        """
        results, _ = execute_query(query)
        recent_count = results[0]["count"] if results else 0

        output = f"""📊 Queue Statistics

Prompts by Status:
"""
        for status in ["pending", "assigned", "in_progress", "completed", "failed", "cancelled"]:
            count = stats_by_status.get(status, 0)
            output += f"  • {status}: {count}\n"

        output += f"""
Sessions:
  • Total tracked: {session_stats['total']}
  • Claude sessions: {session_stats['claude_sessions']}

Activity:
  • Prompts in last hour: {recent_count}

Health: {'✅ OK' if session_stats['total'] > 0 else '⚠️ No tracked sessions'}
"""
        return [TextContent(type="text", text=output)]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream, app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
