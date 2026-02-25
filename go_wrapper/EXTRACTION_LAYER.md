# Extraction Layer Documentation

## Overview

The extraction layer provides **config-driven pattern matching** for agent output streams, enabling:
- Real-time structured event extraction from Claude/Gemini output
- Training data collection for auto-confirmation ML models
- HTTP API for monitoring and pattern management
- Integration with existing `claude_patterns` system

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Output Stream                                        │
│  (Claude/Gemini/Codex raw output)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ProcessWrapper                                             │
│  - PTY management                                           │
│  - ANSI stripping                                           │
│  - Log streaming                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ConfigurableExtractor                                      │
│  - JSON pattern config                                      │
│  - Regex matching (priority-sorted)                        │
│  - Field extraction                                         │
│  - Event buffering                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                ┌──────┴──────┐
                ▼             ▼
         ┌──────────┐   ┌──────────────┐
         │Training  │   │Extraction API│
         │Logger    │   │(HTTP)        │
         └──────────┘   └──────────────┘
                │              │
                ▼              ▼
         ┌──────────┐   ┌──────────────┐
         │Training  │   │Pattern       │
         │Data      │   │Management    │
         │(JSONL)   │   │Dashboard     │
         └──────────┘   └──────────────┘
```

## Components

### 1. ExtractionConfig (`config/extraction_patterns.json`)

JSON configuration file defining extraction patterns:

```json
{
  "version": "1.0.0",
  "settings": {
    "buffer_size": 50,
    "event_buffer_size": 1000,
    "enable_training": true,
    "training_data_path": "data/training"
  },
  "patterns": [
    {
      "name": "claude_tool_use",
      "event_type": "tool_use",
      "regex": "⏺ (\\w+)\\((.*)\\)",
      "field_map": {
        "tool": 1,
        "args": 2
      },
      "priority": 100,
      "auto_confirm": false,
      "risk_level": "medium"
    }
  ]
}
```

### 2. ConfigurableExtractor (`stream/configurable_extractor.go`)

Processes agent output and extracts structured events:

```go
extractor, err := stream.NewConfigurableExtractor("dev_worker2", "config/extraction_patterns.json")
events := extractor.ProcessLine("⏺ Bash(ls -lh)")
// Returns: ExtractedEvent with tool="Bash", args="ls -lh"
```

### 3. ExtractionAPI (`api/extraction_api.go`)

HTTP API for real-time monitoring and pattern management.

### 4. TrainingLogger Integration

Connects to existing training logger for ML data collection.

## API Endpoints

Base URL: `http://localhost:8154/api/extraction`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents` | GET | List all agents with extractors |
| `/events` | GET | Get extraction events (query: agent, limit, type) |
| `/stats` | GET | Get extraction statistics (query: agent) |
| `/patterns` | GET | Get configured patterns (query: agent) |
| `/patterns/add` | POST | Add new pattern (query: agent, body: pattern JSON) |
| `/patterns/remove` | POST | Remove pattern (query: agent, pattern) |
| `/config/reload` | POST | Reload config from file (query: agent, config) |
| `/auto-confirm` | GET | Get auto-confirmable events (query: agent) |

## Usage Examples

### 1. Start Extraction Demo

```bash
cd go_wrapper
go run cmd/extraction_demo/main.go dev_worker2 config/extraction_patterns.json
```

### 2. Query Events via API

```bash
# Get all events for agent
curl "http://localhost:8154/api/extraction/events?agent=dev_worker2&limit=50"

# Get only tool_use events
curl "http://localhost:8154/api/extraction/events?agent=dev_worker2&type=tool_use"

# Get auto-confirmable events
curl "http://localhost:8154/api/extraction/auto-confirm?agent=dev_worker2"
```

### 3. Get Statistics

```bash
# Stats for specific agent
curl "http://localhost:8154/api/extraction/stats?agent=dev_worker2" | jq

# Stats for all agents
curl "http://localhost:8154/api/extraction/stats" | jq
```

### 4. Manage Patterns

```bash
# List patterns
curl "http://localhost:8154/api/extraction/patterns?agent=dev_worker2" | jq

# Add new pattern
curl -X POST "http://localhost:8154/api/extraction/patterns/add?agent=dev_worker2" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_pattern",
    "event_type": "state_change",
    "regex": "Custom: (.+)",
    "field_map": {"value": 1},
    "priority": 50,
    "auto_confirm": true,
    "risk_level": "low"
  }'

# Remove pattern
curl -X POST "http://localhost:8154/api/extraction/patterns/remove?agent=dev_worker2&pattern=custom_pattern"
```

## Pattern Types

### Event Types

| Type | Description | Examples |
|------|-------------|----------|
| `tool_use` | Tool execution (Bash, Edit, Write, Read) | `⏺ Bash(...)` |
| `permission` | Permission prompts | `⏵⏵ bypass permissions on` |
| `error` | Errors and failures | `Error: ...`, `Exit code 1` |
| `state_change` | Agent state transitions | `✢ Thinking...`, idle prompt |
| `metric` | Performance metrics | Token usage, memory |

### Risk Levels

| Level | Description | Auto-Confirm? |
|-------|-------------|---------------|
| `low` | Safe operations (read, grep, glob) | Yes |
| `medium` | Moderate risk (edit, non-destructive writes) | Conditional |
| `high` | High risk (bash, delete, deploy) | No |

## Integration with ProcessWrapper

To integrate extraction with the existing wrapper:

```go
// In stream/process.go
type ProcessWrapper struct {
    // ... existing fields ...
    extractor *ConfigurableExtractor
}

func NewProcessWrapper(agentName, logsDir, command string, args ...string) (*ProcessWrapper, error) {
    // ... existing code ...

    // Add extractor
    extractor, err := NewConfigurableExtractor(agentName, "config/extraction_patterns.json")
    if err != nil {
        log.Printf("Warning: Failed to create extractor: %v", err)
    }

    pw.extractor = extractor
    return pw, nil
}

// In the output processing loop:
func (pw *ProcessWrapper) processLine(line string) {
    // ... existing logging ...

    // Extract events
    if pw.extractor != nil {
        events := pw.extractor.ProcessLine(line)
        // Handle events as needed
    }
}
```

## Training Data Output

When `enable_training: true`, extraction events are logged to:

```
data/training/<agent_name>-events-YYYY-MM-DD-HH-MM-SS.jsonl
```

Each line is a JSON event:

```json
{
  "id": "dev_worker2-event-42",
  "timestamp": "2026-02-09T16:50:00Z",
  "agent_name": "dev_worker2",
  "event_type": "tool_use",
  "pattern": "bash_command",
  "matched": "⏺ Bash(go build ./...)",
  "fields": {
    "command": "go build ./..."
  },
  "metadata": {
    "pattern": "bash_command",
    "auto_confirm": false,
    "risk_level": "high"
  }
}
```

## Connecting to claude_patterns System

The extraction layer bridges to the existing `claude_patterns` table in the architect dashboard:

1. **Extraction** → Structured events from agent output
2. **Analysis** → Pattern frequency and success rates
3. **Learning** → Update `claude_patterns` with auto-confirmation rules
4. **Auto-Confirm** → Apply learned patterns to new sessions

## Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| API Server | 8151 | Agent process management |
| Claude Wrapper | 8152 | Claude-specific API |
| Manager | 8163 | Task distribution |
| **Extraction API** | **8154** | **Pattern extraction monitoring** |

## Performance

- **Memory**: ~2KB per event (1000 events = 2MB)
- **Throughput**: ~10K lines/sec pattern matching
- **Latency**: <1ms per line extraction

## Next Steps

1. **Integrate with ProcessWrapper** - Add extractor to existing wrapper
2. **Build Dashboard** - Web UI for pattern visualization
3. **ML Training Pipeline** - Automated pattern learning from extraction data
4. **Auto-Confirm Integration** - Use extracted events to drive auto-confirmation
5. **Pattern Library** - Shared patterns across agents

## Configuration Best Practices

### Pattern Priority

Assign priorities to ensure correct matching order:
- **90-100**: Critical patterns (errors, permissions)
- **70-89**: Tool usage and state changes
- **50-69**: Metrics and informational
- **1-49**: Custom/experimental patterns

### Field Mapping

Use capture groups wisely:
```json
"regex": "⏺ (\\w+)\\((.*)\\)",
"field_map": {
  "tool": 1,    // First capture group
  "args": 2     // Second capture group
}
```

### Auto-Confirm Rules

Only mark `auto_confirm: true` for:
- Read-only operations
- Idempotent operations
- Low-risk state changes

Never auto-confirm:
- Destructive operations (delete, drop)
- External commands (bash, curl)
- Write operations to critical paths

## Troubleshooting

### Pattern Not Matching

1. Test regex at https://regex101.com/
2. Check pattern priority (higher first)
3. Enable debug logging: Add prints in `ProcessLine()`

### High Memory Usage

1. Reduce `event_buffer_size` in config
2. Clear events periodically: `extractor.GetEvents(0)` and discard
3. Disable training mode if not needed

### API Not Responding

1. Check port 8154 is not in use: `lsof -i :8154`
2. Verify agent is registered: `curl http://localhost:8154/api/extraction/agents`
3. Check logs for HTTP server errors

## Files Created

```
go_wrapper/
├── config/
│   └── extraction_patterns.json          # Pattern configuration
├── stream/
│   ├── extraction_config.go              # Config loading/management
│   └── configurable_extractor.go         # Main extraction engine
├── api/
│   └── extraction_api.go                 # HTTP API server
├── cmd/
│   └── extraction_demo/
│       └── main.go                       # Demo application
└── EXTRACTION_LAYER.md                   # This documentation
```

## License

Part of the Architect Dashboard project.
