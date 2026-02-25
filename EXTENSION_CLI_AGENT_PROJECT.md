# 🏗️ Extension CLI + Agent Control System

**Status**: DESIGN PHASE
**Priority**: 8
**Type**: Automation & Integration
**Target**: Command-line control + Agent integration

---

## Overview

Enable **command-line control** of the extension sidebar and **agent automation** for sending prompts to Comet through the extension.

### What It Enables

```bash
# CLI from terminal
architect-send "check flights to addis from sfo"
architect-send "analyze this code" --target comet --priority high
architect-send "list my recent conversations"

# Agent automation
# Comet agent can send commands to extension/GAIA
# Extension can queue prompts for processing
```

### Architecture

```
┌─────────────────────────────────────┐
│ Command Line / Agent / Script       │
│ (sends HTTP request)                │
└────────────┬────────────────────────┘
             │ HTTP POST
             ↓
┌─────────────────────────────────────┐
│ Extension Service Worker            │
│ (HTTP API endpoint)                 │
├─────────────────────────────────────┤
│ POST /api/send-command              │
│ POST /api/send-to-comet             │
│ GET /api/messages                   │
│ POST /api/queue-prompt              │
└────────────┬────────────────────────┘
             │ WebSocket
             ↓
┌─────────────────────────────────────┐
│ GAIA Server (Mac Mini)              │
│ (message router)                    │
├─────────────────────────────────────┤
│ Processes commands                  │
│ Routes to Comet/agents              │
│ Sends responses back                │
└─────────────────────────────────────┘
```

---

## Component 1: HTTP API in Service Worker

Add REST endpoints to `background.js`:

```javascript
// HTTP Server in service worker
const API_PORT = 9999;

// Endpoints:
// POST /api/send-command
// {
//   "message": "check flights to addis from sfo",
//   "target": "comet",
//   "priority": "high"
// }

// POST /api/send-to-comet
// {
//   "prompt": "analyze this conversation",
//   "context": { ... }
// }

// GET /api/messages?limit=10
// Returns last N messages from GAIA

// POST /api/queue-prompt
// {
//   "content": "do this task",
//   "queue_name": "comet_tasks"
// }
```

**Implementation**: Use Chrome's native HTTP handling or websocket proxy.

---

## Component 2: CLI Tool

Create `architect-send` command:

```bash
#!/bin/bash
# /usr/local/bin/architect-send

PROMPT="$@"
TARGET="${TARGET:-comet}"
PRIORITY="${PRIORITY:-medium}"

# Send to extension API
curl -X POST http://localhost:9999/api/send-command \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"$PROMPT\",
    \"target\": \"$TARGET\",
    \"priority\": \"$PRIORITY\"
  }"

echo "✓ Command sent to extension"
```

**Features**:
- Simple command-line interface
- Environment variables for target/priority
- Response status display
- JSON output option

**Usage**:
```bash
architect-send "what's the weather in addis"
architect-send "analyze flights" --target comet --priority high
TARGET=comet architect-send "process this"
```

---

## Component 3: Agent Wrapper

Python agent that can use the CLI:

```python
#!/usr/bin/env python3
# agents/extension_agent.py

import subprocess
import json
from typing import Optional

class ExtensionAgent:
    """Send commands to extension sidebar via CLI"""

    def __init__(self, target: str = "comet", priority: str = "medium"):
        self.target = target
        self.priority = priority

    def send_prompt(self, prompt: str) -> dict:
        """Send prompt to extension"""
        try:
            result = subprocess.run(
                ["architect-send", prompt],
                env={"TARGET": self.target, "PRIORITY": self.priority},
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Sent to extension",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_messages(self, limit: int = 10) -> list:
        """Get last N messages from GAIA"""
        try:
            response = subprocess.run(
                ["curl", "-s", f"http://localhost:9999/api/messages?limit={limit}"],
                capture_output=True,
                text=True
            )
            return json.loads(response.stdout)
        except:
            return []

# Usage in agent code:
agent = ExtensionAgent(target="comet", priority="high")
result = agent.send_prompt("check flights to addis from sfo")
print(result)
```

---

## Component 4: Integration Points

### 4.1 GAIA Dashboard

Add widget to control/monitor extension commands:

```
┌─ Extension Control ────────────────┐
│                                    │
│ Send Command to Comet:             │
│ [_________________] [Send]         │
│                                    │
│ Recent Commands:                   │
│ • check flights (5m ago) - ✓       │
│ • analyze code (12m ago) - ✓       │
│ • search data (2h ago) - ✓         │
│                                    │
└────────────────────────────────────┘
```

### 4.2 Comet App Integration

Comet can now:
- Send commands back to extension
- Queue tasks via extension CLI
- Monitor extension status
- Control browser from agent

### 4.3 Automation Hooks

```bash
# Run task and send result to Comet via extension
architect-send "$(python analyze_data.py)"

# Chain multiple commands
architect-send "task1" && \
architect-send "task2" && \
architect-send "task3"
```

---

## Implementation Phases

### Phase 1: HTTP API in Service Worker (2 days)
- [ ] Add HTTP endpoint to background.js
- [ ] Message routing handlers
- [ ] Queue management
- [ ] Response formatting

### Phase 2: CLI Tool (1 day)
- [ ] Create `architect-send` script
- [ ] Install to `/usr/local/bin`
- [ ] Test basic send/receive
- [ ] Add environment variable support

### Phase 3: Agent Wrapper (1 day)
- [ ] Python ExtensionAgent class
- [ ] Integration with GAIA assigner
- [ ] Error handling
- [ ] Unit tests

### Phase 4: Dashboard Integration (2 days)
- [ ] Command widget in GAIA
- [ ] Message history display
- [ ] Status monitoring
- [ ] Real-time updates

### Phase 5: Advanced Features (2 days)
- [ ] Command queuing
- [ ] Priority scheduling
- [ ] Timeout handling
- [ ] Batch operations

---

## API Specification

### POST /api/send-command

Send a command to GAIA via extension.

**Request**:
```json
{
  "message": "check flights to addis from sfo",
  "target": "comet",
  "priority": "high",
  "context": {
    "source": "cli",
    "user": "jgirmay"
  }
}
```

**Response**:
```json
{
  "success": true,
  "command_id": "cmd-12345",
  "target": "comet",
  "sent_at": "2026-02-21T15:45:00Z"
}
```

### POST /api/send-to-comet

Send directly to Comet application.

**Request**:
```json
{
  "prompt": "analyze this conversation",
  "conversation_id": "BRIMBbZBTDeonPH_S.ZYGA",
  "priority": "medium"
}
```

### GET /api/messages

Retrieve messages from GAIA.

**Query Parameters**:
- `limit`: Number of messages (default: 10)
- `source`: Filter by source (comet, extension, agent)
- `since`: Messages after timestamp

**Response**:
```json
[
  {
    "id": "msg-001",
    "source": "comet",
    "content": "Found 5 flights",
    "timestamp": "2026-02-21T15:45:30Z",
    "priority": "high"
  }
]
```

### POST /api/queue-prompt

Queue a prompt for later processing.

**Request**:
```json
{
  "content": "do this task when available",
  "queue_name": "comet_tasks",
  "priority": "low",
  "timeout": 3600
}
```

---

## File Structure

```
architect/
├── bin/
│   └── architect-send          ← CLI tool
│
├── agents/
│   └── extension_agent.py      ← Agent wrapper
│
├── chrome_extension_fixed/
│   ├── background.js           ← Add HTTP API
│   └── popup.js                ← Update sidebar
│
└── docs/
    └── EXTENSION_CLI_GUIDE.md   ← Usage guide
```

---

## Testing Strategy

### Unit Tests

```python
def test_send_command_success():
    agent = ExtensionAgent()
    result = agent.send_prompt("test message")
    assert result["success"] == True

def test_send_command_invalid_target():
    agent = ExtensionAgent(target="invalid")
    result = agent.send_prompt("test")
    assert result["success"] == False

def test_get_messages():
    agent = ExtensionAgent()
    messages = agent.get_messages(limit=5)
    assert len(messages) <= 5
```

### Integration Tests

```bash
# Test CLI
architect-send "test command"
# Verify response

# Test agent
python -c "from agents.extension_agent import ExtensionAgent; ExtensionAgent().send_prompt('test')"

# Test GAIA integration
# Verify message appears in dashboard
```

---

## Use Cases

### 1. Quick Commands from Terminal

```bash
$ architect-send "what's the weather in addis"
✓ Command sent to extension
(Comet processes, responds in sidebar)
```

### 2. Agent Automation

```python
# In agent code:
from agents.extension_agent import ExtensionAgent

def analyze_conversation(conv_id):
    agent = ExtensionAgent(target="comet", priority="high")
    result = agent.send_prompt(
        f"Analyze conversation {conv_id} for key insights"
    )
    return result
```

### 3. Shell Scripts

```bash
#!/bin/bash
# Process multiple conversations
for conv_id in $(get_conversation_ids); do
    architect-send "analyze $conv_id"
    sleep 5
done
```

### 4. Batch Processing

```bash
# Queue 10 tasks
for i in {1..10}; do
    architect-send "process_item_$i" --priority low
done

# Check status
architect-send "list tasks"
```

---

## Security Considerations

1. **Local-only API** - Only accept connections from localhost (127.0.0.1)
2. **Port binding** - Use high-numbered port (9999) to avoid privilege issues
3. **Message signing** - Add HMAC signature for authenticity
4. **Rate limiting** - Limit commands per minute to prevent abuse
5. **Access control** - Only allow from whitelisted IPs/users

---

## Success Criteria

- [ ] CLI tool sends commands to extension without error
- [ ] Agent wrapper successfully integrates with GAIA
- [ ] Commands appear in dashboard within 1 second
- [ ] Response messages return to CLI/agent
- [ ] Batch operations work smoothly
- [ ] No race conditions with concurrent messages
- [ ] Rate limiting prevents abuse
- [ ] Works across all machines (Pink Laptop, Mac Mini)

---

## Dependencies

- Chrome extension HTTP API support (or alternative transport)
- Python 3.8+
- curl for CLI HTTP calls
- GAIA message routing infrastructure
- Comet app ready to receive commands

---

## Timeline

**Total**: 8 days
- Phase 1: 2 days
- Phase 2: 1 day
- Phase 3: 1 day
- Phase 4: 2 days
- Phase 5: 2 days

---

## Queue Command

```
os: Build Extension CLI & Agent Control System for automated command routing --priority 8
```

---

## Notes

This system bridges CLI/agent automation with the extension-GAIA ecosystem:
- **Power users**: Use `architect-send` from terminal
- **Agents**: Programmatically control extension/Comet
- **Automation**: Script complex workflows
- **Scalability**: Send commands to any machine running extension

Without this, commands can only be sent via extension UI. With this, the entire system becomes CLI/agent-controllable.

---

**Status**: READY FOR DESIGN REVIEW
**Next**: Approve architecture, then queue for implementation
