#!/usr/bin/env python3
"""
Hello World MCP Server - Proof of Concept
Simple MCP server to test basic functionality.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Create MCP server instance
app = Server("hello-architect")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="greet",
            description="Say hello to someone",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of person to greet"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_system_info",
            description="Get Architect system information",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "greet":
        person_name = arguments.get("name", "World")
        message = f"Hello, {person_name}! This is the Architect MCP server."
        return [TextContent(type="text", text=message)]

    elif name == "get_system_info":
        info = """
🏗️ Architect Multi-Agent System

Status: MCP Integration Testing
Sessions: 8 (High-Level, 2 Managers, 5 Workers)
Tools: Google Docs, tmux, Browser Automation, Database
Architecture: 3-Tier Hierarchy
MCP Status: Phase 1 - Proof of Concept ✅
"""
        return [TextContent(type="text", text=info.strip())]

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
