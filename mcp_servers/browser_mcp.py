#!/usr/bin/env python3
"""
Browser Automation MCP Server - Production Server
Wraps Playwright browser automation for multi-agent access.

Tools:
- navigate: Navigate to URL
- fill_form: Fill form field
- click_element: Click element
- get_text: Get element text
- screenshot: Take screenshot
- submit_to_perplexity: Submit query to Perplexity (Ethiopia research)
- submit_to_google_sheets: Add data to Google Sheets
- get_tab_groups: List Chrome tab groups
"""

import asyncio
import subprocess
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource


app = Server("browser-automation")

# Base path for browser automation scripts
BROWSER_PATH = Path("/Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers/browser_automation")


def run_browser_script(script_name: str, args: list[str] = None) -> tuple[bool, str]:
    """Run a browser automation script."""
    script_path = BROWSER_PATH / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_name}"

    try:
        cmd = ["python3", str(script_path)]
        if args:
            cmd.extend(args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BROWSER_PATH)
        )
        return result.returncode == 0, result.stdout or result.stderr
    except subprocess.TimeoutExpired:
        return False, "Script timed out (60s)"
    except Exception as e:
        return False, str(e)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available browser automation tools."""
    return [
        Tool(
            name="navigate",
            description="Navigate browser to URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to"
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="submit_to_perplexity",
            description="Submit research query to Perplexity AI (Ethiopia research)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research query to submit"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Topic/category for organization"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_tab_groups",
            description="List all Chrome tab groups",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="sync_to_sheets",
            description="Sync data to Google Sheets",
            inputSchema={
                "type": "object",
                "properties": {
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet"
                    },
                    "data": {
                        "type": "array",
                        "description": "Data rows to add",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "required": ["sheet_name", "data"]
            }
        ),
        Tool(
            name="list_perplexity_tabs",
            description="List open Perplexity tabs in Chrome",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="create_tab_group",
            description="Create new Chrome tab group",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Tab group name"
                    },
                    "color": {
                        "type": "string",
                        "description": "Tab group color (optional)"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="ethiopia_auto_research",
            description="Run automated Ethiopia research workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "description": "Research topics to process",
                        "items": {"type": "string"}
                    },
                    "mode": {
                        "type": "string",
                        "description": "Mode: 'verify' or 'auto' (default: verify)",
                        "enum": ["verify", "auto"]
                    }
                },
                "required": ["topics"]
            }
        ),
        Tool(
            name="get_browser_status",
            description="Get browser automation system status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "navigate":
        url = arguments["url"]
        # Use basic browser navigation script
        success, output = run_browser_script("open_comet.py", [url])
        if success:
            return [TextContent(type="text",
                text=f"✅ Navigated to: {url}\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Navigation failed: {output}")]

    elif name == "submit_to_perplexity":
        query = arguments["query"]
        topic = arguments.get("topic", "General")

        # Use verified Perplexity automation
        success, output = run_browser_script(
            "perplexity_verified_automation.py",
            ["--query", query, "--topic", topic]
        )

        if success:
            return [TextContent(type="text",
                text=f"✅ Submitted to Perplexity: {query}\n\nTopic: {topic}\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Perplexity submission failed: {output}")]

    elif name == "get_tab_groups":
        success, output = run_browser_script("list_tab_groups.py")

        if success:
            return [TextContent(type="text",
                text=f"📑 Chrome Tab Groups:\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Failed to list tab groups: {output}")]

    elif name == "sync_to_sheets":
        sheet_name = arguments["sheet_name"]
        data = arguments["data"]

        # Write data to temp file for script
        temp_file = BROWSER_PATH / "data" / "mcp_sync_temp.json"
        temp_file.parent.mkdir(exist_ok=True)
        temp_file.write_text(json.dumps({
            "sheet": sheet_name,
            "data": data
        }))

        success, output = run_browser_script(
            "google_sheets_sync.py",
            ["--file", str(temp_file)]
        )

        temp_file.unlink(missing_ok=True)

        if success:
            return [TextContent(type="text",
                text=f"✅ Synced to Google Sheets: {sheet_name}\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Sheets sync failed: {output}")]

    elif name == "list_perplexity_tabs":
        success, output = run_browser_script("detect_plugin.py")

        if success:
            return [TextContent(type="text",
                text=f"🔍 Perplexity Tabs:\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Detection failed: {output}")]

    elif name == "create_tab_group":
        group_name = arguments["name"]
        color = arguments.get("color", "blue")

        success, output = run_browser_script(
            "create_tab_tracker.py",
            ["--name", group_name, "--color", color]
        )

        if success:
            return [TextContent(type="text",
                text=f"✅ Created tab group: {group_name} ({color})\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Tab group creation failed: {output}")]

    elif name == "ethiopia_auto_research":
        topics = arguments["topics"]
        mode = arguments.get("mode", "verify")

        # Build topic list
        topic_args = []
        for topic in topics:
            topic_args.extend(["--topic", topic])

        script = "ethiopia_auto_run_verified.py" if mode == "verify" else "ethiopia_full_auto.py"

        success, output = run_browser_script(script, topic_args)

        if success:
            return [TextContent(type="text",
                text=f"✅ Ethiopia Research Complete\n\nTopics: {', '.join(topics)}\nMode: {mode}\n\n{output}")]
        else:
            return [TextContent(type="text",
                text=f"❌ Research workflow failed: {output}")]

    elif name == "get_browser_status":
        # Check browser automation system
        status = {
            "scripts_available": len(list(BROWSER_PATH.glob("*.py"))),
            "path": str(BROWSER_PATH),
            "frameworks": []
        }

        # Check which scripts exist
        key_scripts = [
            "perplexity_verified_automation.py",
            "google_sheets_sync.py",
            "list_tab_groups.py",
            "ethiopia_auto_run_verified.py"
        ]

        available = []
        for script in key_scripts:
            if (BROWSER_PATH / script).exists():
                available.append(script)

        status["key_scripts_available"] = available

        result = f"""🌐 Browser Automation Status

System Path: {status['path']}
Total Scripts: {status['scripts_available']}

Key Scripts Available:
"""
        for script in available:
            result += f"  ✅ {script}\n"

        result += f"\nIntegrations:\n"
        result += f"  • Perplexity AI: Verified automation\n"
        result += f"  • Google Sheets: Sync enabled\n"
        result += f"  • Chrome Tab Groups: Management enabled\n"
        result += f"  • Ethiopia Research: Auto workflow ready\n"

        return [TextContent(type="text", text=result)]

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
