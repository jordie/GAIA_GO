# MCP Servers for Architect Multi-Agent System

**Status**: Phase 2 Complete
**Servers**: 3 (all custom)

---

## Overview

Model Context Protocol (MCP) servers that provide standardized tool access for all Claude sessions in the multi-agent system.

## Available Servers

### 1. tmux-architect (`tmux_mcp.py`)
**Status**: ✅ Production
**Tools**: 6

Manages tmux sessions for multi-agent orchestration.

**Tools**:
- `list_sessions` - List all tmux sessions with details
- `send_command` - Send command to session
- `capture_output` - Capture session output
- `create_session` - Create new session
- `kill_session` - Kill session
- `session_status` - Get detailed session status

**Use Cases**:
- Multi-agent session management
- Inter-session communication
- Session monitoring and control

**Example**:
```python
# List all sessions
result = await session.call_tool(name="list_sessions", arguments={})

# Send command to worker
result = await session.call_tool(
    name="send_command",
    arguments={"session": "claude_codex", "command": "ls -la"}
)
```

---

### 2. browser-automation (`browser_mcp.py`)
**Status**: ✅ Production
**Tools**: 8

Wraps 70+ Playwright browser automation scripts into standardized MCP interface.

**Tools**:
- `navigate` - Navigate browser to URL
- `submit_to_perplexity` - Submit research query to Perplexity AI
- `get_tab_groups` - List all Chrome tab groups
- `sync_to_sheets` - Sync data to Google Sheets
- `list_perplexity_tabs` - List open Perplexity tabs
- `create_tab_group` - Create new Chrome tab group
- `ethiopia_auto_research` - Run automated Ethiopia research workflow
- `get_browser_status` - Get browser automation system status

**Use Cases**:
- Web research automation (Ethiopia project)
- Google Sheets data sync
- Chrome tab management
- Perplexity AI integration

**Example**:
```python
# Submit research query
result = await session.call_tool(
    name="submit_to_perplexity",
    arguments={
        "query": "Best hotels in Addis Ababa under $100/night",
        "topic": "Accommodation"
    }
)

# Run Ethiopia research workflow
result = await session.call_tool(
    name="ethiopia_auto_research",
    arguments={
        "topics": ["Flights", "Hotels", "Visa"],
        "mode": "verify"
    }
)
```

---

### 3. database-architect (`database_mcp.py`)
**Status**: ✅ Production
**Tools**: 8

Unified database access for architect.db and assigner.db with intelligent query tools.

**Tools**:
- `query` - Execute raw SQL on architect or assigner database
- `list_tables` - List all tables in database
- `describe_table` - Get table schema (columns, types, constraints)
- `get_projects` - List all projects (with optional status filter)
- `get_features` - List features with filters (project_id, status, limit)
- `get_bugs` - List bugs with filters (project_id, severity, status, limit)
- `get_prompts` - List queued prompts from assigner (status, limit)
- `get_stats` - Get dashboard statistics (projects, features, bugs, prompts)

**Use Cases**:
- Query project management data across all Claude sessions
- Access task queue and assignment status
- Retrieve statistics for dashboard and reporting
- Execute custom SQL queries for complex data needs

**Example**:
```python
# Get all projects
result = await session.call_tool(name="get_projects", arguments={})

# Get pending prompts
result = await session.call_tool(
    name="get_prompts",
    arguments={"status": "pending", "limit": 10}
)

# Get statistics
result = await session.call_tool(name="get_stats", arguments={})

# Custom query
result = await session.call_tool(
    name="query",
    arguments={
        "sql": "SELECT * FROM features WHERE status = ? ORDER BY priority DESC",
        "database": "architect"
    }
)
```

---

## Testing

Each server has corresponding test files:

```bash
# Test tmux server
python3 mcp_servers/test_tmux_mcp.py

# Test browser automation server
python3 mcp_servers/test_browser_mcp.py

# Test database server
python3 mcp_servers/test_database_mcp.py

# Test basic MCP functionality
python3 mcp_servers/test_mcp_client.py
```

## Configuration

Claude Code automatically loads MCP servers from `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "tmux-architect": {
      "command": "python3",
      "args": ["/path/to/architect/mcp_servers/tmux_mcp.py"],
      "description": "Manage tmux sessions for multi-agent orchestration"
    },
    "browser-automation": {
      "command": "python3",
      "args": ["/path/to/architect/mcp_servers/browser_mcp.py"],
      "description": "Browser automation (Perplexity, Google Sheets, Tab Groups)"
    },
    "database-architect": {
      "command": "python3",
      "args": ["/path/to/architect/mcp_servers/database_mcp.py"],
      "description": "Unified database access for architect.db and assigner.db"
    }
  }
}
```

## Architecture

```
┌────────────────────────────────────────────┐
│  Claude Sessions (8+)                      │
│  • High-Level, Managers, Workers           │
│  • All can use MCP tools                   │
└──────────────┬─────────────────────────────┘
               │ (MCP Protocol)
               ▼
┌────────────────────────────────────────────┐
│  MCP Servers                               │
│  ┌──────────────┐ ┌─────────────────────┐ │
│  │ tmux_mcp     │ │ browser_mcp         │ │
│  │ 6 tools      │ │ 8 tools             │ │
│  │ 242 lines    │ │ 320 lines           │ │
│  └──────────────┘ └─────────────────────┘ │
│  ┌──────────────┐                         │
│  │ database_mcp │                         │
│  │ 8 tools      │                         │
│  │ 422 lines    │                         │
│  └──────────────┘                         │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│  System Resources                          │
│  • 28 tmux sessions                        │
│  • 78 browser automation scripts           │
│  • architect.db (40 tables)                │
│  • assigner.db (prompt queue)              │
└────────────────────────────────────────────┘
```

## Performance

| Server | Startup | Tool Latency | Memory |
|--------|---------|--------------|--------|
| tmux-architect | <100ms | 50-200ms | ~10 MB |
| browser-automation | <200ms | 1-5s | ~50 MB |
| database-architect | <100ms | 10-50ms | ~15 MB |

## Code Statistics

| File | Lines | Purpose |
|------|-------|---------|
| `hello_mcp.py` | 68 | Example/template |
| `tmux_mcp.py` | 242 | Production tmux server |
| `browser_mcp.py` | 320 | Production browser server |
| `database_mcp.py` | 422 | Production database server |
| `test_mcp_client.py` | 65 | Test framework |
| `test_tmux_mcp.py` | 54 | tmux tests |
| `test_browser_mcp.py` | 45 | browser tests |
| `test_database_mcp.py` | 59 | database tests |
| `test_google_drive_mcp.py` | 62 | google-drive tests (server unavailable) |
| **Total** | **1,337** | **MCP infrastructure** |

## Phase 2 Status: ✅ COMPLETE

All core MCP servers implemented and tested:
1. ✅ tmux server (6 tools) - Multi-agent session management
2. ✅ browser automation server (8 tools) - Playwright wrapper
3. ✅ database server (8 tools) - Unified DB access

**Total: 22 tools available to all Claude sessions**

## Next Steps

### Phase 3 (Advanced Specialized Servers)
- Multi-agent context server (shared state between sessions)
- Assigner worker MCP server (prompt routing and delegation)
- Milestone worker MCP server (project scanning and planning)
- Error aggregation MCP server (cross-node error collection)
- Google Drive MCP server (custom, since official not yet available)

### Integration Opportunities
- Replace custom `utils/google_docs_client.py` with Google Drive MCP server
- Integrate database MCP with dashboard API for real-time queries
- Add MCP tools for autopilot orchestration
- Create MCP tools for secure vault operations

## Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Servers Registry](https://github.com/modelcontextprotocol/servers)
- [Architect MCP Analysis](../docs/MCP_ANALYSIS.md)
- [MCP Phase 1 Complete](../docs/MCP_PHASE1_COMPLETE.md)
