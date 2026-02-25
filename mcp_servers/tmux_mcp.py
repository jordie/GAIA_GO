#!/usr/bin/env python3
"""
tmux MCP Server - Production Server
Provides tmux session management tools for multi-agent orchestration.

Tools:
- list_sessions: List all tmux sessions
- send_command: Send command to session
- capture_output: Capture session output
- create_session: Create new session
- kill_session: Kill session
- session_status: Get session status
"""

import asyncio
import subprocess
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


app = Server("tmux-architect")


def run_tmux_command(args: list[str]) -> tuple[bool, str]:
    """Run tmux command and return success, output."""
    try:
        result = subprocess.run(
            ["tmux"] + args,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout or result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tmux tools."""
    return [
        Tool(
            name="list_sessions",
            description="List all tmux sessions with details",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="send_command",
            description="Send command to a tmux session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "string",
                        "description": "Session name or index"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to send"
                    }
                },
                "required": ["session", "command"]
            }
        ),
        Tool(
            name="capture_output",
            description="Capture output from tmux session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "string",
                        "description": "Session name or index"
                    },
                    "lines": {
                        "type": "number",
                        "description": "Number of lines to capture (default: 50)"
                    }
                },
                "required": ["session"]
            }
        ),
        Tool(
            name="create_session",
            description="Create new tmux session",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Session name"
                    },
                    "command": {
                        "type": "string",
                        "description": "Initial command to run (optional)"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="kill_session",
            description="Kill a tmux session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "string",
                        "description": "Session name or index"
                    }
                },
                "required": ["session"]
            }
        ),
        Tool(
            name="session_status",
            description="Get detailed status of a tmux session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "string",
                        "description": "Session name or index"
                    }
                },
                "required": ["session"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_sessions":
        success, output = run_tmux_command(["list-sessions", "-F",
            "#{session_name}|#{session_created}|#{session_windows}|#{session_attached}"])
        if not success:
            return [TextContent(type="text", text=f"Error: {output}")]

        sessions = []
        for line in output.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 4:
                    sessions.append({
                        "name": parts[0],
                        "created": parts[1],
                        "windows": parts[2],
                        "attached": parts[3] == "1"
                    })

        result = f"📊 tmux Sessions ({len(sessions)}):\n\n"
        for sess in sessions:
            status = "🟢 Attached" if sess["attached"] else "⚪ Detached"
            result += f"• {sess['name']}\n"
            result += f"  Status: {status}\n"
            result += f"  Windows: {sess['windows']}\n"
            result += f"  Created: {sess['created']}\n\n"

        return [TextContent(type="text", text=result.strip())]

    elif name == "send_command":
        session = arguments["session"]
        command = arguments["command"]

        success, output = run_tmux_command([
            "send-keys", "-t", session, command, "C-m"
        ])

        if success:
            return [TextContent(type="text",
                text=f"✅ Sent command to session '{session}':\n{command}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Failed to send command: {output}")]

    elif name == "capture_output":
        session = arguments["session"]
        lines = arguments.get("lines", 50)

        success, output = run_tmux_command([
            "capture-pane", "-t", session, "-p", "-S", f"-{lines}"
        ])

        if success:
            return [TextContent(type="text",
                text=f"📋 Output from session '{session}':\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Failed to capture output: {output}")]

    elif name == "create_session":
        session_name = arguments["name"]
        command = arguments.get("command")

        args = ["new-session", "-d", "-s", session_name]
        if command:
            args.append(command)

        success, output = run_tmux_command(args)

        if success:
            return [TextContent(type="text",
                text=f"✅ Created session '{session_name}'")]
        else:
            return [TextContent(type="text",
                text=f"❌ Failed to create session: {output}")]

    elif name == "kill_session":
        session = arguments["session"]

        success, output = run_tmux_command(["kill-session", "-t", session])

        if success:
            return [TextContent(type="text",
                text=f"✅ Killed session '{session}'")]
        else:
            return [TextContent(type="text",
                text=f"❌ Failed to kill session: {output}")]

    elif name == "session_status":
        session = arguments["session"]

        # Get detailed session info
        success, output = run_tmux_command([
            "list-panes", "-t", session, "-F",
            "#{pane_id}|#{pane_current_command}|#{pane_width}x#{pane_height}"
        ])

        if not success:
            return [TextContent(type="text", text=f"❌ Session not found: {output}")]

        result = f"📊 Session '{session}' Status:\n\n"
        for line in output.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    result += f"Pane: {parts[0]}\n"
                    result += f"  Command: {parts[1]}\n"
                    result += f"  Size: {parts[2]}\n\n"

        return [TextContent(type="text", text=result.strip())]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
