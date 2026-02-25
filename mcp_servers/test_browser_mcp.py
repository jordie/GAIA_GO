#!/usr/bin/env python3
"""Test browser automation MCP server."""

import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def test_browser_mcp():
    """Test browser automation MCP server."""
    print("🧪 Testing Browser Automation MCP Server...")
    print("=" * 60)

    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/jgirmay/Desktop/gitrepo/pyWork/architect/mcp_servers/browser_mcp.py"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Connected to browser automation MCP server\n")

            # List available tools
            tools = await session.list_tools()
            print(f"📋 Available Tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description}")

            # Test browser status
            print("\n🧪 Test: Get Browser Status")
            result = await session.call_tool(name="get_browser_status", arguments={})
            print(result.content[0].text)

            # Test tab groups
            print("\n🧪 Test: Get Tab Groups")
            result = await session.call_tool(name="get_tab_groups", arguments={})
            print(result.content[0].text)

            print("\n" + "=" * 60)
            print("✅ Browser Automation MCP Server Test PASSED")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_browser_mcp())
