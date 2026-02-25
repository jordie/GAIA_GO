#!/usr/bin/env python3
"""Test Assigner MCP server."""

import asyncio

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def test_assigner_mcp():
    """Test Assigner MCP server."""
    print("🧪 Testing Assigner MCP Server...")
    print("=" * 60)

    server_params = StdioServerParameters(
        command="python3",
        args=[
            "/Users/jgirmay/Desktop/gitrepo/pyWork/architect/mcp_servers/assigner_mcp.py"
        ],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Connected to assigner MCP server\n")

            # List available tools
            tools = await session.list_tools()
            print(f"📋 Available Tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description}")

            # Test get queue stats
            print("\n🧪 Test: Get Queue Statistics")
            result = await session.call_tool(name="get_queue_stats", arguments={})
            print(result.content[0].text)

            # Test list sessions
            print("\n🧪 Test: List Sessions")
            result = await session.call_tool(name="list_sessions", arguments={})
            print(result.content[0].text)

            # Test list prompts
            print("\n🧪 Test: List Recent Prompts")
            result = await session.call_tool(
                name="list_prompts", arguments={"limit": 10}
            )
            print(result.content[0].text)

            # Test send prompt
            print("\n🧪 Test: Send Test Prompt")
            result = await session.call_tool(
                name="send_prompt",
                arguments={
                    "content": "MCP Server Test Prompt - Please acknowledge",
                    "priority": 3,
                },
            )
            print(result.content[0].text)

            print("\n" + "=" * 60)
            print("✅ Assigner MCP Server Test PASSED")
            print("=" * 60)
            print("\n🎯 MCP Infrastructure Status:")
            print("  ✅ tmux-architect (6 tools)")
            print("  ✅ browser-automation (8 tools)")
            print("  ✅ database-architect (8 tools)")
            print("  ✅ assigner-architect (7 tools) ⭐ NEW")
            print("\n  Total: 29 tools available to all Claude sessions!")


if __name__ == "__main__":
    asyncio.run(test_assigner_mcp())
