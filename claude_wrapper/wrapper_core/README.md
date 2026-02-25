# wrapper_core

Hot-reloadable modules for the Claude Wrapper. This package provides all the logic for capturing and processing Claude Code permission prompts, designed to be updated without restarting the wrapper session.

## Architecture

```
wrapper_core/
├── __init__.py      # Module loader, reload_all(), version info
├── config.py        # Patterns, rules, template types
├── state.py         # Session state, persistence
├── extractors.py    # Prompt detection and classification
├── handlers.py      # I/O handlers, logging
└── README.md        # This file
```

## Modules

### `__init__.py`
Package entry point with hot-reload functionality.

```python
import wrapper_core

# Get version info
info = wrapper_core.get_version()
# Returns: {'core_version': '1.0.0', 'reload_count': 2, 'last_reload': '...'}

# Reload all modules
success, message = wrapper_core.reload_all()
# Returns: (True, 'Reloaded 4 modules') or (False, 'Errors: ...')
```

### `config.py`
Configuration and patterns for prompt detection.

- `PROMPT_PATTERN` - Regex to detect permission prompts
- `RESPONSE_RULES` - Auto-response rules for known prompts
- `TEMPLATE_TYPES` - Template classifications (BASH_SIMPLE, FILE_EDIT, etc.)
- `STATE_FILE` - Path to state persistence file
- `RELOAD_SIGNAL_FILE` - Path to reload trigger file

### `state.py`
Session state management with file persistence.

```python
from wrapper_core import state

# Initialize session
session_id = state.init_session()

# Update state
state.update_state(status='running', prompts_detected=5)

# Increment counter
state.increment_counter('bytes_received', 1024)

# Record a prompt
state.record_prompt({'type': 'Bash', 'command': 'git status'})

# Get current state
current = state.get_state()

# Load state from file (for recovery)
saved = state.load_state()
```

State is persisted to `/tmp/claude_wrapper_state.json` for:
- API access by Architecture Dashboard
- Recovery after module reload
- Session monitoring

### `extractors.py`
Prompt extraction and classification.

```python
from wrapper_core import extractors

# Parse prompts from output
prompts = extractors.parse_prompts(output_text)
# Returns: [{'operation_type': 'Bash', 'command': '...', 'template': 'BASH_SIMPLE'}]

# Classify a prompt template
template = extractors.classify_template(prompt_dict)
# Returns: 'BASH_SIMPLE', 'FILE_EDIT', 'FILE_CREATE', etc.

# Strip ANSI codes
clean = extractors.strip_ansi(colored_text)

# Format for logging
formatted = extractors.format_prompt_for_log(prompt_dict)
```

### `handlers.py`
I/O processing handlers.

```python
from wrapper_core.handlers import OutputHandler, InputHandler, ReloadHandler

# Output handler - processes Claude output
output_handler = OutputHandler(log_file='session.log', no_log=False)
output_handler.process_output(data)
stats = output_handler.get_stats()

# Input handler - tracks input
input_handler = InputHandler()
input_handler.track_input(data)

# Reload handler - checks for reload signal
reload_handler = ReloadHandler()
if reload_handler.should_reload():
    # Trigger module reload
    reload_handler.clear_signal()
```

## Hot Reload

The wrapper checks for reload signals periodically. To trigger a reload:

```bash
# Create the signal file
touch /tmp/claude_wrapper_reload

# Or use the API
curl -X POST https://localhost:5051/architecture/api/wrapper/reload
```

When reload is triggered:
1. All wrapper_core modules are reloaded via `importlib.reload()`
2. Handlers are recreated with new code
3. State (session ID, counters, buffers) is preserved
4. New patterns/rules take effect immediately

## State File Format

`/tmp/claude_wrapper_state.json`:

```json
{
  "session_id": "session_1702665600",
  "start_time": "2025-12-15T10:00:00",
  "status": "running",
  "prompts_detected": 15,
  "prompts_approved": 12,
  "bytes_received": 524288,
  "bytes_sent": 1024,
  "last_activity": "2025-12-15T10:30:00",
  "reload_count": 2,
  "errors": []
}
```

## Testing

Run the test suite:

```bash
# Run all tests
python3 test_wrapper_reload.py

# Verbose output
python3 test_wrapper_reload.py --verbose

# JSON output
python3 test_wrapper_reload.py --json
```

Tests cover:
- Module imports (5 tests)
- Hot reload functionality (3 tests)
- State persistence across reloads (3 tests)
- Prompt extraction (3 tests)
- Output handler (3 tests)

## Development

To add new functionality:

1. **Edit the appropriate module** in `wrapper_core/`
2. **Test locally**: `python3 -c "from wrapper_core import extractors; print('OK')"`
3. **Trigger reload**: `touch /tmp/claude_wrapper_reload`
4. **Verify**: Check wrapper logs or API for updated behavior

Changes to `config.py` patterns take effect immediately after reload.
Changes to `handlers.py` recreate handler instances with new logic.
State in `state.py` persists across reloads.

## Integration

The Claude wrapper (`claude_wrapper.py`) is a thin shell that:
1. Sets up PTY for Claude process
2. Loads wrapper_core modules
3. Forwards I/O through handlers
4. Checks for reload signals periodically
5. Persists state for API access

The Architecture Dashboard monitors wrapper status via:
- `GET /architecture/api/wrapper/status` - Session health
- `POST /architecture/api/wrapper/reload` - Trigger reload
