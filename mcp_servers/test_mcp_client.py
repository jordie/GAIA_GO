#!/usr/bin/env python3
"""
MCP Client Test - Verify server connectivity
Tests the hello_mcp server.
"""

import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def test_mcp_server():
    """Test connecting to and using the MCP server."""
    print("🧪 Testing MCP Server Connection...")
    print("-" * 60)

    # Configure connection to our hello_mcp server
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/jgirmay/Desktop/gitrepo/pyWork/architect/mcp_servers/hello_mcp.py"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()
            print("✓ Connected to MCP server")

            # List available tools
            tools_result = await session.list_tools()
            print(f"\n📋 Available Tools ({len(tools_result.tools)}):")
            for tool in tools_result.tools:
                print(f"  • {tool.name}: {tool.description}")

            # Test 1: Call greet tool
            print("\n🧪 Test 1: Greet Tool")
            greet_result = await session.call_tool(
                name="greet",
                arguments={"name": "Architect Team"}
            )
            print(f"  Result: {greet_result.content[0].text}")

            # Test 2: Call get_system_info tool
            print("\n🧪 Test 2: System Info Tool")
            info_result = await session.call_tool(
                name="get_system_info",
                arguments={}
            )
            print(f"  Result:\n{info_result.content[0].text}")

            print("\n" + "=" * 60)
            print("✅ MCP Server Test PASSED")
            print("=" * 60)
            print("\nNext Steps:")
            print("1. ✅ MCP SDK installed and working")
            print("2. ✅ Basic MCP server functional")
            print("3. → Configure Claude to use MCP servers")
            print("4. → Build custom tmux MCP server")
            print("5. → Test Google Drive MCP server")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
